from app.services.live_small_review import build_live_small_review_packet
from app.services.shadow_observation_health import ShadowObservationHealthPayload
from app.services.shadow_review import ShadowReviewPayload
from app.services.shadow_validation import ShadowValidationPayload
from app.services.strategy_lifecycle import StrategyLifecyclePayload


def test_live_small_review_blocks_until_strategy_is_in_shadow_stage():
    packet = build_live_small_review_packet(
        lifecycle=lifecycle_payload(current_stage="paper"),
        shadow_validation=shadow_validation_payload(shadow_ready=True),
        shadow_health=shadow_health_payload(stable=True),
        shadow_review=shadow_review_payload(can_request=True),
    )

    assert packet.status == "blocked"
    assert packet.can_request_live_small_review is False
    assert packet.recommended_stage == "shadow"
    assert packet.auto_promotion_enabled is False
    assert any(item.code == "current_stage_shadow" and not item.passed for item in packet.checklist)


def test_live_small_review_ready_only_after_shadow_validation_passes_in_shadow_stage():
    packet = build_live_small_review_packet(
        lifecycle=lifecycle_payload(current_stage="shadow"),
        shadow_validation=shadow_validation_payload(shadow_ready=True),
        shadow_health=shadow_health_payload(stable=True),
        shadow_review=shadow_review_payload(can_request=True),
    )

    assert packet.status == "ready_for_manual_review"
    assert packet.can_request_live_small_review is True
    assert packet.recommended_stage == "live_small"
    assert all(item.passed for item in packet.checklist)
    assert "manual" in packet.summary.lower()


def test_live_small_review_blocks_when_shadow_observation_sample_is_not_ready():
    packet = build_live_small_review_packet(
        lifecycle=lifecycle_payload(current_stage="shadow"),
        shadow_validation=shadow_validation_payload(shadow_ready=False),
        shadow_health=shadow_health_payload(stable=False),
        shadow_review=shadow_review_payload(can_request=True),
    )

    assert packet.status == "blocked"
    assert packet.can_request_live_small_review is False
    assert any(item.code == "shadow_validation_passed" and not item.passed for item in packet.checklist)
    assert any(item.code == "shadow_observation_sample" and not item.passed for item in packet.checklist)


def test_live_small_review_blocks_when_shadow_health_is_not_stable():
    packet = build_live_small_review_packet(
        lifecycle=lifecycle_payload(current_stage="shadow"),
        shadow_validation=shadow_validation_payload(shadow_ready=True),
        shadow_health=shadow_health_payload(stable=False),
        shadow_review=shadow_review_payload(can_request=True),
    )

    assert packet.status == "blocked"
    assert packet.can_request_live_small_review is False
    assert any(item.code == "shadow_health_stable" and not item.passed for item in packet.checklist)


def lifecycle_payload(*, current_stage: str) -> StrategyLifecyclePayload:
    return StrategyLifecyclePayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        current_stage=current_stage,
        recommended_stage="shadow_candidate",
        recommended_action="eligible_for_shadow_review",
        gate_status="eligible",
        promotion_gate="eligible_for_shadow",
        can_promote=True,
        can_kill=False,
        auto_actions_enabled=False,
        rules=[],
        missing_capabilities=[],
        summary="lifecycle",
    )


def shadow_health_payload(*, stable: bool) -> ShadowObservationHealthPayload:
    return ShadowObservationHealthPayload(
        strategy_id="deterministic_watchlist_v1",
        status="stable" if stable else "attention",
        sample_ready=stable,
        observation_count=5,
        observing_count=5,
        blocked_count=0,
        consecutive_observing_count=5,
        latest_trading_day="2026-07-04",
        average_would_route_order_count=2,
        average_event_chain_count=6,
        average_residual_risk_count=1 if stable else 3,
        warnings=[] if stable else ["residual_risk_high"],
        summary="shadow health",
    )


def shadow_validation_payload(*, shadow_ready: bool) -> ShadowValidationPayload:
    return ShadowValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        shadow_ready=shadow_ready,
        status="shadow_validated" if shadow_ready else "collecting",
        observation_count=5 if shadow_ready else 1,
        observing_count=5 if shadow_ready else 1,
        blocked_count=0,
        latest_trading_day="2026-07-04" if shadow_ready else "2026-06-30",
        min_observations_required=5,
        remaining_observations=0 if shadow_ready else 4,
        residual_risk_count=5 if shadow_ready else 2,
        blockers=[] if shadow_ready else ["shadow_observation_sample"],
        summary="shadow validation",
    )


def shadow_review_payload(*, can_request: bool) -> ShadowReviewPayload:
    return ShadowReviewPayload(
        status="ready_for_manual_review" if can_request else "blocked",
        strategy_id="deterministic_watchlist_v1",
        can_request_shadow_review=can_request,
        recommended_stage="shadow" if can_request else "paper",
        auto_promotion_enabled=False,
        checklist=[],
        residual_risks=[],
        summary="shadow review",
    )
