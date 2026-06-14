from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload
from app.services.paper_action_plan import build_paper_action_plan
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, PaperExecutionRejectionReason
from app.services.paper_operations import PaperOperationsStatusPayload
from app.services.paper_risk_limit_review import PaperRiskLimitReviewPayload
from app.services.paper_risk_profile import PaperRiskProfilePayload


def test_paper_action_plan_prioritizes_event_ledger_repair():
    plan = build_paper_action_plan(
        operations=_operations(blockers=["event_ledger_not_replayable"], health_status="blocked"),
        alpha_gates=_alpha_gates([]),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(),
    )

    assert plan.primary_action == "repair_event_ledger"
    assert plan.items[0].action_code == "repair_event_ledger"
    assert plan.items[0].priority == 1


def test_paper_action_plan_recommends_risk_review_when_daily_order_limit_blocks_closed_trades():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("consecutive_positive_expectancy", "连续正期望", 4, 5, 1, "天"),
                _gate("filled_order_sample", "成交订单", 19, 30, 11, "笔"),
                _gate("closed_trade_sample", "闭环交易", 9, 10, 1, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=26),
        risk_profile=_risk_profile(),
    )

    assert plan.primary_action == "review_daily_order_limit"
    assert plan.items[0].action_code == "review_daily_order_limit"
    assert "max_daily_orders=5" in plan.items[0].detail
    assert any(item.action_code == "continue_paper_validation" for item in plan.items)


def test_paper_action_plan_collects_post_limit_sample_after_risk_limit_update():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("filled_order_sample", "成交订单", 6, 30, 24, "笔"),
                _gate("closed_trade_sample", "闭环交易", 0, 10, 10, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=25),
        risk_profile=_risk_profile(max_daily_orders=6),
        risk_limit_review=PaperRiskLimitReviewPayload(
            status="hold",
            current_max_daily_orders=6,
            recommended_paper_max_daily_orders=6,
            live_change_allowed=False,
            max_daily_order_rejections=25,
            max_daily_order_buy_rejections=5,
            max_daily_order_sell_rejections=20,
            filled_order_count=6,
            closed_trade_count=0,
            sample_collection_blocked=False,
            blockers=["awaiting_post_limit_sample"],
            summary="Paper risk limit review: hold max_daily_orders at 6.",
        ),
    )

    assert plan.primary_action == "collect_post_limit_sample"
    assert plan.items[0].action_code == "collect_post_limit_sample"
    assert "max_daily_orders=6" in plan.items[0].detail
    assert all(item.action_code != "review_daily_order_limit" for item in plan.items)


def test_paper_action_plan_prioritizes_legacy_manual_future_run_quarantine():
    plan = build_paper_action_plan(
        operations=_operations(
            blockers=[],
            health_status="ready",
            legacy_manual_future_run_count=3,
            latest_legacy_manual_future_trading_day="2026-06-30",
            data_quality_warnings=["legacy_manual_future_runs_detected"],
        ),
        alpha_gates=_alpha_gates([]),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(),
    )

    assert plan.primary_action == "quarantine_legacy_manual_future_runs"
    assert plan.items[0].title == "标记旧运行"
    assert "3 条旧 manual 未来日期运行" in plan.items[0].detail
    assert "latest_legacy_trading_day=2026-06-30" in plan.items[0].evidence


def _operations(
    *,
    blockers: list[str],
    health_status: str,
    legacy_manual_future_run_count: int = 0,
    latest_legacy_manual_future_trading_day: str | None = None,
    data_quality_warnings: list[str] | None = None,
) -> PaperOperationsStatusPayload:
    return PaperOperationsStatusPayload(
        trading_day="2026-06-13",
        run_state="completed",
        health_status=health_status,
        latest_run_id="00000000-0000-0000-0000-000000000101",
        latest_run_trading_day="2026-06-13",
        latest_run_status="completed",
        today_run_id="00000000-0000-0000-0000-000000000101",
        review_id="00000000-0000-0000-0000-000000000102",
        latest_error=None,
        can_retry_today=False,
        event_ledger_ready="event_ledger_not_replayable" not in blockers,
        latest_run_event_count=10,
        legacy_manual_future_run_count=legacy_manual_future_run_count,
        latest_legacy_manual_future_trading_day=latest_legacy_manual_future_trading_day,
        data_quality_warnings=data_quality_warnings or [],
        blockers=blockers,
        recommended_action="hold_until_next_session",
        summary="fixture operations",
    )


def _alpha_gates(items: list[AlphaGateProgressItem]) -> AlphaGateProgressPayload:
    return AlphaGateProgressPayload(
        alpha_ready=False,
        validation_level="collecting",
        passed_gates=5,
        total_gates=8,
        items=items,
        summary="Alpha gate progress: 5/8 gates passed.",
    )


def _gate(gate: str, label: str, current: float, required: float, remaining: float, unit: str) -> AlphaGateProgressItem:
    return AlphaGateProgressItem(
        gate=gate,
        label=label,
        current=current,
        required=required,
        remaining=remaining,
        unit=unit,
        comparison="at_least",
        passed=False,
    )


def _execution(*, max_daily_order_rejections: int) -> PaperExecutionDiagnosticsPayload:
    return PaperExecutionDiagnosticsPayload(
        order_count=45,
        filled_order_count=19,
        rejected_order_count=max_daily_order_rejections,
        buy_order_count=16,
        sell_order_count=29,
        closed_trade_count=9,
        fill_rate=0.4222,
        rejection_rate=0.5778,
        realized_pnl=1435.04,
        average_realized_pnl=159.45,
        latest_rejection_code="max_daily_orders" if max_daily_order_rejections else None,
        max_daily_order_rejections=max_daily_order_rejections,
        max_daily_order_buy_rejections=max_daily_order_rejections,
        max_daily_order_sell_rejections=0,
        rejection_reasons=[
            PaperExecutionRejectionReason(
                risk_code="max_daily_orders",
                count=max_daily_order_rejections,
                latest_reason="Orders today 5 reached limit 5.",
            )
        ]
        if max_daily_order_rejections
        else [],
        summary="fixture execution",
    )


def _risk_profile(*, max_daily_orders: int = 5) -> PaperRiskProfilePayload:
    return PaperRiskProfilePayload(
        risk_engine="Trading Core RiskEngine",
        max_order_notional=2000,
        max_position_weight=0.1,
        max_daily_orders=max_daily_orders,
        exit_take_profit_pct=0.1,
        exit_stop_loss_pct=-0.05,
        summary="fixture risk",
    )
