"""Explicit, additive JOB-005 recovery schema migration.

The existing 0003_order_files Alembic revision is deliberately unchanged:
this extension is separately managed, so the previous API can still boot.
Run only after taking a backup. No automatic migration during requests.
"""
from __future__ import annotations

import argparse

from sqlalchemy import DateTime, String, create_engine, inspect, text

from app.core.config import get_settings
from app.db.base import Base
from render_recovery import recovery_tokens
from render_recovery_limits import recovery_limits

BASE_REVISION = "0003_order_files"


def migrate(engine, *, check_only: bool = False) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Recovery migration requires PostgreSQL.")
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        conn.execute(text("SET LOCAL statement_timeout = '30s'"))
        conn.execute(text("SELECT pg_advisory_xact_lock(74000502)"))
        inspector = inspect(conn)
        expected = set(Base.metadata.tables) - {recovery_tokens.name}
        existing = set(inspector.get_table_names())
        if not (expected | {"alembic_version"}).issubset(existing):
            raise RuntimeError("Base schema is incomplete.")
        revisions = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if revisions != [BASE_REVISION]:
            raise RuntimeError("Unexpected base schema revision.")
        for name in expected:
            actual = {c["name"] for c in inspector.get_columns(name)}
            if not {c.name for c in Base.metadata.tables[name].columns}.issubset(actual):
                raise RuntimeError(f"Incomplete base table: {name}")
        if check_only:
            if not {recovery_tokens.name, recovery_limits.name}.issubset(existing):
                raise RuntimeError("Recovery schema missing; run explicit migration first.")
        else:
            recovery_tokens.create(conn, checkfirst=True)
            recovery_limits.create(conn, checkfirst=True)
        inspector = inspect(conn)
        columns = {c["name"]: c for c in inspector.get_columns(recovery_tokens.name)}
        if set(columns) != {c.name for c in recovery_tokens.columns}:
            raise RuntimeError("Unexpected recovery table columns.")
        for expected_column in recovery_tokens.columns:
            actual = columns[expected_column.name]
            actual_type = actual["type"]
            expected_type = expected_column.type
            if actual["nullable"] != expected_column.nullable:
                raise RuntimeError("Recovery table nullability mismatch.")
            if isinstance(expected_type, String):
                if not isinstance(actual_type, String) or actual_type.length != expected_type.length:
                    raise RuntimeError("Recovery table string type mismatch.")
            elif isinstance(expected_type, DateTime):
                if not isinstance(actual_type, DateTime) or not actual_type.timezone:
                    raise RuntimeError("Recovery table timestamp type mismatch.")
            else:
                raise RuntimeError("Unexpected recovery column type.")
        pk = inspector.get_pk_constraint(recovery_tokens.name)
        if pk.get("constrained_columns") != ["order_id"]:
            raise RuntimeError("Recovery primary key mismatch.")
        fks = inspector.get_foreign_keys(recovery_tokens.name)
        if len(fks) != 1 or not (
            fks[0]["constrained_columns"] == ["order_id"]
            and fks[0]["referred_table"] == "orders"
            and fks[0]["referred_columns"] == ["order_id"]
            and fks[0].get("options", {}).get("ondelete", "").upper() == "CASCADE"
        ):
            raise RuntimeError("Recovery foreign key mismatch.")
        quota_columns = {c["name"]: c for c in inspector.get_columns(recovery_limits.name)}
        if set(quota_columns) != {"bucket", "quota_key", "attempts"}:
            raise RuntimeError("Unexpected quota table columns.")
        for name in ("bucket", "attempts"):
            col = quota_columns[name]
            if col["nullable"] or type(col["type"]).__name__ != "INTEGER":
                raise RuntimeError("Quota integer column mismatch.")
        key = quota_columns["quota_key"]
        if key["nullable"] or not isinstance(key["type"], String) or key["type"].length != 80:
            raise RuntimeError("Quota key mismatch.")
        if inspector.get_pk_constraint(recovery_limits.name).get("constrained_columns") != ["bucket", "quota_key"]:
            raise RuntimeError("Quota primary key mismatch.")
        if inspector.get_foreign_keys(recovery_limits.name):
            raise RuntimeError("Unexpected quota foreign key.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without creating tables")
    args = parser.parse_args()
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        migrate(engine, check_only=args.check)
    finally:
        engine.dispose()
    print("RECOVERY_SCHEMA: PASS")


if __name__ == "__main__":
    main()
