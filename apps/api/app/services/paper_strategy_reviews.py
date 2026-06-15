import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog
from app.services.workspace import get_or_create_default_workspace


class PaperStrategyReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    action_code: str
    title: str
    detail: str
    evidence: list[str]
    inverted_tickers: list[str]
    review_status: str
    created_at: datetime


class PaperStrategyReviewsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_count: int
    items: list[PaperStrategyReviewItem]
    summary: str


def get_paper_strategy_reviews(
    session: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 10,
) -> PaperStrategyReviewsPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    events = session.exec(
        select(CoreEventLog)
        .where(CoreEventLog.team_id == team_id)
        .where(CoreEventLog.run_id == None)  # noqa: E711
        .where(CoreEventLog.topic == "strategy_review")
        .order_by(CoreEventLog.published_at.desc(), CoreEventLog.sequence.desc())
        .limit(limit)
    ).all()
    items = [_item for event in events if (_item := _item_from_event(event)) is not None]
    return PaperStrategyReviewsPayload(
        review_count=len(items),
        items=items,
        summary=_summary(items),
    )


def _item_from_event(event: CoreEventLog) -> PaperStrategyReviewItem | None:
    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    return PaperStrategyReviewItem(
        event_id=event.event_id,
        action_code=_text(payload.get("action_code"), "unknown"),
        title=_text(payload.get("title"), "策略复盘"),
        detail=_text(payload.get("detail"), ""),
        evidence=_string_list(payload.get("evidence")),
        inverted_tickers=sorted({ticker.upper() for ticker in _string_list(payload.get("inverted_tickers"))}),
        review_status=_text(payload.get("review_status"), "required"),
        created_at=event.published_at,
    )


def _text(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _summary(items: list[PaperStrategyReviewItem]) -> str:
    if not items:
        return "No strategy reviews are recorded yet."
    latest = items[0]
    tickers = ",".join(latest.inverted_tickers) or "unknown"
    return f"Strategy reviews: {len(items)} recorded; latest {latest.action_code} covers {tickers}."
