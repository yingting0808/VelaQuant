from app.services.portfolio import PositionInput, calculate_exposure


def test_calculate_exposure_returns_weights_and_total_market_value():
    positions = [
        PositionInput(ticker="AAPL", quantity=10, price=200),
        PositionInput(ticker="MSFT", quantity=5, price=400),
    ]

    result = calculate_exposure(positions)

    assert result.total_market_value == 4000
    assert result.items[0].ticker == "AAPL"
    assert result.items[0].market_value == 2000
    assert result.items[0].weight == 0.5
    assert result.items[1].ticker == "MSFT"
    assert result.items[1].weight == 0.5


def test_calculate_exposure_rejects_negative_quantity():
    positions = [PositionInput(ticker="AAPL", quantity=-1, price=200)]

    try:
        calculate_exposure(positions)
    except ValueError as exc:
        assert "quantity must be non-negative" in str(exc)
    else:
        raise AssertionError("negative quantity should fail")
