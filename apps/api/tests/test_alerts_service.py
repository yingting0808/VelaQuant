from app.services.alerts import AlertCandidate, generate_event_alerts


def test_generate_event_alerts_matches_portfolio_tickers():
    candidates = [
        AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="sec_edgar"),
        AlertCandidate(ticker="TSLA", title="TSLA news", reason="News event", source="mock_news"),
    ]

    alerts = generate_event_alerts(portfolio_tickers=["aapl", "msft"], candidates=candidates)

    assert len(alerts) == 1
    assert alerts[0].ticker == "AAPL"
    assert alerts[0].title == "AAPL 10-Q filed"


def test_generate_event_alerts_deduplicates_by_ticker_title_source():
    candidates = [
        AlertCandidate(ticker="MSFT", title="Earnings date changed", reason="Calendar update", source="calendar"),
        AlertCandidate(ticker="MSFT", title="Earnings date changed", reason="Calendar update", source="calendar"),
    ]

    alerts = generate_event_alerts(portfolio_tickers=["MSFT"], candidates=candidates)

    assert len(alerts) == 1
    assert alerts[0].ticker == "MSFT"
    assert alerts[0].title == "Earnings date changed"
    assert alerts[0].source == "calendar"


def test_generate_event_alerts_strips_portfolio_and_candidate_tickers():
    candidates = [
        AlertCandidate(ticker=" aapl ", title="AAPL 10-Q filed", reason="SEC filing", source="sec_edgar"),
    ]

    alerts = generate_event_alerts(portfolio_tickers=[" aapl "], candidates=candidates)

    assert len(alerts) == 1
    assert alerts[0].ticker == "AAPL"
