from pydantic import BaseModel, Field


class AlertCandidate(BaseModel):
    ticker: str = Field(min_length=1)
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source: str = Field(min_length=1)


class GeneratedAlert(BaseModel):
    ticker: str
    title: str
    reason: str
    source: str


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def generate_event_alerts(
    *,
    portfolio_tickers: list[str],
    candidates: list[AlertCandidate],
) -> list[GeneratedAlert]:
    tracked = {_normalize_ticker(ticker) for ticker in portfolio_tickers}
    seen: set[tuple[str, str, str]] = set()
    alerts: list[GeneratedAlert] = []

    for candidate in candidates:
        ticker = _normalize_ticker(candidate.ticker)
        key = (ticker, candidate.title, candidate.source)
        if ticker not in tracked or key in seen:
            continue
        seen.add(key)
        alerts.append(
            GeneratedAlert(
                ticker=ticker,
                title=candidate.title,
                reason=candidate.reason,
                source=candidate.source,
            )
        )

    return alerts
