from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.domain.models import RuntimeConfiguration, utc_now


class RuntimeSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["defaults", "database"]
    openai_research_enabled: bool
    openai_research_model: str
    openai_base_url: str
    openai_timeout_seconds: float
    openai_api_key_configured: bool
    openai_api_key_source: str | None


class RuntimeSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openai_research_enabled: bool
    openai_research_model: str = Field(min_length=1, max_length=80)
    openai_base_url: str = Field(min_length=8, max_length=200)
    openai_timeout_seconds: float = Field(gt=0, le=120)

    @field_validator("openai_research_model", "openai_base_url")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

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
            "openai_research_enabled": row.openai_research_enabled,
            "openai_research_model": row.openai_research_model,
            "openai_base_url": row.openai_base_url,
            "openai_timeout_seconds": row.openai_timeout_seconds,
        }
    )


def _payload_from_values(
    *,
    source: Literal["defaults", "database"],
    openai_research_enabled: bool,
    openai_research_model: str,
    openai_base_url: str,
    openai_timeout_seconds: float,
    settings: Settings,
) -> RuntimeSettingsPayload:
    api_key_source = _openai_api_key_source(settings)
    return RuntimeSettingsPayload(
        source=source,
        openai_research_enabled=openai_research_enabled,
        openai_research_model=openai_research_model,
        openai_base_url=openai_base_url,
        openai_timeout_seconds=openai_timeout_seconds,
        openai_api_key_configured=api_key_source is not None,
        openai_api_key_source=api_key_source,
    )


def _openai_api_key_source(settings: Settings) -> str | None:
    if settings.openai_api_key:
        return "AI_STOCKS_OPENAI_API_KEY"
    if os.getenv("OPENAI_API_KEY"):
        return "OPENAI_API_KEY"
    return None
