import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import AuditLog


DEFAULT_STRATEGY_ID = "deterministic_watchlist_v1"


class StrategyLifecycleAuditItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    action: str
    entity_type: str
    entity_id: str | None
    approved_by: str | None
    reason: str | None
    previous_stage: str | None
    current_stage: str | None
    auto_promotion_enabled: bool | None
    execution_enabled: bool | None = None
    created_at: str


class StrategyLifecycleAuditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    items: list[StrategyLifecycleAuditItem]
    summary: str


def get_strategy_lifecycle_audit(
    session: Session,
    *,
    strategy_id: str = DEFAULT_STRATEGY_ID,
) -> StrategyLifecycleAuditPayload:
    rows = list(
        session.exec(
            select(AuditLog)
            .where(AuditLog.entity_type == "strategy", AuditLog.entity_id == strategy_id)
            .order_by(AuditLog.created_at.desc())
        ).all()
    )
    items = [_item(row) for row in rows if row.action.startswith("strategy_")]
    return StrategyLifecycleAuditPayload(
        strategy_id=strategy_id,
        items=items[:20],
        summary=_summary(len(items)),
    )


def _item(row: AuditLog) -> StrategyLifecycleAuditItem:
    metadata = _metadata(row.metadata_json)
    auto_promotion_enabled = metadata.get("auto_promotion_enabled")
    execution_enabled = metadata.get("execution_enabled")
    return StrategyLifecycleAuditItem(
        id=row.id,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        approved_by=_optional_str(metadata.get("approved_by")),
        reason=_optional_str(metadata.get("reason")),
        previous_stage=_optional_str(metadata.get("previous_stage")),
        current_stage=_optional_str(metadata.get("current_stage")),
        auto_promotion_enabled=auto_promotion_enabled if isinstance(auto_promotion_enabled, bool) else None,
        execution_enabled=execution_enabled if isinstance(execution_enabled, bool) else None,
        created_at=row.created_at.isoformat(),
    )


def _metadata(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _summary(count: int) -> str:
    if count == 0:
        return "No lifecycle audit entries recorded for this strategy."
    return f"{count} lifecycle audit entries recorded for this strategy."
