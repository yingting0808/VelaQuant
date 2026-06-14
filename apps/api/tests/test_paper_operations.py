from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperReview,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
    Team,
)
from app.services.paper_operations import (
    get_paper_operations_history,
    get_paper_operations_status,
    quarantine_legacy_manual_future_runs,
    repair_paper_operations_event_ledger,
)


TRADING_DAY = "2026-06-12"


def test_operations_status_marks_today_missing_as_runnable():
    with make_session() as session:
        team, _account = _team_and_account(session)

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "not_started"
        assert status.can_retry_today is True
        assert status.event_ledger_ready is False
        assert status.blockers == ["daily_run_missing"]
        assert status.recommended_action == "run_daily_paper_trading"


def test_operations_status_marks_completed_review_with_events_healthy():
    with make_session() as session:
        team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        run = _run(account, TRADING_DAY, PaperRunStatus.completed, review_id=review.id)
        session.add(run)
        session.flush()
        _add_complete_order_chain(session, team.id, run)
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "completed"
        assert status.health_status == "ready"
        assert status.can_retry_today is False
        assert status.event_ledger_ready is True
        assert status.latest_run_event_count == 5
        assert status.blockers == []
        assert status.recommended_action == "hold_until_next_session"


def test_operations_status_surfaces_latest_scheduler_decision_event():
    with make_session() as session:
        team, _account = _team_and_account(session)
        session.add(
            CoreEventLog(
                team_id=team.id,
                run_id=None,
                event_id="paper_scheduler:2026-06-11:1:scheduler_decision",
                topic="scheduler_decision",
                sequence=1,
                correlation_id="paper_scheduler:2026-06-11",
                causation_id=None,
                payload_json=(
                    '{"executed":true,"execution_gate":"ready_to_run","market_date":"2026-06-11",'
                    '"trading_day":"2026-06-11","reason":"current_session_closed",'
                    '"summary":"Scheduled paper trading completed."}'
                ),
            )
        )
        session.add(
            CoreEventLog(
                team_id=team.id,
                run_id=None,
                event_id="paper_scheduler:2026-06-12:2:scheduler_decision",
                topic="scheduler_decision",
                sequence=2,
                correlation_id="paper_scheduler:2026-06-12",
                causation_id=None,
                payload_json=(
                    '{"executed":false,"execution_gate":"ready_to_run","market_date":"2026-06-12",'
                    '"trading_day":"2026-06-12","reason":"current_session_closed",'
                    '"summary":"Scheduled paper trading failed: paper loop failed."}'
                ),
            )
        )
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.latest_scheduler_decision == "failed"
        assert status.latest_scheduler_decision_trading_day == TRADING_DAY
        assert status.latest_scheduler_decision_reason == "current_session_closed"
        assert status.latest_scheduler_decision_summary == "Scheduled paper trading failed: paper loop failed."
        assert status.latest_scheduler_decision_at is not None


def test_operations_status_prefers_completed_trade_run_over_newer_duplicate_skipped_run():
    with make_session() as session:
        team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        completed_run = _run(account, TRADING_DAY, PaperRunStatus.completed, review_id=review.id)
        skipped_run = _run(account, TRADING_DAY, PaperRunStatus.skipped, review_id=review.id)
        skipped_run.started_at = completed_run.started_at.replace(tzinfo=timezone.utc) + timedelta(minutes=1)
        session.add(review)
        session.add(completed_run)
        session.add(skipped_run)
        session.flush()
        _add_complete_order_chain(session, team.id, completed_run)
        _add_run_audit_event(session, team.id, skipped_run)
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "completed"
        assert status.latest_run_id == completed_run.id
        assert status.today_run_id == completed_run.id
        assert status.latest_run_event_count == 5
        assert status.event_ledger_ready is True
        assert status.summary == "Daily paper pipeline is complete for the trading day; hold until the next session."


def test_operations_status_blocks_completed_review_with_broken_event_chain():
    with make_session() as session:
        team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        run = _run(account, TRADING_DAY, PaperRunStatus.completed, review_id=review.id)
        session.add(run)
        session.flush()
        session.add(
            CoreEventLog(
                team_id=team.id,
                run_id=run.id,
                event_id="filled",
                topic="order_state",
                sequence=1,
                correlation_id="corr-1",
                causation_id="missing",
                payload_json='{"state":"filled","ticker":"NVDA"}',
            )
        )
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "completed"
        assert status.health_status == "blocked"
        assert status.event_ledger_ready is False
        assert status.latest_run_event_count == 1
        assert status.blockers == ["event_ledger_not_replayable"]
        assert status.recommended_action == "repair_event_ledger"


def test_operations_status_treats_trade_intent_only_chain_as_replayable():
    with make_session() as session:
        team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        run = _run(account, TRADING_DAY, PaperRunStatus.completed, review_id=review.id)
        session.add(run)
        session.flush()
        _add_trade_intent_chain_without_order_state(session, team.id, run)
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "completed"
        assert status.health_status == "ready"
        assert status.event_ledger_ready is True
        assert status.latest_run_event_count == 3
        assert status.blockers == []
        assert status.recommended_action == "hold_until_next_session"


def test_operations_status_ignores_future_trading_day_runs_for_latest_baseline():
    with make_session() as session:
        team, account = _team_and_account(session)
        today_review = _review(account, TRADING_DAY)
        today_run = _run(account, TRADING_DAY, PaperRunStatus.skipped, review_id=today_review.id)
        future_run = _run(account, "2026-06-30", PaperRunStatus.completed)
        future_run.started_at = datetime(2026, 6, 13, 23, 0, tzinfo=timezone.utc)
        session.add(today_review)
        session.add(today_run)
        session.add(future_run)
        session.flush()
        _add_run_audit_event(session, team.id, today_run)
        _add_complete_order_chain(session, team.id, future_run, correlation_id="future-corr")
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "skipped"
        assert status.latest_run_id == today_run.id
        assert status.latest_run_trading_day == TRADING_DAY
        assert status.today_run_id == today_run.id
        assert status.event_ledger_ready is True


def test_operations_status_reports_legacy_manual_future_run_contamination():
    with make_session() as session:
        team, account = _team_and_account(session)
        today_review = _review(account, TRADING_DAY)
        today_run = _run(account, TRADING_DAY, PaperRunStatus.skipped, review_id=today_review.id)
        future_run = _run(account, "2026-06-30", PaperRunStatus.completed)
        session.add(today_review)
        session.add(today_run)
        session.add(future_run)
        session.flush()
        _add_run_audit_event(session, team.id, today_run)
        _add_complete_order_chain(session, team.id, future_run, correlation_id="future-corr")
        session.commit()

        status = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)

        assert status.run_state == "skipped"
        assert status.legacy_manual_future_run_count == 1
        assert status.latest_legacy_manual_future_trading_day == "2026-06-30"
        assert status.data_quality_warnings == ["legacy_manual_future_runs_detected"]
        assert status.summary == (
            "Daily paper pipeline is complete for the trading day; hold until the next session. "
            "Data quality warning: legacy manual future-dated runs detected."
        )


def test_operations_status_marks_failed_today_as_retryable():
    with make_session() as session:
        _team, account = _team_and_account(session)
        run = _run(account, TRADING_DAY, PaperRunStatus.failed, error_message="quote source failed")
        session.add(run)
        session.commit()

        status = get_paper_operations_status(session, team_id=account.team_id, trading_day=TRADING_DAY)

        assert status.run_state == "failed"
        assert status.health_status == "blocked"
        assert status.can_retry_today is True
        assert status.latest_error == "quote source failed"
        assert "latest_run_failed" in status.blockers
        assert status.recommended_action == "retry_daily_paper_trading"


def test_operations_status_marks_stale_running_run_as_retryable():
    with make_session() as session:
        _team, account = _team_and_account(session)
        run = _run(account, TRADING_DAY, PaperRunStatus.started)
        run.started_at = datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc)
        session.add(run)
        session.commit()

        status = get_paper_operations_status(session, team_id=account.team_id, trading_day=TRADING_DAY)

        assert status.run_state == "running"
        assert status.health_status == "blocked"
        assert status.can_retry_today is False
        assert "running_run_stale" in status.blockers
        assert status.recommended_action == "retry_daily_paper_trading"


def test_operations_status_blocks_completed_run_without_event_ledger():
    with make_session() as session:
        _team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        session.add(_run(account, TRADING_DAY, PaperRunStatus.completed, review_id=review.id))
        session.commit()

        status = get_paper_operations_status(session, team_id=account.team_id, trading_day=TRADING_DAY)

        assert status.run_state == "completed"
        assert status.can_retry_today is False
        assert status.event_ledger_ready is False
        assert status.blockers == ["event_ledger_not_replayable"]
        assert status.recommended_action == "repair_event_ledger"


def test_operations_history_aggregates_recent_run_health():
    with make_session() as session:
        team, account = _team_and_account(session)
        healthy_review = _review(account, "2026-06-11")
        healthy_run = _run(account, "2026-06-11", PaperRunStatus.completed, review_id=healthy_review.id)
        skipped_review = _review(account, "2026-06-12")
        skipped_run = _run(account, "2026-06-12", PaperRunStatus.skipped, review_id=skipped_review.id)
        session.add(healthy_review)
        session.add(skipped_review)
        session.add(healthy_run)
        session.add(skipped_run)
        session.flush()
        _add_complete_order_chain(session, team.id, healthy_run, correlation_id="corr-1")
        _add_run_audit_event(session, team.id, skipped_run)
        session.commit()

        history = get_paper_operations_history(session, team_id=team.id, limit=5)

        assert history.window_size == 2
        assert history.completed_days == 2
        assert history.failed_days == 0
        assert history.blocked_days == 0
        assert history.replayable_days == 2
        assert history.review_days == 2
        assert history.completion_rate == 1
        assert history.replay_rate == 1
        assert history.latest_health_status == "ready"
        assert history.items[0].trading_day == "2026-06-12"
        assert history.items[0].event_count == 1


def test_operations_history_marks_failed_and_unreplayable_runs():
    with make_session() as session:
        team, account = _team_and_account(session)
        failed_run = _run(account, "2026-06-12", PaperRunStatus.failed, error_message="provider timeout")
        failed_run.started_at = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
        completed_without_events = _run(account, "2026-06-11", PaperRunStatus.completed)
        completed_without_events.started_at = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
        session.add(failed_run)
        session.add(completed_without_events)
        session.commit()

        history = get_paper_operations_history(session, team_id=team.id, limit=5)

        assert history.window_size == 2
        assert history.completed_days == 0
        assert history.failed_days == 1
        assert history.blocked_days == 2
        assert history.replayable_days == 0
        assert history.review_days == 0
        assert history.completion_rate == 0
        assert history.replay_rate == 0
        assert history.latest_health_status == "blocked"
        assert history.items[0].blockers == ["latest_run_failed"]
        assert history.items[1].blockers == ["review_missing", "event_ledger_not_replayable"]


def test_repair_event_ledger_backfills_audit_event_for_completed_or_skipped_runs():
    with make_session() as session:
        team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        run = _run(account, TRADING_DAY, PaperRunStatus.skipped, review_id=review.id)
        session.add(review)
        session.add(run)
        session.commit()

        before = get_paper_operations_history(session, team_id=team.id)
        assert before.items[0].blockers == ["event_ledger_not_replayable"]

        repair = repair_paper_operations_event_ledger(session, team_id=team.id, limit=5)

        assert repair.scanned_runs == 1
        assert repair.repaired_runs == 1
        assert repair.skipped_runs == 0
        assert repair.items[0].event_created is True
        assert repair.items[0].topic == "run_audit"

        after = get_paper_operations_history(session, team_id=team.id)
        assert after.items[0].health_status == "ready"
        assert after.items[0].event_count == 1
        assert after.replay_rate == 1


def test_repair_event_ledger_reports_integrity_failed_when_events_are_present_but_broken():
    with make_session() as session:
        team, account = _team_and_account(session)
        review = _review(account, TRADING_DAY)
        run = _run(account, TRADING_DAY, PaperRunStatus.completed, review_id=review.id)
        session.add(review)
        session.add(run)
        session.flush()
        session.add(
            CoreEventLog(
                team_id=team.id,
                run_id=run.id,
                event_id="filled",
                topic="order_state",
                sequence=1,
                correlation_id="corr-1",
                causation_id="missing",
                payload_json='{"state":"filled","ticker":"NVDA"}',
            )
        )
        session.commit()

        repair = repair_paper_operations_event_ledger(session, team_id=team.id, limit=5)

        assert repair.scanned_runs == 1
        assert repair.repaired_runs == 0
        assert repair.skipped_runs == 1
        assert repair.items[0].event_created is False
        assert repair.items[0].reason == "event_ledger_integrity_failed"


def test_repair_event_ledger_does_not_backfill_failed_or_running_runs():
    with make_session() as session:
        team, account = _team_and_account(session)
        failed_run = _run(account, "2026-06-13", PaperRunStatus.failed, error_message="provider timeout")
        running_run = _run(account, "2026-06-12", PaperRunStatus.started)
        session.add(failed_run)
        session.add(running_run)
        session.commit()

        repair = repair_paper_operations_event_ledger(session, team_id=team.id, limit=5)

        assert repair.scanned_runs == 2
        assert repair.repaired_runs == 0
        assert repair.skipped_runs == 2
        assert {item.reason for item in repair.items} == {"status_not_repairable"}
        assert session.exec(select(CoreEventLog)).all() == []


def test_quarantine_legacy_manual_future_runs_marks_runs_as_simulation_and_audits():
    with make_session() as session:
        team, account = _team_and_account(session)
        today_review = _review(account, TRADING_DAY)
        today_run = _run(account, TRADING_DAY, PaperRunStatus.skipped, review_id=today_review.id)
        future_run = _run(account, "2026-06-30", PaperRunStatus.completed)
        session.add(today_review)
        session.add(today_run)
        session.add(future_run)
        session.flush()
        _add_run_audit_event(session, team.id, today_run)
        _add_complete_order_chain(session, team.id, future_run, correlation_id="future-corr")
        session.commit()

        before = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)
        assert before.legacy_manual_future_run_count == 1

        quarantine = quarantine_legacy_manual_future_runs(session, team_id=team.id, trading_day=TRADING_DAY)

        session.refresh(future_run)
        assert quarantine.scanned_runs == 1
        assert quarantine.quarantined_runs == 1
        assert quarantine.items[0].previous_trigger == "manual"
        assert quarantine.items[0].new_trigger == "simulation"
        assert future_run.trigger == PaperRunTrigger.simulation
        audit_events = session.exec(
            select(CoreEventLog).where(
                CoreEventLog.run_id == future_run.id,
                CoreEventLog.topic == "run_audit",
            )
        ).all()
        assert any("legacy_manual_future_run_quarantined" in event.payload_json for event in audit_events)

        after = get_paper_operations_status(session, team_id=team.id, trading_day=TRADING_DAY)
        assert after.legacy_manual_future_run_count == 0
        assert after.data_quality_warnings == []

        second = quarantine_legacy_manual_future_runs(session, team_id=team.id, trading_day=TRADING_DAY)
        assert second.scanned_runs == 0
        assert second.quarantined_runs == 0


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _team_and_account(session: Session) -> tuple[Team, PaperAccount]:
    team = Team(name="Paper Ops")
    session.add(team)
    session.commit()
    session.refresh(team)
    account = PaperAccount(team_id=team.id, name="paper")
    session.add(account)
    session.commit()
    session.refresh(account)
    return team, account


def _review(account: PaperAccount, trading_day: str) -> PaperReview:
    review = PaperReview(
        account_id=account.id,
        team_id=account.team_id,
        trading_day=trading_day,
        equity=100000,
        cash=98000,
        realized_pnl=0,
        unrealized_pnl=0,
        trade_count=0,
        win_rate=0,
        average_win=0,
        average_loss=0,
        expectancy=0,
        notes="fixture",
    )
    return review


def _run(
    account: PaperAccount,
    trading_day: str,
    status: PaperRunStatus,
    *,
    review_id=None,
    error_message: str | None = None,
) -> PaperRun:
    return PaperRun(
        account_id=account.id,
        team_id=account.team_id,
        review_id=review_id,
        trading_day=trading_day,
        trigger=PaperRunTrigger.manual,
        status=status,
        candidates_count=1,
        orders_count=1,
        positions_count=1,
        error_message=error_message,
    )


def _add_complete_order_chain(
    session: Session,
    team_id,
    run: PaperRun,
    *,
    correlation_id: str = "corr-1",
) -> None:
    events = [
        ("market", "market_event", 1, None, '{"ticker":"NVDA"}'),
        ("input", "strategy_input", 2, "market", '{"ticker":"NVDA"}'),
        ("intent", "trade_intent", 3, "input", '{"ticker":"NVDA"}'),
        ("risk", "risk_decision", 4, "intent", '{"ticker":"NVDA","status":"approved"}'),
        ("filled", "order_state", 5, "risk", '{"ticker":"NVDA","state":"filled"}'),
    ]
    for event_id, topic, sequence, causation_id, payload_json in events:
        session.add(
            CoreEventLog(
                team_id=team_id,
                run_id=run.id,
                event_id=f"{correlation_id}-{event_id}",
                topic=topic,
                sequence=sequence,
                correlation_id=correlation_id,
                causation_id=f"{correlation_id}-{causation_id}" if causation_id is not None else None,
                payload_json=payload_json,
            )
        )


def _add_trade_intent_chain_without_order_state(session: Session, team_id, run: PaperRun) -> None:
    events = [
        ("market", "market_event", 1, None, '{"ticker":"NVDA"}'),
        ("input", "strategy_input", 2, "market", '{"ticker":"NVDA"}'),
        ("intent", "trade_intent", 3, "input", '{"ticker":"NVDA"}'),
    ]
    for event_id, topic, sequence, causation_id, payload_json in events:
        session.add(
            CoreEventLog(
                team_id=team_id,
                run_id=run.id,
                event_id=f"incomplete-{event_id}",
                topic=topic,
                sequence=sequence,
                correlation_id="incomplete-corr",
                causation_id=f"incomplete-{causation_id}" if causation_id is not None else None,
                payload_json=payload_json,
            )
        )


def _add_run_audit_event(session: Session, team_id, run: PaperRun) -> None:
    session.add(
        CoreEventLog(
            team_id=team_id,
            run_id=run.id,
            event_id=f"{run.id}:run_audit",
            topic="run_audit",
            sequence=1,
            correlation_id=str(run.id),
            payload_json='{"status":"skipped"}',
        )
    )
