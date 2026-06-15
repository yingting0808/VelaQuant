import json
from datetime import timedelta

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import CoreEventLog, utc_now
from app.services.paper_strategy_reviews import get_paper_strategy_reviews
from app.services.workspace import get_or_create_default_workspace


def test_paper_strategy_reviews_return_latest_strategy_review_events_first():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        older_at = utc_now() - timedelta(minutes=10)
        newer_at = utc_now()
        _add_strategy_review(
            session,
            team_id=workspace.team.id,
            event_id="paper_action:review_score_pnl_inversion:MSFT:1:strategy_review",
            sequence=1,
            published_at=older_at,
            payload={
                "action_code": "review_score_pnl_inversion",
                "title": "复盘评分背离",
                "detail": "MSFT 评分与盈亏反向。",
                "evidence": ["inverted_tickers=MSFT", "score_pnl_inversion_count=1"],
                "inverted_tickers": ["MSFT"],
                "review_status": "required",
            },
        )
        _add_strategy_review(
            session,
            team_id=workspace.team.id,
            event_id="paper_action:review_score_pnl_inversion:AAPL,NVDA:2:strategy_review",
            sequence=2,
            published_at=newer_at,
            payload={
                "action_code": "review_score_pnl_inversion",
                "title": "复盘评分背离",
                "detail": "AAPL/NVDA 评分与盈亏反向。",
                "evidence": ["inverted_tickers=AAPL,NVDA", "score_pnl_inversion_count=2"],
                "inverted_tickers": ["AAPL", "NVDA"],
                "review_status": "required",
            },
        )
        session.commit()

        payload = get_paper_strategy_reviews(session)

        assert payload.review_count == 2
        assert payload.items[0].event_id == "paper_action:review_score_pnl_inversion:AAPL,NVDA:2:strategy_review"
        assert payload.items[0].inverted_tickers == ["AAPL", "NVDA"]
        assert payload.items[0].evidence == ["inverted_tickers=AAPL,NVDA", "score_pnl_inversion_count=2"]
        assert payload.items[1].event_id == "paper_action:review_score_pnl_inversion:MSFT:1:strategy_review"
        assert "2 recorded" in payload.summary
        assert "AAPL,NVDA" in payload.summary


def test_paper_strategy_reviews_ignore_malformed_strategy_review_payloads():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            CoreEventLog(
                team_id=workspace.team.id,
                run_id=None,
                event_id="broken-review",
                topic="strategy_review",
                sequence=1,
                correlation_id="paper_action:review_score_pnl_inversion:broken",
                causation_id=None,
                payload_json="{not json",
                published_at=utc_now(),
            )
        )
        session.commit()

        payload = get_paper_strategy_reviews(session)

        assert payload.review_count == 0
        assert payload.items == []
        assert payload.summary == "No strategy reviews are recorded yet."


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _add_strategy_review(
    session: Session,
    *,
    team_id: object,
    event_id: str,
    sequence: int,
    published_at,
    payload: dict,
) -> None:
    session.add(
        CoreEventLog(
            team_id=team_id,
            run_id=None,
            event_id=event_id,
            topic="strategy_review",
            sequence=sequence,
            correlation_id=event_id.rsplit(":", 2)[0],
            causation_id=None,
            payload_json=json.dumps(payload, ensure_ascii=False),
            published_at=published_at,
        )
    )
