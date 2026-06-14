from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
    PaperReview,
    Team,
)
from app.services.alpha_validation import build_alpha_validation, get_alpha_validation


def test_alpha_validation_real_market_backtest_gate_reads_strategy_history(monkeypatch):
    monkeypatch.setattr(
        "app.services.alpha_validation.read_latest_backtest",
        lambda: _backtest_result(
            strategy_id="moving_average_cross",
            status="success",
            uses_real_market_data=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.alpha_validation.read_backtest_history",
        lambda: [
            _backtest_result(
                strategy_id="moving_average_cross",
                status="success",
                uses_real_market_data=True,
            ),
            _backtest_result(
                strategy_id="deterministic_watchlist_v1",
                status="success",
                uses_real_market_data=True,
            ),
        ],
        raising=False,
    )

    payload = build_alpha_validation(
        reviews=[
            _review("2026-06-08", expectancy=0.8, equity=100100),
            _review("2026-06-09", expectancy=1.1, equity=100250),
            _review("2026-06-10", expectancy=1.3, equity=100460),
            _review("2026-06-11", expectancy=1.0, equity=100620),
            _review("2026-06-12", expectancy=1.4, equity=100900),
        ],
        orders=_orders(filled=34, closed=12),
        event_chain_count=50,
        has_real_market_backtest=__import__(
            "app.services.alpha_validation",
            fromlist=["_has_real_market_backtest"],
        )._has_real_market_backtest("deterministic_watchlist_v1"),
    )

    assert payload.has_real_market_backtest is True
    assert "real_market_backtest" not in payload.blockers


def test_alpha_validation_blocks_without_consecutive_positive_reviews():
    payload = build_alpha_validation(
        reviews=[
            _review("2026-06-10", expectancy=1.2, equity=100200),
            _review("2026-06-11", expectancy=-0.5, equity=100100),
            _review("2026-06-12", expectancy=1.1, equity=100350),
        ],
        orders=_orders(filled=12, closed=4),
        event_chain_count=120,
    )

    assert payload.alpha_ready is False
    assert payload.consecutive_positive_expectancy_days == 1
    assert "consecutive_positive_expectancy" in payload.blockers
    assert "closed_trade_sample" in payload.blockers
    assert payload.validation_level == "collecting"


def test_alpha_validation_marks_stable_positive_paper_sample_ready():
    payload = build_alpha_validation(
        reviews=[
            _review("2026-06-08", expectancy=0.8, equity=100100),
            _review("2026-06-09", expectancy=1.1, equity=100250),
            _review("2026-06-10", expectancy=1.3, equity=100460),
            _review("2026-06-11", expectancy=1.0, equity=100620),
            _review("2026-06-12", expectancy=1.5, equity=100900),
        ],
        orders=_orders(filled=34, closed=12),
        event_chain_count=160,
        has_real_market_backtest=True,
    )

    assert payload.alpha_ready is True
    assert payload.validation_level == "paper_validated"
    assert payload.blockers == []
    assert payload.consecutive_positive_expectancy_days == 5
    assert payload.closed_trade_count == 12


def test_alpha_validation_blocks_without_real_market_backtest_evidence():
    payload = build_alpha_validation(
        reviews=[
            _review("2026-06-08", expectancy=0.8, equity=100100),
            _review("2026-06-09", expectancy=1.1, equity=100250),
            _review("2026-06-10", expectancy=1.3, equity=100460),
            _review("2026-06-11", expectancy=1.0, equity=100620),
            _review("2026-06-12", expectancy=1.5, equity=100900),
        ],
        orders=_orders(filled=34, closed=12),
        event_chain_count=160,
        has_real_market_backtest=False,
    )

    assert payload.alpha_ready is False
    assert payload.validation_level == "collecting"
    assert payload.has_real_market_backtest is False
    assert "real_market_backtest" in payload.blockers


def test_alpha_validation_reads_runtime_database_facts(monkeypatch):
    monkeypatch.setattr("app.services.alpha_validation._has_real_market_backtest", lambda strategy_id: False)
    with make_session() as session:
        team = Team(name="Alpha Validation")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        for day in range(1, 6):
            session.add(
                PaperReview(
                    account_id=account.id,
                    team_id=team.id,
                    trading_day=f"2026-06-0{day}",
                    equity=100000 + day * 100,
                    cash=90000,
                    realized_pnl=day * 10,
                    unrealized_pnl=day * 20,
                    trade_count=day,
                    win_rate=0.6,
                    average_win=20,
                    average_loss=-10,
                    expectancy=1.0,
                    notes="fixture",
                )
            )
        for index, order in enumerate(_orders(filled=34, closed=12)):
            order.team_id = team.id
            order.account_id = account.id
            session.add(order)
            if index < 160:
                session.add(
                    CoreEventLog(
                        team_id=team.id,
                        event_id=f"event-{index}",
                        topic="order_state",
                        sequence=index + 1,
                        correlation_id=str(uuid4()),
                        payload_json="{}",
                    )
                )
        session.commit()

        payload = get_alpha_validation(session, team_id=team.id, as_of_trading_day="2026-06-14")

        assert payload.alpha_ready is False
        assert payload.review_day_count == 5
        assert payload.event_chain_count == 34
        assert "real_market_backtest" in payload.blockers


def test_alpha_validation_reads_runtime_real_market_backtest_gate(monkeypatch):
    with make_session() as session:
        team = Team(name="Alpha Validation With Backtest")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        for day in range(1, 6):
            session.add(
                PaperReview(
                    account_id=account.id,
                    team_id=team.id,
                    trading_day=f"2026-06-0{day}",
                    equity=100000 + day * 100,
                    cash=90000,
                    realized_pnl=day * 10,
                    unrealized_pnl=day * 20,
                    trade_count=day,
                    win_rate=0.6,
                    average_win=20,
                    average_loss=-10,
                    expectancy=1.0,
                    notes="fixture",
                )
            )
        for index, order in enumerate(_orders(filled=34, closed=12)):
            order.team_id = team.id
            order.account_id = account.id
            session.add(order)
            if index < 160:
                session.add(
                    CoreEventLog(
                        team_id=team.id,
                        event_id=f"event-{index}",
                        topic="order_state",
                        sequence=index + 1,
                        correlation_id=str(uuid4()),
                        payload_json="{}",
                    )
                )
        session.commit()
        monkeypatch.setattr("app.services.alpha_validation._has_real_market_backtest", lambda strategy_id: True)

        payload = get_alpha_validation(session, team_id=team.id, as_of_trading_day="2026-06-14")

        assert payload.alpha_ready is True
        assert payload.has_real_market_backtest is True
        assert "real_market_backtest" not in payload.blockers


def test_alpha_validation_excludes_manual_override_orders_from_strategy_sample():
    with make_session() as session:
        team = Team(name="Alpha Manual Override Filter")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        for day in range(1, 6):
            session.add(
                PaperReview(
                    account_id=account.id,
                    team_id=team.id,
                    trading_day=f"2026-06-0{day}",
                    equity=100000 + day * 100,
                    cash=90000,
                    realized_pnl=day * 10,
                    unrealized_pnl=day * 20,
                    trade_count=day,
                    win_rate=0.6,
                    average_win=20,
                    average_loss=-10,
                    expectancy=1.0,
                    notes="fixture",
                )
            )
        for index, order in enumerate(_orders(filled=34, closed=12)):
            order.team_id = team.id
            order.account_id = account.id
            order.strategy_id = "deterministic_watchlist_v1:manual_override"
            session.add(order)
            session.add(
                CoreEventLog(
                    team_id=team.id,
                    event_id=f"event-{index}",
                    topic="order_state",
                    sequence=index + 1,
                    correlation_id=str(uuid4()),
                    payload_json="{}",
                )
            )
        session.commit()

        payload = get_alpha_validation(session, team_id=team.id)

        assert payload.alpha_ready is False
        assert payload.filled_order_count == 0
        assert payload.closed_trade_count == 0
        assert "filled_order_sample" in payload.blockers
        assert "closed_trade_sample" in payload.blockers


def test_alpha_validation_ignores_future_trading_day_facts_for_readiness():
    with make_session() as session:
        team = Team(name="Alpha Future Filter")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=team.id,
                trading_day="2026-06-13",
                equity=100000,
                cash=90000,
                realized_pnl=0,
                unrealized_pnl=0,
                trade_count=1,
                win_rate=0.5,
                average_win=10,
                average_loss=-5,
                expectancy=0.2,
                notes="today",
            )
        )
        for day in range(14, 19):
            session.add(
                PaperReview(
                    account_id=account.id,
                    team_id=team.id,
                    trading_day=f"2026-06-{day}",
                    equity=101000 + day,
                    cash=90000,
                    realized_pnl=100,
                    unrealized_pnl=0,
                    trade_count=10,
                    win_rate=0.8,
                    average_win=20,
                    average_loss=-5,
                    expectancy=2.0,
                    notes="future simulation",
                )
            )
        future_run = PaperRun(
            account_id=account.id,
            team_id=team.id,
            trading_day="2026-06-18",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.completed,
        )
        session.add(future_run)
        session.flush()
        for index, order in enumerate(_orders(filled=34, closed=12)):
            order.team_id = team.id
            order.account_id = account.id
            order.submitted_at = datetime(2026, 6, 18, 21, 0, tzinfo=timezone.utc)
            session.add(order)
            session.add(
                CoreEventLog(
                    team_id=team.id,
                    run_id=future_run.id,
                    event_id=f"future-event-{index}",
                    topic="order_state",
                    sequence=index + 1,
                    correlation_id=str(uuid4()),
                    payload_json="{}",
                )
            )
        session.commit()

        payload = get_alpha_validation(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert payload.alpha_ready is False
        assert payload.review_day_count == 1
        assert payload.filled_order_count == 0
        assert payload.event_chain_count == 0
        assert payload.latest_expectancy == 0.2


def test_alpha_validation_does_not_count_scheduler_decisions_as_trade_events():
    with make_session() as session:
        team = Team(name="Alpha Audit Event Filter")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=team.id,
                trading_day="2026-06-13",
                equity=100000,
                cash=90000,
                realized_pnl=0,
                unrealized_pnl=0,
                trade_count=1,
                win_rate=0.5,
                average_win=10,
                average_loss=-5,
                expectancy=0.2,
                notes="today",
            )
        )
        session.add(
            CoreEventLog(
                team_id=team.id,
                run_id=None,
                event_id="paper_scheduler:2026-06-13:1:scheduler_decision",
                topic="scheduler_decision",
                sequence=1,
                correlation_id="paper_scheduler:2026-06-13",
                payload_json='{"executed":false,"reason":"market_closed"}',
                published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        payload = get_alpha_validation(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert payload.event_chain_count == 0
        assert "event_ledger_populated" in payload.blockers


def test_alpha_validation_counts_trade_correlations_not_raw_event_rows():
    with make_session() as session:
        team = Team(name="Alpha Correlation Count")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        run = PaperRun(
            account_id=account.id,
            team_id=team.id,
            trading_day="2026-06-13",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.completed,
        )
        session.add(run)
        session.flush()
        for index, topic in enumerate(["market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"]):
            session.add(
                CoreEventLog(
                    team_id=team.id,
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
                team_id=team.id,
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

        payload = get_alpha_validation(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert payload.event_chain_count == 2


def test_alpha_validation_excludes_manual_override_event_chains():
    with make_session() as session:
        team = Team(name="Alpha Manual Event Filter")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
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
                    team_id=team.id,
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

        payload = get_alpha_validation(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert payload.event_chain_count == 0


def test_alpha_validation_uses_latest_review_per_trading_day():
    old_review = _review("2026-06-13", expectancy=-2.0, equity=99000)
    old_review.created_at = datetime(2026, 6, 13, 1, 0, tzinfo=timezone.utc)
    latest_review = _review("2026-06-13", expectancy=2.0, equity=101000)
    latest_review.created_at = datetime(2026, 6, 13, 2, 0, tzinfo=timezone.utc)
    prior_day = _review("2026-06-12", expectancy=1.0, equity=100500)
    prior_day.created_at = datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)

    payload = build_alpha_validation(
        reviews=[old_review, latest_review, prior_day],
        orders=_orders(filled=2, closed=1),
        event_chain_count=10,
    )

    assert payload.review_day_count == 2
    assert payload.latest_expectancy == 2.0
    assert payload.average_expectancy == 1.5
    assert payload.consecutive_positive_expectancy_days == 2


def _review(day: str, *, expectancy: float, equity: float) -> PaperReview:
    return PaperReview(
        account_id=uuid4(),
        team_id=uuid4(),
        trading_day=day,
        equity=equity,
        cash=90000,
        realized_pnl=0,
        unrealized_pnl=0,
        trade_count=0,
        win_rate=0,
        average_win=0,
        average_loss=0,
        expectancy=expectancy,
        notes="fixture",
    )


def _orders(*, filled: int, closed: int) -> list[PaperOrder]:
    orders: list[PaperOrder] = []
    for index in range(filled):
        side = PaperOrderSide.sell if index < closed else PaperOrderSide.buy
        orders.append(
            PaperOrder(
                account_id=uuid4(),
                team_id=uuid4(),
                ticker="AAPL",
                side=side,
                quantity=1,
                status=PaperOrderStatus.filled,
                fill_price=100,
                realized_pnl=1 if side == PaperOrderSide.sell else 0,
            )
        )
    return orders


def _backtest_result(*, strategy_id: str, status: str, uses_real_market_data: bool):
    return SimpleNamespace(
        run_id=f"run-{strategy_id}-{status}",
        strategy_id=strategy_id,
        status=status,
        uses_real_market_data=uses_real_market_data,
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
