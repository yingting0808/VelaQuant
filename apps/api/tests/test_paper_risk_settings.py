from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
    Team,
)
from app.services.paper_risk_profile import get_paper_risk_profile
from app.services.paper_risk_limit_review import get_paper_risk_limit_review
from app.services.paper_risk_settings import apply_paper_risk_limit_recommendation


def test_apply_paper_risk_limit_recommendation_updates_paper_only_profile_and_audits():
    with make_session() as session:
        team = Team(name="Risk Settings")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        for index in range(6):
            session.add(
                _order(
                    account,
                    side=PaperOrderSide.buy,
                    risk_code="max_daily_orders",
                    submitted_at=datetime(2026, 6, 1, 14, index, tzinfo=timezone.utc),
                )
            )
        session.commit()

        result = apply_paper_risk_limit_recommendation(session, team_id=team.id)

        profile = get_paper_risk_profile(session, team_id=team.id)
        audit_events = session.exec(
            select(CoreEventLog).where(CoreEventLog.team_id == team.id).where(CoreEventLog.topic == "risk_config_audit")
        ).all()

        assert result.applied is True
        assert result.previous_max_daily_orders == 5
        assert result.applied_max_daily_orders == 6
        assert result.live_change_allowed is False
        assert profile.max_daily_orders == 6
        assert profile.risk_engine == "Trading Core RiskEngine"
        assert len(audit_events) == 1
        assert "paper_risk_limit_recommendation_applied" in audit_events[0].payload_json


def test_risk_limit_review_does_not_reapply_same_historical_rejections_after_setting_update():
    with make_session() as session:
        team = Team(name="Risk Settings")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        for index in range(6):
            session.add(
                _order(
                    account,
                    side=PaperOrderSide.buy,
                    risk_code="max_daily_orders",
                    submitted_at=datetime(2026, 6, 1, 14, index, tzinfo=timezone.utc),
                )
            )
        session.commit()

        apply_paper_risk_limit_recommendation(session, team_id=team.id)
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                risk_code="max_daily_orders",
                submitted_at=datetime(2026, 6, 20, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        profile = get_paper_risk_profile(session, team_id=team.id)
        review = get_paper_risk_limit_review(session, team_id=team.id)

        assert profile.max_daily_orders == 6
        assert review.status == "hold"
        assert review.current_max_daily_orders == 6
        assert review.recommended_paper_max_daily_orders == 6
        assert "awaiting_post_limit_sample" in review.blockers


def test_risk_limit_review_counts_completed_run_after_limit_update_even_when_orders_are_trading_day_anchored():
    with make_session() as session:
        team = Team(name="Risk Settings")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        for index in range(6):
            session.add(
                _order(
                    account,
                    side=PaperOrderSide.buy,
                    risk_code="max_daily_orders",
                    submitted_at=datetime(2026, 6, 1, 14, index, tzinfo=timezone.utc),
                )
            )
        session.commit()

        apply_paper_risk_limit_recommendation(session, team_id=team.id)
        setting_event = session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.team_id == team.id)
            .where(CoreEventLog.topic == "risk_config_audit")
        ).one()
        setting_time = setting_event.published_at
        run = PaperRun(
            account_id=account.id,
            team_id=team.id,
            trading_day="2026-06-12",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.completed,
            started_at=setting_time + timedelta(minutes=1),
            finished_at=setting_time + timedelta(minutes=2),
        )
        session.add(run)
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                risk_code="max_daily_orders",
                submitted_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        review = get_paper_risk_limit_review(session, team_id=team.id)

        assert review.status == "review_required"
        assert review.current_max_daily_orders == 6
        assert review.recommended_paper_max_daily_orders == 7
        assert "awaiting_post_limit_sample" not in review.blockers


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _order(
    account: PaperAccount,
    *,
    side: PaperOrderSide,
    risk_code: str,
    submitted_at: datetime,
) -> PaperOrder:
    return PaperOrder(
        account_id=account.id,
        team_id=account.team_id,
        ticker="NVDA",
        side=side,
        order_type="market",
        quantity=1,
        status=PaperOrderStatus.rejected,
        realized_pnl=0,
        risk_code=risk_code,
        rejection_reason="Orders today 5 reached limit 5.",
        submitted_at=submitted_at,
    )
