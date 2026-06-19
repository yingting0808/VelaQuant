from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from app.data.providers.mock import MockMarketDataProvider
from app.domain.models import CoreEventLog, PaperAccount, PaperOrder, PaperOrderSide, PaperOrderStatus, StrategyAlphaSnapshot
from app.services import paper_action_executor
from app.services.paper_action_executor import execute_paper_primary_action, queue_paper_primary_action
from app.services.paper_risk_profile import get_paper_risk_profile
from app.services.workspace import get_or_create_default_workspace


def test_execute_primary_action_applies_safe_paper_risk_recommendation_and_advances_next_action():
    with make_session() as session:
        team = get_or_create_default_workspace(session).team
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=team.id,
                ticker="NVDA",
                side=PaperOrderSide.buy,
                order_type="market",
                quantity=1,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="max_daily_orders",
                rejection_reason="Orders today 5 reached limit 5.",
                submitted_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        result = execute_paper_primary_action(session, MockMarketDataProvider())

        profile = get_paper_risk_profile(session, team_id=team.id)
        assert result.executed is True
        assert result.action_code == "apply_paper_risk_limit_recommendation"
        assert result.next_primary_action == "collect_post_limit_sample"
        assert result.result is not None
        assert result.result["applied"] is True
        assert profile.max_daily_orders == 6


def test_execute_primary_action_collects_post_limit_sample_by_running_daily_loop(monkeypatch):
    calls = []

    def action_plan(session):
        return SimpleNamespace(primary_action="collect_post_limit_sample")

    def daily_run(session, provider, **kwargs):
        calls.append((session, provider, kwargs))
        return SimpleNamespace(model_dump=lambda mode="json": {"daily_run": "executed"})

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", action_plan)
    monkeypatch.setattr(paper_action_executor, "run_daily_paper_trading_loop", daily_run)

    with make_session() as session:
        provider = MockMarketDataProvider()

        result = execute_paper_primary_action(session, provider)

        assert result.executed is True
        assert result.action_code == "collect_post_limit_sample"
        assert result.result == {"daily_run": "executed"}
        assert calls == [(session, provider, {"force_new_sample": True})]


def test_execute_primary_action_continue_validation_records_alpha_snapshot(monkeypatch):
    def action_plan(session):
        return SimpleNamespace(primary_action="continue_paper_validation")

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", action_plan)

    with make_session() as session:
        team = get_or_create_default_workspace(session).team

        result = execute_paper_primary_action(session, MockMarketDataProvider())

        snapshots = session.exec(select(StrategyAlphaSnapshot)).all()
        assert result.executed is True
        assert result.status == "completed"
        assert result.action_code == "continue_paper_validation"
        assert result.result is not None
        result_snapshots = result.result["snapshots"]
        result_strategy_ids = {snapshot["strategy_id"] for snapshot in result_snapshots}
        stored_strategy_ids = {snapshot.strategy_id for snapshot in snapshots}
        assert {"deterministic_watchlist_v1", "moving_average_cross"} <= result_strategy_ids
        assert {"deterministic_watchlist_v1", "moving_average_cross"} <= stored_strategy_ids
        assert {snapshot["team_id"] for snapshot in result_snapshots} == {str(team.id)}
        assert {snapshot.team_id for snapshot in snapshots} == {team.id}


def test_execute_primary_action_hold_until_next_session_returns_waiting_scheduler_status(monkeypatch):
    plan = SimpleNamespace(
        primary_action="hold_until_next_session",
        items=[
            SimpleNamespace(
                detail="当前交易日 Alpha 验证快照已记录，等待下一交易日继续收集样本。",
            )
        ],
    )
    scheduler = SimpleNamespace(
        running=True,
        next_run_at=datetime(2026, 6, 15, 6, 30, tzinfo=timezone.utc),
        execution_gate="market_closed",
        trading_day="2026-06-12",
        model_dump=lambda mode="json": {
            "running": True,
            "next_run_at": "2026-06-15T06:30:00+00:00",
            "execution_gate": "market_closed",
            "trading_day": "2026-06-12",
        },
    )

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", lambda session: plan)
    monkeypatch.setattr(paper_action_executor, "get_paper_scheduler_status", lambda: scheduler)

    with make_session() as session:
        result = execute_paper_primary_action(session, MockMarketDataProvider())

        assert result.executed is False
        assert result.status == "waiting"
        assert result.action_code == "hold_until_next_session"
        assert result.next_primary_action == "hold_until_next_session"
        assert result.result == {
            "reason": "当前交易日 Alpha 验证快照已记录，等待下一交易日继续收集样本。",
            "scheduler": {
                "running": True,
                "next_run_at": "2026-06-15T06:30:00+00:00",
                "execution_gate": "market_closed",
                "trading_day": "2026-06-12",
            },
        }
        assert "waiting for the next scheduled paper run" in result.summary


def test_execute_primary_action_score_pnl_inversion_returns_review_required(monkeypatch):
    plan = SimpleNamespace(
        primary_action="review_score_pnl_inversion",
        items=[
            SimpleNamespace(
                action_code="review_score_pnl_inversion",
                title="复盘评分背离",
                detail="检测到 AMZN 的候选评分方向与观测盈亏相反。",
                evidence=["inverted_tickers=AMZN"],
            )
        ],
    )

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", lambda session: plan)

    with make_session() as session:
        result = execute_paper_primary_action(session, MockMarketDataProvider())

        assert result.executed is False
        assert result.status == "review_required"
        assert result.action_code == "review_score_pnl_inversion"
        assert result.next_primary_action == "review_score_pnl_inversion"
        assert result.result is not None
        assert result.result["title"] == "复盘评分背离"
        assert result.result["detail"] == "检测到 AMZN 的候选评分方向与观测盈亏相反。"
        assert result.result["evidence"] == ["inverted_tickers=AMZN"]
        assert result.result["audit_event_created"] is True
        assert result.result["audit_event_id"] == "paper_action:review_score_pnl_inversion:AMZN:1:strategy_review"
        assert "manual review required" in result.summary


def test_execute_primary_action_expectancy_quality_returns_review_required(monkeypatch):
    plan = SimpleNamespace(
        primary_action="review_expectancy_quality",
        items=[
            SimpleNamespace(
                action_code="review_expectancy_quality",
                title="复盘期望质量",
                detail="策略级 Alpha 期望质量未达标。",
                evidence=[
                    "latest_alpha_snapshot_trading_day=2026-06-18",
                    "latest_positive_expectancy_current=0",
                ],
            )
        ],
    )

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", lambda session: plan)

    with make_session() as session:
        result = execute_paper_primary_action(session, MockMarketDataProvider())

        assert result.executed is False
        assert result.status == "review_required"
        assert result.action_code == "review_expectancy_quality"
        assert result.result is not None
        assert result.result["title"] == "复盘期望质量"
        assert result.result["evidence"] == [
            "latest_alpha_snapshot_trading_day=2026-06-18",
            "latest_positive_expectancy_current=0",
        ]
        assert result.result["audit_event_created"] is True
        assert result.result["audit_event_id"] == "paper_action:review_expectancy_quality:expectancy:1:strategy_review"
        assert "manual review required" in result.summary


def test_execute_primary_action_score_pnl_inversion_persists_strategy_review_event(monkeypatch):
    plan = SimpleNamespace(
        primary_action="review_score_pnl_inversion",
        items=[
            SimpleNamespace(
                action_code="review_score_pnl_inversion",
                title="复盘评分背离",
                detail="检测到 AMZN 的候选评分方向与观测盈亏相反。",
                evidence=[
                    "Alpha gate progress: 5/10 gates passed.",
                    "score_pnl_inversion_remaining=1",
                    "inverted_tickers=AMZN",
                ],
            )
        ],
    )

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", lambda session: plan)

    with make_session() as session:
        team = get_or_create_default_workspace(session).team

        result = execute_paper_primary_action(session, MockMarketDataProvider())

        events = session.exec(select(CoreEventLog).where(CoreEventLog.topic == "strategy_review")).all()
        assert len(events) == 1
        event = events[0]
        assert event.team_id == team.id
        assert event.run_id is None
        assert event.correlation_id == "paper_action:review_score_pnl_inversion:AMZN"
        assert result.result is not None
        assert result.result["audit_event_created"] is True
        assert result.result["audit_event_id"] == event.event_id
        assert '"action_code":"review_score_pnl_inversion"' in event.payload_json
        assert '"inverted_tickers":["AMZN"]' in event.payload_json
        assert '"review_status":"required"' in event.payload_json


def test_queue_primary_action_collects_post_limit_sample_without_blocking(monkeypatch):
    class CapturingTasks:
        def __init__(self):
            self.tasks = []

        def add_task(self, fn, *args, **kwargs):
            self.tasks.append((fn, args, kwargs))

    def action_plan(session):
        return SimpleNamespace(primary_action="collect_post_limit_sample")

    def daily_run(session, provider):
        raise AssertionError("daily run should be deferred to a background task")

    monkeypatch.setattr(paper_action_executor, "get_paper_action_plan", action_plan)
    monkeypatch.setattr(paper_action_executor, "run_daily_paper_trading_loop", daily_run)

    with make_session() as session:
        tasks = CapturingTasks()

        result = queue_paper_primary_action(session, tasks)

        assert result.executed is False
        assert result.queued is True
        assert result.status == "queued"
        assert result.action_code == "collect_post_limit_sample"
        assert result.next_primary_action == "collect_post_limit_sample"
        assert result.result == {"status_url": "/api/mvp/paper-trading/runs"}
        assert len(tasks.tasks) == 1


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
