import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

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
    Position,
    WatchlistItem,
    utc_now,
)
from app.services.workspace import get_or_create_default_workspace
from app.trading_core.execution import CoreOrder, ExecutionEngine, OrderState
from app.trading_core.portfolio import PortfolioPosition, PortfolioState
from app.trading_core.risk import RiskEngine, RiskLimits
from app.trading_core.strategy import TradeIntent, TradeIntentSide


DEFAULT_ACCOUNT_NAME = "默认模拟盘"
DEFAULT_STARTING_CASH = 100000.0
DEFAULT_CANDIDATE_NOTIONAL = 2000.0
DEFAULT_DAILY_AUTO_ORDER_LIMIT = 1


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

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized


class PaperOrderPayload(BaseModel):
    id: UUID
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


def get_paper_trading_summary(session: Session, provider: MarketDataProvider) -> PaperTradingSummary:
    workspace = get_or_create_default_workspace(session)
    account = _get_or_create_account(session, workspace.team.id)
    _mark_positions_to_market(session, account, provider)
    session.commit()
    session.refresh(account)
    return _summary_payload(session, account)


def run_daily_paper_trading_loop(
    session: Session,
    provider: MarketDataProvider,
    trigger: PaperRunTrigger = PaperRunTrigger.manual,
) -> PaperTradingSummary:
    workspace = get_or_create_default_workspace(session)
    account = _get_or_create_account(session, workspace.team.id)
    trading_day = _current_trading_day()
    run = _start_paper_run(session, account, trading_day, trigger)
    try:
        existing_review = _review_for_trading_day(session, account, trading_day)
        if existing_review is not None:
            _mark_positions_to_market(session, account, provider)
            _finish_paper_run(session, account, run, PaperRunStatus.skipped, existing_review)
            session.commit()
            session.refresh(account)
            return _summary_payload(session, account)

        _generate_candidates(session, workspace.team.id, workspace.portfolio.id, account, provider)
        session.flush()
        _auto_submit_candidate_orders(session, provider, account, run.id)
        session.refresh(account)
        _mark_positions_to_market(session, account, provider)
        review = _create_review(session, account)
        session.add(review)
        session.flush()
        _finish_paper_run(session, account, run, PaperRunStatus.completed, review)
        account.updated_at = utc_now()
        session.commit()
        session.refresh(account)
        return _summary_payload(session, account)
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
) -> PaperOrderPayload:
    workspace = get_or_create_default_workspace(session)
    account = _get_or_create_account(session, workspace.team.id)
    price = _quote_price(provider, data.ticker)
    side = PaperOrderSide(data.side)
    cost = round(price * data.quantity, 2)
    _mark_positions_to_market(session, account, provider)
    core_order = _submit_core_order(session, account, data, cost)
    if core_order.current_state == OrderState.rejected:
        order = _new_paper_order(
            account=account,
            team_id=workspace.team.id,
            data=data,
            side=side,
            core_order=core_order,
            status=PaperOrderStatus.rejected,
            rejection_reason=core_order.risk_decision.reason if core_order.risk_decision is not None else "Trading Core rejected order.",
        )
        session.add(order)
        _persist_core_order_events(session, workspace.team.id, core_order, run_id)
        account.updated_at = utc_now()
        session.commit()
        session.refresh(order)
        return _order_payload(order)

    realized_pnl = 0.0
    filled_at = utc_now()

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
        filled_at=filled_at,
    )
    session.add(order)
    _persist_core_order_events(session, workspace.team.id, core_order, run_id)
    session.commit()
    session.refresh(order)
    return _order_payload(order)


def _get_or_create_account(session: Session, team_id: UUID) -> PaperAccount:
    account = session.exec(select(PaperAccount).where(PaperAccount.team_id == team_id)).first()
    if account is not None:
        return account

    account = PaperAccount(
        team_id=team_id,
        name=DEFAULT_ACCOUNT_NAME,
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


def _candidate_count(session: Session, team_id: UUID) -> int:
    return len(session.exec(select(PaperCandidate).where(PaperCandidate.team_id == team_id)).all())


def _order_count(session: Session, account: PaperAccount) -> int:
    return len(session.exec(select(PaperOrder).where(PaperOrder.account_id == account.id)).all())


def _generate_candidates(
    session: Session,
    team_id: UUID,
    portfolio_id: UUID,
    account: PaperAccount,
    provider: MarketDataProvider,
) -> None:
    for candidate in session.exec(
        select(PaperCandidate).where(
            PaperCandidate.team_id == team_id,
            PaperCandidate.status == PaperCandidateStatus.proposed,
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
    ranked: list[tuple[float, PaperCandidate]] = []

    for ticker in sorted(portfolio_tickers | watchlist_tickers):
        quote = provider.get_quote(ticker)
        if quote.price is None or quote.price <= 0:
            continue
        evidence = provider.get_research_evidence(ticker)
        evidence_count = len(evidence)
        diversification_bonus = 0.15 if ticker not in portfolio_tickers else 0.0
        score = evidence_count * 0.2 + diversification_bonus + 0.1
        confidence = round(min(0.95, 0.45 + score), 2)
        proposed_quantity = max(1, int(min(DEFAULT_CANDIDATE_NOTIONAL, account.cash * 0.02) // quote.price))
        evidence_summary = _evidence_summary(ticker, evidence_count)
        candidate = PaperCandidate(
            team_id=team_id,
            ticker=ticker,
            action=PaperOrderSide.buy,
            rank=0,
            confidence=confidence,
            thesis=f"{ticker} 候选买入：{evidence_summary}，按小额名义本金先进入模拟观察。",
            risk_notes="风险：行情波动、估值压缩、证据过期；模拟结果不能直接代表实盘。",
            evidence_summary=evidence_summary,
            proposed_quantity=float(proposed_quantity),
        )
        ranked.append((score, candidate))

    for index, (_score, candidate) in enumerate(sorted(ranked, key=lambda item: item[0], reverse=True), start=1):
        candidate.rank = index
        session.add(candidate)


def _auto_submit_candidate_orders(
    session: Session,
    provider: MarketDataProvider,
    account: PaperAccount,
    run_id: UUID | None = None,
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
    for candidate in candidates[:DEFAULT_DAILY_AUTO_ORDER_LIMIT]:
        if candidate.action != PaperOrderSide.buy or candidate.proposed_quantity <= 0:
            continue
        order = submit_paper_order(
            session,
            provider,
            PaperOrderCreate(
                ticker=candidate.ticker,
                side=candidate.action.value,
                quantity=candidate.proposed_quantity,
            ),
            run_id=run_id,
        )
        if order.status == PaperOrderStatus.filled.value:
            candidate.status = PaperCandidateStatus.ordered
            session.add(candidate)


def _create_review(session: Session, account: PaperAccount) -> PaperReview:
    positions = _positions(session, account)
    unrealized = round(sum(position.unrealized_pnl for position in positions), 2)
    equity = round(account.cash + sum(position.market_value for position in positions), 2)
    closed_orders = list(
        session.exec(
            select(PaperOrder).where(
                PaperOrder.account_id == account.id,
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
        trading_day=_current_trading_day(),
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
    return datetime.now(timezone.utc).date().isoformat()


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


def _paper_portfolio_state(session: Session, account: PaperAccount) -> PortfolioState:
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
        orders_today=_orders_today(session, account),
    )


def _orders_today(session: Session, account: PaperAccount) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return len(
        [
            order
            for order in session.exec(select(PaperOrder).where(PaperOrder.account_id == account.id)).all()
            if order.submitted_at.date().isoformat() == today
        ]
    )


def _paper_risk_limits() -> RiskLimits:
    return RiskLimits(
        max_order_notional=DEFAULT_CANDIDATE_NOTIONAL,
        max_position_weight=0.1,
        max_daily_orders=5,
    )


def _submit_core_order(
    session: Session,
    account: PaperAccount,
    data: PaperOrderCreate,
    notional: float,
) -> CoreOrder:
    intent = TradeIntent(
        ticker=data.ticker,
        side=TradeIntentSide(data.side),
        notional=notional,
        reason=f"Paper {data.side} order for {data.quantity:g} {data.ticker}.",
    )
    execution = ExecutionEngine(RiskEngine(_paper_risk_limits()))
    return execution.submit_intent(intent, _paper_portfolio_state(session, account))


def _new_paper_order(
    account: PaperAccount,
    team_id: UUID,
    data: PaperOrderCreate,
    side: PaperOrderSide,
    core_order: CoreOrder,
    status: PaperOrderStatus,
    rejection_reason: str | None = None,
) -> PaperOrder:
    return PaperOrder(
        account_id=account.id,
        team_id=team_id,
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
    )


def _state_history_json(core_order: CoreOrder) -> str:
    return json.dumps([record.model_dump(mode="json") for record in core_order.state_history])


def _persist_core_order_events(
    session: Session,
    team_id: UUID,
    core_order: CoreOrder,
    run_id: UUID | None,
) -> None:
    for sequence, record in enumerate(core_order.state_history, start=1):
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
                event_id=f"{core_order.order_id}:{sequence}:{record.state.value}",
                topic="order_state",
                sequence=sequence,
                correlation_id=str(core_order.order_id),
                causation_id=str(core_order.intent.intent_id),
                payload_json=json.dumps(payload),
                published_at=record.recorded_at,
            )
        )


def _summary_payload(session: Session, account: PaperAccount) -> PaperTradingSummary:
    positions = _positions(session, account)
    unrealized = round(sum(position.unrealized_pnl for position in positions), 2)
    equity = round(account.cash + sum(position.market_value for position in positions), 2)
    candidates = list(
        session.exec(
            select(PaperCandidate).where(PaperCandidate.team_id == account.team_id).order_by(PaperCandidate.rank)
        ).all()
    )
    orders = list(
        session.exec(
            select(PaperOrder).where(PaperOrder.account_id == account.id).order_by(PaperOrder.submitted_at.desc())
        ).all()
    )
    latest_review = session.exec(
        select(PaperReview).where(PaperReview.account_id == account.id).order_by(PaperReview.created_at.desc())
    ).first()
    return PaperTradingSummary(
        account=PaperAccountPayload(
            id=account.id,
            name=account.name,
            mode=account.mode.value,
            starting_cash=round(account.starting_cash, 2),
            cash=round(account.cash, 2),
            realized_pnl=round(account.realized_pnl, 2),
            unrealized_pnl=unrealized,
            equity=equity,
            updated_at=account.updated_at,
        ),
        candidates=[_candidate_payload(candidate) for candidate in candidates],
        orders=[_order_payload(order) for order in orders],
        positions=[_position_payload(position) for position in positions],
        latest_review=_review_payload(latest_review) if latest_review is not None else None,
    )


def _candidate_payload(candidate: PaperCandidate) -> PaperCandidatePayload:
    return PaperCandidatePayload(
        id=candidate.id,
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


def _order_payload(order: PaperOrder) -> PaperOrderPayload:
    return PaperOrderPayload(
        id=order.id,
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
