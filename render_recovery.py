"""JOB-005.2 recovery service. Not wired into the running API yet.

Caller must own a transaction, commit before delivering/returning any raw
credential, and roll back on failure. PostgreSQL order-row locks serialize
issue/redeem operations. Never log the returned credentials. Email delivery,
public response uniformity, throttling and schema migration are separate gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus
from app.security.tokens import (
    ensure_aware_utc, generate_raw_token, hash_token, is_expired, utcnow,
    verify_token,
)

RECOVERY_TTL = timedelta(minutes=15)
ELIGIBLE = frozenset({
    OrderStatus.WAITING_UPLOAD, OrderStatus.READY, OrderStatus.PROCESSING,
    OrderStatus.REVIEW, OrderStatus.COMPLETED,
})

# Explicit migration required before integration; no DDL at request time.
recovery_tokens = Table(
    "order_recovery_tokens", Order.__table__.metadata,
    Column("order_id", String(32), ForeignKey("orders.order_id", ondelete="CASCADE"),
           primary_key=True),
    Column("token_hash", String(64), nullable=False),
    Column("access_hash_at_issue", String(128), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True), nullable=True),
)


@dataclass(frozen=True, repr=False)
class RecoveryDelivery:
    order_id: str
    recipient: str
    raw_token: str
    expires_at: datetime


@dataclass(frozen=True, repr=False)
class RecoveredAccess:
    order_id: str
    order_token: str


def _lock_order(db: Session, order_id: str) -> Order | None:
    return db.execute(
        select(Order).where(Order.order_id == order_id)
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _eligible(order: Order | None, now: datetime) -> bool:
    return bool(
        order is not None
        and order.payment_provider == "paypal"
        and order.payment_reference.startswith("PAYPAL:")
        and order.status in ELIGIBLE
        and order.access_token_hash
        and not is_expired(order.access_expires_at, now=now)
    )


def issue_recovery(
    db: Session, *, order_id: str, email: str, now: datetime | None = None,
) -> RecoveryDelivery | None:
    """Internal service result, not a public response. Never sends mail."""
    current = ensure_aware_utc(now or utcnow())
    order = _lock_order(db, order_id)
    if not _eligible(order, current):
        return None
    # Deliver only to the stored address, never to caller-supplied text.
    if email.strip() != order.customer_email:
        return None
    row = db.execute(
        select(recovery_tokens).where(recovery_tokens.c.order_id == order_id)
    ).mappings().one_or_none()
    # Do not invalidate a pending link through repeated requests.
    if (row and row["consumed_at"] is None
            and row["access_hash_at_issue"] == order.access_token_hash
            and not is_expired(row["expires_at"], now=current)):
        return None
    raw = generate_raw_token()
    expiry = min(current + RECOVERY_TTL, ensure_aware_utc(order.access_expires_at))
    values = dict(token_hash=hash_token(raw),
                  access_hash_at_issue=order.access_token_hash,
                  expires_at=expiry, consumed_at=None)
    if row is None:
        db.execute(recovery_tokens.insert().values(order_id=order_id, **values))
    else:
        db.execute(recovery_tokens.update().where(
            recovery_tokens.c.order_id == order_id).values(**values))
    return RecoveryDelivery(order_id, order.customer_email, raw, expiry)


def redeem_recovery(
    db: Session, *, order_id: str, raw_token: str, now: datetime | None = None,
) -> RecoveredAccess | None:
    """Rotate the customer credential once; preserve existing access/upload TTLs."""
    current = ensure_aware_utc(now or utcnow())
    order = _lock_order(db, order_id)
    if not _eligible(order, current):
        return None
    row = db.execute(
        select(recovery_tokens).where(recovery_tokens.c.order_id == order_id)
    ).mappings().one_or_none()
    if (row is None or row["consumed_at"] is not None
            or is_expired(row["expires_at"], now=current)
            or row["access_hash_at_issue"] != order.access_token_hash
            or not verify_token(raw_token, row["token_hash"])):
        return None
    raw = generate_raw_token()
    order.access_token_hash = hash_token(raw)
    db.execute(recovery_tokens.update().where(
        recovery_tokens.c.order_id == order_id).values(consumed_at=current))
    db.flush()
    return RecoveredAccess(order_id, raw)
