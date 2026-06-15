import json
import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, SQLModel, create_engine, select

from app.data.providers.base import (
    EvidenceItem,
    FundamentalSnapshot,
    MarketDataProvider,
    MarketSnapshot,
    PriceHistoryBar,
    ProviderStatus,
    Quote,
)
from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperCandidate,
    PaperOrder,
    PaperOrderSide,
    PaperRiskSetting,
    PaperReview,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
    StrategyCompetitionEntry,
    StrategyCompetitionSnapshot,
    StrategyAlphaSnapshot,
)
from app.services import paper_trading
from app.services.paper_trading import (
    PaperOrderCreate,
    get_paper_trading_summary,
    list_paper_run_events,
    list_paper_runs,
    run_daily_paper_trading_loop,
    submit_paper_order,
)
from app.services.event_ledger import get_event_ledger_status, replay_paper_run
from app.services.strategy_candidate_backtest import (
    StrategyCandidateBacktestItem,
    StrategyCandidateBacktestPayload,
)
from app.services.workspace import get_or_create_default_workspace
from app.trading_core.event_bus import RedisStreamEventBus


class FixtureProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.prices = {"AAPL": 100.0, "MSFT": 200.0, "NVDA": 50.0, "AMZN": 150.0, "META": 300.0}

    def get_quote(self, ticker: str) -> Quote:
        normalized = ticker.strip().upper()
        return Quote(
            ticker=normalized,
            price=self.prices.get(normalized),
            currency="USD",
            source="fixture",
            updated_at="2026-06-13T00:00:00Z",
            is_fallback=False,
            message="fixture quote",
        )

    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        return []

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker.strip().upper(),
            market_cap=None,
            pe_ratio=None,
            eps=None,
            price_to_sales=None,
            price_to_book=None,
            gross_margin=None,
            profit_margin=None,
            operating_margin=None,
            debt_to_equity=None,
            source="fixture",
            period_ending=None,
            updated_at="2026-06-13T00:00:00Z",
        )

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.strip().upper()
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=[],
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        normalized = ticker.strip().upper()
        counts = {"NVDA": 3, "AAPL": 2, "MSFT": 1, "AMZN": 1, "META": 1}
        return [
            EvidenceItem(
                ticker=normalized,
                title=f"{normalized} evidence {index}",
                summary=f"{normalized} has fixture evidence {index}.",
                source="fixture",
                source_url="https://example.test/evidence",
                observed_at="2026-06-13T00:00:00Z",
            )
            for index in range(1, counts.get(normalized, 0) + 1)
        ]

    def get_statuses(self) -> list[ProviderStatus]:
        return []


class FailingQuoteProvider(FixtureProvider):
    def get_quote(self, ticker: str) -> Quote:
        raise RuntimeError(f"quote source failed for {ticker}")


class FakeRedisStreamClient:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, str]]] = []

    def xadd(self, stream_name: str, fields: dict[str, str]):
        self.entries.append((stream_name, fields))
        return "1-0"


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_summary_latest_review_ignores_future_simulation_reviews():
    with make_session() as session:
        provider = FixtureProvider()
        get_paper_trading_summary(session, provider)
        account = session.exec(select(PaperAccount)).one()
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-13",
                equity=100000,
                cash=99000,
                realized_pnl=10,
                unrealized_pnl=5,
                trade_count=1,
                win_rate=1,
                average_win=10,
                average_loss=0,
                expectancy=10,
                notes="today review",
                created_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-30",
                equity=120000,
                cash=110000,
                realized_pnl=1000,
                unrealized_pnl=500,
                trade_count=30,
                win_rate=0.9,
                average_win=100,
                average_loss=10,
                expectancy=90,
                notes="future simulation review",
                created_at=datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        summary = get_paper_trading_summary(session, provider, as_of_trading_day="2026-06-13")

        assert summary.latest_review is not None
        assert summary.latest_review.trading_day == "2026-06-13"
        assert summary.latest_review.expectancy == 10


def test_summary_defaults_to_effective_trading_day_for_latest_review(monkeypatch):
    monkeypatch.setattr(paper_trading, "_current_trading_day", lambda: "2026-06-13")
    with make_session() as session:
        provider = FixtureProvider()
        get_paper_trading_summary(session, provider)
        account = session.exec(select(PaperAccount)).one()
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-13",
                equity=100000,
                cash=99000,
                realized_pnl=10,
                unrealized_pnl=5,
                trade_count=1,
                win_rate=1,
                average_win=10,
                average_loss=0,
                expectancy=10,
                notes="effective trading day review",
                created_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-14",
                equity=120000,
                cash=110000,
                realized_pnl=1000,
                unrealized_pnl=500,
                trade_count=30,
                win_rate=0.9,
                average_win=100,
                average_loss=10,
                expectancy=90,
                notes="non-trading-day manual review",
                created_at=datetime(2026, 6, 14, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        summary = get_paper_trading_summary(session, provider)

        assert summary.latest_review is not None
        assert summary.latest_review.trading_day == "2026-06-13"
        assert summary.latest_review.expectancy == 10


def test_daily_run_creates_account_candidates_and_review():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())
        runs = session.exec(select(PaperRun)).all()

        assert summary.account.name == "默认模拟盘"
        assert summary.account.mode == "paper"
        assert summary.account.cash < 100000.0
        assert summary.candidates
        assert summary.candidates[0].ticker == "NVDA"
        assert summary.candidates[0].strategy_id == "deterministic_watchlist_v1"
        assert summary.candidates[0].action == "buy"
        assert summary.candidates[0].status == "ordered"
        assert summary.candidates[0].proposed_quantity > 0
        assert "证据" in summary.candidates[0].thesis
        assert summary.orders
        assert summary.orders[0].risk_status == "approved"
        assert [item["state"] for item in summary.orders[0].state_history] == [
            "new",
            "validated",
            "risk_approved",
            "sent",
            "filled",
        ]
        assert summary.positions
        assert summary.latest_review is not None
        assert summary.latest_review.readiness == "collecting"
        assert summary.latest_review.trade_count == 0
        assert len(runs) == 1
        assert runs[0].trigger == PaperRunTrigger.manual
        assert runs[0].status == PaperRunStatus.completed
        assert runs[0].candidates_count == len(summary.candidates)
        assert runs[0].orders_count == len(summary.orders)
        assert runs[0].review_id == summary.latest_review.id
        assert runs[0].finished_at is not None
        snapshots = session.exec(select(StrategyAlphaSnapshot)).all()
        snapshots_by_strategy = {snapshot.strategy_id: snapshot for snapshot in snapshots}
        assert {"deterministic_watchlist_v1", "moving_average_cross"} <= set(snapshots_by_strategy)
        assert snapshots_by_strategy["deterministic_watchlist_v1"].trading_day == summary.latest_review.trading_day
        assert snapshots_by_strategy["deterministic_watchlist_v1"].latest_expectancy == summary.latest_review.expectancy
        assert snapshots_by_strategy["moving_average_cross"].trading_day == summary.latest_review.trading_day
        competition_snapshots = session.exec(select(StrategyCompetitionSnapshot)).all()
        competition_entries = session.exec(select(StrategyCompetitionEntry)).all()
        assert len(competition_snapshots) == 1
        assert competition_snapshots[0].trading_day == summary.latest_review.trading_day
        assert competition_snapshots[0].strategy_count >= 1
        assert any(entry.strategy_id == "deterministic_watchlist_v1" for entry in competition_entries)


def test_daily_run_routes_moving_average_cross_through_paper_runtime():
    class TrendHistoryProvider(FixtureProvider):
        def get_price_history(
            self,
            ticker: str,
            start_date: str | None = None,
            end_date: str | None = None,
            interval: str = "1d",
        ) -> list[PriceHistoryBar]:
            normalized = ticker.strip().upper()
            if normalized != "AAPL":
                return []
            closes = [100.0 for _ in range(40)] + [120.0 + day for day in range(20)]
            return [
                PriceHistoryBar(
                    ticker=normalized,
                    date=(datetime(2026, 1, 1) + timedelta(days=index)).date().isoformat(),
                    open=close - 1,
                    high=close + 1,
                    low=close - 2,
                    close=close,
                    volume=1_000_000,
                    source="fixture_history",
                )
                for index, close in enumerate(closes)
            ]

    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            PaperRiskSetting(
                team_id=workspace.team.id,
                max_daily_orders=5,
                source="multi_strategy_runtime_test",
            )
        )
        session.commit()

        summary = run_daily_paper_trading_loop(session, TrendHistoryProvider())
        moving_average_candidate = next(
            (candidate for candidate in summary.candidates if candidate.strategy_id == "moving_average_cross"),
            None,
        )
        moving_average_order = next(
            (order for order in summary.orders if order.strategy_id == "moving_average_cross"),
            None,
        )
        market_events = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "market_event")).all()
        trade_intent_events = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "trade_intent")).all()

        assert moving_average_candidate is not None
        assert moving_average_candidate.ticker == "AAPL"
        assert moving_average_order is not None
        assert moving_average_order.risk_status == "approved"
        assert any(
            json.loads(event.payload_json).get("intent_id") == moving_average_order.core_intent_id
            for event in trade_intent_events
        )
        assert any(
            (metadata := json.loads(event.payload_json).get("metadata", {})).get("strategy_id") == "moving_average_cross"
            and metadata.get("fast_sma") > metadata.get("slow_sma")
            for event in market_events
        )
        snapshots = session.exec(select(StrategyAlphaSnapshot)).all()
        moving_average_snapshot = next(
            (snapshot for snapshot in snapshots if snapshot.strategy_id == "moving_average_cross"),
            None,
        )
        assert moving_average_snapshot is not None
        assert moving_average_snapshot.trading_day == summary.latest_review.trading_day
        assert moving_average_snapshot.filled_order_count >= 1
        assert moving_average_snapshot.event_chain_count >= 1


def test_daily_run_uses_active_paper_risk_order_capacity_for_candidate_collection():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            PaperRiskSetting(
                team_id=workspace.team.id,
                max_daily_orders=3,
                source="sample_collection_test",
            )
        )
        session.commit()

        summary = run_daily_paper_trading_loop(session, FixtureProvider())

        ordered_candidates = [candidate for candidate in summary.candidates if candidate.status == "ordered"]
        filled_buy_orders = [order for order in summary.orders if order.side == "buy" and order.status == "filled"]

        assert len(ordered_candidates) == 3
        assert len(filled_buy_orders) == 3
        assert [candidate.rank for candidate in ordered_candidates] == [1, 2, 3]


def test_daily_run_prioritizes_real_backtest_candidate(monkeypatch):
    calls: list[dict[str, object]] = []

    class RealHistoryProvider(FixtureProvider):
        def get_price_history(
            self,
            ticker: str,
            start_date: str | None = None,
            end_date: str | None = None,
            interval: str = "1d",
        ) -> list[PriceHistoryBar]:
            normalized = ticker.strip().upper()
            return [
                PriceHistoryBar(
                    ticker=normalized,
                    date=f"2025-01-{day:02d}",
                    open=100.0 + day,
                    high=101.0 + day,
                    low=99.0 + day,
                    close=100.0 + day,
                    volume=1_000_000,
                    source="openbb_yfinance",
                )
                for day in range(1, 8)
            ]

    def fake_candidate_backtests(**kwargs):
        calls.append(kwargs)
        return StrategyCandidateBacktestPayload(
            strategy_id="deterministic_watchlist_v1",
            candidate_count=2,
            real_market_candidate_count=2,
            best_ticker="AAPL",
            summary="Ranked 2 candidates; 1 passed, best ticker AAPL.",
            items=[
                StrategyCandidateBacktestItem(
                    rank=1,
                    ticker="AAPL",
                    recommendation="candidate",
                    score=2.12,
                    reason="真实历史数据；收益为正；Sharpe 1.45；回撤 17.91%；交易 8 笔；结论 candidate",
                    run_id="bt-aapl",
                    status="success",
                    engine="vectorbt",
                    data_source="openbb_yfinance",
                    uses_real_market_data=True,
                    total_net_profit="38.60%",
                    sharpe_ratio="1.45",
                    drawdown="17.91%",
                    total_trades="8",
                ),
                StrategyCandidateBacktestItem(
                    rank=2,
                    ticker="NVDA",
                    recommendation="reject",
                    score=-0.2,
                    reason="真实历史数据；收益未通过；Sharpe 0.21；回撤 39.44%；交易 6 笔；结论 reject",
                    run_id="bt-nvda",
                    status="success",
                    engine="vectorbt",
                    data_source="openbb_yfinance",
                    uses_real_market_data=True,
                    total_net_profit="-0.79%",
                    sharpe_ratio="0.21",
                    drawdown="39.44%",
                    total_trades="6",
                ),
            ],
        )

    monkeypatch.setattr(paper_trading, "run_strategy_candidate_backtests", fake_candidate_backtests, raising=False)

    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, RealHistoryProvider())

        assert calls
        assert "AAPL" in calls[0]["tickers"]
        assert "NVDA" in calls[0]["tickers"]
        ordered = next(candidate for candidate in summary.candidates if candidate.status == "ordered")
        assert ordered.ticker == "AAPL"
        assert ordered.rank == 1
        assert "真实历史数据" in ordered.thesis
        assert "收益为正" in ordered.thesis
        assert "38.60%" in ordered.evidence_summary
        assert "Sharpe 1.45" in ordered.risk_notes
        explanation_events = session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.topic == "trade_explanation")
            .order_by(CoreEventLog.sequence)
        ).all()
        assert explanation_events
        aapl_explanation = next(
            event
            for event in explanation_events
            if json.loads(event.payload_json)["ticker"] == "AAPL"
        )
        payload = json.loads(aapl_explanation.payload_json)
        assert payload["strategy_id"] == "deterministic_watchlist_v1"
        assert payload["decision"] == "candidate"
        assert payload["backtest"]["run_id"] == "bt-aapl"
        assert payload["backtest"]["total_net_profit"] == "38.60%"
        trade_intent_event = session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.topic == "trade_intent")
            .where(CoreEventLog.correlation_id == aapl_explanation.correlation_id)
        ).one()
        assert aapl_explanation.causation_id == trade_intent_event.event_id


def test_daily_run_records_trade_explanations_for_candidates_without_backtests(monkeypatch):
    def fake_candidate_backtests(**kwargs):
        return StrategyCandidateBacktestPayload(
            strategy_id="deterministic_watchlist_v1",
            candidate_count=0,
            real_market_candidate_count=0,
            best_ticker=None,
            items=[],
            summary="No candidate backtests were available.",
        )

    monkeypatch.setattr(paper_trading, "run_strategy_candidate_backtests", fake_candidate_backtests, raising=False)

    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())

        candidate_tickers = {candidate.ticker for candidate in summary.candidates}
        explanation_events = session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.topic == "trade_explanation")
            .order_by(CoreEventLog.sequence)
        ).all()

        assert explanation_events
        explanation_payloads = [json.loads(event.payload_json) for event in explanation_events]
        explained_tickers = {payload["ticker"] for payload in explanation_payloads}
        assert candidate_tickers <= explained_tickers
        nvda_payload = next(payload for payload in explanation_payloads if payload["ticker"] == "NVDA")
        assert nvda_payload["strategy_id"] == "deterministic_watchlist_v1"
        assert nvda_payload["decision"] == "candidate"
        assert "3 条证据支持继续跟踪 NVDA" in nvda_payload["explanation"]
        assert "evidence_count=3" in nvda_payload["evidence"]
        assert "quote_source=fixture" in nvda_payload["evidence"]
        assert "base_score=0.85" in nvda_payload["evidence"]
        assert "backtest_score=0.00" in nvda_payload["evidence"]
        assert "final_score=0.85" in nvda_payload["evidence"]
        assert nvda_payload["backtest"] == {}
        nvda_event = next(event for event in explanation_events if json.loads(event.payload_json)["ticker"] == "NVDA")
        trade_intent_event = session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.topic == "trade_intent")
            .where(CoreEventLog.correlation_id == nvda_event.correlation_id)
        ).one()
        assert nvda_event.causation_id == trade_intent_event.event_id


def test_daily_run_skips_new_buy_candidates_with_required_score_pnl_review(monkeypatch):
    calls = []

    class ReviewAwareRealHistoryProvider(FixtureProvider):
        def get_price_history(
            self,
            ticker: str,
            start_date: str | None = None,
            end_date: str | None = None,
            interval: str = "1d",
        ) -> list[PriceHistoryBar]:
            normalized = ticker.strip().upper()
            return [
                PriceHistoryBar(
                    ticker=normalized,
                    date=f"2025-01-{day:02d}",
                    open=100.0 + day,
                    high=101.0 + day,
                    low=99.0 + day,
                    close=100.0 + day,
                    volume=1_000_000,
                    source="openbb_yfinance",
                )
                for day in range(1, 8)
            ]

    def fake_candidate_backtests(**kwargs):
        calls.append(kwargs)
        return StrategyCandidateBacktestPayload(
            strategy_id="deterministic_watchlist_v1",
            candidate_count=0,
            real_market_candidate_count=0,
            best_ticker=None,
            items=[],
            summary="No candidate backtests were available.",
        )

    monkeypatch.setattr(paper_trading, "run_strategy_candidate_backtests", fake_candidate_backtests, raising=False)

    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            CoreEventLog(
                team_id=workspace.team.id,
                run_id=None,
                event_id="paper_action:review_score_pnl_inversion:AMZN:1:strategy_review",
                topic="strategy_review",
                sequence=1,
                correlation_id="paper_action:review_score_pnl_inversion:AMZN",
                payload_json=(
                    '{"action_code":"review_score_pnl_inversion",'
                    '"inverted_tickers":["AMZN"],'
                    '"review_status":"required"}'
                ),
            )
        )
        session.commit()

        summary = run_daily_paper_trading_loop(
            session,
            ReviewAwareRealHistoryProvider(),
            trading_day="2026-06-20",
            force_new_sample=True,
        )

        assert calls
        assert "AMZN" not in calls[0]["tickers"]
        assert all(candidate.ticker != "AMZN" for candidate in summary.candidates)
        assert all(order.ticker != "AMZN" for order in summary.orders if order.side == "buy")
        explanation_events = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "trade_explanation")).all()
        assert all(json.loads(event.payload_json)["ticker"] != "AMZN" for event in explanation_events)


def test_daily_run_auto_exits_profitable_open_position_before_review():
    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 125.0

        summary = run_daily_paper_trading_loop(session, provider)

        orders = session.exec(select(PaperOrder).order_by(PaperOrder.submitted_at)).all()
        sell_orders = [order for order in orders if order.side == PaperOrderSide.sell]
        assert sell_orders
        assert sell_orders[0].ticker == "AAPL"
        assert sell_orders[0].status.value == "filled"
        assert sell_orders[0].realized_pnl == 50.0
        assert summary.latest_review is not None
        assert summary.latest_review.trade_count == 1
        assert summary.latest_review.expectancy == 50.0
        intent_events = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "trade_intent")).all()
        assert any("Paper exit rule take_profit" in event.payload_json for event in intent_events)


def test_daily_run_persists_core_order_state_events_for_run():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())

        run = session.exec(select(PaperRun)).one()
        events = list(
            session.exec(
                select(CoreEventLog)
                .where(CoreEventLog.run_id == run.id, CoreEventLog.topic == "order_state")
                .order_by(CoreEventLog.sequence)
            ).all()
        )
        states_by_correlation: dict[str, list[str]] = {}
        for event in events:
            states_by_correlation.setdefault(event.correlation_id, []).append(json.loads(event.payload_json)["state"])

        assert len(states_by_correlation) == len(summary.orders)
        assert all(
            states == ["new", "validated", "risk_approved", "sent", "filled"]
            for states in states_by_correlation.values()
        )
        assert all(event.team_id == run.team_id for event in events)


def test_daily_run_persists_full_core_pipeline_events_for_selected_order():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())
        run = session.exec(select(PaperRun)).one()

        events = list_paper_run_events(session, run.id)
        order_correlations = {
            event.correlation_id
            for event in events
            if event.topic == "order_state"
        }
        selected_correlation = next(
            correlation_id
            for correlation_id in order_correlations
            if any(
                event.correlation_id == correlation_id
                and event.topic == "trade_intent"
                and json.loads(event.payload_json)["ticker"] == summary.orders[0].ticker
                for event in events
            )
        )
        selected_chain = [event for event in events if event.correlation_id == selected_correlation]

        assert [event.topic for event in selected_chain] == [
            "market_event",
            "strategy_input",
            "trade_intent",
            "trade_explanation",
            "risk_decision",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
        ]
        market_payload = json.loads(selected_chain[0].payload_json)
        assert market_payload["ticker"] == summary.orders[0].ticker
        assert "action" not in market_payload
        assert "quantity" not in market_payload

        trade_intent_payload = json.loads(selected_chain[2].payload_json)
        ordered_candidate = next(candidate for candidate in summary.candidates if candidate.status == "ordered")
        assert trade_intent_payload["reason"] in ordered_candidate.thesis
        assert trade_intent_payload["ticker"] == ordered_candidate.ticker

        explanation_payload = json.loads(selected_chain[3].payload_json)
        assert explanation_payload["ticker"] == ordered_candidate.ticker
        assert explanation_payload["decision"] == "candidate"
        assert ordered_candidate.evidence_summary in explanation_payload["explanation"]

        risk_payload = json.loads(selected_chain[4].payload_json)
        assert risk_payload["status"] == "approved"
        assert risk_payload["code"] == "approved"


def test_list_paper_run_events_returns_persisted_core_events():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())
        run = session.exec(select(PaperRun)).one()

        events = list_paper_run_events(session, run.id)
        order_events = [event for event in events if event.topic == "order_state"]
        states_by_correlation: dict[str, list[str]] = {}
        for event in order_events:
            states_by_correlation.setdefault(event.correlation_id, []).append(json.loads(event.payload_json)["state"])

        assert len(order_events) == len(summary.orders) * 5
        assert all(event.topic == "order_state" for event in order_events)
        assert all(
            states == ["new", "validated", "risk_approved", "sent", "filled"]
            for states in states_by_correlation.values()
        )


def test_event_ledger_status_replays_latest_completed_run_chain():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())
        run = session.exec(select(PaperRun)).one()

        status = get_event_ledger_status(session)
        replay = replay_paper_run(session, run.id)
        selected_chain = next(chain for chain in status.latest_replay.chains if chain.order_states)

        assert status.total_event_count >= 8
        assert status.latest_run_id == run.id
        assert status.latest_run_status == "completed"
        assert status.latest_run_event_count == replay.event_count
        assert status.replay_ready is True
        assert status.warnings == []
        assert {item.topic for item in status.latest_topic_counts} >= {
            "market_event",
            "strategy_input",
            "trade_intent",
            "risk_decision",
            "order_state",
        }
        assert selected_chain.ticker in {order.ticker for order in summary.orders}
        assert selected_chain.topics == [
            "market_event",
            "strategy_input",
            "trade_intent",
            "trade_explanation",
            "risk_decision",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
        ]
        assert selected_chain.order_states == ["new", "validated", "risk_approved", "sent", "filled"]
        assert selected_chain.terminal_state == "filled"
        assert replay.chains[0].event_count > 0


def test_event_ledger_status_keeps_completed_chain_when_same_day_run_is_repeated():
    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider)
        run_daily_paper_trading_loop(session, provider)

        status = get_event_ledger_status(session)

        assert status.total_event_count > 0
        assert status.latest_run_status == "completed"
        assert status.latest_run_event_count > 1
        assert status.latest_replay is not None
        assert status.replay_ready is True
        assert status.warnings == []
        assert "order_state" in status.latest_replay.chains[0].topics


def test_daily_run_is_idempotent_for_current_trading_day():
    with make_session() as session:
        provider = FixtureProvider()

        first = run_daily_paper_trading_loop(session, provider)
        second = run_daily_paper_trading_loop(session, provider)

        orders = session.exec(select(PaperOrder)).all()
        reviews = session.exec(select(PaperReview)).all()
        runs = session.exec(select(PaperRun).order_by(PaperRun.started_at)).all()
        assert len(orders) == len(first.orders)
        assert len(reviews) == 1
        assert [run.status for run in runs] == [PaperRunStatus.completed]
        assert second.account.cash == first.account.cash
        assert {order.id for order in second.orders} == {order.id for order in first.orders}


def test_daily_run_can_force_post_limit_sample_after_completed_same_day_run():
    with make_session() as session:
        provider = FixtureProvider()

        first = run_daily_paper_trading_loop(session, provider, trading_day="2026-06-12")
        second = run_daily_paper_trading_loop(
            session,
            provider,
            trading_day="2026-06-12",
            force_new_sample=True,
        )

        reviews = session.exec(select(PaperReview)).all()
        runs = session.exec(select(PaperRun).where(PaperRun.trading_day == "2026-06-12")).all()
        completed_runs = [run for run in runs if run.status == PaperRunStatus.completed]
        assert len(completed_runs) == 2
        assert len(reviews) == 2
        assert first.latest_review is not None
        assert second.latest_review is not None
        assert second.latest_review.id != first.latest_review.id
        assert len(second.orders) >= len(first.orders)


def test_daily_run_reruns_when_existing_review_has_no_completed_core_run():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        account = PaperAccount(team_id=workspace.team.id, strategy_id="deterministic_watchlist_v1", name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        legacy_review = PaperReview(
            account_id=account.id,
            team_id=workspace.team.id,
            trading_day="2026-06-13",
            equity=100000,
            cash=100000,
            realized_pnl=0,
            unrealized_pnl=0,
            trade_count=0,
            win_rate=0,
            average_win=0,
            average_loss=0,
            expectancy=0,
            notes="legacy placeholder review",
        )
        session.add(legacy_review)
        session.commit()
        session.refresh(legacy_review)
        session.add(
            PaperRun(
                account_id=account.id,
                team_id=workspace.team.id,
                review_id=legacy_review.id,
                trading_day="2026-06-13",
                trigger=PaperRunTrigger.manual,
                status=PaperRunStatus.skipped,
            )
        )
        session.commit()

        summary = run_daily_paper_trading_loop(session, FixtureProvider(), trading_day="2026-06-13")

        runs = session.exec(select(PaperRun).where(PaperRun.trading_day == "2026-06-13")).all()
        reviews = session.exec(select(PaperReview).where(PaperReview.trading_day == "2026-06-13")).all()
        completed_run = next(run for run in runs if run.status == PaperRunStatus.completed)
        events = list_paper_run_events(session, completed_run.id)
        assert len(reviews) == 2
        assert summary.candidates
        assert summary.orders[0].core_order_id is not None
        order_correlation = next(event.correlation_id for event in events if event.topic == "order_state")
        selected_chain = [event.topic for event in events if event.correlation_id == order_correlation]
        assert selected_chain == [
            "market_event",
            "strategy_input",
            "trade_intent",
            "trade_explanation",
            "risk_decision",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
        ]


def test_daily_run_anchors_candidate_timestamps_to_explicit_trading_day():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider(), trading_day="2026-06-12")

        candidates = session.exec(select(PaperCandidate)).all()
        assert summary.candidates
        assert candidates
        assert {candidate.created_at.date().isoformat() for candidate in candidates} == {"2026-06-12"}


def test_daily_run_reruns_when_completed_run_has_future_dated_candidates():
    with make_session() as session:
        run_daily_paper_trading_loop(session, FixtureProvider(), trading_day="2026-06-12")
        for candidate in session.exec(select(PaperCandidate)).all():
            candidate.created_at = datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc)
            session.add(candidate)
        session.commit()

        summary = run_daily_paper_trading_loop(session, FixtureProvider(), trading_day="2026-06-12")

        runs = session.exec(select(PaperRun).where(PaperRun.trading_day == "2026-06-12")).all()
        completed_runs = [run for run in runs if run.status == PaperRunStatus.completed]
        assert len(completed_runs) == 2
        assert summary.candidates
        assert {candidate.created_at.date().isoformat() for candidate in session.exec(select(PaperCandidate)).all()} == {
            "2026-06-12"
        }


def test_daily_run_rejects_when_same_trading_day_run_is_already_started():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        account = PaperAccount(team_id=workspace.team.id, strategy_id="deterministic_watchlist_v1", name="paper")
        session.add(account)
        session.commit()
        session.add(
            PaperRun(
                account_id=account.id,
                team_id=workspace.team.id,
                trading_day="2026-06-13",
                trigger=PaperRunTrigger.scheduled,
                status=PaperRunStatus.started,
            )
        )
        session.commit()

        with pytest.raises(ValueError, match="already running for 2026-06-13"):
            run_daily_paper_trading_loop(session, FixtureProvider(), trading_day="2026-06-13")

        assert len(session.exec(select(PaperRun)).all()) == 1
        assert session.exec(select(PaperOrder)).all() == []


def test_daily_run_recovers_stale_started_run_before_starting_new_run():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        account = PaperAccount(team_id=workspace.team.id, strategy_id="deterministic_watchlist_v1", name="paper")
        session.add(account)
        session.commit()
        stale_run = PaperRun(
            account_id=account.id,
            team_id=workspace.team.id,
            trading_day="2026-06-13",
            trigger=PaperRunTrigger.scheduled,
            status=PaperRunStatus.started,
            started_at=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
        )
        session.add(stale_run)
        session.commit()

        summary = run_daily_paper_trading_loop(session, FixtureProvider(), trading_day="2026-06-13")

        runs = session.exec(select(PaperRun).order_by(PaperRun.started_at)).all()
        assert summary.latest_review is not None
        assert len(runs) == 2
        assert runs[0].status == PaperRunStatus.failed
        assert "stale running lock expired" in runs[0].error_message
        assert runs[1].status == PaperRunStatus.completed


def test_daily_run_accepts_explicit_trading_day_for_lab_simulation():
    with make_session() as session:
        provider = FixtureProvider()

        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-14")
        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-15")

        reviews = session.exec(select(PaperReview).order_by(PaperReview.trading_day)).all()
        runs = session.exec(select(PaperRun).order_by(PaperRun.trading_day)).all()
        assert [review.trading_day for review in reviews] == ["2026-06-14", "2026-06-15"]
        assert [run.trading_day for run in runs] == ["2026-06-14", "2026-06-15"]
        assert all(run.status == PaperRunStatus.completed for run in runs)


def test_scheduled_daily_run_records_scheduled_trigger():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider(), trigger=PaperRunTrigger.scheduled)
        runs = list_paper_runs(session)

        assert len(runs) == 1
        assert runs[0].trigger == "scheduled"
        assert runs[0].status == "completed"
        assert runs[0].trading_day == summary.latest_review.trading_day


def test_daily_run_marks_run_failed_when_provider_raises():
    with make_session() as session:
        with pytest.raises(RuntimeError, match="quote source failed"):
            run_daily_paper_trading_loop(session, FailingQuoteProvider())

        runs = session.exec(select(PaperRun)).all()
        assert len(runs) == 1
        assert runs[0].status == PaperRunStatus.failed
        assert "quote source failed" in runs[0].error_message
        assert runs[0].finished_at is not None


def test_buy_order_fills_and_updates_cash_and_position():
    with make_session() as session:
        provider = FixtureProvider()

        order = submit_paper_order(session, provider, PaperOrderCreate(ticker="aapl", side="buy", quantity=2))
        summary = get_paper_trading_summary(session, provider)

        assert order.status == "filled"
        assert order.fill_price == 100.0
        assert order.core_order_id is not None
        assert order.core_intent_id is not None
        assert order.risk_status == "approved"
        assert order.risk_code == "approved"
        assert [item["state"] for item in order.state_history] == [
            "new",
            "validated",
            "risk_approved",
            "sent",
            "filled",
        ]
        assert summary.account.cash == 99800.0
        assert summary.account.equity == 100000.0
        assert len(summary.positions) == 1
        assert summary.positions[0].ticker == "AAPL"
        assert summary.positions[0].quantity == 2
        assert summary.positions[0].average_cost == 100.0
        assert summary.positions[0].unrealized_pnl == 0.0


def test_summary_without_as_of_includes_manual_orders_after_latest_market_session(monkeypatch):
    monkeypatch.setattr(paper_trading, "_current_trading_day", lambda: "2026-06-12")
    monkeypatch.setattr(
        paper_trading,
        "utc_now",
        lambda: datetime(2026, 6, 14, 11, 0, tzinfo=timezone.utc),
    )

    with make_session() as session:
        provider = FixtureProvider()

        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        summary = get_paper_trading_summary(session, provider)

        assert summary.account.cash == 99800.0
        assert [order.ticker for order in summary.orders] == ["AAPL"]
        assert [position.ticker for position in summary.positions] == ["AAPL"]


def test_manual_order_rejects_unregistered_strategy():
    with make_session() as session:
        provider = FixtureProvider()

        with pytest.raises(ValueError, match="Strategy is not registered for execution"):
            submit_paper_order(
                session,
                provider,
                PaperOrderCreate(ticker="aapl", side="buy", quantity=2, strategy_id="missing_strategy"),
            )


def test_manual_order_is_tagged_as_manual_override_for_alpha_isolation():
    with make_session() as session:
        provider = FixtureProvider()

        order = submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="aapl", side="buy", quantity=2, strategy_id="deterministic_watchlist_v1"),
        )

        assert order.strategy_id == "deterministic_watchlist_v1:manual_override"


def test_manual_order_event_metadata_marks_manual_override_origin():
    with make_session() as session:
        provider = FixtureProvider()

        submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="aapl", side="buy", quantity=2, strategy_id="deterministic_watchlist_v1"),
        )
        market_event = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "market_event")).first()

        payload = json.loads(market_event.payload_json)
        assert payload["source"] == "manual"
        assert payload["metadata"]["order_origin"] == "manual_override"
        assert payload["metadata"]["order_strategy_id"] == "deterministic_watchlist_v1:manual_override"


def test_run_scoped_system_order_event_metadata_is_not_manual_override():
    with make_session() as session:
        provider = FixtureProvider()
        workspace = get_or_create_default_workspace(session)
        account = PaperAccount(team_id=workspace.team.id, strategy_id="deterministic_watchlist_v1", name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        run = PaperRun(
            account_id=account.id,
            team_id=workspace.team.id,
            trading_day="2026-06-13",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.started,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="aapl", side="buy", quantity=2, strategy_id="deterministic_watchlist_v1"),
            run_id=run.id,
            trading_day=run.trading_day,
        )
        market_event = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "market_event")).first()

        payload = json.loads(market_event.payload_json)
        assert payload["source"] == "market_data"
        assert payload["metadata"]["order_origin"] == "paper_run_order"
        assert payload["metadata"]["order_strategy_id"] == "deterministic_watchlist_v1"


def test_manual_order_persists_ordered_event_chain_with_strategy_id():
    with make_session() as session:
        provider = FixtureProvider()

        order = submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="aapl", side="buy", quantity=2, strategy_id="deterministic_watchlist_v1"),
        )
        events = list(
            session.exec(
                select(CoreEventLog)
                .where(CoreEventLog.correlation_id != str(order.core_order_id))
                .order_by(CoreEventLog.sequence)
            ).all()
        )

        assert [event.sequence for event in events] == list(range(1, 10))
        assert [event.topic for event in events] == [
            "market_event",
            "strategy_input",
            "trade_intent",
            "risk_decision",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
            "order_state",
        ]
        assert len({event.correlation_id for event in events}) == 1


def test_manual_order_streams_full_event_chain_to_redis(monkeypatch):
    redis_client = FakeRedisStreamClient()

    def fake_build_event_bus(**kwargs):
        return RedisStreamEventBus(
            client=redis_client,
            stream_name="trading:events",
            initial_sequence=kwargs.get("initial_sequence", 0),
        )

    monkeypatch.setattr("app.services.paper_trading.build_event_bus", fake_build_event_bus)

    with make_session() as session:
        provider = FixtureProvider()

        submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="aapl", side="buy", quantity=2, strategy_id="deterministic_watchlist_v1"),
        )

    assert [entry[1]["topic"] for entry in redis_client.entries] == [
        "market_event",
        "strategy_input",
        "trade_intent",
        "risk_decision",
        "order_state",
        "order_state",
        "order_state",
        "order_state",
        "order_state",
    ]
    assert [int(entry[1]["sequence"]) for entry in redis_client.entries] == list(range(1, 10))


def test_sell_order_realizes_profit_and_reduces_position():
    with make_session() as session:
        provider = FixtureProvider()

        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 125.0
        order = submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))
        summary = get_paper_trading_summary(session, provider)

        assert order.status == "filled"
        assert order.realized_pnl == 25.0
        assert summary.account.cash == 99925.0
        assert summary.account.realized_pnl == 25.0
        assert summary.account.equity == 100050.0
        assert summary.positions[0].quantity == 1
        assert summary.positions[0].unrealized_pnl == 25.0


def test_review_expectancy_excludes_manual_override_closed_trades():
    with make_session() as session:
        provider = FixtureProvider()

        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 125.0
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))
        account = session.exec(select(PaperAccount)).first()

        review = paper_trading._create_review(session, account, "2026-06-13")

        assert review.trade_count == 0
        assert review.expectancy == 0.0


def test_order_rejects_insufficient_cash_and_oversell():
    with make_session() as session:
        provider = FixtureProvider()

        rejected_buy = submit_paper_order(session, provider, PaperOrderCreate(ticker="MSFT", side="buy", quantity=1000))
        summary = get_paper_trading_summary(session, provider)

        assert rejected_buy.status == "rejected"
        assert rejected_buy.risk_status == "rejected"
        assert rejected_buy.risk_code == "max_order_notional"
        assert "exceeds" in rejected_buy.rejection_reason
        assert summary.account.cash == 100000.0
        assert summary.positions == []

        rejected_sell = submit_paper_order(session, provider, PaperOrderCreate(ticker="NVDA", side="sell", quantity=1))

        assert rejected_sell.status == "rejected"
        assert rejected_sell.risk_status == "rejected"
        assert rejected_sell.risk_code == "insufficient_position_value"


def test_submit_paper_order_uses_paper_risk_setting_daily_order_limit():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            PaperRiskSetting(
                team_id=workspace.team.id,
                max_daily_orders=6,
                source="risk_limit_review",
            )
        )
        session.commit()
        provider = FixtureProvider()

        tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "AAPL"]
        filled_orders = [
            submit_paper_order(session, provider, PaperOrderCreate(ticker=ticker, side="buy", quantity=1))
            for ticker in tickers
        ]
        rejected = submit_paper_order(session, provider, PaperOrderCreate(ticker="MSFT", side="buy", quantity=1))

        assert [order.status for order in filled_orders] == ["filled"] * 6
        assert rejected.status == "rejected"
        assert rejected.risk_code == "max_daily_orders"


def test_manual_daily_order_limit_counts_orders_after_latest_market_session(monkeypatch):
    monkeypatch.setattr(paper_trading, "_current_trading_day", lambda: "2026-06-12")
    monkeypatch.setattr(
        paper_trading,
        "utc_now",
        lambda: datetime(2026, 6, 14, 11, 0, tzinfo=timezone.utc),
    )

    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            PaperRiskSetting(
                team_id=workspace.team.id,
                max_daily_orders=1,
                source="manual_order_limit_test",
            )
        )
        session.commit()
        provider = FixtureProvider()

        first = submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=1))
        second = submit_paper_order(session, provider, PaperOrderCreate(ticker="MSFT", side="buy", quantity=1))

        assert first.status == "filled"
        assert second.status == "rejected"
        assert second.risk_code == "max_daily_orders"


def test_paper_trading_summary_filters_future_orders_for_as_of_trading_day():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        account = PaperAccount(team_id=workspace.team.id, name="paper", cash=50)
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=workspace.team.id,
                ticker="AAPL",
                side=PaperOrderSide.buy,
                order_type="market",
                quantity=1,
                status="filled",
                fill_price=100,
                submitted_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=workspace.team.id,
                ticker="MSFT",
                side=PaperOrderSide.buy,
                order_type="market",
                quantity=1,
                status="rejected",
                risk_code="max_daily_orders",
                submitted_at=datetime(2026, 6, 20, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=workspace.team.id,
                ticker="AAPL",
                side=PaperOrderSide.sell,
                order_type="market",
                quantity=1,
                status="filled",
                fill_price=120,
                realized_pnl=20,
                submitted_at=datetime(2026, 6, 20, 21, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()

        summary = get_paper_trading_summary(session, FixtureProvider(), as_of_trading_day="2026-06-13")

        assert [order.ticker for order in summary.orders] == ["AAPL"]
        assert summary.account.cash == 99900
        assert summary.account.realized_pnl == 0
        assert summary.account.equity == 100000
        assert [(position.ticker, position.quantity) for position in summary.positions] == [("AAPL", 1)]
