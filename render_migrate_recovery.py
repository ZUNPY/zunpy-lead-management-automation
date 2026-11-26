"""Explicit, additive JOB-005 recovery schema migration.

The existing 0003_order_files Alembic revision is deliberately unchanged:
this extension is separately managed, so the previous API can still boot.
Run only after taking a backup. No automatic migration during requests.
"""
from __future__ import annotations

from sqlalchemy import DateTime, String, create_engine, inspect, text

from app.core.config import get_settings
from app.db.base import Base
from render_recovery import recovery_tokens

BASE_REVISION = "0003_order_files"


def migrate(engine) -> None:
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
        recovery_tokens.create(conn, checkfirst=True)
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


def main() -> None:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        migrate(engine)
    finally:
        engine.dispose()
    print("RECOVERY_SCHEMA: PASS")


if __name__ == "__main__":
    main()
