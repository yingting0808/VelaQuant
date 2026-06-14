import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.data.providers.base import PriceHistoryBar
from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPosition,
    PaperReadiness,
    PaperReview,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
)
from app.services.strategy_attribution import attribute_current_paper_strategy
from app.services.workspace import get_or_create_default_workspace


def _bar(ticker: str, date: str, close: float) -> PriceHistoryBar:
    return PriceHistoryBar(
        ticker=ticker,
        date=date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        source="test",
    )


class RegimeFixtureProvider:
    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        histories = {
            "NVDA": [_bar("NVDA", "2026-06-01", 100), _bar("NVDA", "2026-06-02", 104), _bar("NVDA", "2026-06-03", 108)],
            "MSFT": [_bar("MSFT", "2026-06-01", 100), _bar("MSFT", "2026-06-02", 100.6), _bar("MSFT", "2026-06-03", 100.3)],
            "TSLA": [_bar("TSLA", "2026-06-01", 100), _bar("TSLA", "2026-06-02", 118), _bar("TSLA", "2026-06-03", 92)],
            "AMZN": [_bar("AMZN", "2026-06-01", 100), _bar("AMZN", "2026-06-02", 101)],
        }
        return histories[ticker]


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _account(session: Session) -> PaperAccount:
    workspace = get_or_create_default_workspace(session)
    account = PaperAccount(team_id=workspace.team.id, name="默认模拟盘", cash=100000)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _core_event(
    session: Session,
    account: PaperAccount,
    topic: str,
    sequence: int,
    payload: dict,
    published_at: datetime | None = None,
) -> CoreEventLog:
    event = CoreEventLog(
        team_id=account.team_id,
        event_id=f"{topic}-{sequence}",
        topic=topic,
        sequence=sequence,
        correlation_id="paper-run-test",
        payload_json=json.dumps(payload),
        published_at=published_at or datetime(2026, 6, 12, tzinfo=timezone.utc) + timedelta(seconds=sequence),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def _filled_buy(session: Session, account: PaperAccount, ticker: str = "NVDA") -> PaperOrder:
    order = PaperOrder(
        account_id=account.id,
        team_id=account.team_id,
        ticker=ticker,
        side=PaperOrderSide.buy,
        quantity=1,
        status=PaperOrderStatus.filled,
        fill_price=100,
        risk_status="approved",
        risk_code="approved",
        submitted_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def _filled_sell(
    session: Session,
    account: PaperAccount,
    ticker: str = "NVDA",
    realized_pnl: float = -12,
) -> PaperOrder:
    order = PaperOrder(
        account_id=account.id,
        team_id=account.team_id,
        ticker=ticker,
        side=PaperOrderSide.sell,
        quantity=1,
        status=PaperOrderStatus.filled,
        fill_price=90,
        realized_pnl=realized_pnl,
        risk_status="approved",
        risk_code="approved",
        submitted_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def _rejected_buy(
    session: Session,
    account: PaperAccount,
    ticker: str = "NVDA",
    risk_code: str = "max_position_weight",
) -> PaperOrder:
    order = PaperOrder(
        account_id=account.id,
        team_id=account.team_id,
        ticker=ticker,
        side=PaperOrderSide.buy,
        quantity=1,
        status=PaperOrderStatus.rejected,
        rejection_reason="Risk limit rejected order.",
        risk_status="rejected",
        risk_code=risk_code,
        submitted_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def _review(
    session: Session,
    account: PaperAccount,
    trading_day: str,
    equity: float,
    created_at: datetime,
) -> PaperReview:
    review = PaperReview(
        account_id=account.id,
        team_id=account.team_id,
        trading_day=trading_day,
        equity=equity,
        cash=equity,
        realized_pnl=0,
        unrealized_pnl=0,
        trade_count=1,
        win_rate=0,
        average_win=0,
        average_loss=0,
        expectancy=0,
        readiness=PaperReadiness.collecting,
        notes="test",
        created_at=created_at,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


def test_strategy_attribution_reports_data_quality_warnings_without_history():
    with make_session() as session:
        attribution = attribute_current_paper_strategy(session)

        assert attribution.strategy_id == "deterministic_watchlist_v1"
        assert attribution.signal_quality.market_event_count == 0
        assert attribution.signal_quality.trade_intent_count == 0
        assert attribution.regime.regime == "insufficient_data"
        assert attribution.drawdown.source == "insufficient_data"
        assert "missing_market_events" in attribution.data_quality_warnings
        assert "insufficient_review_history" in attribution.data_quality_warnings


def test_strategy_attribution_counts_signal_quality_from_core_events():
    with make_session() as session:
        account = _account(session)
        _core_event(session, account, "market_event", 1, {"ticker": "NVDA", "confidence": 0.8})
        _core_event(session, account, "market_event", 2, {"ticker": "MSFT", "confidence": 0.6})
        _core_event(session, account, "trade_intent", 3, {"ticker": "NVDA", "side": "buy"})

        attribution = attribute_current_paper_strategy(session)

        assert attribution.signal_quality.market_event_count == 2
        assert attribution.signal_quality.trade_intent_count == 1
        assert attribution.signal_quality.actionable_signal_rate == 0.5
        assert attribution.signal_quality.average_confidence == 0.7


def test_strategy_attribution_ignores_future_events_orders_and_reviews_for_as_of_baseline():
    with make_session() as session:
        account = _account(session)
        _core_event(
            session,
            account,
            "market_event",
            1,
            {"ticker": "NVDA", "confidence": 0.8},
            published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
        )
        _core_event(
            session,
            account,
            "market_event",
            2,
            {"ticker": "AMZN", "confidence": 0.95},
            published_at=datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc),
        )
        today_order = _filled_sell(session, account, "NVDA", realized_pnl=10)
        today_order.submitted_at = datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc)
        future_order = _filled_sell(session, account, "AMZN", realized_pnl=500)
        future_order.submitted_at = datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc)
        _review(session, account, "2026-06-13", 100000, datetime(2026, 6, 13, tzinfo=timezone.utc))
        _review(session, account, "2026-06-30", 103000, datetime(2026, 6, 30, tzinfo=timezone.utc))
        session.commit()

        attribution = attribute_current_paper_strategy(session, as_of_trading_day="2026-06-13")

        assert attribution.signal_quality.market_event_count == 1
        assert attribution.expectancy_decomposition.realized_pnl == 10
        assert attribution.regime.review_count == 1


def test_strategy_attribution_warns_when_position_snapshot_may_include_future_runs():
    with make_session() as session:
        account = _account(session)
        session.add(
            PaperRun(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-30",
                trigger=PaperRunTrigger.manual,
                status=PaperRunStatus.completed,
            )
        )
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="AMZN",
                quantity=1,
                average_cost=100,
                last_price=95,
                market_value=95,
                unrealized_pnl=-5,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session, as_of_trading_day="2026-06-13")

        assert "position_snapshot_may_include_future_run_state" in attribution.data_quality_warnings


def test_strategy_attribution_reports_per_ticker_signal_diagnostics():
    with make_session() as session:
        account = _account(session)
        _core_event(session, account, "market_event", 1, {"ticker": "NVDA", "confidence": 0.8})
        _core_event(session, account, "market_event", 2, {"ticker": "NVDA", "confidence": 0.6})
        _core_event(session, account, "trade_intent", 3, {"ticker": "NVDA", "side": "buy"})
        _core_event(session, account, "market_event", 4, {"ticker": "MSFT", "confidence": 0.5})
        _filled_buy(session, account, "NVDA")
        _filled_sell(session, account, "NVDA", realized_pnl=15)
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=110,
                market_value=110,
                unrealized_pnl=10,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)
        diagnostics = {item.ticker: item for item in attribution.ticker_diagnostics}

        assert diagnostics["NVDA"].market_event_count == 2
        assert diagnostics["NVDA"].trade_intent_count == 1
        assert diagnostics["NVDA"].filled_order_count == 2
        assert diagnostics["NVDA"].average_confidence == 0.7
        assert diagnostics["NVDA"].observed_pnl == 25
        assert diagnostics["NVDA"].false_positive_rate == 0.0
        assert diagnostics["MSFT"].market_event_count == 1
        assert diagnostics["MSFT"].trade_intent_count == 0


def test_strategy_attribution_flags_losing_open_position_as_false_positive():
    with make_session() as session:
        account = _account(session)
        _filled_buy(session, account)
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=90,
                market_value=90,
                unrealized_pnl=-10,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)

        assert attribution.signal_quality.false_positive_rate == 1.0
        assert attribution.expectancy_decomposition.unrealized_pnl == -10
        assert attribution.expectancy_decomposition.open_trade_component == -10
        assert attribution.expectancy_decomposition.total_observed_pnl == -10


def test_strategy_attribution_reports_signal_decay_for_stale_open_positions():
    with make_session() as session:
        account = _account(session)
        stale_submitted_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        fresh_submitted_at = datetime(2026, 6, 9, tzinfo=timezone.utc)
        as_of = datetime(2026, 6, 10, tzinfo=timezone.utc)
        stale = _filled_buy(session, account, "NVDA")
        stale.submitted_at = stale_submitted_at
        fresh = _filled_buy(session, account, "MSFT")
        fresh.submitted_at = fresh_submitted_at
        _core_event(session, account, "market_event", 9, {"ticker": "NVDA", "confidence": 0.7}, published_at=as_of)
        _review(session, account, "2026-06-10", 100000, as_of)
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=101,
                market_value=101,
                unrealized_pnl=1,
                updated_at=as_of,
            )
        )
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="MSFT",
                quantity=1,
                average_cost=100,
                last_price=101,
                market_value=101,
                unrealized_pnl=1,
                updated_at=as_of,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)

        assert attribution.signal_decay.threshold_days == 5
        assert attribution.signal_decay.open_position_count == 2
        assert attribution.signal_decay.stale_open_position_count == 1
        assert attribution.signal_decay.stale_tickers == ["NVDA"]
        assert attribution.signal_decay.average_holding_days == 5.0


def test_strategy_attribution_excludes_scheduler_audit_events_from_signal_decay_as_of():
    with make_session() as session:
        account = _account(session)
        stale_submitted_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        fresh_submitted_at = datetime(2026, 6, 9, tzinfo=timezone.utc)
        signal_as_of = datetime(2026, 6, 10, tzinfo=timezone.utc)
        stale = _filled_buy(session, account, "NVDA")
        stale.submitted_at = stale_submitted_at
        fresh = _filled_buy(session, account, "MSFT")
        fresh.submitted_at = fresh_submitted_at
        _core_event(session, account, "market_event", 9, {"ticker": "NVDA", "confidence": 0.7}, published_at=signal_as_of)
        _core_event(
            session,
            account,
            "scheduler_decision",
            10,
            {"execution_gate": "market_closed"},
            published_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        _review(session, account, "2026-06-10", 100000, signal_as_of)
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=101,
                market_value=101,
                unrealized_pnl=1,
                updated_at=signal_as_of,
            )
        )
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="MSFT",
                quantity=1,
                average_cost=100,
                last_price=101,
                market_value=101,
                unrealized_pnl=1,
                updated_at=signal_as_of,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session, as_of_trading_day="2026-06-30")

        assert attribution.signal_decay.stale_tickers == ["NVDA"]
        assert attribution.signal_decay.average_holding_days == 5.0


def test_strategy_attribution_identifies_drawdown_regime_and_source():
    with make_session() as session:
        account = _account(session)
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        _review(session, account, "2026-06-01", 100000, start)
        _review(session, account, "2026-06-02", 112000, start + timedelta(days=1))
        _review(session, account, "2026-06-03", 99000, start + timedelta(days=2))
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=90,
                market_value=90,
                unrealized_pnl=-10,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)

        assert attribution.regime.regime == "drawdown_pressure"
        assert attribution.regime.review_count == 3
        assert attribution.drawdown.source == "open_position_pressure"
        assert attribution.drawdown.max_drawdown == 0.1161


def test_strategy_attribution_breaks_down_expectancy_and_drawdown_contributors():
    with make_session() as session:
        account = _account(session)
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        _review(session, account, "2026-06-01", 100000, start)
        _review(session, account, "2026-06-02", 112000, start + timedelta(days=1))
        _review(session, account, "2026-06-03", 99000, start + timedelta(days=2))
        _filled_sell(session, account, "NVDA", realized_pnl=-30)
        _rejected_buy(session, account, "NVDA")
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=85,
                market_value=85,
                unrealized_pnl=-15,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)
        components = {item.name: item for item in attribution.expectancy_decomposition.components}
        contributors = {item.name: item for item in attribution.drawdown.contributors}

        assert components["timing_component"].value == -15
        assert components["volatility_component"].value == 0
        assert components["noise_component"].value == -45
        assert components["risk_component"].value == -1
        assert contributors["signal_failure"].value == -45
        assert contributors["risk_overreach"].value == 1
        assert contributors["execution_lag"].value == 0


def test_strategy_attribution_breaks_down_performance_by_market_regime():
    with make_session() as session:
        account = _account(session)
        _core_event(session, account, "market_event", 1, {"ticker": "NVDA", "confidence": 0.8})
        _core_event(session, account, "market_event", 2, {"ticker": "MSFT", "confidence": 0.7})
        _core_event(session, account, "market_event", 3, {"ticker": "TSLA", "confidence": 0.6})
        _core_event(session, account, "market_event", 4, {"ticker": "AMZN", "confidence": 0.5})
        _filled_sell(session, account, "NVDA", realized_pnl=25)
        _filled_sell(session, account, "MSFT", realized_pnl=-4)
        _filled_sell(session, account, "TSLA", realized_pnl=-15)
        _filled_sell(session, account, "AMZN", realized_pnl=3)

        attribution = attribute_current_paper_strategy(session, provider=RegimeFixtureProvider())
        breakdown = {item.regime: item for item in attribution.regime_breakdown.items}

        assert breakdown["trend_market"].ticker_count == 1
        assert breakdown["trend_market"].observed_pnl == 25
        assert breakdown["trend_market"].sample_count == 2
        assert breakdown["trend_market"].sharpe_proxy == 3.9231
        assert breakdown["trend_market"].tickers == ["NVDA"]
        assert breakdown["range_market"].observed_pnl == -4
        assert breakdown["range_market"].sample_count == 2
        assert breakdown["range_market"].tickers == ["MSFT"]
        assert breakdown["high_volatility"].observed_pnl == -15
        assert breakdown["high_volatility"].sample_count == 2
        assert breakdown["high_volatility"].sharpe_proxy == -0.1008
        assert breakdown["high_volatility"].tickers == ["TSLA"]
        assert breakdown["insufficient_data"].observed_pnl == 3
        assert breakdown["insufficient_data"].sample_count == 0
        assert breakdown["insufficient_data"].sharpe_proxy == 0
        assert breakdown["insufficient_data"].tickers == ["AMZN"]
        assert attribution.regime_breakdown.primary_regime == "trend_market"
        components = {item.name: item for item in attribution.expectancy_decomposition.components}
        assert components["volatility_component"].value == -15
