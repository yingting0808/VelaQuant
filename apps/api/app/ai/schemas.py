from pydantic import BaseModel, Field, field_validator


class EvidenceItemInput(BaseModel):
    title: str
    summary: str
    source: str
    source_url: str


class ResearchRequest(BaseModel):
    ticker: str = Field(min_length=1)
    question: str = Field(min_length=1)
    evidence: list[EvidenceItemInput]

    @field_validator("ticker", "question")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TradePlanDraft(BaseModel):
    entry_condition: str
    invalidation_condition: str
    risk_notes: list[str]
    requires_human_review: bool = True


class ResearchResult(BaseModel):
    ticker: str
    status: str
    summary: str
    bull_case: str
    bear_case: str
    watch_items: list[str]
    evidence_count: int
    trade_plan_draft: TradePlanDraft
