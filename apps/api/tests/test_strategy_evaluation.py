from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

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
)
from app.services.strategy_evaluation import StrategyEvaluationReadiness, evaluate_current_paper_strategy
from app.services.workspace import get_or_create_default_workspace


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


def _candidate(session: Session, account: PaperAccount, ticker: str = "NVDA") -> PaperCandidate:
    candidate = PaperCandidate(
        team_id=account.team_id,
        ticker=ticker,
        action=PaperOrderSide.buy,
        rank=1,
        confidence=0.82,
        thesis=f"{ticker} positive event.",
        risk_notes="test",
        evidence_summary="test evidence",
        proposed_quantity=1,
        status=PaperCandidateStatus.ordered,
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


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
    expectancy: float,
    trade_count: int,
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
        trade_count=trade_count,
        win_rate=0.6,
        average_win=50,
        average_loss=20,
        expectancy=expectancy,
        readiness=PaperReadiness.collecting,
        notes="test",
        created_at=created_at,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


def test_strategy_evaluation_reports_insufficient_sample_without_trades():
    with make_session() as session:
        evaluation = evaluate_current_paper_strategy(session, as_of_trading_day="2026-06-30")

        assert evaluation.strategy_id == "deterministic_watchlist_v1"
        assert evaluation.sample_size == 0
        assert evaluation.filled_order_count == 0
        assert evaluation.readiness == StrategyEvaluationReadiness.insufficient_sample
        assert evaluation.promotion_gate == "blocked"


def test_strategy_evaluation_counts_signals_orders_and_precision():
    with make_session() as session:
        account = _account(session)
        _candidate(session, account)
        _filled_buy(session, account)
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=115,
                market_value=115,
                unrealized_pnl=15,
            )
        )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session)

        assert evaluation.sample_size == 1
        assert evaluation.filled_order_count == 1
        assert evaluation.rejected_order_count == 0
        assert evaluation.signal_precision == 1.0
        assert evaluation.event_chain_count == 0


def test_strategy_evaluation_excludes_manual_override_orders_from_strategy_sample():
    with make_session() as session:
        account = _account(session)
        _candidate(session, account)
        _filled_buy(session, account, "NVDA")
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=account.team_id,
                strategy_id="deterministic_watchlist_v1:manual_override",
                ticker="AAPL",
                side=PaperOrderSide.buy,
                quantity=1,
                status=PaperOrderStatus.filled,
                fill_price=100,
                risk_status="approved",
                risk_code="approved",
            )
        )
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=115,
                market_value=115,
                unrealized_pnl=15,
            )
        )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session)

        assert evaluation.filled_order_count == 1
        assert evaluation.rejected_order_count == 0


def test_strategy_evaluation_calculates_max_drawdown_from_reviews():
    with make_session() as session:
        account = _account(session)
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        _review(session, account, "2026-06-01", 100000, 0, 0, start)
        _review(session, account, "2026-06-02", 110000, 0, 0, start + timedelta(days=1))
        _review(session, account, "2026-06-03", 99000, 0, 0, start + timedelta(days=2))

        evaluation = evaluate_current_paper_strategy(session)

        assert evaluation.max_drawdown == 0.1


def test_strategy_evaluation_marks_positive_large_sample_as_paper_ready():
    with make_session() as session:
        account = _account(session)
        for index in range(30):
            _candidate(session, account, f"T{index}")
            _filled_buy(session, account, f"T{index}")
            session.add(
                PaperPosition(
                    account_id=account.id,
                    team_id=account.team_id,
                    ticker=f"T{index}",
                    quantity=1,
                    average_cost=100,
                    last_price=110,
                    market_value=110,
                    unrealized_pnl=10,
                )
            )
        _review(
            session,
            account,
            "2026-06-30",
            103000,
            12.5,
            30,
            datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session, as_of_trading_day="2026-06-30")

        assert evaluation.filled_order_count == 30
        assert evaluation.expectancy == 12.5
        assert evaluation.readiness == StrategyEvaluationReadiness.paper_ready
        assert evaluation.promotion_gate == "eligible_for_shadow"
        assert evaluation.stability_score > 0.8


def test_strategy_evaluation_ignores_future_trading_day_facts_for_readiness():
    with make_session() as session:
        account = _account(session)
        future_run = PaperRun(
            account_id=account.id,
            team_id=account.team_id,
            trading_day="2026-06-30",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.completed,
        )
        session.add(future_run)
        session.flush()
        for index in range(30):
            order = _filled_buy(session, account, f"F{index}")
            order.submitted_at = datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc)
            session.add(
                PaperPosition(
                    account_id=account.id,
                    team_id=account.team_id,
                    ticker=f"F{index}",
                    quantity=1,
                    average_cost=100,
                    last_price=110,
                    market_value=110,
                    unrealized_pnl=10,
                )
            )
            session.add(
                CoreEventLog(
                    team_id=account.team_id,
                    run_id=future_run.id,
                    event_id=f"future-event-{index}",
                    topic="order_state",
                    sequence=index + 1,
                    correlation_id=f"future-{index}",
                    payload_json="{}",
                )
            )
        _review(
            session,
            account,
            "2026-06-30",
            103000,
            12.5,
            30,
            datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session, as_of_trading_day="2026-06-13")

        assert evaluation.filled_order_count == 0
        assert evaluation.event_chain_count == 0
        assert evaluation.expectancy == 0
        assert evaluation.readiness == StrategyEvaluationReadiness.insufficient_sample
        assert evaluation.promotion_gate == "blocked"


def test_strategy_evaluation_ignores_scheduler_decision_audit_events():
    with make_session() as session:
        account = _account(session)
        session.add(
            CoreEventLog(
                team_id=account.team_id,
                run_id=None,
                event_id="paper_scheduler:2026-06-13:1:scheduler_decision",
                topic="scheduler_decision",
                sequence=1,
                correlation_id="paper_scheduler:2026-06-13",
                payload_json='{"executed":false}',
                published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session, as_of_trading_day="2026-06-13")

        assert evaluation.event_chain_count == 0


def test_strategy_evaluation_counts_trade_correlations_not_raw_event_rows():
    with make_session() as session:
        account = _account(session)
        run = PaperRun(
            account_id=account.id,
            team_id=account.team_id,
            trading_day="2026-06-13",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.completed,
        )
        session.add(run)
        session.flush()
        for index, topic in enumerate(["market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"]):
            session.add(
                CoreEventLog(
                    team_id=account.team_id,
                    run_id=run.id,
                    event_id=f"corr-1-{topic}",
                    topic=topic,
                    sequence=index + 1,
                    correlation_id="corr-1",
                    payload_json="{}",
                    published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
                )
            )
        session.add(
            CoreEventLog(
                team_id=account.team_id,
                run_id=run.id,
                event_id="corr-2-market",
                topic="market_event",
                sequence=6,
                correlation_id="corr-2",
                payload_json="{}",
                published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session, as_of_trading_day="2026-06-13")

        assert evaluation.event_chain_count == 2


def test_strategy_evaluation_excludes_manual_override_event_chains():
    with make_session() as session:
        account = _account(session)
        for index, (topic, payload) in enumerate(
            [
                (
                    "market_event",
                    '{"ticker":"AAPL","metadata":{"order_strategy_id":"deterministic_watchlist_v1:manual_override"}}',
                ),
                ("strategy_input", "{}"),
                ("trade_intent", "{}"),
                ("risk_decision", "{}"),
                ("order_state", "{}"),
            ]
        ):
            session.add(
                CoreEventLog(
                    team_id=account.team_id,
                    run_id=None,
                    event_id=f"manual-corr-{topic}",
                    topic=topic,
                    sequence=index + 1,
                    correlation_id="manual-corr",
                    payload_json=payload,
                    published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
                )
            )
        session.commit()

        evaluation = evaluate_current_paper_strategy(session, as_of_trading_day="2026-06-13")

        assert evaluation.event_chain_count == 0
