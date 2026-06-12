from app.services.imports import parse_positions_csv


def test_parse_positions_csv_accepts_valid_rows():
    content = "ticker,quantity,average_cost,currency\nAAPL,10,150,USD\nMSFT,5,300,USD\n"

    result = parse_positions_csv(content)

    assert len(result.positions) == 2
    assert result.positions[0].ticker == "AAPL"
    assert result.positions[0].quantity == 10
    assert result.errors == []


def test_parse_positions_csv_reports_row_level_errors():
    content = "ticker,quantity,average_cost,currency\n,10,150,USD\nTSLA,nope,200,USD\n"

    result = parse_positions_csv(content)

    assert result.positions == []
    assert result.errors == [
        {"row": 2, "field": "ticker", "message": "ticker is required"},
        {"row": 3, "field": "quantity", "message": "quantity must be a number"},
    ]


def test_parse_positions_csv_defaults_blank_currency_to_usd():
    content = "ticker,quantity,average_cost,currency\n aapl ,10,150,   \n"

    result = parse_positions_csv(content)

    assert len(result.positions) == 1
    assert result.positions[0].ticker == "AAPL"
    assert result.positions[0].currency == "USD"
    assert result.errors == []


def test_parse_positions_csv_reports_invalid_average_cost():
    content = "ticker,quantity,average_cost,currency\nAAPL,10,nope,USD\n"

    result = parse_positions_csv(content)

    assert result.positions == []
    assert result.errors == [
        {"row": 2, "field": "average_cost", "message": "average_cost must be a number"},
    ]
