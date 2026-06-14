from app.services.live_small_review import LiveSmallReviewChecklistItem, LiveSmallReviewPayload
from app.services.shadow_daily_report import build_shadow_daily_report
from app.services.shadow_observation import ShadowObservationPayload, ShadowObservationSummaryPayload
from app.services.shadow_observation_health import ShadowObservationHealthPayload
from app.services.shadow_validation import ShadowValidationPayload


def test_shadow_daily_report_collects_until_shadow_sample_is_ready():
    report = build_shadow_daily_report(
        observations=shadow_observation_summary(),
        health=shadow_health_payload(status="collecting", sample_ready=False, warnings=["sample_not_ready"]),
        validation=shadow_validation_payload(shadow_ready=False, remaining_observations=4),
        live_small_review=live_small_payload(can_request=False),
    )

    assert report.status == "collecting"
    assert report.trading_day == "2026-06-30"
    assert report.observed_intent_count == 6
    assert report.would_route_order_count == 2
    assert report.event_chain_count == 6
    assert report.residual_risk_count == 2
    assert report.remaining_observations == 4
    assert report.warnings == ["sample_not_ready"]
    assert report.blockers == ["shadow_observation_sample"]
    assert report.next_actions[0].action_code == "continue_shadow_observation"
    assert report.live_or_broker_execution_enabled is False


def test_shadow_daily_report_requires_manual_live_small_review_when_shadow_is_ready():
    report = build_shadow_daily_report(
        observations=shadow_observation_summary(),
        health=shadow_health_payload(status="stable", sample_ready=True, warnings=[]),
        validation=shadow_validation_payload(shadow_ready=True, remaining_observations=0),
        live_small_review=live_small_payload(can_request=True),
    )

    assert report.status == "ready_for_manual_review"
    assert report.remaining_observations == 0
    assert report.warnings == []
    assert report.blockers == []
    assert [item.action_code for item in report.next_actions] == ["manual_live_small_review"]
    assert "manual" in report.summary.lower()
    assert report.live_or_broker_execution_enabled is False


def test_shadow_daily_report_blocks_on_broken_event_chain():
    report = build_shadow_daily_report(
        observations=shadow_observation_summary(event_chain_count=0, status="observing"),
        health=shadow_health_payload(status="blocked", sample_ready=False, warnings=["event_chain_missing"]),
        validation=shadow_validation_payload(shadow_ready=False, remaining_observations=4),
        live_small_review=live_small_payload(can_request=False),
    )

    assert report.status == "blocked"
    assert "event_chain_missing" in report.warnings
    assert report.next_actions[0].action_code == "repair_shadow_event_chain"


def test_shadow_daily_report_guides_recording_when_no_observation_exists():
    report = build_shadow_daily_report(
        observations=ShadowObservationSummaryPayload(
            can_record_shadow_observation=True,
            latest=None,
            items=[],
            summary="No shadow observations have been recorded yet.",
        ),
        health=shadow_health_payload(
            status="collecting",
            sample_ready=False,
            warnings=["sample_not_ready"],
            latest_trading_day=None,
            observed_count=0,
        ),
        validation=shadow_validation_payload(shadow_ready=False, remaining_observations=5, latest_trading_day=None),
        live_small_review=live_small_payload(can_request=False),
    )

    assert report.status == "collecting"
    assert report.trading_day is None
    assert report.next_actions[0].action_code == "record_shadow_observation"
    assert report.summary == "Shadow daily report is waiting for the first observation record."


def shadow_observation_summary(
    *,
    status: str = "observing",
    event_chain_count: int = 6,
) -> ShadowObservationSummaryPayload:
    latest = ShadowObservationPayload(
        id="00000000-0000-0000-0000-000000000201",
        team_id="00000000-0000-0000-0000-000000000202",
        strategy_id="deterministic_watchlist_v1",
        trading_day="2026-06-30",
        status=status,
        can_request_shadow_review=status == "observing",
        observed_intent_count=6,
        would_route_order_count=2,
        event_chain_count=event_chain_count,
        residual_risk_count=2,
        blocked_reason=None if status == "observing" else "blocked",
        created_at="2026-06-13T00:00:00Z",
    )
    return ShadowObservationSummaryPayload(
        can_record_shadow_observation=True,
        latest=latest,
        items=[latest],
        summary="Shadow observation latest observing on 2026-06-30.",
    )


def shadow_health_payload(
    *,
    status: str,
    sample_ready: bool,
    warnings: list[str],
    latest_trading_day: str | None = "2026-06-30",
    observed_count: int = 1,
) -> ShadowObservationHealthPayload:
    return ShadowObservationHealthPayload(
        strategy_id="deterministic_watchlist_v1",
        status=status,
        sample_ready=sample_ready,
        observation_count=observed_count,
        observing_count=observed_count,
        blocked_count=0,
        consecutive_observing_count=observed_count,
        latest_trading_day=latest_trading_day,
        average_would_route_order_count=2,
        average_event_chain_count=6,
        average_residual_risk_count=2,
        warnings=warnings,
        summary="Shadow observation health summary.",
    )


def shadow_validation_payload(
    *,
    shadow_ready: bool,
    remaining_observations: int,
    latest_trading_day: str | None = "2026-06-30",
) -> ShadowValidationPayload:
    return ShadowValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        shadow_ready=shadow_ready,
        status="shadow_validated" if shadow_ready else "collecting",
        observation_count=5 if shadow_ready else 1,
        observing_count=5 if shadow_ready else 1,
        blocked_count=0,
        latest_trading_day=latest_trading_day,
        min_observations_required=5,
        remaining_observations=remaining_observations,
        residual_risk_count=0 if shadow_ready else 2,
        blockers=[] if shadow_ready else ["shadow_observation_sample"],
        summary="Shadow validation summary.",
    )


def live_small_payload(*, can_request: bool) -> LiveSmallReviewPayload:
    return LiveSmallReviewPayload(
        status="ready_for_manual_review" if can_request else "blocked",
        strategy_id="deterministic_watchlist_v1",
        can_request_live_small_review=can_request,
        recommended_stage="live_small" if can_request else "shadow",
        auto_promotion_enabled=False,
        checklist=[
            LiveSmallReviewChecklistItem(
                code="shadow_health_stable",
                label="Shadow 健康稳定",
                passed=can_request,
                evidence=["shadow health"],
            )
        ],
        residual_risks=[],
        summary="Live-small review summary.",
    )
