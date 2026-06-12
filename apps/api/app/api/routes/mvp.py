from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow
from app.core.config import get_settings
from app.data.providers.base import MarketDataProvider
from app.data.providers.registry import build_market_data_provider
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.lean_backtest import read_latest_backtest, run_lean_backtest
from app.services.portfolio import PositionInput, calculate_exposure
from app.services.strategy_catalog import load_enabled_strategies
from app.services.strategy_lab import get_strategy_lab_status

router = APIRouter(prefix="/api/mvp", tags=["mvp"])


class ResearchBody(BaseModel):
    ticker: str = Field(min_length=1)
    question: str = Field(min_length=1)

    @field_validator("ticker", "question")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class BacktestBody(BaseModel):
    strategy_id: str = Field(min_length=1)

    @field_validator("strategy_id")
    @classmethod
    def strip_strategy_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


def get_market_data_provider() -> Iterator[MarketDataProvider]:
    provider = build_market_data_provider(get_settings())
    try:
        yield provider
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


@router.get("/dashboard")
def dashboard(provider: MarketDataProvider = Depends(get_market_data_provider)) -> dict:
    settings = get_settings()
    positions = [
        PositionInput(ticker="AAPL", quantity=10, price=provider.get_quote("AAPL").price),
        PositionInput(ticker="MSFT", quantity=5, price=provider.get_quote("MSFT").price),
    ]
    exposure = calculate_exposure(positions)
    alerts = generate_event_alerts(
        portfolio_tickers=[item.ticker for item in exposure.items],
        candidates=[
            AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="mock_sec"),
            AlertCandidate(ticker="NVDA", title="NVDA news", reason="News event", source="mock_news"),
        ],
    )
    return {
        "portfolio": {
            "name": "主组合",
            "total_market_value": exposure.total_market_value,
            "positions": [item.model_dump() for item in exposure.items],
        },
        "alerts": [alert.model_dump() for alert in alerts],
        "ai_prompts": [
            "解释当前页面",
            "识别组合风险",
            "生成多/中/空情景",
            "起草交易计划",
        ],
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
        "strategy_lab": get_strategy_lab_status().model_dump(),
    }


@router.get("/data-sources/status")
def data_sources_status(provider: MarketDataProvider = Depends(get_market_data_provider)) -> dict:
    settings = get_settings()
    return {
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }


@router.get("/strategy-lab/status")
def strategy_lab_status() -> dict:
    return get_strategy_lab_status().model_dump()


@router.get("/strategy-lab/strategies")
def strategy_lab_strategies() -> dict:
    return {"strategies": [strategy.public_payload() for strategy in load_enabled_strategies()]}


@router.post("/strategy-lab/backtests")
def strategy_lab_run_backtest(body: BacktestBody) -> dict:
    try:
        result = run_lean_backtest(body.strategy_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return result.model_dump()


@router.get("/strategy-lab/backtests/latest")
def strategy_lab_latest_backtest() -> dict:
    latest = read_latest_backtest()
    return {"latest": latest.model_dump() if latest is not None else None}


def _normalize_path_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")
    return normalized


@router.get("/market/quote/{ticker}")
def market_quote(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    normalized = _normalize_path_ticker(ticker)
    return provider.get_quote(normalized).model_dump()


@router.get("/market/history/{ticker}")
def market_history(
    ticker: str = Path(min_length=1),
    interval: Literal["1d", "1W", "1M"] = "1d",
    start_date: str | None = None,
    end_date: str | None = None,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> list[dict]:
    normalized = _normalize_path_ticker(ticker)
    return [
        bar.model_dump()
        for bar in provider.get_price_history(
            normalized,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
    ]


@router.get("/market/fundamentals/{ticker}")
def market_fundamentals(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    normalized = _normalize_path_ticker(ticker)
    return provider.get_fundamentals(normalized).model_dump()


@router.get("/market/snapshot/{ticker}")
def market_snapshot(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    settings = get_settings()
    normalized = _normalize_path_ticker(ticker)
    snapshot = provider.get_market_snapshot(normalized)
    return {
        "ticker": snapshot.ticker,
        "quote": snapshot.quote.model_dump(),
        "fundamentals": snapshot.fundamentals.model_dump(),
        "history": [bar.model_dump() for bar in snapshot.history],
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }


@router.post("/research")
def research(body: ResearchBody, provider: MarketDataProvider = Depends(get_market_data_provider)) -> dict:
    evidence = [
        EvidenceItemInput(
            title=item.title,
            summary=item.summary,
            source=item.source,
            source_url=item.source_url,
        )
        for item in provider.get_research_evidence(body.ticker)
    ]
    result = run_research_workflow(
        ResearchRequest(ticker=body.ticker, question=body.question, evidence=evidence)
    )
    return result.model_dump()
