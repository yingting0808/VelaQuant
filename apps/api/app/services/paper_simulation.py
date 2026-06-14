from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session, select

from app.data.providers.base import (
    EvidenceItem,
    FundamentalSnapshot,
    MarketDataProvider,
    MarketSnapshot,
    PriceHistoryBar,
    ProviderStatus,
    Quote,
)
from app.domain.models import PaperReview, PaperRun, PaperRunStatus, PaperRunTrigger, PaperTradingMode
from app.services.alpha_validation import get_alpha_validation
from app.services.paper_review_trend import get_paper_review_trend
from app.services.paper_trading import run_daily_paper_trading_loop
from app.services.workspace import get_or_create_default_workspace


PaperSimulationScenario = Literal["baseline", "bullish", "bearish", "volatile"]


class PaperSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    days: int = Field(default=5, ge=1, le=60)
    scenario: PaperSimulationScenario = "bullish"

    @field_validator("scenario")
    @classmethod
    def normalize_scenario(cls, value: str) -> str:
        return value.strip().lower()


class PaperSimulationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trading_day: str
    run_status: str
    orders_count: int
    candidates_count: int
    positions_count: int
    review_id: str | None


class PaperSimulationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: PaperSimulationScenario
    start_date: str
    days_requested: int
    days_completed: int
    days_skipped: int
    review_day_count: int
    consecutive_positive_expectancy_days: int
    latest_expectancy: float
    average_expectancy: float
    event_chain_count: int
    alpha_ready: bool
    blockers: list[str]
    items: list[PaperSimulationItem]
    summary: str


def run_paper_simulation_lab(
    session: Session,
    base_provider: MarketDataProvider,
    request: PaperSimulationRequest,
) -> PaperSimulationPayload:
    workspace = get_or_create_default_workspace(session)
    start = request.start_date or _default_start_date(session, workspace.team.id)
    known_run_ids = {run.id for run in session.exec(select(PaperRun).where(PaperRun.team_id == workspace.team.id)).all()}
    request_items: list[PaperSimulationItem] = []
    completed = 0
    skipped = 0
    for day_index in range(request.days):
        trading_day = (start + timedelta(days=day_index)).isoformat()
        existing_run = _latest_run_for_trading_day(session, workspace.team.id, trading_day)
        scenario_provider = _ScenarioMarketDataProvider(
            base_provider=base_provider,
            scenario=request.scenario,
            day_index=day_index,
            trading_day=trading_day,
        )
        run_daily_paper_trading_loop(
            session,
            scenario_provider,
            trigger=PaperRunTrigger.simulation,
            trading_day=trading_day,
            account_mode=PaperTradingMode.simulation,
        )
        new_runs = [
            run
            for run in session.exec(
                select(PaperRun).where(PaperRun.team_id == workspace.team.id, PaperRun.trading_day == trading_day)
            ).all()
            if run.id not in known_run_ids
        ]
        if new_runs:
            latest_run = max(new_runs, key=lambda run: run.started_at)
            request_items.append(_item(latest_run))
            known_run_ids.add(latest_run.id)
            if latest_run.status == PaperRunStatus.completed:
                completed += 1
            elif latest_run.status == PaperRunStatus.skipped:
                skipped += 1
        else:
            existing_run = existing_run or _latest_run_for_trading_day(session, workspace.team.id, trading_day)
            if existing_run is not None:
                request_items.append(_skipped_item(existing_run))
                skipped += 1

    request_items = sorted(request_items, key=lambda item: item.trading_day)
    as_of_trading_day = (start + timedelta(days=request.days - 1)).isoformat()
    trend = get_paper_review_trend(
        session,
        team_id=workspace.team.id,
        limit=max(request.days, 1),
        as_of_trading_day=as_of_trading_day,
    )
    alpha = get_alpha_validation(session, team_id=workspace.team.id, as_of_trading_day=as_of_trading_day)
    return PaperSimulationPayload(
        scenario=request.scenario,
        start_date=start.isoformat(),
        days_requested=request.days,
        days_completed=completed,
        days_skipped=skipped,
        review_day_count=alpha.review_day_count,
        consecutive_positive_expectancy_days=alpha.consecutive_positive_expectancy_days,
        latest_expectancy=alpha.latest_expectancy,
        average_expectancy=alpha.average_expectancy,
        event_chain_count=alpha.event_chain_count,
        alpha_ready=alpha.alpha_ready,
        blockers=alpha.blockers,
        items=request_items,
        summary=_summary(request.scenario, completed, skipped, request.days, trend.latest_expectancy, alpha.blockers),
    )


def _default_start_date(session: Session, team_id) -> date:
    latest_review_day: date | None = None
    reviews = session.exec(select(PaperReview).where(PaperReview.team_id == team_id)).all()
    for review in reviews:
        try:
            review_day = date.fromisoformat(review.trading_day)
        except ValueError:
            continue
        if latest_review_day is None or review_day > latest_review_day:
            latest_review_day = review_day
    if latest_review_day is not None:
        return latest_review_day + timedelta(days=1)
    return datetime.now(timezone.utc).date() + timedelta(days=1)


class _ScenarioMarketDataProvider:
    def __init__(
        self,
        *,
        base_provider: MarketDataProvider,
        scenario: PaperSimulationScenario,
        day_index: int,
        trading_day: str,
    ) -> None:
        self._base_provider = base_provider
        self._scenario = scenario
        self._day_index = day_index
        self._trading_day = trading_day

    def get_quote(self, ticker: str) -> Quote:
        quote = self._base_provider.get_quote(ticker)
        if quote.price is None:
            return quote
        return quote.model_copy(
            update={
                "price": round(float(quote.price) * _scenario_multiplier(self._scenario, self._day_index), 2),
                "source": f"{quote.source}:paper_simulation_{self._scenario}",
                "updated_at": f"{self._trading_day}T21:00:00Z",
                "message": f"Paper simulation {self._scenario} day {self._day_index + 1}.",
            }
        )

    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        return self._base_provider.get_price_history(ticker, start_date=start_date, end_date=end_date, interval=interval)

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return self._base_provider.get_fundamentals(ticker)

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.strip().upper()
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=self.get_price_history(normalized),
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        return self._base_provider.get_research_evidence(ticker)

    def get_statuses(self) -> list[ProviderStatus]:
        return self._base_provider.get_statuses()


def _scenario_multiplier(scenario: PaperSimulationScenario, day_index: int) -> float:
    if scenario == "bullish":
        return 1 + 0.12 * day_index
    if scenario == "bearish":
        return max(0.2, 1 - 0.06 * day_index)
    if scenario == "volatile":
        pattern = [1.0, 1.14, 0.93, 1.18, 0.96]
        cycle = day_index // len(pattern)
        return pattern[day_index % len(pattern)] * (1 + 0.02 * cycle)
    return 1.0


def _item(run: PaperRun) -> PaperSimulationItem:
    return PaperSimulationItem(
        trading_day=run.trading_day,
        run_status=run.status.value,
        orders_count=run.orders_count,
        candidates_count=run.candidates_count,
        positions_count=run.positions_count,
        review_id=str(run.review_id) if run.review_id is not None else None,
    )


def _skipped_item(run: PaperRun) -> PaperSimulationItem:
    return PaperSimulationItem(
        trading_day=run.trading_day,
        run_status=PaperRunStatus.skipped.value,
        orders_count=run.orders_count,
        candidates_count=run.candidates_count,
        positions_count=run.positions_count,
        review_id=str(run.review_id) if run.review_id is not None else None,
    )


def _latest_run_for_trading_day(session: Session, team_id, trading_day: str) -> PaperRun | None:
    return session.exec(
        select(PaperRun)
        .where(PaperRun.team_id == team_id, PaperRun.trading_day == trading_day)
        .order_by(PaperRun.started_at.desc())
    ).first()


def _summary(
    scenario: PaperSimulationScenario,
    completed: int,
    skipped: int,
    requested: int,
    latest_expectancy: float,
    blockers: list[str],
) -> str:
    if completed == requested and latest_expectancy > 0:
        return (
            f"Paper simulation completed {completed}/{requested} days under {scenario}; "
            f"latest expectancy is positive, remaining blockers: {', '.join(blockers) or 'none'}."
        )
    return (
        f"Paper simulation completed {completed}/{requested} days under {scenario}; "
        f"skipped {skipped}, latest expectancy {latest_expectancy:.2f}, blockers: {', '.join(blockers) or 'none'}."
    )
