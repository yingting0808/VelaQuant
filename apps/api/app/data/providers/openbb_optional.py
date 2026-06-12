from collections.abc import Callable
from datetime import UTC, datetime
from importlib import import_module
from importlib.util import find_spec
from typing import Any

from app.data.providers.base import EvidenceItem, FundamentalSnapshot, PriceHistoryBar, ProviderStatus, Quote


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _records_from_result(result: Any) -> list[dict[str, Any]]:
    data = result
    if hasattr(data, "to_df"):
        data = data.to_df()
    elif hasattr(data, "to_dataframe"):
        data = data.to_dataframe()

    if hasattr(data, "to_dict"):
        try:
            records = data.to_dict("records")
        except TypeError:
            records = data.to_dict()
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
        if isinstance(records, dict):
            return [records]

    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]
    if isinstance(data, dict):
        return [data]
    return []


class OpenBBOptionalProvider:
    def __init__(
        self,
        module_finder: Callable[[str], object | None] = find_spec,
        openbb_client: object | None = None,
    ) -> None:
        self._client = openbb_client
        self.available = openbb_client is not None or module_finder("openbb") is not None

    @property
    def client(self) -> object | None:
        if self._client is not None:
            return self._client
        if not self.available:
            return None
        module = import_module("openbb")
        self._client = getattr(module, "obb", None)
        return self._client

    def get_quote(self, ticker: str) -> Quote:
        normalized = _normalize_ticker(ticker)
        client = self.client
        if client is None:
            return self._unavailable_quote(normalized, "OpenBB package is not installed.")
        try:
            result = client.equity.price.quote(symbol=normalized, provider="yfinance")
            record = _records_from_result(result)[0]
        except (IndexError, AttributeError, RuntimeError, ValueError, TypeError) as error:
            return self._unavailable_quote(normalized, str(error))

        return Quote(
            ticker=normalized,
            price=_number(record.get("last_price") or record.get("price") or record.get("close")),
            currency=str(record.get("currency") or "USD"),
            source="openbb_yfinance",
            updated_at=_utc_now(),
            change=_number(record.get("change")),
            change_percent=_number(record.get("change_percent")),
            volume=_integer(record.get("volume")),
            is_fallback=False,
            message="OpenBB yfinance quote loaded.",
        )

    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        normalized = _normalize_ticker(ticker)
        client = self.client
        if client is None:
            return []
        try:
            result = client.equity.price.historical(
                symbol=normalized,
                provider="yfinance",
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )
        except (AttributeError, RuntimeError, ValueError, TypeError):
            return []

        bars: list[PriceHistoryBar] = []
        for record in _records_from_result(result):
            bars.append(
                PriceHistoryBar(
                    ticker=normalized,
                    date=str(record.get("date") or record.get("datetime") or ""),
                    open=_number(record.get("open")),
                    high=_number(record.get("high")),
                    low=_number(record.get("low")),
                    close=_number(record.get("close")),
                    volume=_integer(record.get("volume")),
                    source="openbb_yfinance",
                )
            )
        return [bar for bar in bars if bar.date]

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        normalized = _normalize_ticker(ticker)
        client = self.client
        if client is None:
            return self._unavailable_fundamentals(normalized, "OpenBB package is not installed.")
        try:
            result = client.equity.fundamental.metrics(symbol=normalized, provider="yfinance")
            record = _records_from_result(result)[0]
        except (IndexError, AttributeError, RuntimeError, ValueError, TypeError) as error:
            return self._unavailable_fundamentals(normalized, str(error))

        return FundamentalSnapshot(
            ticker=normalized,
            market_cap=_number(record.get("market_cap")),
            pe_ratio=_number(record.get("pe_ratio") or record.get("trailing_pe")),
            eps=_number(record.get("eps") or record.get("eps_ttm")),
            price_to_sales=_number(record.get("price_to_sales")),
            price_to_book=_number(record.get("price_to_book")),
            gross_margin=_number(record.get("gross_margin")),
            profit_margin=_number(record.get("profit_margin")),
            operating_margin=_number(record.get("operating_margin")),
            debt_to_equity=_number(record.get("debt_to_equity")),
            source="openbb_yfinance",
            period_ending=str(record.get("period_ending")) if record.get("period_ending") else None,
            updated_at=_utc_now(),
            is_fallback=False,
            message="OpenBB yfinance fundamentals loaded.",
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        return []

    def get_statuses(self) -> list[ProviderStatus]:
        if self.available:
            return [
                ProviderStatus(
                    name="OpenBB",
                    mode="openbb_optional",
                    available=True,
                    message="OpenBB package is available for yfinance quote, history, and fundamentals.",
                    checked_at=_utc_now(),
                    version="installed",
                )
            ]
        return [
            ProviderStatus(
                name="OpenBB",
                mode="openbb_optional",
                available=False,
                message="OpenBB package is not installed.",
                checked_at=_utc_now(),
                version=None,
            )
        ]

    def _unavailable_quote(self, ticker: str, message: str) -> Quote:
        return Quote(
            ticker=ticker,
            price=None,
            currency="USD",
            source="openbb_yfinance",
            updated_at=_utc_now(),
            is_fallback=False,
            message=message,
        )

    def _unavailable_fundamentals(self, ticker: str, message: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker,
            market_cap=None,
            pe_ratio=None,
            eps=None,
            price_to_sales=None,
            price_to_book=None,
            gross_margin=None,
            profit_margin=None,
            operating_margin=None,
            debt_to_equity=None,
            source="openbb_yfinance",
            period_ending=None,
            updated_at=_utc_now(),
            is_fallback=False,
            message=message,
        )
