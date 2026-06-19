from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import PaperPosition
from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload
from app.services.alpha_validation_forecast import AlphaValidationForecastItem, AlphaValidationForecastPayload
from app.services.paper_action_plan import _triggered_exit_sample_count, build_paper_action_plan
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, PaperExecutionRejectionReason
from app.services.paper_operations import PaperOperationsStatusPayload
from app.services.paper_review_trend import PaperReviewTrendItem, PaperReviewTrendPayload
from app.services.paper_risk_limit_review import PaperRiskLimitReviewPayload
from app.services.paper_risk_profile import PaperRiskProfilePayload
from app.services.paper_scheduler import PaperSchedulerStatus
from app.services.paper_trading import PaperOrderCreate, submit_paper_order
from tests.test_paper_trading_service import FixtureProvider


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


def test_paper_action_plan_runs_daily_pipeline_before_repair_when_no_run_exists():
    plan = build_paper_action_plan(
        operations=_operations(
            blockers=["daily_run_missing"],
            health_status="blocked",
            run_state="not_started",
            recommended_action="run_daily_paper_trading",
            latest_run_id=None,
            today_run_id=None,
            latest_run_event_count=0,
            event_ledger_ready=False,
        ),
        alpha_gates=_alpha_gates([]),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(),
    )

    assert plan.primary_action == "run_daily_paper_trading"
    assert all(item.action_code != "repair_event_ledger" for item in plan.items)


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


def test_paper_action_plan_applies_paper_only_risk_recommendation_when_review_is_ready():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("filled_order_sample", "成交订单", 8, 30, 22, "笔"),
                _gate("closed_trade_sample", "闭环交易", 4, 10, 6, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=1),
        risk_profile=_risk_profile(max_daily_orders=6),
        risk_limit_review=PaperRiskLimitReviewPayload(
            status="review_required",
            current_max_daily_orders=6,
            recommended_paper_max_daily_orders=7,
            live_change_allowed=False,
            max_daily_order_rejections=1,
            max_daily_order_buy_rejections=1,
            max_daily_order_sell_rejections=0,
            filled_order_count=8,
            closed_trade_count=4,
            sample_collection_blocked=True,
            blockers=["filled_order_sample", "closed_trade_sample", "max_daily_orders"],
            summary="Paper risk limit review: paper-only review required; max_daily_orders 6 -> 7.",
        ),
    )

    assert plan.primary_action == "apply_paper_risk_limit_recommendation"
    assert plan.items[0].action_code == "apply_paper_risk_limit_recommendation"
    assert "max_daily_orders 6 -> 7" in plan.items[0].detail
    assert "Live 不变" in plan.items[0].detail


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


def test_paper_action_plan_does_not_reopen_daily_limit_review_after_clear_post_limit_sample():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("filled_order_sample", "成交订单", 10, 30, 20, "笔"),
                _gate("closed_trade_sample", "闭环交易", 6, 10, 4, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=1),
        risk_profile=_risk_profile(max_daily_orders=10),
        risk_limit_review=PaperRiskLimitReviewPayload(
            status="hold",
            current_max_daily_orders=10,
            recommended_paper_max_daily_orders=10,
            live_change_allowed=False,
            max_daily_order_rejections=1,
            max_daily_order_buy_rejections=1,
            max_daily_order_sell_rejections=0,
            filled_order_count=10,
            closed_trade_count=6,
            sample_collection_blocked=False,
            blockers=[],
            summary="Paper risk limit review: hold max_daily_orders at 10; no paper-only capacity change is recommended.",
        ),
    )

    assert plan.primary_action == "continue_paper_validation"
    assert all(item.action_code != "review_daily_order_limit" for item in plan.items)
    assert all(item.action_code != "apply_paper_risk_limit_recommendation" for item in plan.items)
    assert all(item.action_code != "collect_post_limit_sample" for item in plan.items)


def test_paper_action_plan_prioritizes_score_pnl_inversion_review():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("score_pnl_inversion_review", "评分盈亏反向", 1, 0, 1, "项", comparison="at_most"),
                _gate("review_day_sample", "复盘天数", 1, 5, 4, "天"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        inverted_score_pnl_tickers=["AMZN"],
    )

    assert plan.primary_action == "review_score_pnl_inversion"
    assert plan.items[0].action_code == "review_score_pnl_inversion"
    assert plan.items[0].title == "复盘评分背离"
    assert "AMZN" in plan.items[0].detail
    assert "inverted_tickers=AMZN" in plan.items[0].evidence
    assert any(item.action_code == "continue_paper_validation" for item in plan.items)


def test_paper_action_plan_holds_when_score_pnl_inversion_review_is_recorded_for_current_tickers():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("score_pnl_inversion_review", "评分盈亏反向", 1, 0, 1, "项", comparison="at_most"),
                _gate("review_day_sample", "复盘天数", 1, 5, 4, "天"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        latest_alpha_snapshot_trading_day="2026-06-13",
        inverted_score_pnl_tickers=["AMZN"],
        score_pnl_inversion_review_recorded=True,
    )

    assert plan.primary_action == "hold_until_next_session"
    assert all(item.action_code != "review_score_pnl_inversion" for item in plan.items)
    assert "score_pnl_inversion_review_recorded=true" in plan.items[0].evidence


def test_paper_action_plan_prioritizes_expectancy_quality_review_for_strategy_alpha_blocker():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("latest_positive_expectancy", "最新期望", 0, 0, 0.01, "USD", comparison="greater_than"),
                _gate("consecutive_positive_expectancy", "连续正期望", 0, 5, 5, "天"),
                _gate("closed_trade_sample", "闭环交易", 7, 10, 3, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        latest_alpha_snapshot_trading_day="2026-06-13",
    )

    assert plan.primary_action == "review_expectancy_quality"
    assert plan.items[0].action_code == "review_expectancy_quality"
    assert plan.items[0].title == "复盘期望质量"
    assert "最新期望" in plan.items[0].detail
    assert "latest_alpha_snapshot_trading_day=2026-06-13" in plan.items[0].evidence
    assert "latest_positive_expectancy_current=0" in plan.items[0].evidence
    assert any(item.action_code == "hold_until_next_session" for item in plan.items)


def test_paper_action_plan_holds_after_expectancy_quality_review_is_recorded():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("latest_positive_expectancy", "最新期望", 0, 0, 0.01, "USD", comparison="greater_than"),
                _gate("consecutive_positive_expectancy", "连续正期望", 0, 5, 5, "天"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        latest_alpha_snapshot_trading_day="2026-06-13",
        expectancy_quality_review_recorded=True,
    )

    assert plan.primary_action == "hold_until_next_session"
    assert all(item.action_code != "review_expectancy_quality" for item in plan.items)
    assert "expectancy_quality_review_recorded=true" in plan.items[0].evidence


def test_paper_action_plan_holds_after_current_alpha_snapshot_is_recorded():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("review_day_sample", "复盘天数", 1, 5, 4, "天"),
                _gate("filled_order_sample", "成交订单", 10, 30, 20, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        latest_alpha_snapshot_trading_day="2026-06-13",
    )

    assert plan.primary_action == "hold_until_next_session"
    assert all(item.action_code != "continue_paper_validation" for item in plan.items)
    assert plan.items[0].detail == "当前交易日 Alpha 验证快照已记录，等待下一交易日继续收集样本。"


def test_paper_action_plan_hold_includes_next_actionable_alpha_sampling_plan():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("review_day_sample", "复盘天数", 1, 5, 4, "天"),
                _gate("filled_order_sample", "成交订单", 10, 30, 20, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        alpha_forecast=_alpha_forecast(estimated_sessions=4, limiting_gate="review_day_sample"),
        scheduler=_scheduler_status(),
        latest_alpha_snapshot_trading_day="2026-06-13",
    )

    assert plan.primary_action == "hold_until_next_session"
    assert "预计还需 4 次有效 paper sessions" in plan.items[0].detail
    assert "下一次有效采样 2026-06-16T06:30:00+08:00" in plan.items[0].detail
    assert "next_actionable_trading_day=2026-06-15" in plan.items[0].evidence
    assert "limiting_gate=review_day_sample" in plan.items[0].evidence


def test_paper_action_plan_hold_includes_triggered_exit_sample_forecast():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates(
            [
                _gate("review_day_sample", "复盘天数", 1, 5, 4, "天"),
                _gate("closed_trade_sample", "闭环交易", 6, 10, 4, "笔"),
            ]
        ),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(max_daily_orders=10),
        alpha_forecast=_alpha_forecast(estimated_sessions=4, limiting_gate="review_day_sample"),
        scheduler=_scheduler_status(),
        latest_alpha_snapshot_trading_day="2026-06-13",
        triggered_exit_sample_count=3,
    )

    assert plan.primary_action == "hold_until_next_session"
    assert "下次运行预计补 3 笔闭环交易样本" in plan.items[0].detail
    assert "closed_trade_gap_after_next_exit_run=1" in plan.items[0].evidence
    assert "triggered_exit_sample_count=3" in plan.items[0].evidence
    assert plan.items[0].projected_gate_impacts == [
        {
            "gate": "closed_trade_sample",
            "label": "闭环交易",
            "projected_increment": 3.0,
            "current_remaining": 4.0,
            "projected_remaining": 1.0,
            "unit": "笔",
        }
    ]


def test_triggered_exit_sample_count_projects_from_orders_when_position_table_is_stale():
    with _make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 115.0
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))
        for position in session.exec(select(PaperPosition)).all():
            session.delete(position)
        session.commit()

        assert _triggered_exit_sample_count(session) == 1


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


def test_paper_action_plan_prioritizes_negative_daily_pnl_review():
    plan = build_paper_action_plan(
        operations=_operations(blockers=[], health_status="ready"),
        alpha_gates=_alpha_gates([]),
        execution=_execution(max_daily_order_rejections=0),
        risk_profile=_risk_profile(),
        review_trend=_review_trend(daily_pnl=-420.25, daily_return=-0.0042),
    )

    assert plan.primary_action == "review_negative_daily_pnl"
    assert plan.items[0].title == "复盘亏损日"
    assert "2026-06-13 日 PnL -420.25" in plan.items[0].detail
    assert "daily_return=-0.0042" in plan.items[0].evidence


def _operations(
    *,
    blockers: list[str],
    health_status: str,
    run_state: str = "completed",
    recommended_action: str = "hold_until_next_session",
    latest_run_id: str | None = "00000000-0000-0000-0000-000000000101",
    today_run_id: str | None = "00000000-0000-0000-0000-000000000101",
    latest_run_event_count: int = 10,
    event_ledger_ready: bool | None = None,
    legacy_manual_future_run_count: int = 0,
    latest_legacy_manual_future_trading_day: str | None = None,
    data_quality_warnings: list[str] | None = None,
) -> PaperOperationsStatusPayload:
    return PaperOperationsStatusPayload(
        trading_day="2026-06-13",
        run_state=run_state,
        health_status=health_status,
        latest_run_id=latest_run_id,
        latest_run_trading_day="2026-06-13",
        latest_run_status="completed",
        today_run_id=today_run_id,
        review_id="00000000-0000-0000-0000-000000000102",
        latest_error=None,
        can_retry_today=run_state in {"not_started", "failed"},
        event_ledger_ready=event_ledger_ready
        if event_ledger_ready is not None
        else "event_ledger_not_replayable" not in blockers,
        latest_run_event_count=latest_run_event_count,
        legacy_manual_future_run_count=legacy_manual_future_run_count,
        latest_legacy_manual_future_trading_day=latest_legacy_manual_future_trading_day,
        data_quality_warnings=data_quality_warnings or [],
        blockers=blockers,
        recommended_action=recommended_action,
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


def _review_trend(*, daily_pnl: float, daily_return: float) -> PaperReviewTrendPayload:
    return PaperReviewTrendPayload(
        sample_size=2,
        positive_expectancy_days=1,
        consecutive_positive_expectancy_days=0,
        average_expectancy=0.4,
        latest_expectancy=1.2,
        total_realized_pnl=100,
        total_unrealized_pnl=-30,
        latest_readiness="watch",
        items=[
            PaperReviewTrendItem(
                trading_day="2026-06-13",
                equity=99579.75,
                daily_pnl=daily_pnl,
                daily_return=daily_return,
                cash=98000,
                realized_pnl=100,
                unrealized_pnl=-30,
                trade_count=3,
                win_rate=0.33,
                expectancy=1.2,
                readiness="watch",
            )
        ],
        summary="Paper review trend fixture.",
    )


def _alpha_forecast(*, estimated_sessions: int, limiting_gate: str) -> AlphaValidationForecastPayload:
    return AlphaValidationForecastPayload(
        alpha_ready=False,
        status="forecastable",
        estimated_sessions_to_alpha_ready=estimated_sessions,
        limiting_gate=limiting_gate,
        items=[
            AlphaValidationForecastItem(
                gate=limiting_gate,
                label="复盘天数",
                current=1,
                required=5,
                remaining=4,
                unit="天",
                passed=False,
                estimated_per_session=1,
                estimated_sessions=estimated_sessions,
                reason="按当前样本速度估算。",
            )
        ],
        summary=f"Alpha validation needs about {estimated_sessions} more paper sessions.",
    )


def _scheduler_status() -> PaperSchedulerStatus:
    return PaperSchedulerStatus(
        enabled=True,
        running=True,
        job_count=1,
        job_id="paper_trading_daily_run",
        cron="30 6 * * *",
        timezone="Asia/Shanghai",
        next_run_at=datetime(2026, 6, 15, 6, 30, tzinfo=timezone.utc),
        next_run_will_execute=False,
        next_run_execution_gate="market_closed",
        next_run_trading_day="2026-06-12",
        next_run_gate_reason="market_closed",
        next_actionable_run_at=datetime.fromisoformat("2026-06-16T06:30:00+08:00"),
        next_actionable_trading_day="2026-06-15",
        next_actionable_execution_gate="ready_to_run",
        next_actionable_gate_reason="current_session_closed",
        last_checked_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        can_run_now=False,
        execution_gate="market_closed",
        market_date="2026-06-14",
        trading_day="2026-06-12",
        is_market_session=False,
        session_closed=False,
        calendar_provider="pandas_market_calendars",
        gate_reason="market_closed",
    )


def _gate(
    gate: str,
    label: str,
    current: float,
    required: float,
    remaining: float,
    unit: str,
    *,
    comparison: str = "at_least",
) -> AlphaGateProgressItem:
    return AlphaGateProgressItem(
        gate=gate,
        label=label,
        current=current,
        required=required,
        remaining=remaining,
        unit=unit,
        comparison=comparison,
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


def _make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
