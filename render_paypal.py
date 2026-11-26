from __future__ import annotations

from secrets import token_urlsafe
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import Order, OrderStatus
from app.schemas.order import OrderCreateInternal
from app.security.tokens import is_expired, issue_order_token
from app.services.orders import add_event
from app.services.payments import (
    PaymentConfigurationError,
    PaymentProviderError,
    PaymentValidationError,
    capture_paypal_order,
    create_paypal_order,
    verify_webhook_signature,
)

from render_sensitive_http import SensitiveRoute

router = APIRouter(tags=["payments"], route_class=SensitiveRoute)

JOB001_PRICE_CENTS = 2900
JOB001_CURRENCY = "EUR"
JOB001_MAX_DOCUMENTS = 1


class PayPalCapturePayload(BaseModel):
    claim_secret: str = Field(min_length=20, max_length=128)


@router.post("/payments/paypal/order", status_code=status.HTTP_201_CREATED)
def create_checkout_order(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    claim_secret = token_urlsafe(24)
    try:
        created = create_paypal_order(
            settings,
            amount_cents=JOB001_PRICE_CENTS,
            currency=JOB001_CURRENCY,
            claim_secret=claim_secret,
        )
    except PaymentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "status": "ok",
        "result": "paypal_order_created",
        "paypal_order_id": created.order_id,
        "approval_url": created.approval_url,
        "claim_secret": created.claim_secret,
        "amount_cents": JOB001_PRICE_CENTS,
        "currency": JOB001_CURRENCY,
    }


@router.post("/payments/paypal/order/{paypal_order_id}/capture")
def capture_checkout_order(
    paypal_order_id: str,
    payload: PayPalCapturePayload,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not paypal_order_id.isalnum() or len(paypal_order_id) > 64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid PayPal order id.",
        )

    try:
        verified = capture_paypal_order(
            settings,
            paypal_order_id=paypal_order_id,
            claim_secret=payload.claim_secret,
            expected_amount_cents=JOB001_PRICE_CENTS,
            expected_currency=JOB001_CURRENCY,
        )
    except PaymentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except PaymentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if verified.amount_cents != JOB001_PRICE_CENTS or verified.currency != JOB001_CURRENCY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PayPal payment amount or currency does not match JOB-001.",
        )

    payment_reference = f"PAYPAL:{verified.order_id}"
    # A checkout claim proves the PayPal transaction, not perpetual ownership
    # of an already issued ZUNPY access credential. Never rotate it here.
    existing = db.execute(
        select(Order).where(Order.payment_reference == payment_reference)
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.payment_provider != "paypal"
            or existing.amount_cents != verified.amount_cents
            or existing.currency != verified.currency
            or existing.customer_email != verified.payer_email
            or existing.status in {
                OrderStatus.CANCELLED, OrderStatus.REFUNDED, OrderStatus.FAILED,
            }
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existing order requires review.",
            )
        if (
            existing.status == OrderStatus.PAID
            or not existing.access_token_hash
            or is_expired(existing.access_expires_at)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existing order requires reconciliation or has expired.",
            )
        return {
            "status": "ok",
            "result": "paypal_order_recovery_required",
            "order_id": existing.order_id,
            "order_status": existing.status.value,
            "paypal_order_id": verified.order_id,
            "capture_id": verified.capture_id,
        }

    issued = issue_order_token(
        access_ttl_hours=settings.order_access_token_ttl_hours,
        upload_ttl_hours=settings.order_upload_token_ttl_hours,
    )

    order_id = f"ZJ-{uuid4().hex[:16].upper()}"
    # Validate with the original schema, then persist the final order and
    # both audit events in ONE transaction. A failure cannot leave PAID
    # committed without WAITING_UPLOAD. Existing legacy PAID rows stay blocked.
    try:
        data = OrderCreateInternal(
            customer_email=verified.payer_email,
            payment_reference=payment_reference,
            amount_cents=verified.amount_cents,
            currency=verified.currency,
            max_documents=JOB001_MAX_DOCUMENTS,
        )
        order = Order(
            order_id=order_id,
            status=OrderStatus.WAITING_UPLOAD,
            customer_email=str(data.customer_email),
            payment_provider="paypal",
            payment_reference=data.payment_reference,
            amount_cents=data.amount_cents,
            currency=data.currency.upper(),
            max_documents=data.max_documents,
            access_token_hash=issued.token_hash,
            access_expires_at=issued.access_expires_at,
            upload_expires_at=issued.upload_expires_at,
        )
        db.add(order)
        db.flush()
        add_event(db, order_id, "PAYMENT_CONFIRMED", {
            "provider": "paypal", "payment_reference": payment_reference,
        })
        add_event(db, order_id, "PAYPAL_PAYMENT_CAPTURED", {
            "from": OrderStatus.PAID.value,
            "to": OrderStatus.WAITING_UPLOAD.value,
            "paypal_order_id": verified.order_id,
            "capture_id": verified.capture_id,
        })
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # A concurrent winner is authoritative; never issue its token.
        existing = db.execute(
            select(Order.order_id).where(Order.payment_reference == payment_reference)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="PayPal payment has already been claimed.",
            ) from None
        raise HTTPException(status_code=503, detail="Order requires reconciliation.") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="Order requires reconciliation.") from None

    return {
        "status": "ok",
        "result": "paypal_payment_verified_order_ready",
        "order_id": order_id,
        "order_token": issued.raw,
        "order_status": OrderStatus.WAITING_UPLOAD.value,
        "paypal_order_id": verified.order_id,
        "capture_id": verified.capture_id,
        "max_documents": order.max_documents,
    }


@router.post("/webhooks/paypal")
async def paypal_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        event = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON webhook body.",
        ) from exc
    if not isinstance(event, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PayPal webhook event.",
        )

    headers = {key.lower(): value for key, value in request.headers.items()}
    try:
        verified = verify_webhook_signature(
            settings,
            headers=headers,
            event=event,
        )
    except PaymentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except PaymentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PayPal webhook signature verification failed.",
        )

    event_type = event.get("event_type")
    return {
        "status": "ok",
        "result": "paypal_webhook_verified",
        "event_id": event.get("id"),
        "event_type": event_type,
        "action": (
            "payment_completed_observed"
            if event_type == "PAYMENT.CAPTURE.COMPLETED"
            else "verified_no_action"
        ),
    }
