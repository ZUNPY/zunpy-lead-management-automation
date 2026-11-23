from __future__ import annotations

from io import BytesIO
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pypdf import PdfWriter
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import OrderStatus
from app.schemas.file import UploadRequest
from app.schemas.order import OrderCreateInternal
from app.security.auth import require_internal_service
from app.security.tokens import issue_order_token, verify_token
from app.services.files import create_upload_ticket, finalize_upload, submit_order
from app.services.orders import create_order, transition_order
from app.services.storage import R2Storage, get_storage

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_service)],
)


def not_implemented(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


def _smoke_pdf() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({"/Title": "ZUNPY JOB-001 production smoke test"})
    writer.write(buffer)
    return buffer.getvalue()


@router.post("/test/job001-smoke", status_code=status.HTTP_201_CREATED)
def job001_smoke(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: R2Storage = Depends(get_storage),
) -> dict[str, object]:
    suffix = uuid4().hex[:12].upper()
    order_id = f"ZJ-TST-{suffix}"
    payment_reference = f"TEST-{uuid4().hex.upper()}"
    issued = issue_order_token(
        access_ttl_hours=settings.order_access_token_ttl_hours,
        upload_ttl_hours=settings.order_upload_token_ttl_hours,
    )

    order = create_order(
        db,
        order_id=order_id,
        payload=OrderCreateInternal(
            customer_email="job001-smoke@zunpyai.com",
            payment_reference=payment_reference,
            amount_cents=2900,
            currency="EUR",
            max_documents=1,
        ),
        access_token_hash=issued.token_hash,
        access_expires_at=issued.access_expires_at,
        upload_expires_at=issued.upload_expires_at,
    )
    order = transition_order(
        db,
        order_id=order.order_id,
        new_status=OrderStatus.WAITING_UPLOAD,
        event_type="TEST_ORDER_READY",
        detail={"kind": "job001-production-smoke"},
    )

    pdf = _smoke_pdf()
    item, upload_url = create_upload_ticket(
        db,
        order=order,
        payload=UploadRequest(
            filename="job001-production-smoke.pdf",
            size_bytes=len(pdf),
            content_type="application/pdf",
        ),
        storage=storage,
        settings=settings,
    )

    try:
        request = Request(
            upload_url,
            data=pdf,
            method="PUT",
            headers={"Content-Type": "application/pdf"},
        )
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"R2 PUT returned HTTP {response.status}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Smoke upload failed: {type(exc).__name__}",
        ) from exc

    item = finalize_upload(
        db,
        order_id=order.order_id,
        upload_id=item.upload_id,
        storage=storage,
        settings=settings,
    )
    order = submit_order(db, order_id=order.order_id)

    token_hash_verified = verify_token(issued.raw, order.access_token_hash)
    if not token_hash_verified:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored order token hash verification failed.",
        )

    return {
        "status": "ok",
        "result": "job001_api_db_r2_verified",
        "order_id": order.order_id,
        "order_status": order.status.value,
        "document_count": order.document_count,
        "upload_status": item.status.value,
        "invoice_result_id": item.invoice_result_id,
        "page_count": item.page_count,
        "token_hash_verified": token_hash_verified,
        "stages": [
            "order_created_in_postgres",
            "order_waiting_upload",
            "presigned_upload_issued",
            "pdf_uploaded_to_r2",
            "pdf_validated",
            "copied_to_source",
            "upload_object_deleted",
            "order_submitted_ready",
        ],
    }


@router.post("/orders/{order_id}/start")
def start_order(order_id: str) -> None:
    not_implemented("Processing start is not implemented yet.")


@router.post("/orders/{order_id}/invoice-result")
def invoice_result(order_id: str) -> None:
    not_implemented("Invoice result persistence is not implemented yet.")


@router.post("/orders/{order_id}/review")
def review_order(order_id: str) -> None:
    not_implemented("Review queue integration is not implemented yet.")


@router.post("/orders/{order_id}/complete")
def complete_order(order_id: str) -> None:
    not_implemented("Completion rules are not implemented yet.")


@router.post("/orders/{order_id}/fail")
def fail_order(order_id: str) -> None:
    not_implemented("Failure handling is not implemented yet.")
