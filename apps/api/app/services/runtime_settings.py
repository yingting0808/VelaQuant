from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.domain.models import RuntimeConfiguration, utc_now

DataMode = Literal["hybrid", "mock", "openbb_optional", "sec_edgar"]


class RuntimeSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["defaults", "database"]
    data_mode: str
    sec_user_agent: str
    lean_backtest_timeout_seconds: float
    paper_scheduler_enabled: bool
    paper_scheduler_cron: str
    paper_scheduler_timezone: str
    event_bus_mode: str
    redis_stream_name: str
    redis_configured: bool
    openai_research_enabled: bool
    openai_research_model: str
    openai_base_url: str
    openai_timeout_seconds: float
    openai_api_key_configured: bool
    openai_api_key_source: str | None


class RuntimeSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_mode: DataMode | None = None
    sec_user_agent: str | None = Field(default=None, min_length=12, max_length=200)
    lean_backtest_timeout_seconds: float | None = Field(default=None, ge=30, le=3600)
    openai_research_enabled: bool
    openai_research_model: str = Field(min_length=1, max_length=80)
    openai_base_url: str = Field(min_length=8, max_length=200)
    openai_timeout_seconds: float = Field(gt=0, le=120)
    openai_api_key: str | None = Field(default=None, max_length=500)
    clear_openai_api_key: bool = False

    @field_validator("openai_research_model", "openai_base_url")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("sec_user_agent")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("openai_api_key")
    @classmethod
    def normalize_optional_secret(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("openai_base_url")
    @classmethod
    def require_http_base_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("OpenAI base URL must start with http:// or https://")
        return value.rstrip("/")


def get_runtime_settings_payload(
    session: Session,
    settings: Settings | None = None,
) -> RuntimeSettingsPayload:
    active_settings = settings or get_settings()
    row = session.get(RuntimeConfiguration, "default")
    source: Literal["defaults", "database"] = "database" if row else "defaults"
    return _payload_from_values(
        source=source,
        data_mode=row.data_mode if row else active_settings.data_mode,
        sec_user_agent=row.sec_user_agent if row else active_settings.sec_user_agent,
        lean_backtest_timeout_seconds=(
            row.lean_backtest_timeout_seconds if row else active_settings.lean_backtest_timeout_seconds
        ),
        openai_api_key=row.openai_api_key if row else None,
        openai_research_enabled=row.openai_research_enabled if row else active_settings.openai_research_enabled,
        openai_research_model=row.openai_research_model if row else active_settings.openai_research_model,
        openai_base_url=row.openai_base_url if row else active_settings.openai_base_url,
        openai_timeout_seconds=row.openai_timeout_seconds if row else active_settings.openai_timeout_seconds,
        settings=active_settings,
    )


def update_runtime_settings(
    session: Session,
    update: RuntimeSettingsUpdate,
    settings: Settings | None = None,
) -> RuntimeSettingsPayload:
    row = session.get(RuntimeConfiguration, "default")
    if row is None:
        row = RuntimeConfiguration(id="default")
        session.add(row)

    if update.data_mode is not None:
        row.data_mode = update.data_mode
    if update.sec_user_agent is not None:
        row.sec_user_agent = update.sec_user_agent
    if update.lean_backtest_timeout_seconds is not None:
        row.lean_backtest_timeout_seconds = update.lean_backtest_timeout_seconds
    if update.clear_openai_api_key:
        row.openai_api_key = None
    elif update.openai_api_key is not None:
        row.openai_api_key = update.openai_api_key
    row.openai_research_enabled = update.openai_research_enabled
    row.openai_research_model = update.openai_research_model
    row.openai_base_url = update.openai_base_url
    row.openai_timeout_seconds = update.openai_timeout_seconds
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)

    return get_runtime_settings_payload(session, settings)


def get_effective_settings(session: Session, settings: Settings | None = None) -> Settings:
    active_settings = settings or get_settings()
    row = session.get(RuntimeConfiguration, "default")
    if row is None:
        return active_settings
    return active_settings.model_copy(
        update={
            "data_mode": row.data_mode,
            "sec_user_agent": row.sec_user_agent,
            "lean_backtest_timeout_seconds": row.lean_backtest_timeout_seconds,
            "openai_api_key": row.openai_api_key or active_settings.openai_api_key,
            "openai_research_enabled": row.openai_research_enabled,
            "openai_research_model": row.openai_research_model,
            "openai_base_url": row.openai_base_url,
            "openai_timeout_seconds": row.openai_timeout_seconds,
        }
    )


def _payload_from_values(
    *,
    source: Literal["defaults", "database"],
    data_mode: str,
    sec_user_agent: str,
    lean_backtest_timeout_seconds: float,
    openai_api_key: str | None,
    openai_research_enabled: bool,
    openai_research_model: str,
    openai_base_url: str,
    openai_timeout_seconds: float,
    settings: Settings,
) -> RuntimeSettingsPayload:
    api_key_source = _openai_api_key_source(settings, runtime_api_key=openai_api_key)
    return RuntimeSettingsPayload(
        source=source,
        data_mode=data_mode,
        sec_user_agent=sec_user_agent,
        lean_backtest_timeout_seconds=lean_backtest_timeout_seconds,
        paper_scheduler_enabled=settings.paper_scheduler_enabled,
        paper_scheduler_cron=settings.paper_scheduler_cron,
        paper_scheduler_timezone=settings.paper_scheduler_timezone,
        event_bus_mode=settings.event_bus_mode,
        redis_stream_name=settings.redis_stream_name,
        redis_configured=settings.event_bus_mode == "redis" and bool(settings.redis_url and settings.redis_stream_name),
        openai_research_enabled=openai_research_enabled,
        openai_research_model=openai_research_model,
        openai_base_url=openai_base_url,
        openai_timeout_seconds=openai_timeout_seconds,
        openai_api_key_configured=api_key_source is not None,
        openai_api_key_source=api_key_source,
    )


def _openai_api_key_source(settings: Settings, *, runtime_api_key: str | None = None) -> str | None:
    if runtime_api_key:
        return "runtime_database"
    if settings.openai_api_key:
        return "AI_STOCKS_OPENAI_API_KEY"
    if os.getenv("OPENAI_API_KEY"):
        return "OPENAI_API_KEY"
    return None
