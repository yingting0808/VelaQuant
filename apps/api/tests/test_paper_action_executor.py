from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine

from app.data.providers.mock import MockMarketDataProvider
from app.domain.models import PaperAccount, PaperOrder, PaperOrderSide, PaperOrderStatus
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
                submitted_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
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
