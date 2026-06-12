from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow
from app.core.config import get_settings
from app.data.providers.registry import build_market_data_provider
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.portfolio import PositionInput, calculate_exposure
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


def get_market_data_provider():
    return build_market_data_provider(get_settings())


@router.get("/dashboard")
def dashboard() -> dict:
    settings = get_settings()
    provider = get_market_data_provider()
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
def data_sources_status() -> dict:
    settings = get_settings()
    provider = get_market_data_provider()
    return {
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }


@router.post("/research")
def research(body: ResearchBody) -> dict:
    provider = get_market_data_provider()
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
