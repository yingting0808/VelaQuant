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


def test_runtime_settings_persist_non_secret_openai_overrides(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "external-key")
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        payload = update_runtime_settings(
            session,
            RuntimeSettingsUpdate(
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
    assert effective.openai_research_enabled is False
    assert effective.openai_research_model == "gpt-5.4"
    assert effective.openai_base_url == "https://api.openai.example/v1"
    assert effective.openai_timeout_seconds == 12.5
