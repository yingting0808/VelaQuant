from datetime import datetime, timezone

from app.services.alpha_gate_progress import AlphaGateProgressPayload
from app.services.event_ledger import EventLedgerStatus
from app.services.event_bus_health import EventBusHealthPayload
from app.services.live_small_review import LiveSmallReviewPayload
from app.services.paper_scheduler import PaperSchedulerStatus
from app.services.shadow_observation import ShadowObservationSummaryPayload
from app.services.shadow_validation import ShadowValidationPayload
from app.services.strategy_alpha_isolation import StrategyAlphaIsolationPayload
from app.services.strategy_lifecycle import StrategyLifecyclePayload
from app.services.trading_system_readiness import build_trading_system_readiness


def test_trading_system_readiness_is_operational_for_shadow_daily_run():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="shadow"),
        shadow_observations=shadow_observations(can_record=True),
        shadow_validation=shadow_validation(ready=False, remaining=4),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=True),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=True),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "operational"
    assert result.lifecycle_stage == "shadow"
    assert result.shadow_can_record is True
    assert result.shadow_remaining_observations == 4
    assert result.live_or_broker_execution_enabled is False
    assert result.blockers == []
    assert result.manual_override_isolated is True


def test_trading_system_readiness_blocks_when_scheduler_or_ledger_is_not_ready():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=False),
        lifecycle=lifecycle(stage="shadow"),
        shadow_observations=shadow_observations(can_record=True),
        shadow_validation=shadow_validation(ready=False, remaining=4),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=False),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=True),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "blocked"
    assert "scheduler_not_running" in result.blockers
    assert "event_ledger_not_replayable" in result.blockers


def test_trading_system_readiness_blocks_when_event_ledger_has_broken_trade_chains():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="shadow"),
        shadow_observations=shadow_observations(can_record=True),
        shadow_validation=shadow_validation(ready=False, remaining=4),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(
            replay_ready=True,
            traceable_chain_count=4,
            complete_order_chain_count=3,
            broken_chain_count=1,
            traceability_ratio=0.75,
        ),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=True),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "blocked"
    assert result.event_ledger_traceable_chain_count == 4
    assert result.event_ledger_complete_order_chain_count == 3
    assert result.event_ledger_broken_chain_count == 1
    assert result.event_ledger_traceability_ratio == 0.75
    assert "event_ledger_broken_trade_chains" in result.blockers


def test_trading_system_readiness_blocks_when_redis_event_bus_is_not_ready():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="shadow"),
        shadow_observations=shadow_observations(can_record=True),
        shadow_validation=shadow_validation(ready=False, remaining=4),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=True),
        event_bus=event_bus(ready=False),
        alpha_gates=alpha_gates(alpha_ready=True),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "blocked"
    assert result.event_bus_ready is False
    assert result.event_bus_mode == "redis"
    assert "event_bus_not_ready" in result.blockers


def test_trading_system_readiness_blocks_when_lifecycle_is_ahead_of_alpha_validation():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="shadow"),
        shadow_observations=shadow_observations(can_record=False),
        shadow_validation=shadow_validation(ready=False, remaining=5),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=True),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=False),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "blocked"
    assert "lifecycle_stage_ahead_of_alpha_validation" in result.blockers
    assert "paper_alpha_validation" in result.pending_gates


def test_trading_system_readiness_blocks_when_strategy_is_killed():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="killed"),
        shadow_observations=shadow_observations(can_record=False),
        shadow_validation=shadow_validation(ready=False, remaining=5),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=True),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=False),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "blocked"
    assert "strategy_killed" in result.blockers
    assert result.live_or_broker_execution_enabled is False


def test_trading_system_readiness_blocks_when_strategy_requires_kill_review():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="shadow", can_kill=True),
        shadow_observations=shadow_observations(can_record=True),
        shadow_validation=shadow_validation(ready=False, remaining=4),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=True),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=True),
        alpha_isolation=alpha_isolation(isolated=True),
    )

    assert result.status == "blocked"
    assert "strategy_kill_review_required" in result.blockers
    assert result.live_or_broker_execution_enabled is False


def test_trading_system_readiness_blocks_when_manual_override_alpha_isolation_fails():
    result = build_trading_system_readiness(
        scheduler=scheduler(running=True),
        lifecycle=lifecycle(stage="paper"),
        shadow_observations=shadow_observations(can_record=False),
        shadow_validation=shadow_validation(ready=False, remaining=5),
        live_small_review=live_small_review(can_request=False),
        event_ledger=event_ledger(replay_ready=True),
        event_bus=event_bus(ready=True),
        alpha_gates=alpha_gates(alpha_ready=False),
        alpha_isolation=alpha_isolation(isolated=False),
    )

    assert result.status == "blocked"
    assert result.manual_override_isolated is False
    assert "manual_override_alpha_leak" in result.blockers


def scheduler(*, running: bool) -> PaperSchedulerStatus:
    return PaperSchedulerStatus(
        enabled=True,
        running=running,
        job_count=1 if running else 0,
        job_id="paper_trading_daily_run",
        cron="30 6 * * *",
        timezone="Asia/Shanghai",
        next_run_at=datetime(2026, 6, 14, 6, 30, tzinfo=timezone.utc),
        last_checked_at=datetime(2026, 6, 13, 13, 30, tzinfo=timezone.utc),
        can_run_now=True,
        execution_gate="ready_to_run",
        market_date="2026-06-13",
        trading_day="2026-06-13",
        is_market_session=True,
        session_closed=True,
        calendar_provider="pandas_market_calendars",
        gate_reason="current_session_closed",
    )


def lifecycle(*, stage: str, can_kill: bool = False) -> StrategyLifecyclePayload:
    return StrategyLifecyclePayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        current_stage=stage,
        recommended_stage="killed" if can_kill else stage,
        recommended_action="kill_review" if can_kill else "hold_current_stage",
        gate_status="blocked" if can_kill else "watch",
        promotion_gate="negative_expectancy" if can_kill else "eligible_for_shadow",
        can_promote=False,
        can_kill=can_kill,
        auto_actions_enabled=False,
        rules=[],
        missing_capabilities=[],
        summary="lifecycle",
    )


def shadow_observations(*, can_record: bool) -> ShadowObservationSummaryPayload:
    return ShadowObservationSummaryPayload(
        can_record_shadow_observation=can_record,
        latest=None,
        items=[],
        summary="shadow observations",
    )


def shadow_validation(*, ready: bool, remaining: int) -> ShadowValidationPayload:
    return ShadowValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        shadow_ready=ready,
        status="shadow_validated" if ready else "collecting",
        observation_count=5 - remaining,
        observing_count=5 - remaining,
        blocked_count=0,
        latest_trading_day="2026-06-30",
        min_observations_required=5,
        remaining_observations=remaining,
        residual_risk_count=2,
        blockers=[] if ready else ["shadow_observation_sample"],
        summary="shadow validation",
    )


def live_small_review(*, can_request: bool) -> LiveSmallReviewPayload:
    return LiveSmallReviewPayload(
        status="ready_for_manual_review" if can_request else "blocked",
        strategy_id="deterministic_watchlist_v1",
        can_request_live_small_review=can_request,
        recommended_stage="live_small" if can_request else "shadow",
        auto_promotion_enabled=False,
        checklist=[],
        residual_risks=[],
        summary="live small",
    )


def event_ledger(
    *,
    replay_ready: bool,
    traceable_chain_count: int | None = None,
    complete_order_chain_count: int | None = None,
    broken_chain_count: int | None = None,
    traceability_ratio: float | None = None,
) -> EventLedgerStatus:
    return EventLedgerStatus(
        total_event_count=680 if replay_ready else 0,
        latest_run_id=None,
        latest_run_status="completed" if replay_ready else "missing",
        latest_run_event_count=30 if replay_ready else 0,
        latest_topic_counts=[],
        latest_correlation_count=6 if replay_ready else 0,
        traceable_chain_count=traceable_chain_count if traceable_chain_count is not None else (6 if replay_ready else 0),
        complete_order_chain_count=(
            complete_order_chain_count if complete_order_chain_count is not None else (6 if replay_ready else 0)
        ),
        broken_chain_count=broken_chain_count if broken_chain_count is not None else 0,
        traceability_ratio=traceability_ratio if traceability_ratio is not None else (1.0 if replay_ready else 0.0),
        replay_ready=replay_ready,
        warnings=[] if replay_ready else ["latest_run_has_no_events"],
        summary="event ledger",
        latest_replay=None,
    )


def event_bus(*, ready: bool) -> EventBusHealthPayload:
    return EventBusHealthPayload(
        mode="redis",
        stream_name="trading:events",
        redis_url_configured=True,
        redis_available=ready,
        stream_length=42 if ready else None,
        ready=ready,
        error=None if ready else "connection refused",
        summary="event bus",
    )


def alpha_gates(*, alpha_ready: bool) -> AlphaGateProgressPayload:
    return AlphaGateProgressPayload(
        alpha_ready=alpha_ready,
        validation_level="paper_validated" if alpha_ready else "collecting",
        passed_gates=8 if alpha_ready else 7,
        total_gates=8,
        items=[],
        summary="alpha gates",
    )


def alpha_isolation(*, isolated: bool) -> StrategyAlphaIsolationPayload:
    return StrategyAlphaIsolationPayload(
        strategy_id="deterministic_watchlist_v1",
        isolated=isolated,
        strategy_order_count=8,
        manual_override_order_count=2,
        manual_override_event_chain_count=2,
        filtered_event_chain_count=8,
        summary="alpha isolation",
    )
