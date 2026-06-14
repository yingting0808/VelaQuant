import json

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import AuditLog
from app.services.strategy_lifecycle_audit import get_strategy_lifecycle_audit


def test_strategy_lifecycle_audit_returns_manual_shadow_approval_entries():
    with make_session() as session:
        session.add(
            AuditLog(
                action="strategy_shadow_approved",
                entity_type="strategy",
                entity_id="deterministic_watchlist_v1",
                metadata_json=json.dumps(
                    {
                        "approved_by": "operator",
                        "reason": "Paper gates reviewed.",
                        "previous_stage": "paper",
                        "current_stage": "shadow",
                        "auto_promotion_enabled": False,
                    }
                ),
            )
        )
        session.commit()

        result = get_strategy_lifecycle_audit(session)

        assert result.strategy_id == "deterministic_watchlist_v1"
        assert result.items[0].action == "strategy_shadow_approved"
        assert result.items[0].approved_by == "operator"
        assert result.items[0].previous_stage == "paper"
        assert result.items[0].current_stage == "shadow"
        assert result.items[0].auto_promotion_enabled is False
        assert "1 lifecycle audit" in result.summary


def test_strategy_lifecycle_audit_exposes_kill_execution_disabled_metadata():
    with make_session() as session:
        session.add(
            AuditLog(
                action="strategy_killed",
                entity_type="strategy",
                entity_id="deterministic_watchlist_v1",
                metadata_json=json.dumps(
                    {
                        "approved_by": "operator",
                        "reason": "Negative expectancy reviewed.",
                        "previous_stage": "shadow",
                        "current_stage": "killed",
                        "auto_promotion_enabled": False,
                        "execution_enabled": False,
                    }
                ),
            )
        )
        session.commit()

        result = get_strategy_lifecycle_audit(session)

        assert result.items[0].action == "strategy_killed"
        assert result.items[0].current_stage == "killed"
        assert result.items[0].execution_enabled is False


def test_strategy_lifecycle_audit_handles_empty_history():
    with make_session() as session:
        result = get_strategy_lifecycle_audit(session)

        assert result.items == []
        assert "No lifecycle audit" in result.summary


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
