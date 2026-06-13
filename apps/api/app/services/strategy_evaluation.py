from enum import Enum

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperCandidate, PaperOrder, PaperOrderSide, PaperOrderStatus, PaperPosition, PaperReview
from app.services.workspace import get_or_create_default_workspace


DEFAULT_STRATEGY_ID = "deterministic_watchlist_v1"
DEFAULT_STRATEGY_NAME = "Deterministic Watchlist Strategy"


class StrategyEvaluationReadiness(str, Enum):
    insufficient_sample = "insufficient_sample"
    negative_expectancy = "negative_expectancy"
    watch = "watch"
    paper_ready = "paper_ready"


class StrategyEvaluationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    strategy_name: str
    sample_size: int
    filled_order_count: int
    rejected_order_count: int
    closed_trade_count: int
    signal_precision: float
    expectancy: float
    max_drawdown: float
    stability_score: float
    readiness: StrategyEvaluationReadiness
    promotion_gate: str
    event_chain_count: int
    notes: str


def evaluate_current_paper_strategy(session: Session) -> StrategyEvaluationPayload:
    workspace = get_or_create_default_workspace(session)
    team_id = workspace.team.id
    candidates = list(session.exec(select(PaperCandidate).where(PaperCandidate.team_id == team_id)).all())
    orders = list(session.exec(select(PaperOrder).where(PaperOrder.team_id == team_id)).all())
    positions = list(session.exec(select(PaperPosition).where(PaperPosition.team_id == team_id)).all())
    reviews = list(
        session.exec(select(PaperReview).where(PaperReview.team_id == team_id).order_by(PaperReview.created_at)).all()
    )
    event_chain_count = len(session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id)).all())

    filled_orders = [order for order in orders if order.status == PaperOrderStatus.filled]
    rejected_orders = [order for order in orders if order.status == PaperOrderStatus.rejected]
    closed_orders = [
        order
        for order in filled_orders
        if order.side == PaperOrderSide.sell
    ]
    signal_precision = _signal_precision(filled_orders, positions)
    expectancy = round(reviews[-1].expectancy, 2) if reviews else 0.0
    max_drawdown = _max_drawdown(reviews)
    readiness = _readiness(len(filled_orders), expectancy, max_drawdown)
    stability_score = _stability_score(
        filled_order_count=len(filled_orders),
        signal_precision=signal_precision,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
    )
    return StrategyEvaluationPayload(
        strategy_id=DEFAULT_STRATEGY_ID,
        strategy_name=DEFAULT_STRATEGY_NAME,
        sample_size=len(candidates),
        filled_order_count=len(filled_orders),
        rejected_order_count=len(rejected_orders),
        closed_trade_count=len(closed_orders),
        signal_precision=signal_precision,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
        stability_score=stability_score,
        readiness=readiness,
        promotion_gate=_promotion_gate(readiness),
        event_chain_count=event_chain_count,
        notes=_notes(readiness, len(filled_orders), expectancy, max_drawdown),
    )


def _signal_precision(orders: list[PaperOrder], positions: list[PaperPosition]) -> float:
    if not orders:
        return 0.0
    positions_by_ticker = {position.ticker: position for position in positions}
    positive = 0
    for order in orders:
        if order.side == PaperOrderSide.sell:
            if order.realized_pnl >= 0:
                positive += 1
            continue
        position = positions_by_ticker.get(order.ticker)
        if position is not None and position.unrealized_pnl >= 0:
            positive += 1
    return round(positive / len(orders), 4)


def _max_drawdown(reviews: list[PaperReview]) -> float:
    peak = 0.0
    worst = 0.0
    for review in reviews:
        peak = max(peak, review.equity)
        if peak <= 0:
            continue
        worst = max(worst, (peak - review.equity) / peak)
    return round(worst, 4)


def _readiness(filled_order_count: int, expectancy: float, max_drawdown: float) -> StrategyEvaluationReadiness:
    if filled_order_count < 20:
        return StrategyEvaluationReadiness.insufficient_sample
    if expectancy <= 0:
        return StrategyEvaluationReadiness.negative_expectancy
    if filled_order_count < 30 or max_drawdown > 0.15:
        return StrategyEvaluationReadiness.watch
    return StrategyEvaluationReadiness.paper_ready


def _promotion_gate(readiness: StrategyEvaluationReadiness) -> str:
    if readiness == StrategyEvaluationReadiness.paper_ready:
        return "eligible_for_shadow"
    if readiness == StrategyEvaluationReadiness.watch:
        return "keep_paper_running"
    return "blocked"


def _stability_score(
    filled_order_count: int,
    signal_precision: float,
    expectancy: float,
    max_drawdown: float,
) -> float:
    sample_score = min(filled_order_count / 30, 1.0)
    expectancy_score = 1.0 if expectancy > 0 else 0.0
    drawdown_score = max(0.0, 1 - (max_drawdown / 0.2))
    return round(
        min(
            1.0,
            sample_score * 0.35
            + signal_precision * 0.25
            + expectancy_score * 0.25
            + drawdown_score * 0.15,
        ),
        4,
    )


def _notes(
    readiness: StrategyEvaluationReadiness,
    filled_order_count: int,
    expectancy: float,
    max_drawdown: float,
) -> str:
    if readiness == StrategyEvaluationReadiness.paper_ready:
        return "样本数、正期望和回撤约束达标，可进入 shadow 阶段前的人工复核。"
    if readiness == StrategyEvaluationReadiness.watch:
        return "策略已有正期望迹象，但样本数或回撤约束仍需继续观察。"
    if readiness == StrategyEvaluationReadiness.negative_expectancy:
        return "样本数已进入评估区间，但净期望不达标，禁止晋级。"
    return f"样本不足：已成交 {filled_order_count} 笔，当前期望值 {expectancy:.2f}，最大回撤 {max_drawdown:.2%}。"
