from collections.abc import Iterator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow
from app.core.config import get_settings
from app.data.providers.base import MarketDataProvider
from app.data.providers.registry import build_market_data_provider
from app.db.session import get_session
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.lean_backtest import (
    BacktestParameterValidationError,
    read_backtest_history,
    read_latest_backtest,
    run_lean_backtest,
)
from app.services.paper_trading import (
    PaperOrderCreate,
    get_paper_trading_summary,
    list_paper_run_events,
    list_paper_runs,
    run_daily_paper_trading_loop,
    submit_paper_order,
)
from app.services.paper_scheduler import get_paper_scheduler_status
from app.services.portfolio import PositionInput, calculate_exposure
from app.services.research_notebook import ResearchNoteCreate, save_research_result_as_note
from app.services.strategy_catalog import UnknownStrategyError, load_enabled_strategies
from app.services.strategy_attribution import attribute_current_paper_strategy
from app.services.strategy_evaluation import evaluate_current_paper_strategy
from app.services.strategy_lab import get_strategy_lab_status
from app.services.strategy_registry import get_strategy_registry
from app.services.workspace import (
    NoteCreate,
    PositionUpsert,
    WatchlistUpsert,
    create_note,
    delete_position,
    delete_watchlist_item,
    get_portfolio_payload,
    get_workspace_summary,
    import_positions_csv,
    list_notes,
    list_watchlist_items,
    upsert_position,
    upsert_watchlist_item,
)
from app.trading_core.engine import TradingEngine
from app.trading_core.event_bus import InMemoryEventBus
from app.trading_core.events import MarketEvent
from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskEngine, RiskLimits
from app.trading_core.strategy import DeterministicWatchlistStrategy

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
    parameters: dict[str, str] = Field(default_factory=dict)

    @field_validator("strategy_id")
    @classmethod
    def strip_strategy_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class ImportPositionsBody(BaseModel):
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TradingCoreDryRunBody(BaseModel):
    event: MarketEvent
    portfolio: PortfolioState
    watchlist: list[str] = Field(default_factory=list)
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    strategy_notional: float = Field(default=1500, gt=0)


def get_market_data_provider() -> Iterator[MarketDataProvider]:
    provider = build_market_data_provider(get_settings())
    try:
        yield provider
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


@router.get("/dashboard")
def dashboard(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    portfolio = get_portfolio_payload(session, provider)
    alerts = generate_event_alerts(
        portfolio_tickers=[item.ticker for item in portfolio.positions],
        candidates=[
            AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="mock_sec"),
            AlertCandidate(ticker="NVDA", title="NVDA news", reason="News event", source="mock_news"),
        ],
    )
    return {
        "portfolio": {
            "name": portfolio.name,
            "total_market_value": portfolio.total_market_value,
            "positions": [item.model_dump() for item in portfolio.positions],
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


@router.get("/workspace")
def workspace_summary(session: Session = Depends(get_session)) -> dict:
    return get_workspace_summary(session).model_dump()


@router.get("/portfolio")
def portfolio_workspace(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_portfolio_payload(session, provider).model_dump()


@router.put("/portfolio/positions")
def portfolio_upsert_position(body: PositionUpsert, session: Session = Depends(get_session)) -> dict:
    return upsert_position(session, body).model_dump()


@router.delete("/portfolio/positions/{ticker}")
def portfolio_delete_position(ticker: str = Path(min_length=1), session: Session = Depends(get_session)) -> dict:
    try:
        deleted = delete_position(session, ticker)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return deleted.model_dump()


@router.post("/portfolio/import")
def portfolio_import_positions(
    body: ImportPositionsBody,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return import_positions_csv(session, body.content, provider=provider).model_dump()


@router.get("/watchlist")
def watchlist_workspace(session: Session = Depends(get_session)) -> dict:
    return {"items": [item.model_dump() for item in list_watchlist_items(session)]}


@router.post("/watchlist")
def watchlist_upsert(body: WatchlistUpsert, session: Session = Depends(get_session)) -> dict:
    return upsert_watchlist_item(session, body).model_dump()


@router.delete("/watchlist/{ticker}")
def watchlist_delete(ticker: str = Path(min_length=1), session: Session = Depends(get_session)) -> dict:
    try:
        deleted = delete_watchlist_item(session, ticker)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return deleted.model_dump()


@router.get("/notes")
def notes_workspace(session: Session = Depends(get_session)) -> dict:
    return {"notes": [note.model_dump() for note in list_notes(session)]}


@router.post("/notes")
def notes_create(body: NoteCreate, session: Session = Depends(get_session)) -> dict:
    return create_note(session, body).model_dump()


@router.post("/research/notes")
def research_note_create(body: ResearchNoteCreate, session: Session = Depends(get_session)) -> dict:
    return save_research_result_as_note(session, body).model_dump()


@router.get("/paper-trading/summary")
def paper_trading_summary(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_paper_trading_summary(session, provider).model_dump()


@router.post("/paper-trading/daily-run")
def paper_trading_daily_run(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return run_daily_paper_trading_loop(session, provider).model_dump()


@router.post("/paper-trading/orders")
def paper_trading_order(
    body: PaperOrderCreate,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    try:
        order = submit_paper_order(session, provider, body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return order.model_dump()


@router.get("/paper-trading/scheduler")
def paper_trading_scheduler_status() -> dict:
    return get_paper_scheduler_status().model_dump()


@router.get("/paper-trading/runs")
def paper_trading_runs(session: Session = Depends(get_session)) -> dict:
    return {"runs": [run.model_dump() for run in list_paper_runs(session)]}


@router.get("/paper-trading/runs/{run_id}/events")
def paper_trading_run_events(run_id: UUID, session: Session = Depends(get_session)) -> dict:
    return {"events": [event.model_dump() for event in list_paper_run_events(session, run_id)]}


@router.post("/trading-core/dry-run")
def trading_core_dry_run(body: TradingCoreDryRunBody) -> dict:
    strategy = DeterministicWatchlistStrategy(watchlist=body.watchlist, notional=body.strategy_notional)
    risk_engine = RiskEngine(body.risk_limits)
    event_bus = InMemoryEventBus()
    engine = TradingEngine(strategy=strategy, risk_engine=risk_engine, event_bus=event_bus)
    return engine.process_event(body.event, body.portfolio).model_dump(mode="json")


@router.get("/strategy-lab/status")
def strategy_lab_status() -> dict:
    return get_strategy_lab_status().model_dump()


@router.get("/strategy-lab/evaluation")
def strategy_lab_evaluation(session: Session = Depends(get_session)) -> dict:
    return evaluate_current_paper_strategy(session).model_dump()


@router.get("/strategy-lab/attribution")
def strategy_lab_attribution(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return attribute_current_paper_strategy(session, provider=provider).model_dump()


@router.get("/strategy-lab/registry")
def strategy_lab_registry(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_strategy_registry(session, provider=provider).model_dump()


@router.get("/strategy-lab/strategies")
def strategy_lab_strategies() -> dict:
    return {"strategies": [strategy.public_payload() for strategy in load_enabled_strategies()]}


@router.post("/strategy-lab/backtests")
def strategy_lab_run_backtest(body: BacktestBody) -> dict:
    try:
        result = run_lean_backtest(body.strategy_id, parameter_overrides=body.parameters)
    except UnknownStrategyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BacktestParameterValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.model_dump()


@router.get("/strategy-lab/backtests/latest")
def strategy_lab_latest_backtest() -> dict:
    latest = read_latest_backtest()
    return {"latest": latest.model_dump() if latest is not None else None}


@router.get("/strategy-lab/backtests/history")
def strategy_lab_backtest_history(limit: int = 10) -> dict:
    history = read_backtest_history(limit=limit)
    return {"history": [item.model_dump() for item in history]}


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
