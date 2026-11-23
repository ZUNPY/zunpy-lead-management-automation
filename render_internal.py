from __future__ import annotations

from base64 import b64decode
from datetime import date
from io import BytesIO
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pypdf import PdfWriter
import pypdfium2 as pdfium
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import Order, OrderStatus
from app.schemas.file import UploadRequest
from app.schemas.order import OrderCreateInternal
from app.security.auth import require_internal_service
from app.security.tokens import issue_order_token, verify_token
from app.services.files import create_upload_ticket, finalize_upload, submit_order
from app.services.orders import create_order, transition_order
from app.services.processing import (
    InvalidProcessingStateError,
    ProcessingInfrastructureError,
    ProcessingOrderNotFoundError,
    ReviewInvoiceNotFoundError,
    process_order,
    resolve_invoice_review,
)
from app.services.storage import R2Storage, StorageConfigurationError, get_storage

class ReviewResolutionPayload(BaseModel):
    invoice_result_id: str = Field(min_length=1, max_length=40)
    supplier: str = Field(min_length=1, max_length=255)
    invoice_number: str = Field(min_length=1, max_length=128)
    invoice_date: date
    currency: str = Field(min_length=3, max_length=3)
    subtotal_cents: int = Field(ge=0)
    tax_cents: int = Field(ge=0)
    total_cents: int = Field(ge=0)
    reviewer_note: str | None = Field(default=None, max_length=500)


router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_service)],
)


def not_implemented(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


def _smoke_pdf() -> bytes:
    # Pre-generated synthetic one-page digital invoice. No customer data.
    return b64decode(
        "JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA1OTUuMjc1NiA4NDEuODg5OCBdIC9QYXJlbnQgNiAwIFIgL1Jlc291cmNlcyA8PAovRm9udCAxIDAgUiAvUHJvY1NldCBbIC9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUkgXQo+PiAvUm90YXRlIDAgL1RyYW5zIDw8Cgo+PiAKICAvVHlwZSAvUGFnZQo+PgplbmRvYmoKNCAwIG9iago8PAovUGFnZU1vZGUgL1VzZU5vbmUgL1BhZ2VzIDYgMCBSIC9UeXBlIC9DYXRhbG9nCj4+CmVuZG9iago1IDAgb2JqCjw8Ci9BdXRob3IgKGFub255bW91cykgL0NyZWF0aW9uRGF0ZSAoRDoyMDI2MTEyMzE5MDUzMyswMCcwMCcpIC9DcmVhdG9yIChhbm9ueW1vdXMpIC9LZXl3b3JkcyAoKSAvTW9kRGF0ZSAoRDoyMDI2MTEyMzE5MDUzMyswMCcwMCcpIC9Qcm9kdWNlciAoUmVwb3J0TGFiIFBERiBMaWJyYXJ5IC0gXChvcGVuc291cmNlXCkpIAogIC9TdWJqZWN0ICh1bnNwZWNpZmllZCkgL1RpdGxlICh1bnRpdGxlZCkgL1RyYXBwZWQgL0ZhbHNlCj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Db3VudCAxIC9LaWRzIFsgMyAwIFIgXSAvVHlwZSAvUGFnZXMKPj4KZW5kb2JqCjcgMCBvYmoKPDwKL0ZpbHRlciBbIC9BU0NJSTg1RGVjb2RlIC9GbGF0ZURlY29kZSBdIC9MZW5ndGggMjcyCj4+CnN0cmVhbQpHYXNKTDYjVj8/JjtCVFBNS2RSSWlsaTBoRTc1I1MtOG9SW21BWkVlZjgqajxaWEE5ND02TkIrYltfM0lwV15sRCM1UjdyKCdbbDViXTNtcWE5K0MxNkhCbHMzViVPclFjOSg1JlohODxiTHA3KXBYWjFuPllKOmU6JFpWSm0laG46WklmO1w/aWtWKkkoP3AmYSYuJSo9JS5JVSRNRF9MLzwiYTE3RD0jPSQ1MWFOTGtrZjprXXBHUjw9NVVrbWpnN2hMbmw3WkQ2PE9SYWdVTUQvVlRhPVc+XmNFUzhEUiIuWGVedT05JjFDMWVSVWA1LyVnXiJAJjB0cV0pREs8VE9cWCZLKEhJWXRKVTB+PmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDgKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDYxIDAwMDAwIG4gCjAwMDAwMDAwOTIgMDAwMDAgbiAKMDAwMDAwMDE5OSAwMDAwMCBuIAowMDAwMDAwNDAyIDAwMDAwIG4gCjAwMDAwMDA0NzAgMDAwMDAgbiAKMDAwMDAwMDczMSAwMDAwMCBuIAowMDAwMDAwNzkwIDAwMDAwIG4gCnRyYWlsZXIKPDwKL0lEIApbPDczNjNkNjY0OTUwNDY1MWQ4ODhkMzk3MTc3OTVlMzg0Pjw3MzYzZDY2NDk1MDQ2NTFkODg4ZDM5NzE3Nzk1ZTM4ND5dCiUgUmVwb3J0TGFiIGdlbmVyYXRlZCBQREYgZG9jdW1lbnQgLS0gZGlnZXN0IChvcGVuc291cmNlKQoKL0luZm8gNSAwIFIKL1Jvb3QgNCAwIFIKL1NpemUgOAo+PgpzdGFydHhyZWYKMTE1MgolJUVPRgo="
    )


def _review_smoke_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def _ocr_smoke_pdf() -> bytes:
    """Create an image-only scan from the already verified digital fixture."""
    document = pdfium.PdfDocument(BytesIO(_smoke_pdf()))
    page = document[0]
    bitmap = None
    image = None
    try:
        bitmap = page.render(scale=2.4)
        image = bitmap.to_pil().convert("RGB")
        output = BytesIO()
        image.save(output, format="PDF", resolution=144.0)
        return output.getvalue()
    finally:
        if image is not None:
            close = getattr(image, "close", None)
            if callable(close):
                close()
        if bitmap is not None:
            close = getattr(bitmap, "close", None)
            if callable(close):
                close()
        close = getattr(page, "close", None)
        if callable(close):
            close()
        close = getattr(document, "close", None)
        if callable(close):
            close()


@router.post("/test/job001-smoke", status_code=status.HTTP_201_CREATED)
def job001_smoke(
    review_case: bool = False,
    ocr_case: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: R2Storage = Depends(get_storage),
) -> dict[str, object]:
    """Run one protected real DB + presigned-R2 + validation smoke test.

    This endpoint is intentionally internal-only. It creates a uniquely named
    synthetic order and one generated one-page PDF. No customer data is used.
    """
    if review_case and ocr_case:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="review_case and ocr_case are mutually exclusive.",
        )

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
        detail={"kind": "job001-review-smoke" if review_case else ("job001-ocr-smoke" if ocr_case else "job001-production-smoke")},
    )

    pdf = _review_smoke_pdf() if review_case else (_ocr_smoke_pdf() if ocr_case else _smoke_pdf())
    filename = "job001-review-smoke.pdf" if review_case else ("job001-ocr-smoke.pdf" if ocr_case else "job001-production-smoke.pdf")
    item, upload_url = create_upload_ticket(
        db,
        order=order,
        payload=UploadRequest(
            filename=filename,
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
def start_order(
    order_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if db.get(Order, order_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    try:
        storage = R2Storage(settings)
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    try:
        return process_order(db, order_id=order_id, storage=storage)
    except ProcessingOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.") from exc
    except InvalidProcessingStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProcessingInfrastructureError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/orders/{order_id}/invoice-result")
def invoice_result(order_id: str) -> None:
    not_implemented("Invoice result persistence is not implemented yet.")


@router.post("/orders/{order_id}/review")
def review_order(
    order_id: str,
    payload: ReviewResolutionPayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return resolve_invoice_review(
            db,
            order_id=order_id,
            invoice_result_id=payload.invoice_result_id,
            supplier=payload.supplier,
            invoice_number=payload.invoice_number,
            invoice_date=payload.invoice_date,
            currency=payload.currency,
            subtotal_cents=payload.subtotal_cents,
            tax_cents=payload.tax_cents,
            total_cents=payload.total_cents,
            reviewer_note=payload.reviewer_note,
        )
    except ProcessingOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.") from exc
    except ReviewInvoiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice result not found.") from exc
    except InvalidProcessingStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/orders/{order_id}/complete")
def complete_order(order_id: str) -> None:
    not_implemented("Completion rules are not implemented yet.")


@router.post("/orders/{order_id}/fail")
def fail_order(order_id: str) -> None:
    not_implemented("Failure handling is not implemented yet.")
