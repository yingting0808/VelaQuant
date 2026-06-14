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
    _ensure_paper_trading_mode_enum_values()
    _ensure_paper_run_trigger_enum_values()
    _ensure_paper_account_strategy_columns()
    _ensure_paper_order_core_columns()


def _ensure_paper_trading_mode_enum_values() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        for statement in _postgres_enum_value_statements("papertradingmode", ["shadow", "live_small", "simulation"]):
            connection.execute(text(statement))


def _ensure_paper_run_trigger_enum_values() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        for statement in _postgres_enum_value_statements("paperruntrigger", ["simulation"]):
            connection.execute(text(statement))


def _postgres_enum_value_statements(enum_name: str, values: list[str]) -> list[str]:
    return [f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'" for value in values]


def _ensure_paper_account_strategy_columns() -> None:
    inspector = inspect(engine)
    if "paperaccount" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("paperaccount")}
    if "strategy_id" in existing:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE paperaccount ADD COLUMN strategy_id VARCHAR DEFAULT 'deterministic_watchlist_v1'")
        )


def _ensure_paper_order_core_columns() -> None:
    inspector = inspect(engine)
    if "paperorder" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("paperorder")}
    columns = {
        "strategy_id": "VARCHAR DEFAULT 'deterministic_watchlist_v1'",
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
