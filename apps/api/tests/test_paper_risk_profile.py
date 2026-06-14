from app.services.paper_risk_profile import get_paper_risk_profile


def test_paper_risk_profile_exposes_current_limits_and_exit_rules():
    profile = get_paper_risk_profile()

    assert profile.max_order_notional == 2000
    assert profile.max_position_weight == 0.1
    assert profile.max_daily_orders == 5
    assert profile.exit_take_profit_pct == 0.1
    assert profile.exit_stop_loss_pct == -0.05
    assert profile.risk_engine == "Trading Core RiskEngine"
    assert "max_daily_orders" in profile.summary
