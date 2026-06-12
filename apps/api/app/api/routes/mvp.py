from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow
from app.data.providers.mock import MockMarketDataProvider
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.portfolio import PositionInput, calculate_exposure

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


@router.get("/dashboard")
def dashboard() -> dict:
    provider = MockMarketDataProvider()
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
            "name": "Main Book",
            "total_market_value": exposure.total_market_value,
            "positions": [item.model_dump() for item in exposure.items],
        },
        "alerts": [alert.model_dump() for alert in alerts],
        "ai_prompts": [
            "Explain current page",
            "Find portfolio risks",
            "Generate bull/base/bear view",
            "Draft a trade plan",
        ],
    }


@router.post("/research")
def research(body: ResearchBody) -> dict:
    provider = MockMarketDataProvider()
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
