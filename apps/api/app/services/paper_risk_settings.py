import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperRiskSetting, PaperTradingMode, utc_now
from app.services.paper_execution_diagnostics import get_paper_execution_diagnostics
from app.services.workspace import get_or_create_default_workspace
from app.trading_core.risk import RiskLimits


DEFAULT_PAPER_MAX_ORDER_NOTIONAL = 2000.0
DEFAULT_PAPER_MAX_POSITION_WEIGHT = 0.1
DEFAULT_PAPER_MAX_DAILY_ORDERS = 5


class PaperRiskLimitApplyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied: bool
    previous_max_daily_orders: int
    applied_max_daily_orders: int
    live_change_allowed: bool
    audit_event_created: bool
    summary: str


def get_paper_risk_limits(
    session: Session | None = None,
    *,
    team_id: UUID | None = None,
    mode: PaperTradingMode = PaperTradingMode.paper,
) -> RiskLimits:
    defaults = RiskLimits(
        max_order_notional=DEFAULT_PAPER_MAX_ORDER_NOTIONAL,
        max_position_weight=DEFAULT_PAPER_MAX_POSITION_WEIGHT,
        max_daily_orders=DEFAULT_PAPER_MAX_DAILY_ORDERS,
    )
    if session is None or team_id is None:
        return defaults
    setting = _active_setting(session, team_id=team_id, mode=mode)
    if setting is None:
        return defaults
    return RiskLimits(
        max_order_notional=setting.max_order_notional,
        max_position_weight=setting.max_position_weight,
        max_daily_orders=setting.max_daily_orders,
    )


def get_active_paper_risk_setting(
    session: Session,
    *,
    team_id: UUID,
    mode: PaperTradingMode = PaperTradingMode.paper,
) -> PaperRiskSetting | None:
    return _active_setting(session, team_id=team_id, mode=mode)


def apply_paper_risk_limit_recommendation(
    session: Session,
    *,
    team_id: UUID | None = None,
) -> PaperRiskLimitApplyPayload:
    resolved_team_id = team_id or get_or_create_default_workspace(session).team.id
    from app.services.paper_risk_limit_review import build_paper_risk_limit_review
    from app.services.paper_risk_profile import get_paper_risk_profile
    from app.services.alpha_gate_progress import get_alpha_gate_progress

    profile = get_paper_risk_profile(session, team_id=resolved_team_id)
    execution = get_paper_execution_diagnostics(session, team_id=resolved_team_id)
    alpha_gates = get_alpha_gate_progress(session, team_id=resolved_team_id)
    review = build_paper_risk_limit_review(execution=execution, risk_profile=profile, alpha_gates=alpha_gates)
    if review.status != "review_required" or review.recommended_paper_max_daily_orders <= profile.max_daily_orders:
        return PaperRiskLimitApplyPayload(
            applied=False,
            previous_max_daily_orders=profile.max_daily_orders,
            applied_max_daily_orders=profile.max_daily_orders,
            live_change_allowed=review.live_change_allowed,
            audit_event_created=False,
            summary="Paper risk limit apply skipped: no paper-only increase is recommended.",
        )

    setting = _active_setting(session, team_id=resolved_team_id, mode=PaperTradingMode.paper)
    if setting is None:
        setting = PaperRiskSetting(
            team_id=resolved_team_id,
            mode=PaperTradingMode.paper,
            max_order_notional=profile.max_order_notional,
            max_position_weight=profile.max_position_weight,
            max_daily_orders=review.recommended_paper_max_daily_orders,
            source="risk_limit_review",
        )
    else:
        setting.max_daily_orders = review.recommended_paper_max_daily_orders
        setting.source = "risk_limit_review"
        setting.updated_at = utc_now()
    session.add(setting)
    _persist_risk_config_audit_event(
        session,
        team_id=resolved_team_id,
        previous_max_daily_orders=profile.max_daily_orders,
        applied_max_daily_orders=review.recommended_paper_max_daily_orders,
        buy_rejections=review.max_daily_order_buy_rejections,
        sell_rejections=review.max_daily_order_sell_rejections,
    )
    session.commit()
    return PaperRiskLimitApplyPayload(
        applied=True,
        previous_max_daily_orders=profile.max_daily_orders,
        applied_max_daily_orders=review.recommended_paper_max_daily_orders,
        live_change_allowed=False,
        audit_event_created=True,
        summary=(
            "Paper risk limit recommendation applied: max_daily_orders "
            f"{profile.max_daily_orders} -> {review.recommended_paper_max_daily_orders}; live limits unchanged."
        ),
    )


def _active_setting(session: Session, *, team_id: UUID, mode: PaperTradingMode) -> PaperRiskSetting | None:
    return session.exec(
        select(PaperRiskSetting)
        .where(PaperRiskSetting.team_id == team_id)
        .where(PaperRiskSetting.mode == mode)
        .order_by(PaperRiskSetting.updated_at.desc())
    ).first()


def _persist_risk_config_audit_event(
    session: Session,
    *,
    team_id: UUID,
    previous_max_daily_orders: int,
    applied_max_daily_orders: int,
    buy_rejections: int,
    sell_rejections: int,
) -> None:
    sequence = _next_team_event_sequence(session, team_id)
    payload = {
        "event_type": "paper_risk_limit_recommendation_applied",
        "previous_max_daily_orders": previous_max_daily_orders,
        "applied_max_daily_orders": applied_max_daily_orders,
        "buy_rejections": buy_rejections,
        "sell_rejections": sell_rejections,
        "live_change_allowed": False,
    }
    event_id = f"{team_id}:{sequence}:risk_config_audit"
    session.add(
        CoreEventLog(
            team_id=team_id,
            run_id=None,
            event_id=event_id,
            topic="risk_config_audit",
            sequence=sequence,
            correlation_id=event_id,
            causation_id=None,
            payload_json=json.dumps(payload),
            published_at=utc_now(),
        )
    )


def _next_team_event_sequence(session: Session, team_id: UUID) -> int:
    return len(session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id)).all()) + 1
