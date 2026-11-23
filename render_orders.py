from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import InvoiceStatus, Order
from app.schemas.file import UploadRequest, UploadTicket, UploadValidationResponse
from app.schemas.order import OrderPublic, OrderStatusResponse
from app.security.auth import require_order_access, require_order_upload_access
from app.services.files import (
    InvalidUploadStateError,
    UploadLimitError,
    UploadNotFoundError,
    UploadedObjectMissingError,
    UploadValidationError,
    create_upload_ticket,
    finalize_upload,
    submit_order as submit_order_service,
)
from app.services.results import (
    ResultDataError,
    ResultExpiredError,
    ResultNotReadyError,
    result_download_payload,
)
from app.services.storage import R2Storage, StorageConfigurationError, get_storage

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/{order_id}", response_model=OrderPublic)
def get_order(order: Order = Depends(require_order_access)) -> Order:
    return order


@router.post("/{order_id}/files", response_model=UploadTicket, status_code=status.HTTP_201_CREATED)
def request_upload(
    payload: UploadRequest,
    order: Order = Depends(require_order_upload_access),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: R2Storage = Depends(get_storage),
) -> UploadTicket:
    try:
        item, url = create_upload_ticket(
            db, order=order, payload=payload, storage=storage, settings=settings
        )
    except UploadLimitError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc))
    except InvalidUploadStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return UploadTicket(
        upload_id=item.upload_id,
        upload_url=url,
        required_headers={"Content-Type": "application/pdf"},
        expires_at=item.presigned_expires_at,
        max_size_bytes=settings.max_pdf_bytes,
    )


@router.post("/{order_id}/files/{upload_id}/complete", response_model=UploadValidationResponse)
def complete_upload(
    upload_id: str,
    order: Order = Depends(require_order_upload_access),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: R2Storage = Depends(get_storage),
) -> UploadValidationResponse:
    try:
        item = finalize_upload(
            db,
            order_id=order.order_id,
            upload_id=upload_id,
            storage=storage,
            settings=settings,
        )
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.") from exc
    except UploadedObjectMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload has not reached object storage yet.",
        ) from exc
    except InvalidUploadStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"reason": exc.reason, "message": exc.detail},
        ) from exc
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return UploadValidationResponse(
        upload_id=item.upload_id,
        status=item.status,
        invoice_result_id=item.invoice_result_id,
        page_count=item.page_count,
        rejection_reason=item.rejection_reason,
    )


@router.post("/{order_id}/submit", response_model=OrderPublic)
def submit_order(
    order: Order = Depends(require_order_upload_access),
    db: Session = Depends(get_db),
) -> Order:
    try:
        return submit_order_service(db, order_id=order.order_id)
    except InvalidUploadStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{order_id}/status", response_model=OrderStatusResponse)
def order_status(order: Order = Depends(require_order_access)) -> OrderStatusResponse:
    statuses = [invoice.status for invoice in order.invoices]
    return OrderStatusResponse(
        order_id=order.order_id,
        status=order.status,
        total=len(statuses),
        ok=sum(value == InvoiceStatus.OK for value in statuses),
        review=sum(value == InvoiceStatus.REVIEW for value in statuses),
        processing=sum(
            value in {InvoiceStatus.RECEIVED, InvoiceStatus.EXTRACTED, InvoiceStatus.VALIDATED}
            for value in statuses
        ),
    )


@router.get("/{order_id}/result")
def order_result(
    order: Order = Depends(require_order_access),
    db: Session = Depends(get_db),
    storage: R2Storage = Depends(get_storage),
) -> dict[str, object]:
    try:
        return result_download_payload(db, order_id=order.order_id, storage=storage)
    except ResultNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ResultExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except ResultDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Completed order result is inconsistent: {exc}",
        ) from exc
