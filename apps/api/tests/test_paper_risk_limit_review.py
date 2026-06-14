from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, PaperExecutionRejectionReason
from app.services.paper_risk_limit_review import build_paper_risk_limit_review
from app.services.paper_risk_profile import PaperRiskProfilePayload


def test_risk_limit_review_recommends_paper_only_capacity_increase_when_sample_collection_is_blocked():
    review = build_paper_risk_limit_review(
        execution=_execution(max_daily_order_buy_rejections=6, max_daily_order_sell_rejections=20),
        risk_profile=_risk_profile(max_daily_orders=5),
        alpha_gates=_alpha_gates(
            [
                _gate("filled_order_sample", "成交订单", 6, 30, 24, "笔"),
                _gate("closed_trade_sample", "闭环交易", 0, 10, 10, "笔"),
            ]
        ),
    )

    assert review.status == "review_required"
    assert review.current_max_daily_orders == 5
    assert review.recommended_paper_max_daily_orders == 6
    assert review.max_daily_order_buy_rejections == 6
    assert review.max_daily_order_sell_rejections == 20
    assert review.live_change_allowed is False
    assert review.sample_collection_blocked is True
    assert review.blockers == ["filled_order_sample", "closed_trade_sample", "max_daily_orders"]
    assert "paper-only" in review.summary


def test_risk_limit_review_does_not_increase_capacity_for_exit_only_daily_order_rejections():
    review = build_paper_risk_limit_review(
        execution=_execution(max_daily_order_buy_rejections=0, max_daily_order_sell_rejections=20),
        risk_profile=_risk_profile(max_daily_orders=5),
        alpha_gates=_alpha_gates(
            [
                _gate("filled_order_sample", "成交订单", 6, 30, 24, "笔"),
                _gate("closed_trade_sample", "闭环交易", 0, 10, 10, "笔"),
            ]
        ),
    )

    assert review.status == "hold"
    assert review.recommended_paper_max_daily_orders == 5
    assert review.sample_collection_blocked is False
    assert review.blockers == ["max_daily_orders_sell_exit_rejections"]


def test_risk_limit_review_holds_when_no_daily_order_rejections_exist():
    review = build_paper_risk_limit_review(
        execution=_execution(max_daily_order_buy_rejections=0, max_daily_order_sell_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=5),
        alpha_gates=_alpha_gates([]),
    )

    assert review.status == "hold"
    assert review.recommended_paper_max_daily_orders == 5
    assert review.sample_collection_blocked is False
    assert review.blockers == []


def _alpha_gates(items: list[AlphaGateProgressItem]) -> AlphaGateProgressPayload:
    return AlphaGateProgressPayload(
        alpha_ready=False,
        validation_level="collecting",
        passed_gates=5,
        total_gates=8,
        items=items,
        summary="fixture gates",
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


def _execution(
    *,
    max_daily_order_buy_rejections: int,
    max_daily_order_sell_rejections: int,
) -> PaperExecutionDiagnosticsPayload:
    max_daily_order_rejections = max_daily_order_buy_rejections + max_daily_order_sell_rejections
    return PaperExecutionDiagnosticsPayload(
        order_count=68,
        filled_order_count=42,
        rejected_order_count=max_daily_order_rejections,
        buy_order_count=28,
        sell_order_count=40,
        closed_trade_count=20,
        fill_rate=0.6176,
        rejection_rate=0.3824 if max_daily_order_rejections else 0,
        realized_pnl=796.87,
        average_realized_pnl=39.84,
        latest_rejection_code="max_daily_orders" if max_daily_order_rejections else None,
        max_daily_order_rejections=max_daily_order_rejections,
        max_daily_order_buy_rejections=max_daily_order_buy_rejections,
        max_daily_order_sell_rejections=max_daily_order_sell_rejections,
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


def _risk_profile(*, max_daily_orders: int) -> PaperRiskProfilePayload:
    return PaperRiskProfilePayload(
        risk_engine="Trading Core RiskEngine",
        max_order_notional=2000,
        max_position_weight=0.1,
        max_daily_orders=max_daily_orders,
        exit_take_profit_pct=0.1,
        exit_stop_loss_pct=-0.05,
        summary="fixture risk",
    )
