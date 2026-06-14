from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload
from app.services.alpha_validation_forecast import AlphaValidationForecastItem, AlphaValidationForecastPayload
from app.services.event_ledger import EventLedgerStatus
from app.services.paper_action_plan import PaperActionPlanItem, PaperActionPlanPayload
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload
from app.services.paper_risk_profile import PaperRiskProfilePayload
from app.services.shadow_review import build_shadow_review_packet


def test_shadow_review_packet_requires_manual_review_after_alpha_ready():
    packet = build_shadow_review_packet(
        alpha_gates=ready_alpha_gates(),
        alpha_forecast=ready_alpha_forecast(),
        action_plan=PaperActionPlanPayload(
            readiness="alpha_ready",
            primary_action="eligible_for_shadow_review",
            items=[
                PaperActionPlanItem(
                    priority=1,
                    action_code="eligible_for_shadow_review",
                    title="进入 Shadow 评审",
                    detail="Alpha 门禁已通过，可以进入人工评审，不自动晋级。",
                    evidence=["8/8 gates passed"],
                )
            ],
            summary="eligible",
        ),
        execution=execution_diagnostics(filled=33, closed=16, rejected=26),
        event_ledger=event_ledger(replay_ready=True, total_event_count=680),
        risk_profile=risk_profile(),
    )

    assert packet.status == "ready_for_manual_review"
    assert packet.can_request_shadow_review is True
    assert packet.recommended_stage == "shadow"
    assert packet.auto_promotion_enabled is False
    assert all(item.passed for item in packet.checklist)
    assert packet.residual_risks
    assert "manual" in packet.summary.lower()


def test_shadow_review_packet_blocks_when_alpha_gates_are_not_ready():
    blocked_gates = ready_alpha_gates().model_copy(update={"alpha_ready": False, "passed_gates": 7})
    packet = build_shadow_review_packet(
        alpha_gates=blocked_gates,
        alpha_forecast=ready_alpha_forecast().model_copy(update={"alpha_ready": False, "status": "forecastable"}),
        action_plan=PaperActionPlanPayload(
            readiness="ready",
            primary_action="continue_paper_validation",
            items=[],
            summary="continue paper validation",
        ),
        execution=execution_diagnostics(filled=29, closed=16, rejected=0),
        event_ledger=event_ledger(replay_ready=True, total_event_count=680),
        risk_profile=risk_profile(),
    )

    assert packet.status == "blocked"
    assert packet.can_request_shadow_review is False
    assert any(item.code == "alpha_gates_passed" and not item.passed for item in packet.checklist)


def ready_alpha_gates() -> AlphaGateProgressPayload:
    return AlphaGateProgressPayload(
        alpha_ready=True,
        validation_level="paper_validated",
        passed_gates=8,
        total_gates=8,
        items=[
            AlphaGateProgressItem(
                gate="filled_order_sample",
                label="成交订单",
                current=33,
                required=30,
                remaining=0,
                unit="笔",
                comparison="at_least",
                passed=True,
            )
        ],
        summary="Alpha gate progress: 8/8 gates passed; validation level paper_validated.",
    )


def ready_alpha_forecast() -> AlphaValidationForecastPayload:
    return AlphaValidationForecastPayload(
        alpha_ready=True,
        status="ready",
        estimated_sessions_to_alpha_ready=0,
        limiting_gate=None,
        items=[
            AlphaValidationForecastItem(
                gate="filled_order_sample",
                label="成交订单",
                current=33,
                required=30,
                remaining=0,
                unit="笔",
                passed=True,
                estimated_per_session=1.7,
                estimated_sessions=0,
                reason="门禁已通过。",
            )
        ],
        summary="Alpha validation already passes all paper gates.",
    )


def execution_diagnostics(*, filled: int, closed: int, rejected: int) -> PaperExecutionDiagnosticsPayload:
    total = filled + rejected
    return PaperExecutionDiagnosticsPayload(
        order_count=total,
        filled_order_count=filled,
        rejected_order_count=rejected,
        buy_order_count=filled,
        sell_order_count=closed,
        closed_trade_count=closed,
        fill_rate=round(filled / total, 4) if total else 0,
        rejection_rate=round(rejected / total, 4) if total else 0,
        realized_pnl=796.87,
        average_realized_pnl=49.8,
        latest_rejection_code="max_daily_orders" if rejected else None,
        max_daily_order_rejections=rejected,
        max_daily_order_buy_rejections=rejected,
        max_daily_order_sell_rejections=0,
        rejection_reasons=[],
        summary="execution diagnostics",
    )


def event_ledger(*, replay_ready: bool, total_event_count: int) -> EventLedgerStatus:
    return EventLedgerStatus(
        total_event_count=total_event_count,
        latest_run_id=None,
        latest_run_status="completed",
        latest_run_event_count=30 if replay_ready else 0,
        latest_topic_counts=[],
        latest_correlation_count=6 if replay_ready else 0,
        replay_ready=replay_ready,
        warnings=[] if replay_ready else ["latest_run_has_no_events"],
        summary="ledger status",
        latest_replay=None,
    )


def risk_profile() -> PaperRiskProfilePayload:
    return PaperRiskProfilePayload(
        risk_engine="Trading Core RiskEngine",
        max_order_notional=2000,
        max_position_weight=0.1,
        max_daily_orders=5,
        exit_take_profit_pct=0.1,
        exit_stop_loss_pct=-0.05,
        summary="risk profile",
    )
