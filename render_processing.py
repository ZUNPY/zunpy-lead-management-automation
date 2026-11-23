"""Deterministic JOB-001 invoice processing for validated digital PDFs.

This stage deliberately fails closed. It extracts only explicit, supported
invoice fields from PDF text and never invents missing values. Documents that
cannot be resolved deterministically are routed to REVIEW.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvoiceResult, InvoiceStatus, Order, OrderStatus, ReviewReason
from app.services.orders import add_event, transition_order
from app.services.storage import R2Storage, StorageObjectNotFoundError


class ProcessingOrderNotFoundError(LookupError):
    pass


class InvalidProcessingStateError(ValueError):
    pass


class ProcessingInfrastructureError(RuntimeError):
    pass


class ReviewInvoiceNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ParsedInvoice:
    supplier: str | None
    invoice_number: str | None
    invoice_date: date | None
    currency: str | None
    subtotal_cents: int | None
    tax_cents: int | None
    total_cents: int | None
    review_reason: ReviewReason | None
    review_notes: str | None


_LABEL_VALUE_RE = re.compile(r"^\s*([^:]{1,60})\s*:\s*(.*?)\s*$")
_NUMBER_TOKEN_RE = re.compile(r"[-+]?\d[\d\s.,']*")


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _labeled_value(lines: list[str], labels: tuple[str, ...]) -> str | None:
    normalized = tuple(_normalize_label(label) for label in labels)
    for line in lines:
        match = _LABEL_VALUE_RE.match(line)
        if match and _normalize_label(match.group(1)) in normalized:
            value = match.group(2).strip()
            return value or None

        low = _normalize_label(line)
        for label in normalized:
            if low.startswith(label + " "):
                value = line[len(label) :].strip(" -#:\t")
                if value:
                    return value
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    candidate = re.sub(r"[,;].*$", "", value.strip()).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _money_to_cents(value: str | None) -> int | None:
    if not value:
        return None
    matches = _NUMBER_TOKEN_RE.findall(value)
    if not matches:
        return None
    raw = matches[-1].strip().replace(" ", "").replace("'", "")
    if raw.startswith("+"):
        raw = raw[1:]
    if raw.startswith("-"):
        return None

    comma = raw.rfind(",")
    dot = raw.rfind(".")
    if comma >= 0 and dot >= 0:
        if comma > dot:
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif comma >= 0:
        decimals = len(raw) - comma - 1
        raw = raw.replace(".", "")
        raw = raw.replace(",", ".") if decimals in {1, 2} else raw.replace(",", "")
    elif dot >= 0:
        decimals = len(raw) - dot - 1
        if decimals not in {1, 2}:
            raw = raw.replace(".", "")

    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return int(amount * 100)


def _money_from_labeled_line(lines: list[str], labels: tuple[str, ...]) -> int | None:
    return _money_to_cents(_labeled_value(lines, labels))


def _detect_currency(lines: list[str], text: str) -> str | None:
    explicit = _labeled_value(lines, ("currency", "moneda", "divisa"))
    if explicit:
        upper = explicit.upper()
        for code in ("EUR", "USD", "GBP"):
            if re.search(rf"\b{code}\b", upper):
                return code
        if "€" in explicit:
            return "EUR"
        if "£" in explicit:
            return "GBP"
        if "$" in explicit:
            return "USD"
        return None

    found: set[str] = set()
    upper_text = text.upper()
    if re.search(r"\bEUR\b", upper_text) or "€" in text:
        found.add("EUR")
    if re.search(r"\bUSD\b", upper_text) or "$" in text:
        found.add("USD")
    if re.search(r"\bGBP\b", upper_text) or "£" in text:
        found.add("GBP")
    return next(iter(found)) if len(found) == 1 else None


def parse_invoice_text(text: str) -> ParsedInvoice:
    lines = _lines(text)
    supplier = _labeled_value(lines, ("supplier", "vendor", "proveedor", "empresa"))
    invoice_number = _labeled_value(
        lines,
        (
            "invoice number",
            "invoice no",
            "invoice no.",
            "invoice #",
            "factura numero",
            "factura número",
            "factura no",
            "factura nº",
            "número factura",
            "numero factura",
        ),
    )
    invoice_date = _parse_date(
        _labeled_value(lines, ("invoice date", "date", "fecha factura", "fecha de factura", "fecha"))
    )
    currency = _detect_currency(lines, text)
    subtotal_cents = _money_from_labeled_line(
        lines, ("subtotal", "taxable base", "base imponible", "base")
    )
    tax_cents = _money_from_labeled_line(lines, ("tax", "vat", "iva", "impuestos"))
    total_cents = _money_from_labeled_line(
        lines, ("grand total", "invoice total", "total factura", "importe total", "total due", "total")
    )

    issues: list[str] = []
    reason: ReviewReason | None = None
    if supplier is None:
        issues.append("supplier missing")
        reason = ReviewReason.MISSING_SUPPLIER
    if invoice_number is None:
        issues.append("invoice number missing")
        reason = reason or ReviewReason.MISSING_INVOICE_NUMBER
    if invoice_date is None:
        issues.append("invoice date missing or unsupported")
        reason = reason or ReviewReason.MISSING_DATE
    if currency is None:
        issues.append("currency missing or ambiguous")
        reason = reason or ReviewReason.CURRENCY_UNCLEAR

    missing_money = [
        name
        for name, value in (
            ("subtotal", subtotal_cents),
            ("tax", tax_cents),
            ("total", total_cents),
        )
        if value is None
    ]
    if missing_money:
        issues.append("missing monetary fields: " + ", ".join(missing_money))
        reason = reason or ReviewReason.EXTRACTION_UNCERTAIN

    if (
        subtotal_cents is not None
        and tax_cents is not None
        and total_cents is not None
        and abs((subtotal_cents + tax_cents) - total_cents) > 1
    ):
        issues.append("subtotal + tax does not equal total")
        reason = ReviewReason.TOTAL_MISMATCH

    return ParsedInvoice(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        review_reason=reason,
        review_notes="; ".join(issues) if issues else None,
    )


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data), strict=False)
    parts: list[str] = []
    for page in reader.pages:
        value = page.extract_text() or ""
        if value.strip():
            parts.append(value)
    return "\n".join(parts).strip()


def _read_source(storage: R2Storage, object_key: str) -> bytes:
    try:
        body = storage.open_object(object_key=object_key)
    except StorageObjectNotFoundError as exc:
        raise ProcessingInfrastructureError("Validated source object is missing from storage.") from exc
    try:
        return body.read()
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()


def _process_invoice(db: Session, storage: R2Storage, invoice: InvoiceResult) -> None:
    if not invoice.source_object_key:
        raise ProcessingInfrastructureError("Invoice result has no validated source object key.")

    data = _read_source(storage, invoice.source_object_key)
    try:
        text = _extract_pdf_text(data)
    except Exception as exc:
        raise ProcessingInfrastructureError(
            f"Validated PDF could not be read during processing: {type(exc).__name__}."
        ) from exc

    if not text:
        invoice.status = InvoiceStatus.REVIEW
        invoice.review_reason = ReviewReason.LOW_QUALITY_SCAN
        invoice.review_notes = "No extractable text found; OCR/manual review required."
        invoice.extraction_method = "pypdf_text_v1"
    else:
        parsed = parse_invoice_text(text)
        invoice.supplier = parsed.supplier
        invoice.invoice_number = parsed.invoice_number
        invoice.invoice_date = parsed.invoice_date
        invoice.currency = parsed.currency
        invoice.subtotal_cents = parsed.subtotal_cents
        invoice.tax_cents = parsed.tax_cents
        invoice.total_cents = parsed.total_cents
        invoice.review_reason = parsed.review_reason
        invoice.review_notes = parsed.review_notes
        invoice.extraction_method = "pypdf_text_v1"
        invoice.status = InvoiceStatus.REVIEW if parsed.review_reason else InvoiceStatus.OK

    add_event(
        db,
        invoice.order_id,
        "INVOICE_PROCESSED",
        {
            "invoice_result_id": invoice.invoice_result_id,
            "status": invoice.status.value,
            "review_reason": invoice.review_reason.value if invoice.review_reason else None,
            "extraction_method": invoice.extraction_method,
        },
    )
    db.commit()
    db.refresh(invoice)


def process_order(db: Session, *, order_id: str, storage: R2Storage) -> dict[str, object]:
    order = db.scalar(select(Order).where(Order.order_id == order_id).with_for_update())
    if order is None:
        raise ProcessingOrderNotFoundError(order_id)
    if order.status != OrderStatus.READY:
        raise InvalidProcessingStateError(
            f"Order must be READY before processing; current state is {order.status.value}."
        )

    invoices = list(
        db.scalars(
            select(InvoiceResult)
            .where(InvoiceResult.order_id == order_id)
            .order_by(InvoiceResult.created_at, InvoiceResult.invoice_result_id)
        )
    )
    if not invoices:
        raise InvalidProcessingStateError("READY order has no invoice results to process.")
    if any(invoice.status != InvoiceStatus.RECEIVED for invoice in invoices):
        raise InvalidProcessingStateError("READY order contains invoices in an unexpected state.")

    transition_order(
        db,
        order_id=order_id,
        new_status=OrderStatus.PROCESSING,
        event_type="ORDER_PROCESSING_STARTED",
        detail={"document_count": len(invoices)},
    )

    try:
        for invoice in invoices:
            _process_invoice(db, storage, invoice)
    except ProcessingInfrastructureError as exc:
        order = db.get(Order, order_id)
        if order is not None:
            order.failure_reason = str(exc)
            db.commit()
            transition_order(
                db,
                order_id=order_id,
                new_status=OrderStatus.FAILED,
                event_type="ORDER_PROCESSING_FAILED",
                detail={"reason": str(exc)},
            )
        raise

    review_count = sum(invoice.status == InvoiceStatus.REVIEW for invoice in invoices)
    ok_count = sum(invoice.status == InvoiceStatus.OK for invoice in invoices)
    order = db.get(Order, order_id)
    assert order is not None
    order.review_count = review_count

    if review_count:
        order = transition_order(
            db,
            order_id=order_id,
            new_status=OrderStatus.REVIEW,
            event_type="ORDER_REQUIRES_REVIEW",
            detail={"ok": ok_count, "review": review_count, "total": len(invoices)},
        )
        result = "job001_processing_requires_review"
    else:
        order = transition_order(
            db,
            order_id=order_id,
            new_status=OrderStatus.COMPLETED,
            event_type="ORDER_PROCESSING_COMPLETED",
            detail={"ok": ok_count, "review": 0, "total": len(invoices)},
        )
        result = "job001_processing_completed"

    return {
        "status": "ok",
        "result": result,
        "order_id": order_id,
        "order_status": order.status.value,
        "total": len(invoices),
        "ok": ok_count,
        "review": review_count,
        "invoices": [
            {
                "invoice_result_id": invoice.invoice_result_id,
                "status": invoice.status.value,
                "review_reason": invoice.review_reason.value if invoice.review_reason else None,
                "supplier": invoice.supplier,
                "invoice_number": invoice.invoice_number,
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "currency": invoice.currency,
                "subtotal_cents": invoice.subtotal_cents,
                "tax_cents": invoice.tax_cents,
                "total_cents": invoice.total_cents,
                "extraction_method": invoice.extraction_method,
            }
            for invoice in invoices
        ],
    }


def resolve_invoice_review(
    db: Session,
    *,
    order_id: str,
    invoice_result_id: str,
    supplier: str,
    invoice_number: str,
    invoice_date: date,
    currency: str,
    subtotal_cents: int,
    tax_cents: int,
    total_cents: int,
    reviewer_note: str | None = None,
) -> dict[str, object]:
    """Apply one explicit human correction to a REVIEW invoice.

    The order temporarily re-enters PROCESSING while the correction is
    validated. It returns to REVIEW if any deterministic rule still fails;
    it reaches COMPLETED only when every invoice in the order is OK.
    """
    order = db.scalar(select(Order).where(Order.order_id == order_id).with_for_update())
    if order is None:
        raise ProcessingOrderNotFoundError(order_id)
    if order.status != OrderStatus.REVIEW:
        raise InvalidProcessingStateError(
            f"Order must be REVIEW before manual resolution; current state is {order.status.value}."
        )

    invoices = list(
        db.scalars(
            select(InvoiceResult)
            .where(InvoiceResult.order_id == order_id)
            .order_by(InvoiceResult.created_at, InvoiceResult.invoice_result_id)
        )
    )
    if not invoices:
        raise InvalidProcessingStateError("REVIEW order has no invoice results.")
    if any(invoice.status not in {InvoiceStatus.OK, InvoiceStatus.REVIEW} for invoice in invoices):
        raise InvalidProcessingStateError(
            "REVIEW order contains invoices in an unexpected state."
        )

    invoice = next(
        (item for item in invoices if item.invoice_result_id == invoice_result_id),
        None,
    )
    if invoice is None:
        raise ReviewInvoiceNotFoundError(invoice_result_id)
    if invoice.status != InvoiceStatus.REVIEW:
        raise InvalidProcessingStateError("Selected invoice is not awaiting review.")

    transition_order(
        db,
        order_id=order_id,
        new_status=OrderStatus.PROCESSING,
        event_type="ORDER_REVIEW_RESOLUTION_STARTED",
        detail={"invoice_result_id": invoice_result_id},
    )

    normalized_supplier = supplier.strip()
    normalized_number = invoice_number.strip()
    normalized_currency = currency.strip().upper()
    issues: list[str] = []
    reason: ReviewReason | None = None

    if not normalized_supplier:
        issues.append("supplier missing")
        reason = ReviewReason.MISSING_SUPPLIER
    if not normalized_number:
        issues.append("invoice number missing")
        reason = reason or ReviewReason.MISSING_INVOICE_NUMBER
    if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
        issues.append("currency must be a three-letter code")
        reason = reason or ReviewReason.CURRENCY_UNCLEAR
    if min(subtotal_cents, tax_cents, total_cents) < 0:
        issues.append("monetary fields must be non-negative")
        reason = reason or ReviewReason.EXTRACTION_UNCERTAIN
    if abs((subtotal_cents + tax_cents) - total_cents) > 1:
        issues.append("subtotal + tax does not equal total")
        reason = ReviewReason.TOTAL_MISMATCH

    invoice.supplier = normalized_supplier or None
    invoice.invoice_number = normalized_number or None
    invoice.invoice_date = invoice_date
    invoice.currency = normalized_currency or None
    invoice.subtotal_cents = subtotal_cents
    invoice.tax_cents = tax_cents
    invoice.total_cents = total_cents
    invoice.extraction_method = "manual_review_v1"

    note_parts = list(issues)
    if reviewer_note and reviewer_note.strip():
        note_parts.append("reviewer note: " + reviewer_note.strip())

    if issues:
        invoice.status = InvoiceStatus.REVIEW
        invoice.review_reason = reason or ReviewReason.EXTRACTION_UNCERTAIN
        invoice.review_notes = "; ".join(note_parts)
    else:
        invoice.status = InvoiceStatus.OK
        invoice.review_reason = None
        invoice.review_notes = reviewer_note.strip() if reviewer_note and reviewer_note.strip() else None

    add_event(
        db,
        order_id,
        "INVOICE_REVIEW_APPLIED",
        {
            "invoice_result_id": invoice.invoice_result_id,
            "status": invoice.status.value,
            "review_reason": invoice.review_reason.value if invoice.review_reason else None,
            "extraction_method": invoice.extraction_method,
        },
    )
    db.commit()
    db.refresh(invoice)

    review_count = sum(item.status == InvoiceStatus.REVIEW for item in invoices)
    ok_count = sum(item.status == InvoiceStatus.OK for item in invoices)
    order = db.get(Order, order_id)
    assert order is not None
    order.review_count = review_count
    db.commit()

    if review_count:
        order = transition_order(
            db,
            order_id=order_id,
            new_status=OrderStatus.REVIEW,
            event_type="ORDER_REVIEW_STILL_REQUIRED",
            detail={"ok": ok_count, "review": review_count, "total": len(invoices)},
        )
        result = "job001_review_still_required"
    else:
        order = transition_order(
            db,
            order_id=order_id,
            new_status=OrderStatus.COMPLETED,
            event_type="ORDER_REVIEW_COMPLETED",
            detail={"ok": ok_count, "review": 0, "total": len(invoices)},
        )
        result = "job001_review_resolved"

    return {
        "status": "ok",
        "result": result,
        "order_id": order_id,
        "order_status": order.status.value,
        "total": len(invoices),
        "ok": ok_count,
        "review": review_count,
        "invoice": {
            "invoice_result_id": invoice.invoice_result_id,
            "status": invoice.status.value,
            "review_reason": invoice.review_reason.value if invoice.review_reason else None,
            "supplier": invoice.supplier,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            "currency": invoice.currency,
            "subtotal_cents": invoice.subtotal_cents,
            "tax_cents": invoice.tax_cents,
            "total_cents": invoice.total_cents,
            "extraction_method": invoice.extraction_method,
        },
    }
