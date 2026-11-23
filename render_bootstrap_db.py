from __future__ import annotations

from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, select

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

HEAD_REVISION = "0003_order_files"


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    inspector = inspect(engine)

    expected_tables = set(Base.metadata.tables)
    existing_tables = set(inspector.get_table_names())
    existing_business_tables = existing_tables & expected_tables

    if existing_business_tables and existing_business_tables != expected_tables:
        missing = sorted(expected_tables - existing_business_tables)
        raise RuntimeError(f"Refusing partial JOB-001 schema; missing tables: {missing}")

    if not existing_business_tables:
        Base.metadata.create_all(engine)

    inspector = inspect(engine)
    for table_name, table in Base.metadata.tables.items():
        actual_columns = {col["name"] for col in inspector.get_columns(table_name)}
        expected_columns = {col.name for col in table.columns}
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            raise RuntimeError(
                f"Refusing to stamp incomplete table {table_name}; "
                f"missing columns: {sorted(missing_columns)}"
            )

    version_metadata = MetaData()
    version_table = Table(
        "alembic_version",
        version_metadata,
        Column("version_num", String(32), primary_key=True),
    )
    version_metadata.create_all(engine, tables=[version_table])

    with engine.begin() as connection:
        current = connection.execute(select(version_table.c.version_num)).scalar_one_or_none()
        if current is None:
            connection.execute(version_table.insert().values(version_num=HEAD_REVISION))
        elif current != HEAD_REVISION:
            raise RuntimeError(
                f"Refusing to overwrite Alembic revision {current!r}; "
                f"expected {HEAD_REVISION!r}"
            )


if __name__ == "__main__":
    main()
