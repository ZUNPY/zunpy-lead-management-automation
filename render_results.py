"""JOB-001 CSV result generation and private download signing."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvoiceResult, InvoiceStatus, Order, OrderStatus
from app.services.orders import add_event
from app.services.storage import R2Storage, StorageObjectNotFoundError


RESULT_RETENTION_DAYS = 30
RESULT_FILENAME = "invoices.csv"
RESULT_CONTENT_TYPE = "text/csv; charset=utf-8"


class ResultOrderNotFoundError(LookupError):
    pass


class ResultNotReadyError(ValueError):
    pass


class ResultExpiredError(ValueError):
    pass


class ResultDataError(ValueError):
    pass


@dataclass(frozen=True)
class ResultArtifact:
    object_key: str
    filename: str
    content_type: str
    size_bytes: int
    row_count: int
    delete_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def result_object_key(order_id: str) -> str:
    return f"results/{order_id}/{RESULT_FILENAME}"


def _money(cents: int | None) -> str:
    if cents is None:
        return ""
    return f"{cents / 100:.2f}"


def _load_invoices(db: Session, order_id: str) -> list[InvoiceResult]:
    return list(
        db.scalars(
            select(InvoiceResult)
            .where(InvoiceResult.order_id == order_id)
            .order_by(InvoiceResult.created_at, InvoiceResult.invoice_result_id)
        )
    )


def _validate_completed_data(order: Order, invoices: list[InvoiceResult]) -> None:
    if order.status != OrderStatus.COMPLETED:
        raise ResultNotReadyError(
            f"Result is only available for COMPLETED orders; current state is {order.status.value}."
        )
    if not invoices:
        raise ResultDataError("COMPLETED order has no invoice results.")
    if any(invoice.status != InvoiceStatus.OK for invoice in invoices):
        raise ResultDataError("COMPLETED order contains a non-OK invoice result.")

    for invoice in invoices:
        required = {
            "supplier": invoice.supplier,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "currency": invoice.currency,
            "subtotal_cents": invoice.subtotal_cents,
            "tax_cents": invoice.tax_cents,
            "total_cents": invoice.total_cents,
        }
        missing = [name for name, value in required.items() if value is None or value == ""]
        if missing:
            raise ResultDataError(
                f"Invoice {invoice.invoice_result_id} is missing required result fields: "
                + ", ".join(missing)
            )
        assert invoice.subtotal_cents is not None
        assert invoice.tax_cents is not None
        assert invoice.total_cents is not None
        if abs((invoice.subtotal_cents + invoice.tax_cents) - invoice.total_cents) > 1:
            raise ResultDataError(
                f"Invoice {invoice.invoice_result_id} fails arithmetic validation."
            )


def build_result_csv(invoices: list[InvoiceResult]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "original_filename",
            "supplier",
            "invoice_number",
            "invoice_date",
            "currency",
            "subtotal",
            "tax",
            "total",
            "validation_status",
            "notes",
            "extraction_method",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for invoice in invoices:
        writer.writerow(
            {
                "original_filename": invoice.source_filename,
                "supplier": invoice.supplier or "",
                "invoice_number": invoice.invoice_number or "",
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else "",
                "currency": invoice.currency or "",
                "subtotal": _money(invoice.subtotal_cents),
                "tax": _money(invoice.tax_cents),
                "total": _money(invoice.total_cents),
                "validation_status": invoice.status.value,
                "notes": invoice.review_notes or "",
                "extraction_method": invoice.extraction_method or "",
            }
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def ensure_result_csv(db: Session, *, order_id: str, storage: R2Storage) -> ResultArtifact:
    order = db.get(Order, order_id)
    if order is None:
        raise ResultOrderNotFoundError(order_id)

    now = _utcnow()
    if order.results_delete_at is not None and _as_utc(order.results_delete_at) <= now:
        raise ResultExpiredError("Result retention period has expired.")

    invoices = _load_invoices(db, order_id)
    _validate_completed_data(order, invoices)
    key = result_object_key(order_id)

    try:
        metadata = storage.head(object_key=key)
        delete_at = order.results_delete_at or (now + timedelta(days=RESULT_RETENTION_DAYS))
        if order.results_delete_at is None:
            order.results_delete_at = delete_at
            db.commit()
        return ResultArtifact(
            object_key=key,
            filename=RESULT_FILENAME,
            content_type=RESULT_CONTENT_TYPE,
            size_bytes=metadata.size_bytes,
            row_count=len(invoices),
            delete_at=_as_utc(delete_at),
        )
    except StorageObjectNotFoundError:
        pass

    payload = build_result_csv(invoices)
    storage.client.put_object(
        Bucket=storage.bucket,
        Key=key,
        Body=payload,
        ContentType=RESULT_CONTENT_TYPE,
        ContentDisposition=f'attachment; filename="{RESULT_FILENAME}"',
        CacheControl="private, no-store",
    )
    metadata = storage.head(object_key=key)
    delete_at = now + timedelta(days=RESULT_RETENTION_DAYS)
    order.results_delete_at = delete_at
    add_event(
        db,
        order_id,
        "RESULT_CSV_GENERATED",
        {
            "object_key": key,
            "filename": RESULT_FILENAME,
            "row_count": len(invoices),
            "size_bytes": metadata.size_bytes,
            "delete_at": delete_at.isoformat(),
        },
    )
    db.commit()

    return ResultArtifact(
        object_key=key,
        filename=RESULT_FILENAME,
        content_type=RESULT_CONTENT_TYPE,
        size_bytes=metadata.size_bytes,
        row_count=len(invoices),
        delete_at=delete_at,
    )


def result_download_payload(
    db: Session,
    *,
    order_id: str,
    storage: R2Storage,
) -> dict[str, object]:
    artifact = ensure_result_csv(db, order_id=order_id, storage=storage)
    return {
        "status": "ok",
        "result": "job001_result_ready",
        "order_id": order_id,
        "filename": artifact.filename,
        "content_type": artifact.content_type,
        "row_count": artifact.row_count,
        "size_bytes": artifact.size_bytes,
        "download_url": storage.presign_download(object_key=artifact.object_key),
        "expires_in_seconds": storage.settings.r2_presigned_download_ttl_seconds,
        "delete_at": artifact.delete_at.isoformat(),
    }
