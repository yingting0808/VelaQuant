from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings
from app.services.runtime_settings import (
    RuntimeSettingsUpdate,
    get_effective_settings,
    get_runtime_settings_payload,
    update_runtime_settings,
)


def test_runtime_settings_default_to_environment_without_storing_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        payload = get_runtime_settings_payload(
            session,
            Settings(
                data_mode="hybrid",
                lean_backtest_timeout_seconds=600,
                event_bus_mode="redis",
                redis_stream_name="trading:events",
                paper_scheduler_enabled=True,
                paper_scheduler_cron="30 6 * * *",
                paper_scheduler_timezone="Asia/Shanghai",
                openai_research_enabled=True,
                openai_api_key=None,
                openai_research_model="gpt-5.5",
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=20,
            ),
        )

    assert payload.source == "defaults"
    assert payload.openai_research_enabled is True
    assert payload.openai_research_model == "gpt-5.5"
    assert payload.openai_base_url == "https://api.openai.com/v1"
    assert payload.openai_timeout_seconds == 20
    assert payload.openai_api_key_configured is False
    assert payload.openai_api_key_source is None
    assert payload.data_mode == "hybrid"
    assert payload.sec_user_agent == "VelaQuant research app contact@example.com"
    assert payload.lean_backtest_timeout_seconds == 600
    assert payload.paper_scheduler_enabled is True
    assert payload.paper_scheduler_cron == "30 6 * * *"
    assert payload.paper_scheduler_timezone == "Asia/Shanghai"
    assert payload.event_bus_mode == "redis"
    assert payload.redis_stream_name == "trading:events"
    assert payload.redis_configured is True


def test_runtime_settings_persist_non_secret_openai_overrides(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "external-key")
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        payload = update_runtime_settings(
            session,
            RuntimeSettingsUpdate(
                data_mode="openbb_optional",
                lean_backtest_timeout_seconds=900,
                openai_research_enabled=False,
                openai_research_model="gpt-5.4",
                openai_base_url="https://api.openai.example/v1",
                openai_timeout_seconds=12.5,
            ),
            Settings(openai_api_key=None),
        )
        effective = get_effective_settings(session, Settings(openai_api_key=None))

    assert payload.source == "database"
    assert payload.openai_research_enabled is False
    assert payload.openai_research_model == "gpt-5.4"
    assert payload.openai_base_url == "https://api.openai.example/v1"
    assert payload.openai_timeout_seconds == 12.5
    assert payload.openai_api_key_configured is True
    assert payload.openai_api_key_source == "OPENAI_API_KEY"
    assert payload.data_mode == "openbb_optional"
    assert payload.lean_backtest_timeout_seconds == 900
    assert effective.openai_research_enabled is False
    assert effective.openai_research_model == "gpt-5.4"
    assert effective.openai_base_url == "https://api.openai.example/v1"
    assert effective.openai_timeout_seconds == 12.5
    assert effective.data_mode == "openbb_optional"
    assert effective.lean_backtest_timeout_seconds == 900


def test_runtime_settings_can_store_runtime_openai_key_without_returning_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        payload = update_runtime_settings(
            session,
            RuntimeSettingsUpdate(
                data_mode="hybrid",
                lean_backtest_timeout_seconds=600,
                sec_user_agent="VelaQuant prod ops@example.com",
                openai_research_enabled=True,
                openai_research_model="gpt-5.5",
                openai_base_url="https://api.openai.com/v1/",
                openai_timeout_seconds=20,
                openai_api_key=" sk-live-runtime-secret ",
            ),
            Settings(openai_api_key=None, sec_user_agent="VelaQuant default contact@example.com"),
        )
        effective = get_effective_settings(
            session,
            Settings(openai_api_key=None, sec_user_agent="VelaQuant default contact@example.com"),
        )

    assert payload.openai_api_key_configured is True
    assert payload.openai_api_key_source == "runtime_database"
    assert "sk-live-runtime-secret" not in payload.model_dump_json()
    assert payload.sec_user_agent == "VelaQuant prod ops@example.com"
    assert effective.openai_api_key == "sk-live-runtime-secret"
    assert effective.sec_user_agent == "VelaQuant prod ops@example.com"


def test_runtime_settings_can_clear_runtime_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        update_runtime_settings(
            session,
            RuntimeSettingsUpdate(
                data_mode="hybrid",
                lean_backtest_timeout_seconds=600,
                sec_user_agent="VelaQuant prod ops@example.com",
                openai_research_enabled=True,
                openai_research_model="gpt-5.5",
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=20,
                openai_api_key="sk-live-runtime-secret",
            ),
            Settings(openai_api_key=None),
        )
        payload = update_runtime_settings(
            session,
            RuntimeSettingsUpdate(
                data_mode="hybrid",
                lean_backtest_timeout_seconds=600,
                sec_user_agent="VelaQuant prod ops@example.com",
                openai_research_enabled=True,
                openai_research_model="gpt-5.5",
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=20,
                clear_openai_api_key=True,
            ),
            Settings(openai_api_key=None),
        )
        effective = get_effective_settings(session, Settings(openai_api_key=None))

    assert payload.openai_api_key_configured is False
    assert payload.openai_api_key_source is None
    assert effective.openai_api_key is None
