"""PostgreSQL recovery-request quota, not yet wired to public routes.

Caller passes a trusted, server-derived source HMAC (never an untrusted
forwarded header). No raw address, email or recovery credential is stored.
Use a dedicated short transaction and commit before issuing recovery.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, MetaData, String, Table, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

WINDOW_SECONDS = 900
GLOBAL_LIMIT = 120
SOURCE_LIMIT = 10
ORDER_LIMIT = 3
LOCK_ID = 74000503

metadata = MetaData()
recovery_limits = Table(
    "order_recovery_limits", metadata,
    Column("bucket", Integer, primary_key=True),
    Column("quota_key", String(80), primary_key=True),
    Column("attempts", Integer, nullable=False),
)


def allow_request(db: Session, *, order_id: str, source_key: str,
                  now: datetime | None = None) -> bool:
    """Atomically reserve one request; applies to unknown orders as well."""
    if not re.fullmatch(r"[0-9a-f]{64}", source_key):
        raise ValueError("Expected a server-derived source HMAC.")
    if not 1 <= len(order_id) <= 32:
        raise ValueError("Invalid order identifier length.")
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Recovery quota requires PostgreSQL.")
    db.execute(text("SET LOCAL lock_timeout = '3s'"))
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_ID})
    current = now if now is not None else db.execute(
        text("SELECT clock_timestamp()")
    ).scalar_one()
    if current.tzinfo is None:
        raise ValueError("Expected timezone-aware time.")
    bucket = int(current.astimezone(timezone.utc).timestamp()) // WINDOW_SECONDS
    target = hashlib.sha256(order_id.strip().upper().encode()).hexdigest()
    quotas = {
        "global": GLOBAL_LIMIT,
        "source:" + source_key: SOURCE_LIMIT,
        "order:" + target: ORDER_LIMIT,
    }
    # Bounded storage: only successful reservations create quota rows.
    db.execute(recovery_limits.delete().where(recovery_limits.c.bucket < bucket))
    counts = dict(db.execute(select(
        recovery_limits.c.quota_key, recovery_limits.c.attempts
    ).where(recovery_limits.c.bucket == bucket,
            recovery_limits.c.quota_key.in_(list(quotas)))).all())
    if any(counts.get(key, 0) >= limit for key, limit in quotas.items()):
        return False
    for key in quotas:
        stmt = insert(recovery_limits).values(bucket=bucket, quota_key=key, attempts=1)
        db.execute(stmt.on_conflict_do_update(
            index_elements=[recovery_limits.c.bucket, recovery_limits.c.quota_key],
            set_={"attempts": recovery_limits.c.attempts + 1},
        ))
    return True
