from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def get_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = get_engine()


def create_db_and_tables() -> None:
    from app.domain import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_paper_order_core_columns()


def _ensure_paper_order_core_columns() -> None:
    inspector = inspect(engine)
    if "paperorder" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("paperorder")}
    columns = {
        "core_order_id": "VARCHAR",
        "core_intent_id": "VARCHAR",
        "risk_status": "VARCHAR",
        "risk_code": "VARCHAR",
        "risk_reason": "VARCHAR",
        "state_history_json": "TEXT",
    }
    missing = [(name, column_type) for name, column_type in columns.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as connection:
        for name, column_type in missing:
            connection.execute(text(f"ALTER TABLE paperorder ADD COLUMN {name} {column_type}"))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
