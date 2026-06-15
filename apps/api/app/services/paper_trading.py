import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.core.config import get_settings
from app.data.providers.base import MarketDataProvider
from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperCandidate,
    PaperCandidateStatus,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPosition,
    PaperReadiness,
    PaperReview,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
    PaperTradingMode,
    Position,
    WatchlistItem,
    utc_now,
)
from app.services.market_calendar import current_market_trading_day
from app.services.paper_risk_settings import get_paper_risk_limits
from app.services.alpha_validation_snapshot import record_registered_alpha_validation_snapshots
from app.services.strategy_competition import record_strategy_competition_snapshot
from app.services.workspace import get_or_create_default_workspace
from app.services.strategy_control import (
    DEFAULT_PAPER_STRATEGY_ID,
    assert_strategy_execution_allowed,
    get_strategy_execution_binding,
)
from app.services.strategy_registry import MOVING_AVERAGE_CROSS_STRATEGY_ID, REGISTERED_PAPER_RUNTIME_STRATEGY_IDS
from app.services.strategy_candidate_backtest import (
    StrategyCandidateBacktestItem,
    run_strategy_candidate_backtests,
)
from app.trading_core.event_bus import EventEnvelope, InMemoryEventBus, TradingEventTopic, build_event_bus
from app.trading_core.events import (
    EventSource,
    MarketEvent,
    MarketEventType,
    Sentiment,
    StrategyInputEvent,
    TradeExplanationEvent,
)
from app.trading_core.execution import CoreOrder, ExecutionEngine, OrderState, order_state_event
from app.trading_core.portfolio import PortfolioPosition, PortfolioState
from app.trading_core.risk import RiskEngine, RiskLimits
from app.trading_core.strategy import TradeIntent, TradeIntentSide


DEFAULT_ACCOUNT_NAME = "默认模拟盘"
DEFAULT_STARTING_CASH = 100000.0
DEFAULT_CANDIDATE_NOTIONAL = 2000.0
DEFAULT_EXIT_TAKE_PROFIT_PCT = 0.10
DEFAULT_EXIT_STOP_LOSS_PCT = -0.05
MANUAL_OVERRIDE_STRATEGY_SUFFIX = ":manual_override"
RUNNING_LOCK_STALE_AFTER_MINUTES = 180
PAPER_RUNTIME_STRATEGY_IDS = REGISTERED_PAPER_RUNTIME_STRATEGY_IDS
MOVING_AVERAGE_FAST_PERIOD = 20
MOVING_AVERAGE_SLOW_PERIOD = 50


@dataclass(frozen=True)
class CoreEventContext:
    correlation_id: UUID
    trade_intent_event_id: UUID
    trade_intent_sequence: int
    intent: TradeIntent
    strategy_id: str


class PaperAccountPayload(BaseModel):
    id: UUID
    name: str
    mode: str
    starting_cash: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    updated_at: datetime


class PaperCandidatePayload(BaseModel):
    id: UUID
    strategy_id: str = DEFAULT_PAPER_STRATEGY_ID
    ticker: str
    action: str
    rank: int
    confidence: float
    thesis: str
    risk_notes: str
    evidence_summary: str
    proposed_quantity: float
    status: str
    created_at: datetime


class PaperOrderCreate(BaseModel):
    ticker: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    order_type: Literal["market"] = "market"
    strategy_id: str = Field(default=DEFAULT_PAPER_STRATEGY_ID, min_length=1)
    candidate_id: UUID | None = None
    reason: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized

    @field_validator("strategy_id")
    @classmethod
    def normalize_strategy_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("strategy_id must not be empty")
        return normalized


class PaperOrderPayload(BaseModel):
    id: UUID
    strategy_id: str = DEFAULT_PAPER_STRATEGY_ID
    candidate_id: UUID | None = None
    ticker: str
    side: str
    order_type: str
    quantity: float
    status: str
    fill_price: float | None
    realized_pnl: float
    rejection_reason: str | None
    core_order_id: str | None = None
    core_intent_id: str | None = None
    risk_status: str | None = None
    risk_code: str | None = None
    risk_reason: str | None = None
    state_history: list[dict[str, str]] = Field(default_factory=list)
    submitted_at: datetime
    filled_at: datetime | None


class PaperPositionPayload(BaseModel):
    id: UUID
    ticker: str
    quantity: float
    average_cost: float
    last_price: float | None
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    updated_at: datetime


class PaperReviewPayload(BaseModel):
    id: UUID
    trading_day: str
    equity: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int
    win_rate: float
    average_win: float
    average_loss: float
    expectancy: float
    readiness: str
    notes: str
    created_at: datetime


class PaperRunPayload(BaseModel):
    id: UUID
    trading_day: str
    trigger: str
    status: str
    candidates_count: int
    orders_count: int
    positions_count: int
    review_id: UUID | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class CoreEventLogPayload(BaseModel):
    id: UUID
    run_id: UUID | None
    event_id: str
    topic: str
    sequence: int
    correlation_id: str
    causation_id: str | None
    payload_json: str
    published_at: datetime


class PaperTradingSummary(BaseModel):
    account: PaperAccountPayload
    candidates: list[PaperCandidatePayload]
    orders: list[PaperOrderPayload]
    positions: list[PaperPositionPayload]
    latest_review: PaperReviewPayload | None


def get_paper_trading_summary(
    session: Session,
    provider: MarketDataProvider,
    *,
    as_of_trading_day: str | None = None,
    use_live_quotes: bool = True,
) -> PaperTradingSummary:
    workspace = get_or_create_default_workspace(session)
    account = _get_or_create_account(session, workspace.team.id)
    if use_live_quotes:
        _mark_positions_to_market(session, account, provider)
        session.commit()
        session.refresh(account)
    return _summary_payload(
        session,
        account,
        provider,
        as_of_trading_day=as_of_trading_day,
        use_live_quotes=use_live_quotes,
    )


def run_daily_paper_trading_loop(
    session: Session,
    provider: MarketDataProvider,
    trigger: PaperRunTrigger = PaperRunTrigger.manual,
    trading_day: str | None = None,
    account_mode: PaperTradingMode = PaperTradingMode.paper,
    force_new_sample: bool = False,
) -> PaperTradingSummary:
    workspace = get_or_create_default_workspace(session)
    account = _get_or_create_account(session, workspace.team.id, mode=account_mode)
    resolved_trading_day = trading_day or _current_trading_day()
    _expire_stale_running_runs(session, account, resolved_trading_day)
    running_run = _running_run_for_trading_day(session, account, resolved_trading_day)
    if running_run is not None:
        raise ValueError(f"Paper trading run is already running for {resolved_trading_day}.")
    existing_review = _review_for_trading_day(session, account, resolved_trading_day)
    if (
        not force_new_sample
        and existing_review is not None
        and _has_completed_core_run_for_trading_day(
            session, account, resolved_trading_day
        )
    ):
        _mark_positions_to_market(session, account, provider)
        session.commit()
        session.refresh(account)
        return _summary_payload(session, account, provider, as_of_trading_day=resolved_trading_day)
    run = _start_paper_run(session, account, resolved_trading_day, trigger)
    try:
        _mark_positions_to_market(session, account, provider)
        _auto_submit_exit_orders(session, provider, account, run.id, trading_day=resolved_trading_day)
        session.refresh(account)
        core_contexts = _generate_candidates(
            session,
            workspace.team.id,
            workspace.portfolio.id,
            account,
            provider,
            run.id,
            trading_day=resolved_trading_day,
        )
        session.flush()
        _auto_submit_candidate_orders(
            session,
            provider,
            account,
            run.id,
            core_contexts,
            trading_day=resolved_trading_day,
        )
        session.refresh(account)
        _mark_positions_to_market(session, account, provider)
        review = _create_review(session, account, resolved_trading_day)
        session.add(review)
        session.flush()
        _finish_paper_run(session, account, run, PaperRunStatus.completed, review)
        record_registered_alpha_validation_snapshots(
            session,
            team_id=workspace.team.id,
            trading_day=resolved_trading_day,
        )
        record_strategy_competition_snapshot(
            session,
            provider=provider,
            team_id=workspace.team.id,
            trading_day=resolved_trading_day,
        )
        account.updated_at = utc_now()
        session.commit()
        session.refresh(account)
        return _summary_payload(session, account, provider, as_of_trading_day=resolved_trading_day)
    except Exception as error:
        _mark_paper_run_failed(session, run.id, error)
        raise


def list_paper_runs(session: Session, limit: int = 20) -> list[PaperRunPayload]:
    workspace = get_or_create_default_workspace(session)
    runs = list(
        session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == workspace.team.id)
            .order_by(PaperRun.started_at.desc())
            .limit(limit)
        ).all()
    )
    return [_run_payload(run) for run in runs]


def list_paper_run_events(session: Session, run_id: UUID) -> list[CoreEventLogPayload]:
    events = list(
        session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.run_id == run_id)
            .order_by(CoreEventLog.sequence)
        ).all()
    )
    return [_core_event_payload(event) for event in events]


def submit_paper_order(
    session: Session,
    provider: MarketDataProvider,
    data: PaperOrderCreate,
    run_id: UUID | None = None,
    core_context: CoreEventContext | None = None,
    trading_day: str | None = None,
    account_mode: PaperTradingMode = PaperTradingMode.paper,
) -> PaperOrderPayload:
    workspace = get_or_create_default_workspace(session)
    account = _get_or_create_account(session, workspace.team.id, mode=account_mode)
    assert_strategy_execution_allowed(session, data.strategy_id, requested_mode="paper")
    binding = get_strategy_execution_binding(
        session,
        workspace.team.id,
        data.strategy_id,
        notional=min(DEFAULT_CANDIDATE_NOTIONAL, max(account.cash * 0.02, 0)),
    )
    price = _quote_price(provider, data.ticker)
    side = PaperOrderSide(data.side)
    cost = round(price * data.quantity, 2)
    _mark_positions_to_market(session, account, provider)
    intent = core_context.intent if core_context is not None else _manual_trade_intent(data, cost, binding.strategy_id)
    order_strategy_id = _paper_order_strategy_id(binding.strategy_id, run_id=run_id, core_context=core_context)
    if core_context is None:
        core_context = _persist_manual_strategy_events(
            session=session,
            team_id=workspace.team.id,
            account=account,
            data=data,
            intent=intent,
            run_id=run_id,
            order_strategy_id=order_strategy_id,
            trading_day=trading_day,
        )
    core_order = _submit_core_order(session, account, intent, core_context, trading_day=trading_day)
    submitted_at = _order_timestamp(trading_day)
    if core_order.current_state == OrderState.rejected:
        order = _new_paper_order(
            account=account,
            team_id=workspace.team.id,
            data=data,
            side=side,
            core_order=core_order,
            status=PaperOrderStatus.rejected,
            rejection_reason=core_order.risk_decision.reason if core_order.risk_decision is not None else "Trading Core rejected order.",
            submitted_at=submitted_at,
            strategy_id=order_strategy_id,
        )
        session.add(order)
        _persist_core_order_events(session, workspace.team.id, core_order, run_id, core_context)
        account.updated_at = utc_now()
        session.commit()
        session.refresh(order)
        return _order_payload(order)

    realized_pnl = 0.0
    filled_at = submitted_at

    if side == PaperOrderSide.buy:
        position = _find_position(session, account, data.ticker)
        if position is None:
            position = PaperPosition(
                account_id=account.id,
                team_id=workspace.team.id,
                ticker=data.ticker,
                quantity=data.quantity,
                average_cost=price,
            )
            session.add(position)
        else:
            total_cost = position.average_cost * position.quantity + cost
            position.quantity += data.quantity
            position.average_cost = round(total_cost / position.quantity, 6)
        account.cash = round(account.cash - cost, 2)
    else:
        position = _find_position(session, account, data.ticker)
        if position is None or position.quantity < data.quantity:
            raise ValueError(f"Insufficient paper quantity for {data.ticker}.")
        proceeds = round(price * data.quantity, 2)
        realized_pnl = round((price - position.average_cost) * data.quantity, 2)
        position.quantity = round(position.quantity - data.quantity, 8)
        position.realized_pnl = round(position.realized_pnl + realized_pnl, 2)
        account.cash = round(account.cash + proceeds, 2)
        account.realized_pnl = round(account.realized_pnl + realized_pnl, 2)

    _update_position_mark(position, price)
    account.updated_at = utc_now()
    order = PaperOrder(
        account_id=account.id,
        team_id=workspace.team.id,
        strategy_id=order_strategy_id,
        candidate_id=data.candidate_id,
        ticker=data.ticker,
        side=side,
        order_type=data.order_type,
        quantity=data.quantity,
        fill_price=price,
        status=PaperOrderStatus.filled,
        realized_pnl=realized_pnl,
        core_order_id=str(core_order.order_id),
        core_intent_id=str(core_order.intent.intent_id),
        risk_status=core_order.risk_decision.status.value if core_order.risk_decision is not None else None,
        risk_code=core_order.risk_decision.code if core_order.risk_decision is not None else None,
        risk_reason=core_order.risk_decision.reason if core_order.risk_decision is not None else None,
        state_history_json=_state_history_json(core_order),
        submitted_at=submitted_at,
        filled_at=filled_at,
    )
    session.add(order)
    _persist_core_order_events(session, workspace.team.id, core_order, run_id, core_context)
    session.commit()
    session.refresh(order)
    return _order_payload(order)


def _get_or_create_account(
    session: Session,
    team_id: UUID,
    *,
    mode: PaperTradingMode = PaperTradingMode.paper,
) -> PaperAccount:
    account = session.exec(
        select(PaperAccount).where(
            PaperAccount.team_id == team_id,
            PaperAccount.strategy_id == DEFAULT_PAPER_STRATEGY_ID,
            PaperAccount.mode == mode,
        )
    ).first()
    if account is not None:
        return account

    account = PaperAccount(
        team_id=team_id,
        strategy_id=DEFAULT_PAPER_STRATEGY_ID,
        name=DEFAULT_ACCOUNT_NAME if mode == PaperTradingMode.paper else f"{DEFAULT_ACCOUNT_NAME} Simulation",
        mode=mode,
        starting_cash=DEFAULT_STARTING_CASH,
        cash=DEFAULT_STARTING_CASH,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _start_paper_run(
    session: Session,
    account: PaperAccount,
    trading_day: str,
    trigger: PaperRunTrigger,
) -> PaperRun:
    run = PaperRun(
        account_id=account.id,
        team_id=account.team_id,
        trading_day=trading_day,
        trigger=trigger,
        status=PaperRunStatus.started,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _running_run_for_trading_day(
    session: Session,
    account: PaperAccount,
    trading_day: str,
) -> PaperRun | None:
    return session.exec(
        select(PaperRun).where(
            PaperRun.account_id == account.id,
            PaperRun.team_id == account.team_id,
            PaperRun.trading_day == trading_day,
            PaperRun.status == PaperRunStatus.started,
        )
    ).first()


def _has_completed_core_run_for_trading_day(
    session: Session,
    account: PaperAccount,
    trading_day: str,
) -> bool:
    if account.mode == PaperTradingMode.paper:
        candidates = session.exec(select(PaperCandidate).where(PaperCandidate.team_id == account.team_id)).all()
        if not candidates or not any(
            _is_on_or_before_trading_day(candidate.created_at, trading_day) for candidate in candidates
        ):
            return False

    runs = session.exec(
        select(PaperRun).where(
            PaperRun.account_id == account.id,
            PaperRun.team_id == account.team_id,
            PaperRun.trading_day == trading_day,
            PaperRun.status == PaperRunStatus.completed,
        )
    ).all()
    for run in runs:
        core_event = session.exec(
            select(CoreEventLog).where(
                CoreEventLog.run_id == run.id,
                CoreEventLog.topic.in_(["market_event", "trade_intent", "order_state"]),
            )
        ).first()
        if core_event is not None:
            return True
    return False


def _expire_stale_running_runs(
    session: Session,
    account: PaperAccount,
    trading_day: str,
) -> None:
    stale_cutoff = utc_now() - timedelta(minutes=RUNNING_LOCK_STALE_AFTER_MINUTES)
    runs = session.exec(
        select(PaperRun).where(
            PaperRun.account_id == account.id,
            PaperRun.team_id == account.team_id,
            PaperRun.trading_day == trading_day,
            PaperRun.status == PaperRunStatus.started,
        )
    ).all()
    expired = False
    for run in runs:
        started_at = run.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if started_at > stale_cutoff:
            continue
        run.status = PaperRunStatus.failed
        run.error_message = (
            f"Paper trading stale running lock expired after {RUNNING_LOCK_STALE_AFTER_MINUTES} minutes."
        )
        run.finished_at = utc_now()
        session.add(run)
        expired = True
    if expired:
        session.commit()


def _finish_paper_run(
    session: Session,
    account: PaperAccount,
    run: PaperRun,
    status: PaperRunStatus,
    review: PaperReview | None,
) -> None:
    run.status = status
    run.review_id = review.id if review is not None else None
    run.candidates_count = _candidate_count(session, account.team_id)
    run.orders_count = _order_count(session, account)
    run.positions_count = len(_positions(session, account))
    run.finished_at = utc_now()
    session.add(run)


def _mark_paper_run_failed(session: Session, run_id: UUID, error: Exception) -> None:
    session.rollback()
    run = session.get(PaperRun, run_id)
    if run is None:
        return
    run.status = PaperRunStatus.failed
    run.error_message = str(error)
    run.finished_at = utc_now()
    session.add(run)
    session.commit()


def _persist_run_audit_event(
    *,
    session: Session,
    team_id: UUID,
    run: PaperRun,
    status: str,
    reason: str,
) -> None:
    sequence = _next_core_event_sequence(session, run.id)
    payload = {
        "run_id": str(run.id),
        "trading_day": run.trading_day,
        "trigger": run.trigger.value,
        "status": status,
        "reason": reason,
    }
    session.add(
        CoreEventLog(
            team_id=team_id,
            run_id=run.id,
            event_id=f"{run.id}:{sequence}:run_audit",
            topic="run_audit",
            sequence=sequence,
            correlation_id=str(run.id),
            causation_id=None,
            payload_json=json.dumps(payload),
            published_at=utc_now(),
        )
    )


def _candidate_count(session: Session, team_id: UUID) -> int:
    return len(session.exec(select(PaperCandidate).where(PaperCandidate.team_id == team_id)).all())


def _order_count(session: Session, account: PaperAccount) -> int:
    return len(session.exec(select(PaperOrder).where(PaperOrder.account_id == account.id)).all())


def _score_pnl_review_blocked_tickers(session: Session, team_id: UUID) -> set[str]:
    events = session.exec(
        select(CoreEventLog)
        .where(CoreEventLog.team_id == team_id)
        .where(CoreEventLog.run_id == None)  # noqa: E711
        .where(CoreEventLog.topic == "strategy_review")
        .order_by(CoreEventLog.published_at, CoreEventLog.sequence)
    ).all()
    review_status_by_ticker: dict[str, str] = {}
    for event in events:
        try:
            payload = json.loads(event.payload_json)
        except json.JSONDecodeError:
            continue
        if payload.get("action_code") != "review_score_pnl_inversion":
            continue
        status = str(payload.get("review_status") or "required").strip().lower()
        for ticker in payload.get("inverted_tickers", []):
            normalized = str(ticker).strip().upper()
            if normalized:
                review_status_by_ticker[normalized] = status
    return {
        ticker
        for ticker, status in review_status_by_ticker.items()
        if status in {"required", "review_required", "pending"}
    }


def _generate_candidates(
    session: Session,
    team_id: UUID,
    portfolio_id: UUID,
    account: PaperAccount,
    provider: MarketDataProvider,
    run_id: UUID,
    trading_day: str | None = None,
) -> dict[UUID, CoreEventContext]:
    for candidate in session.exec(
        select(PaperCandidate).where(
            PaperCandidate.team_id == team_id,
        )
    ).all():
        session.delete(candidate)

    portfolio_tickers = {
        position.ticker
        for position in session.exec(select(Position).where(Position.portfolio_id == portfolio_id)).all()
    }
    watchlist_tickers = {
        item.ticker
        for item in session.exec(select(WatchlistItem).where(WatchlistItem.team_id == team_id)).all()
    }
    blocked_tickers = _score_pnl_review_blocked_tickers(session, team_id)
    all_tickers = sorted((portfolio_tickers | watchlist_tickers) - blocked_tickers)
    bindings = []
    for strategy_id in PAPER_RUNTIME_STRATEGY_IDS:
        assert_strategy_execution_allowed(session, strategy_id, requested_mode="paper")
        bindings.append(
            get_strategy_execution_binding(
                session,
                team_id,
                strategy_id,
                notional=min(DEFAULT_CANDIDATE_NOTIONAL, max(account.cash * 0.02, 0)),
            )
        )
    portfolio_state = _paper_portfolio_state(session, account, trading_day=trading_day)
    event_bus = _build_trading_event_bus()
    ranked: list[tuple[float, str, PaperCandidate, CoreEventContext]] = []
    candidate_created_at = _order_timestamp(trading_day)
    backtest_items = _daily_candidate_backtest_items(provider, all_tickers, trading_day=trading_day)

    for ticker in all_tickers:
        quote = provider.get_quote(ticker)
        if quote.price is None or quote.price <= 0:
            continue
        evidence = provider.get_research_evidence(ticker)
        evidence_count = len(evidence)
        diversification_bonus = 0.15 if ticker not in portfolio_tickers else 0.0
        base_score = _candidate_score(evidence_count, diversification_bonus)
        for binding in bindings:
            event = _market_event_for_strategy(
                strategy_id=binding.strategy_id,
                ticker=ticker,
                quote_price=float(quote.price),
                evidence_count=evidence_count,
                diversification_bonus=diversification_bonus,
                provider=provider,
            )
            if event is None:
                continue
            market_envelope = event_bus.publish(TradingEventTopic.market_event, event)
            strategy_input_envelope = event_bus.publish(
                TradingEventTopic.strategy_input,
                StrategyInputEvent(market_event=event, portfolio=portfolio_state),
                causation_id=market_envelope.event_id,
                correlation_id=market_envelope.correlation_id,
            )
            strategy_result = binding.strategy_engine.generate_intents(event, portfolio_state)
            intents = strategy_result.intents
            if not intents:
                continue
            intent = intents[0]
            trade_intent_envelope = event_bus.publish(
                TradingEventTopic.trade_intent,
                intent,
                causation_id=strategy_input_envelope.event_id,
                correlation_id=strategy_input_envelope.correlation_id,
            )
            proposed_quantity = max(1, int(intent.notional // quote.price))
            evidence_summary = _evidence_summary(ticker, evidence_count)
            candidate = PaperCandidate(
                team_id=team_id,
                strategy_id=binding.strategy_id,
                ticker=ticker,
                action=PaperOrderSide.buy,
                rank=0,
                confidence=event.confidence,
                thesis=f"{intent.reason} {evidence_summary}，按小额名义本金先进入模拟观察。",
                risk_notes="风险：行情波动、估值压缩、证据过期；模拟结果不能直接代表实盘。",
                evidence_summary=evidence_summary,
                proposed_quantity=float(proposed_quantity),
                created_at=candidate_created_at,
            )
            score = base_score
            backtest_item = backtest_items.get(ticker)
            if backtest_item is not None:
                _apply_backtest_evidence(candidate, backtest_item)
                score = _candidate_score_with_backtest(score, backtest_item)
            event_bus.publish(
                TradingEventTopic.trade_explanation,
                _trade_explanation_event(
                    candidate,
                    backtest_item,
                    strategy_id=binding.strategy_id,
                    evidence_count=evidence_count,
                    quote_source=quote.source,
                    diversification_bonus=diversification_bonus,
                    base_score=base_score,
                    final_score=score,
                ),
                causation_id=trade_intent_envelope.event_id,
                correlation_id=trade_intent_envelope.correlation_id,
            )
            ranked.append(
                (
                    score,
                    ticker,
                    candidate,
                    CoreEventContext(
                        correlation_id=trade_intent_envelope.correlation_id,
                        trade_intent_event_id=trade_intent_envelope.event_id,
                        trade_intent_sequence=trade_intent_envelope.sequence,
                        intent=intent,
                        strategy_id=binding.strategy_id,
                    ),
                )
            )

    contexts: dict[UUID, CoreEventContext] = {}
    for index, (_score, _ticker, candidate, context) in enumerate(
        sorted(ranked, key=lambda item: (-item[0], item[1])),
        start=1,
    ):
        candidate.rank = index
        session.add(candidate)
        contexts[candidate.id] = context
    _persist_core_event_envelopes(session, team_id, event_bus.history, run_id=run_id)
    return contexts


def _auto_submit_candidate_orders(
    session: Session,
    provider: MarketDataProvider,
    account: PaperAccount,
    run_id: UUID | None = None,
    core_contexts: dict[UUID, CoreEventContext] | None = None,
    trading_day: str | None = None,
) -> None:
    candidates = list(
        session.exec(
            select(PaperCandidate)
            .where(
                PaperCandidate.team_id == account.team_id,
                PaperCandidate.status == PaperCandidateStatus.proposed,
            )
            .order_by(PaperCandidate.rank)
        ).all()
    )
    risk_limits = _paper_risk_limits(session, team_id=account.team_id, mode=account.mode)
    remaining_order_capacity = max(0, risk_limits.max_daily_orders - _orders_today(session, account, trading_day=trading_day))
    for candidate in candidates[:remaining_order_capacity]:
        if candidate.action != PaperOrderSide.buy or candidate.proposed_quantity <= 0:
            continue
        context = (core_contexts or {}).get(candidate.id)
        order = submit_paper_order(
            session,
            provider,
            PaperOrderCreate(
                ticker=candidate.ticker,
                side=candidate.action.value,
                quantity=candidate.proposed_quantity,
                strategy_id=context.strategy_id if context is not None else candidate.strategy_id,
                candidate_id=candidate.id,
            ),
            run_id=run_id,
            core_context=context,
            trading_day=trading_day,
            account_mode=account.mode,
        )
        if order.status == PaperOrderStatus.filled.value:
            candidate.status = PaperCandidateStatus.ordered
            session.add(candidate)


def _auto_submit_exit_orders(
    session: Session,
    provider: MarketDataProvider,
    account: PaperAccount,
    run_id: UUID,
    trading_day: str | None = None,
) -> None:
    for position in list(_positions(session, account)):
        if position.average_cost <= 0 or position.last_price is None or position.last_price <= 0:
            continue
        return_pct = (position.last_price - position.average_cost) / position.average_cost
        if DEFAULT_EXIT_STOP_LOSS_PCT < return_pct < DEFAULT_EXIT_TAKE_PROFIT_PCT:
            continue
        quantity = _exit_order_quantity(position)
        if quantity <= 0:
            continue
        exit_type = "take_profit" if return_pct >= DEFAULT_EXIT_TAKE_PROFIT_PCT else "stop_loss"
        submit_paper_order(
            session,
            provider,
            PaperOrderCreate(
                ticker=position.ticker,
                side="sell",
                quantity=quantity,
                strategy_id=DEFAULT_PAPER_STRATEGY_ID,
                reason=(
                    f"Paper exit rule {exit_type} triggered for {position.ticker}: "
                    f"return {return_pct:.2%}, last price {position.last_price:.2f}, "
                    f"average cost {position.average_cost:.2f}."
                ),
            ),
            run_id=run_id,
            trading_day=trading_day,
            account_mode=account.mode,
        )


def _exit_order_quantity(position: PaperPosition) -> float:
    if position.last_price is None or position.last_price <= 0:
        return 0.0
    max_quantity = int(DEFAULT_CANDIDATE_NOTIONAL // position.last_price)
    if max_quantity <= 0:
        return 0.0
    return min(position.quantity, float(max_quantity))


def _create_review(session: Session, account: PaperAccount, trading_day: str | None = None) -> PaperReview:
    positions = _positions(session, account)
    unrealized = round(sum(position.unrealized_pnl for position in positions), 2)
    equity = round(account.cash + sum(position.market_value for position in positions), 2)
    closed_orders = list(
        session.exec(
            select(PaperOrder).where(
                PaperOrder.account_id == account.id,
                PaperOrder.strategy_id == DEFAULT_PAPER_STRATEGY_ID,
                PaperOrder.status == PaperOrderStatus.filled,
                PaperOrder.side == PaperOrderSide.sell,
            )
        ).all()
    )
    wins = [order.realized_pnl for order in closed_orders if order.realized_pnl > 0]
    losses = [abs(order.realized_pnl) for order in closed_orders if order.realized_pnl < 0]
    trade_count = len(closed_orders)
    win_rate = round(len(wins) / trade_count, 4) if trade_count else 0.0
    average_win = round(sum(wins) / len(wins), 2) if wins else 0.0
    average_loss = round(sum(losses) / len(losses), 2) if losses else 0.0
    expectancy = round(win_rate * average_win - (1 - win_rate) * average_loss, 2) if trade_count else 0.0
    readiness = _readiness(trade_count, expectancy)
    return PaperReview(
        account_id=account.id,
        team_id=account.team_id,
        trading_day=trading_day or _current_trading_day(),
        equity=equity,
        cash=account.cash,
        realized_pnl=account.realized_pnl,
        unrealized_pnl=unrealized,
        trade_count=trade_count,
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        expectancy=expectancy,
        readiness=readiness,
        notes=_review_notes(readiness, trade_count, expectancy),
    )


def _current_trading_day() -> str:
    return current_market_trading_day()


def _review_for_trading_day(session: Session, account: PaperAccount, trading_day: str) -> PaperReview | None:
    return session.exec(
        select(PaperReview).where(
            PaperReview.account_id == account.id,
            PaperReview.trading_day == trading_day,
        )
    ).first()


def _mark_positions_to_market(session: Session, account: PaperAccount, provider: MarketDataProvider) -> None:
    for position in _positions(session, account):
        price = _quote_price(provider, position.ticker)
        _update_position_mark(position, price)
    account.updated_at = utc_now()


def _update_position_mark(position: PaperPosition, price: float) -> None:
    position.last_price = price
    position.market_value = round(position.quantity * price, 2)
    position.unrealized_pnl = round((price - position.average_cost) * position.quantity, 2)
    position.updated_at = utc_now()


def _quote_price(provider: MarketDataProvider, ticker: str) -> float:
    quote = provider.get_quote(ticker)
    if quote.price is None or quote.price <= 0:
        raise ValueError(f"No usable paper quote for {ticker}.")
    return float(quote.price)


def _find_position(session: Session, account: PaperAccount, ticker: str) -> PaperPosition | None:
    return session.exec(
        select(PaperPosition).where(PaperPosition.account_id == account.id, PaperPosition.ticker == ticker)
    ).first()


def _positions(session: Session, account: PaperAccount) -> list[PaperPosition]:
    return list(
        session.exec(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id, PaperPosition.quantity > 0)
            .order_by(PaperPosition.ticker)
        ).all()
    )


def _paper_portfolio_state(
    session: Session,
    account: PaperAccount,
    trading_day: str | None = None,
) -> PortfolioState:
    positions = _positions(session, account)
    equity = round(account.cash + sum(position.market_value for position in positions), 2)
    return PortfolioState(
        cash=round(account.cash, 2),
        equity=max(equity, 0.01),
        positions=[
            PortfolioPosition(
                ticker=position.ticker,
                quantity=position.quantity,
                market_value=round(position.market_value, 2),
            )
            for position in positions
        ],
        orders_today=_orders_today(session, account, trading_day=trading_day),
    )


def _orders_today(session: Session, account: PaperAccount, trading_day: str | None = None) -> int:
    day = trading_day or utc_now().date().isoformat()
    return len(
        [
            order
            for order in session.exec(select(PaperOrder).where(PaperOrder.account_id == account.id)).all()
            if order.submitted_at.date().isoformat() == day
        ]
    )


def _order_timestamp(trading_day: str | None = None) -> datetime:
    if trading_day is None:
        return utc_now()
    return datetime.fromisoformat(f"{trading_day}T21:00:00+00:00")


def _candidate_score(evidence_count: int, diversification_bonus: float) -> float:
    return evidence_count * 0.2 + diversification_bonus + 0.1


def _daily_candidate_backtest_items(
    provider: MarketDataProvider,
    tickers: list[str],
    *,
    trading_day: str | None,
) -> dict[str, StrategyCandidateBacktestItem]:
    if len(tickers) < 2 or not _provider_has_real_history(provider, tickers, trading_day=trading_day):
        return {}
    try:
        payload = run_strategy_candidate_backtests(
            strategy_id=DEFAULT_PAPER_STRATEGY_ID,
            tickers=tickers,
            parameter_overrides=_daily_candidate_backtest_parameters(trading_day),
            market_data_provider=provider,
        )
    except Exception:
        return {}
    if payload.real_market_candidate_count <= 0:
        return {}
    return {item.ticker: item for item in payload.items}


def _provider_has_real_history(
    provider: MarketDataProvider,
    tickers: list[str],
    *,
    trading_day: str | None,
) -> bool:
    parameters = _daily_candidate_backtest_parameters(trading_day)
    for ticker in tickers[:3]:
        try:
            history = provider.get_price_history(
                ticker,
                start_date=parameters["start_date"],
                end_date=parameters["end_date"],
                interval="1d",
            )
        except Exception:
            continue
        if any(_is_real_market_source(getattr(bar, "source", "")) and bar.close is not None for bar in history):
            return True
    return False


def _daily_candidate_backtest_parameters(trading_day: str | None) -> dict[str, str]:
    end_date = datetime.fromisoformat(trading_day or _current_trading_day()).date()
    start_date = end_date - timedelta(days=365)
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "cash": str(int(DEFAULT_STARTING_CASH)),
    }


def _is_real_market_source(source: str) -> bool:
    normalized = source.strip().lower()
    return normalized.startswith(("openbb_", "alpaca", "polygon")) or normalized == "mixed_real_market_data"


def _candidate_score_with_backtest(base_score: float, item: StrategyCandidateBacktestItem) -> float:
    gate_score = {"candidate": 1000.0, "watch": 100.0, "reject": -1000.0}[item.recommendation]
    return gate_score + max(0.0, 50.0 - float(item.rank)) + item.score + base_score


def _apply_backtest_evidence(candidate: PaperCandidate, item: StrategyCandidateBacktestItem) -> None:
    metrics = _backtest_metric_summary(item)
    candidate.thesis = f"{candidate.thesis} 回测结论：{item.reason}。"
    candidate.evidence_summary = f"{candidate.evidence_summary}；回测 {metrics}"
    candidate.risk_notes = f"{candidate.risk_notes} 回测风控：{item.reason}。"
    if item.recommendation != "candidate":
        candidate.status = PaperCandidateStatus.dismissed


def _trade_explanation_event(
    candidate: PaperCandidate,
    item: StrategyCandidateBacktestItem | None,
    *,
    strategy_id: str,
    evidence_count: int | None = None,
    quote_source: str | None = None,
    diversification_bonus: float | None = None,
    base_score: float | None = None,
    final_score: float | None = None,
) -> TradeExplanationEvent:
    evidence = _trade_explanation_evidence(
        item,
        evidence_count=evidence_count,
        quote_source=quote_source,
        diversification_bonus=diversification_bonus,
        base_score=base_score,
        final_score=final_score,
    )
    return TradeExplanationEvent(
        ticker=candidate.ticker,
        strategy_id=strategy_id,
        decision=item.recommendation if item is not None else _candidate_decision(candidate),
        explanation=candidate.thesis,
        evidence=evidence,
        backtest=_trade_explanation_backtest(item),
    )


def _candidate_decision(candidate: PaperCandidate) -> str:
    return "candidate" if candidate.status == PaperCandidateStatus.proposed else candidate.status.value


def _trade_explanation_evidence(
    item: StrategyCandidateBacktestItem | None,
    *,
    evidence_count: int | None,
    quote_source: str | None,
    diversification_bonus: float | None,
    base_score: float | None,
    final_score: float | None,
) -> list[str]:
    normalized_base_score = base_score or 0.0
    normalized_final_score = final_score if final_score is not None else normalized_base_score
    evidence = [
        f"evidence_count={evidence_count if evidence_count is not None else 0}",
        f"quote_source={quote_source or 'unknown'}",
        f"diversification_bonus={diversification_bonus or 0:.2f}",
        f"base_score={normalized_base_score:.2f}",
        f"backtest_score={normalized_final_score - normalized_base_score:.2f}",
        f"final_score={normalized_final_score:.2f}",
    ]
    if item is not None:
        evidence.extend([item.reason, _backtest_metric_summary(item), f"source={item.data_source or 'unknown'}"])
    return evidence


def _trade_explanation_backtest(item: StrategyCandidateBacktestItem | None) -> dict[str, str | bool | None]:
    if item is None:
        return {}
    return {
        "run_id": item.run_id,
        "status": item.status,
        "engine": item.engine,
        "data_source": item.data_source,
        "uses_real_market_data": item.uses_real_market_data,
        "total_net_profit": item.total_net_profit,
        "sharpe_ratio": item.sharpe_ratio,
        "drawdown": item.drawdown,
        "total_trades": item.total_trades,
    }


def _backtest_metric_summary(item: StrategyCandidateBacktestItem) -> str:
    return (
        f"收益 {item.total_net_profit or 'n/a'}，"
        f"Sharpe {item.sharpe_ratio or 'n/a'}，"
        f"回撤 {item.drawdown or 'n/a'}，"
        f"交易 {item.total_trades or '0'} 笔"
    )


def _market_event_from_evidence(
    ticker: str,
    quote_price: float,
    evidence_count: int,
    diversification_bonus: float,
) -> MarketEvent:
    score = _candidate_score(evidence_count, diversification_bonus)
    sentiment = Sentiment.positive if evidence_count > 0 else Sentiment.neutral
    return MarketEvent(
        source=EventSource.ai_structured,
        event_type=MarketEventType.news,
        ticker=ticker,
        occurred_at=utc_now(),
        summary=_evidence_summary(ticker, evidence_count),
        sentiment=sentiment,
        confidence=round(min(0.95, 0.45 + score), 2),
        impact_score=round(min(0.9, 0.35 + evidence_count * 0.15 + diversification_bonus), 2),
        metadata={
            "evidence_count": evidence_count,
            "quote_price": round(quote_price, 6),
            "diversification_bonus": round(diversification_bonus, 4),
        },
    )


def _market_event_for_strategy(
    *,
    strategy_id: str,
    ticker: str,
    quote_price: float,
    evidence_count: int,
    diversification_bonus: float,
    provider: MarketDataProvider,
) -> MarketEvent | None:
    if strategy_id == MOVING_AVERAGE_CROSS_STRATEGY_ID:
        return _market_event_from_moving_average_cross(
            ticker=ticker,
            quote_price=quote_price,
            provider=provider,
        )
    return _market_event_from_evidence(
        ticker=ticker,
        quote_price=quote_price,
        evidence_count=evidence_count,
        diversification_bonus=diversification_bonus,
    )


def _market_event_from_moving_average_cross(
    *,
    ticker: str,
    quote_price: float,
    provider: MarketDataProvider,
) -> MarketEvent | None:
    bars = provider.get_price_history(ticker, interval="1d")
    closes = [
        float(bar.close)
        for bar in bars
        if bar.close is not None and not isinstance(bar.close, bool) and float(bar.close) > 0
    ]
    if len(closes) < MOVING_AVERAGE_SLOW_PERIOD:
        return None

    fast_sma = sum(closes[-MOVING_AVERAGE_FAST_PERIOD:]) / MOVING_AVERAGE_FAST_PERIOD
    slow_sma = sum(closes[-MOVING_AVERAGE_SLOW_PERIOD:]) / MOVING_AVERAGE_SLOW_PERIOD
    is_bullish = fast_sma > slow_sma
    source = next((bar.source for bar in reversed(bars) if bar.source), "unknown")
    return MarketEvent(
        source=EventSource.market_data,
        event_type=MarketEventType.price_move,
        ticker=ticker,
        occurred_at=utc_now(),
        summary=(
            f"{ticker} 20日均线 {fast_sma:.2f} "
            f"{'高于' if is_bullish else '未高于'} 50日均线 {slow_sma:.2f}。"
        ),
        sentiment=Sentiment.positive if is_bullish else Sentiment.neutral,
        confidence=0.82 if is_bullish else 0.55,
        impact_score=0.68 if is_bullish else 0.45,
        metadata={
            "strategy_id": MOVING_AVERAGE_CROSS_STRATEGY_ID,
            "quote_price": round(quote_price, 6),
            "fast_period": MOVING_AVERAGE_FAST_PERIOD,
            "slow_period": MOVING_AVERAGE_SLOW_PERIOD,
            "fast_sma": round(fast_sma, 6),
            "slow_sma": round(slow_sma, 6),
            "history_bar_count": len(closes),
            "price_source": source,
        },
    )


def _paper_risk_limits(
    session: Session | None = None,
    *,
    team_id: UUID | None = None,
    mode: PaperTradingMode = PaperTradingMode.paper,
) -> RiskLimits:
    return get_paper_risk_limits(session, team_id=team_id, mode=mode)


def _manual_trade_intent(data: PaperOrderCreate, notional: float, strategy_id: str) -> TradeIntent:
    reason = data.reason or f"Registered strategy {strategy_id} manual paper {data.side} order for {data.quantity:g} {data.ticker}."
    return TradeIntent(
        ticker=data.ticker,
        side=TradeIntentSide(data.side),
        notional=notional,
        reason=reason,
    )


def _paper_order_strategy_id(
    registered_strategy_id: str,
    *,
    run_id: UUID | None,
    core_context: CoreEventContext | None,
) -> str:
    if core_context is not None:
        return core_context.strategy_id
    if run_id is not None:
        return registered_strategy_id
    return f"{registered_strategy_id}{MANUAL_OVERRIDE_STRATEGY_SUFFIX}"


def _submit_core_order(
    session: Session,
    account: PaperAccount,
    intent: TradeIntent,
    core_context: CoreEventContext,
    trading_day: str | None = None,
) -> CoreOrder:
    if core_context is None:
        raise ValueError("Execution requires a persisted core event context.")
    execution = ExecutionEngine(RiskEngine(_paper_risk_limits(session, team_id=account.team_id, mode=account.mode)))
    return execution.submit_intent(intent, _paper_portfolio_state(session, account, trading_day=trading_day))


def _new_paper_order(
    account: PaperAccount,
    team_id: UUID,
    data: PaperOrderCreate,
    side: PaperOrderSide,
    core_order: CoreOrder,
    status: PaperOrderStatus,
    rejection_reason: str | None = None,
    submitted_at: datetime | None = None,
    strategy_id: str | None = None,
) -> PaperOrder:
    return PaperOrder(
        account_id=account.id,
        team_id=team_id,
        strategy_id=strategy_id or data.strategy_id,
        candidate_id=data.candidate_id,
        ticker=data.ticker,
        side=side,
        order_type=data.order_type,
        quantity=data.quantity,
        status=status,
        rejection_reason=rejection_reason,
        core_order_id=str(core_order.order_id),
        core_intent_id=str(core_order.intent.intent_id),
        risk_status=core_order.risk_decision.status.value if core_order.risk_decision is not None else None,
        risk_code=core_order.risk_decision.code if core_order.risk_decision is not None else None,
        risk_reason=core_order.risk_decision.reason if core_order.risk_decision is not None else None,
        state_history_json=_state_history_json(core_order),
        submitted_at=submitted_at or utc_now(),
    )


def _state_history_json(core_order: CoreOrder) -> str:
    return json.dumps([record.model_dump(mode="json") for record in core_order.state_history])


def _persist_manual_strategy_events(
    *,
    session: Session,
    team_id: UUID,
    account: PaperAccount,
    data: PaperOrderCreate,
    intent: TradeIntent,
    run_id: UUID | None,
    order_strategy_id: str,
    trading_day: str | None = None,
) -> CoreEventContext:
    event_bus = _build_trading_event_bus()
    order_origin = "manual_override" if order_strategy_id.endswith(MANUAL_OVERRIDE_STRATEGY_SUFFIX) else "paper_run_order"
    event_source = EventSource.manual if order_origin == "manual_override" else EventSource.market_data
    summary = data.reason or _paper_order_event_summary(data, order_origin)
    event = MarketEvent(
        source=event_source,
        event_type=MarketEventType.price_move,
        ticker=data.ticker,
        occurred_at=utc_now(),
        summary=summary,
        sentiment=Sentiment.positive if data.side == "buy" else Sentiment.negative,
        confidence=1.0,
        impact_score=0.1,
        metadata={
            "registered_strategy_id": data.strategy_id,
            "order_strategy_id": order_strategy_id,
            "order_origin": order_origin,
            "candidate_id": str(data.candidate_id) if data.candidate_id is not None else None,
            "quantity": data.quantity,
            "order_type": data.order_type,
            "reason": data.reason,
        },
    )
    market_envelope = event_bus.publish(TradingEventTopic.market_event, event)
    strategy_input_envelope = event_bus.publish(
        TradingEventTopic.strategy_input,
        StrategyInputEvent(market_event=event, portfolio=_paper_portfolio_state(session, account, trading_day=trading_day)),
        causation_id=market_envelope.event_id,
        correlation_id=market_envelope.correlation_id,
    )
    trade_intent_envelope = event_bus.publish(
        TradingEventTopic.trade_intent,
        intent,
        causation_id=strategy_input_envelope.event_id,
        correlation_id=strategy_input_envelope.correlation_id,
    )
    _persist_core_event_envelopes(session, team_id, event_bus.history, run_id=run_id)
    return CoreEventContext(
        correlation_id=trade_intent_envelope.correlation_id,
        trade_intent_event_id=trade_intent_envelope.event_id,
        trade_intent_sequence=trade_intent_envelope.sequence,
        intent=intent,
        strategy_id=order_strategy_id,
    )


def _paper_order_event_summary(data: PaperOrderCreate, order_origin: str) -> str:
    if order_origin == "manual_override":
        return f"Manual paper {data.side} request for {data.quantity:g} {data.ticker}."
    return f"Paper run system {data.side} order for {data.quantity:g} {data.ticker}."


def _persist_core_order_events(
    session: Session,
    team_id: UUID,
    core_order: CoreOrder,
    run_id: UUID | None,
    core_context: CoreEventContext | None = None,
) -> None:
    sequence_start = _next_core_event_sequence(session, run_id)
    correlation_id = str(core_context.correlation_id) if core_context is not None else str(core_order.order_id)
    causation_id = (
        str(core_context.trade_intent_event_id) if core_context is not None else str(core_order.intent.intent_id)
    )
    order_state_causation_id = causation_id
    order_state_offset = 0
    if core_order.risk_decision is not None:
        risk_sequence = sequence_start
        risk_payload = {
            "order_id": str(core_order.order_id),
            "intent_id": str(core_order.intent.intent_id),
            "ticker": core_order.intent.ticker,
            "status": core_order.risk_decision.status.value,
            "code": core_order.risk_decision.code,
            "reason": core_order.risk_decision.reason,
        }
        risk_event_id = f"{correlation_id}:{risk_sequence}:risk_decision"
        session.add(
            CoreEventLog(
                team_id=team_id,
                run_id=run_id,
                event_id=risk_event_id,
                topic="risk_decision",
                sequence=risk_sequence,
                correlation_id=correlation_id,
                causation_id=causation_id,
                payload_json=json.dumps(risk_payload),
                published_at=utc_now(),
            )
        )
        order_state_causation_id = risk_event_id
        order_state_offset = 1

    for offset, record in enumerate(core_order.state_history):
        sequence = sequence_start + order_state_offset + offset
        payload = {
            "order_id": str(core_order.order_id),
            "intent_id": str(core_order.intent.intent_id),
            "ticker": core_order.intent.ticker,
            "state": record.state.value,
            "recorded_at": record.recorded_at.isoformat(),
            "reason": record.reason,
        }
        session.add(
            CoreEventLog(
                team_id=team_id,
                run_id=run_id,
                event_id=f"{correlation_id}:{sequence}:{record.state.value}",
                topic="order_state",
                sequence=sequence,
                correlation_id=correlation_id,
                causation_id=order_state_causation_id,
                payload_json=json.dumps(payload),
                published_at=record.recorded_at,
            )
        )
    if core_context is not None:
        _stream_core_order_events(core_order, core_context)


def _stream_core_order_events(core_order: CoreOrder, core_context: CoreEventContext) -> None:
    event_bus = _build_trading_event_bus(initial_sequence=core_context.trade_intent_sequence)
    risk_envelope = None
    if core_order.risk_decision is not None:
        risk_envelope = event_bus.publish(
            TradingEventTopic.risk_decision,
            core_order.risk_decision,
            causation_id=core_context.trade_intent_event_id,
            correlation_id=core_context.correlation_id,
        )
    for record in core_order.state_history:
        payload = order_state_event(core_order).model_copy(update={"current_state": record.state})
        event_bus.publish(
            TradingEventTopic.order_state,
            payload,
            causation_id=(
                risk_envelope.event_id
                if risk_envelope is not None
                else core_context.trade_intent_event_id
            ),
            correlation_id=core_context.correlation_id,
        )


def _persist_core_event_envelopes(
    session: Session,
    team_id: UUID,
    envelopes: list[EventEnvelope],
    run_id: UUID | None,
) -> None:
    sequence_start = _next_core_event_sequence(session, run_id)
    for envelope in envelopes:
        session.add(
            CoreEventLog(
                team_id=team_id,
                run_id=run_id,
                event_id=str(envelope.event_id),
                topic=envelope.topic.value,
                sequence=sequence_start + envelope.sequence - 1,
                correlation_id=str(envelope.correlation_id),
                causation_id=str(envelope.causation_id) if envelope.causation_id is not None else None,
                payload_json=envelope.payload.model_dump_json(),
                published_at=envelope.published_at,
            )
        )


def _build_trading_event_bus(initial_sequence: int = 0) -> InMemoryEventBus:
    settings = get_settings()
    return build_event_bus(
        mode=settings.event_bus_mode,
        redis_url=settings.redis_url,
        stream_name=settings.redis_stream_name,
        initial_sequence=initial_sequence,
    )


def _next_core_event_sequence(session: Session, run_id: UUID | None) -> int:
    query = select(CoreEventLog)
    if run_id is None:
        query = query.where(CoreEventLog.run_id == None)  # noqa: E711
    else:
        query = query.where(CoreEventLog.run_id == run_id)
    latest = session.exec(query.order_by(CoreEventLog.sequence.desc())).first()
    if latest is None:
        return 1
    return latest.sequence + 1


def _summary_payload(
    session: Session,
    account: PaperAccount,
    provider: MarketDataProvider,
    *,
    as_of_trading_day: str | None = None,
    use_live_quotes: bool = True,
) -> PaperTradingSummary:
    summary_as_of_trading_day = as_of_trading_day or utc_now().date().isoformat()
    review_as_of_trading_day = as_of_trading_day or _current_trading_day()
    candidates = list(
        session.exec(
            select(PaperCandidate).where(PaperCandidate.team_id == account.team_id).order_by(PaperCandidate.rank)
        ).all()
    )
    candidates = [
        candidate
        for candidate in candidates
        if _is_on_or_before_trading_day(candidate.created_at, summary_as_of_trading_day)
    ]
    orders = list(
        session.exec(
            select(PaperOrder).where(PaperOrder.account_id == account.id).order_by(PaperOrder.submitted_at.desc())
        ).all()
    )
    orders = [order for order in orders if _is_on_or_before_trading_day(order.submitted_at, summary_as_of_trading_day)]
    projected_account, projected_positions = _project_as_of_account(
        account,
        orders,
        provider,
        use_live_quotes=use_live_quotes,
    )
    latest_review = session.exec(
        select(PaperReview)
        .where(PaperReview.account_id == account.id)
        .where(PaperReview.trading_day <= review_as_of_trading_day)
        .order_by(PaperReview.trading_day.desc(), PaperReview.created_at.desc())
    ).first()
    return PaperTradingSummary(
        account=projected_account,
        candidates=[_candidate_payload(candidate) for candidate in candidates],
        orders=[_order_payload(order) for order in orders],
        positions=projected_positions,
        latest_review=_review_payload(latest_review) if latest_review is not None else None,
    )


def _project_as_of_account(
    account: PaperAccount,
    orders: list[PaperOrder],
    provider: MarketDataProvider,
    *,
    use_live_quotes: bool = True,
) -> tuple[PaperAccountPayload, list[PaperPositionPayload]]:
    cash = account.starting_cash
    realized_pnl = 0.0
    positions: dict[str, dict[str, float]] = {}
    realized_by_ticker: dict[str, float] = {}
    latest_fill_price_by_ticker: dict[str, float] = {}
    for order in sorted(orders, key=lambda item: item.submitted_at):
        if order.status != PaperOrderStatus.filled or order.fill_price is None:
            continue
        ticker = order.ticker.upper()
        quantity = order.quantity
        fill_price = order.fill_price
        latest_fill_price_by_ticker[ticker] = fill_price
        if order.side == PaperOrderSide.buy:
            current = positions.setdefault(ticker, {"quantity": 0.0, "average_cost": 0.0})
            previous_quantity = current["quantity"]
            new_quantity = previous_quantity + quantity
            current["average_cost"] = (
                ((previous_quantity * current["average_cost"]) + (quantity * fill_price)) / new_quantity
                if new_quantity
                else 0.0
            )
            current["quantity"] = new_quantity
            cash -= quantity * fill_price
            continue

        current = positions.get(ticker)
        if current is None or current["quantity"] <= 0:
            continue
        sell_quantity = min(quantity, current["quantity"])
        cash += sell_quantity * fill_price
        pnl = (fill_price - current["average_cost"]) * sell_quantity
        realized_pnl += pnl
        realized_by_ticker[ticker] = realized_by_ticker.get(ticker, 0.0) + pnl
        current["quantity"] -= sell_quantity
        if current["quantity"] <= 1e-9:
            positions.pop(ticker, None)

    position_payloads: list[PaperPositionPayload] = []
    for ticker, position in sorted(positions.items()):
        last_price = latest_fill_price_by_ticker.get(ticker) or position["average_cost"]
        if use_live_quotes:
            quote = provider.get_quote(ticker)
            last_price = quote.price or last_price
        market_value = position["quantity"] * last_price
        unrealized_pnl = (last_price - position["average_cost"]) * position["quantity"]
        position_payloads.append(
            PaperPositionPayload(
                id=uuid5(NAMESPACE_DNS, f"{account.id}:{ticker}"),
                ticker=ticker,
                quantity=round(position["quantity"], 6),
                average_cost=round(position["average_cost"], 6),
                last_price=round(last_price, 6),
                market_value=round(market_value, 2),
                unrealized_pnl=round(unrealized_pnl, 2),
                realized_pnl=round(realized_by_ticker.get(ticker, 0.0), 2),
                updated_at=account.updated_at,
            )
        )
    unrealized = round(sum(position.unrealized_pnl for position in position_payloads), 2)
    equity = round(cash + sum(position.market_value for position in position_payloads), 2)
    return (
        PaperAccountPayload(
            id=account.id,
            name=account.name,
            mode=account.mode.value,
            starting_cash=round(account.starting_cash, 2),
            cash=round(cash, 2),
            realized_pnl=round(realized_pnl, 2),
            unrealized_pnl=unrealized,
            equity=equity,
            updated_at=account.updated_at,
        ),
        position_payloads,
    )


def _candidate_payload(candidate: PaperCandidate) -> PaperCandidatePayload:
    return PaperCandidatePayload(
        id=candidate.id,
        strategy_id=candidate.strategy_id,
        ticker=candidate.ticker,
        action=candidate.action.value,
        rank=candidate.rank,
        confidence=candidate.confidence,
        thesis=candidate.thesis,
        risk_notes=candidate.risk_notes,
        evidence_summary=candidate.evidence_summary,
        proposed_quantity=candidate.proposed_quantity,
        status=candidate.status.value,
        created_at=candidate.created_at,
    )


def _is_on_or_before_trading_day(value: datetime, trading_day: str) -> bool:
    return value.date() <= datetime.fromisoformat(trading_day).date()


def _order_payload(order: PaperOrder) -> PaperOrderPayload:
    return PaperOrderPayload(
        id=order.id,
        strategy_id=order.strategy_id,
        candidate_id=order.candidate_id,
        ticker=order.ticker,
        side=order.side.value,
        order_type=order.order_type,
        quantity=order.quantity,
        status=order.status.value,
        fill_price=order.fill_price,
        realized_pnl=round(order.realized_pnl, 2),
        rejection_reason=order.rejection_reason,
        core_order_id=order.core_order_id,
        core_intent_id=order.core_intent_id,
        risk_status=order.risk_status,
        risk_code=order.risk_code,
        risk_reason=order.risk_reason,
        state_history=_state_history_payload(order.state_history_json),
        submitted_at=order.submitted_at,
        filled_at=order.filled_at,
    )


def _state_history_payload(value: str | None) -> list[dict[str, str]]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _position_payload(position: PaperPosition) -> PaperPositionPayload:
    return PaperPositionPayload(
        id=position.id,
        ticker=position.ticker,
        quantity=position.quantity,
        average_cost=round(position.average_cost, 6),
        last_price=position.last_price,
        market_value=round(position.market_value, 2),
        unrealized_pnl=round(position.unrealized_pnl, 2),
        realized_pnl=round(position.realized_pnl, 2),
        updated_at=position.updated_at,
    )


def _review_payload(review: PaperReview) -> PaperReviewPayload:
    return PaperReviewPayload(
        id=review.id,
        trading_day=review.trading_day,
        equity=round(review.equity, 2),
        cash=round(review.cash, 2),
        realized_pnl=round(review.realized_pnl, 2),
        unrealized_pnl=round(review.unrealized_pnl, 2),
        trade_count=review.trade_count,
        win_rate=review.win_rate,
        average_win=review.average_win,
        average_loss=review.average_loss,
        expectancy=review.expectancy,
        readiness=review.readiness.value,
        notes=review.notes,
        created_at=review.created_at,
    )


def _run_payload(run: PaperRun) -> PaperRunPayload:
    return PaperRunPayload(
        id=run.id,
        trading_day=run.trading_day,
        trigger=run.trigger.value,
        status=run.status.value,
        candidates_count=run.candidates_count,
        orders_count=run.orders_count,
        positions_count=run.positions_count,
        review_id=run.review_id,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _core_event_payload(event: CoreEventLog) -> CoreEventLogPayload:
    return CoreEventLogPayload(
        id=event.id,
        run_id=event.run_id,
        event_id=event.event_id,
        topic=event.topic,
        sequence=event.sequence,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        payload_json=event.payload_json,
        published_at=event.published_at,
    )


def _evidence_summary(ticker: str, evidence_count: int) -> str:
    if evidence_count:
        return f"{evidence_count} 条证据支持继续跟踪 {ticker}"
    return f"暂无外部证据，{ticker} 仅作为低置信度观察候选"


def _readiness(trade_count: int, expectancy: float) -> PaperReadiness:
    if trade_count < 20:
        return PaperReadiness.collecting
    if expectancy <= 0:
        return PaperReadiness.negative_expectancy
    if trade_count < 30:
        return PaperReadiness.watch
    return PaperReadiness.paper_ready


def _review_notes(readiness: PaperReadiness, trade_count: int, expectancy: float) -> str:
    if readiness == PaperReadiness.paper_ready:
        return "模拟盘净期望为正且样本数达标，可以进入小资金实盘前的人工复核。"
    if readiness == PaperReadiness.watch:
        return "模拟盘净期望为正，但样本数仍偏少，继续观察。"
    if readiness == PaperReadiness.negative_expectancy:
        return "模拟盘净期望不达标，禁止进入实盘。"
    return f"正在收集模拟盘样本：已关闭交易 {trade_count} 笔，当前期望值 {expectancy:.2f}。"
