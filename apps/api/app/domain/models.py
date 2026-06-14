from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemberRole(str, Enum):
    owner = "owner"
    analyst = "analyst"
    viewer = "viewer"


class AlertStatus(str, Enum):
    open = "open"
    assigned = "assigned"
    closed = "closed"


class PaperTradingMode(str, Enum):
    paper = "paper"
    shadow = "shadow"
    live_small = "live_small"
    simulation = "simulation"


class PaperCandidateStatus(str, Enum):
    proposed = "proposed"
    ordered = "ordered"
    dismissed = "dismissed"


class PaperOrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class PaperOrderStatus(str, Enum):
    filled = "filled"
    rejected = "rejected"


class PaperReadiness(str, Enum):
    collecting = "collecting"
    negative_expectancy = "negative_expectancy"
    watch = "watch"
    paper_ready = "paper_ready"


class PaperRunTrigger(str, Enum):
    manual = "manual"
    scheduled = "scheduled"
    simulation = "simulation"


class PaperRunStatus(str, Enum):
    started = "started"
    completed = "completed"
    skipped = "skipped"
    failed = "failed"


class Team(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utc_now)

    portfolios: list["Portfolio"] = Relationship(back_populates="team")


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True)
    display_name: str
    created_at: datetime = Field(default_factory=utc_now)


class TeamMembership(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    role: MemberRole
    created_at: datetime = Field(default_factory=utc_now)


class Security(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    ticker: str = Field(index=True)
    name: str
    exchange: str = "NASDAQ"
    cik: Optional[str] = Field(default=None, index=True)
    currency: str = "USD"
    updated_at: datetime = Field(default_factory=utc_now)


class WatchlistItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: str = Field(index=True)
    thesis: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Portfolio(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: Optional[UUID] = Field(default=None, foreign_key="team.id", index=True)
    name: str
    base_currency: str = "USD"
    created_at: datetime = Field(default_factory=utc_now)

    team: Optional[Team] = Relationship(back_populates="portfolios")
    positions: list["Position"] = Relationship(back_populates="portfolio")


class Position(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    portfolio_id: Optional[UUID] = Field(default=None, foreign_key="portfolio.id", index=True)
    ticker: str = Field(index=True)
    quantity: float
    average_cost: float
    currency: str = "USD"
    updated_at: datetime = Field(default_factory=utc_now)

    portfolio: Optional[Portfolio] = Relationship(back_populates="positions")


class Alert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: str = Field(index=True)
    title: str
    reason: str
    status: AlertStatus = Field(default=AlertStatus.open, index=True)
    source: str
    created_at: datetime = Field(default_factory=utc_now)


class Note(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: Optional[str] = Field(default=None, index=True)
    title: str
    body: str
    created_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utc_now)


class AiRun(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    prompt: str
    output_json: str
    evidence_json: str
    created_at: datetime = Field(default_factory=utc_now)


class AuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: Optional[UUID] = Field(default=None, foreign_key="team.id", index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)


class PaperAccount(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    strategy_id: str = Field(default="deterministic_watchlist_v1", index=True)
    name: str
    mode: PaperTradingMode = Field(default=PaperTradingMode.paper, index=True)
    starting_cash: float = 100000.0
    cash: float = 100000.0
    realized_pnl: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PaperCandidate(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: str = Field(index=True)
    action: PaperOrderSide = Field(default=PaperOrderSide.buy, index=True)
    rank: int
    confidence: float
    thesis: str
    risk_notes: str
    evidence_summary: str
    proposed_quantity: float
    status: PaperCandidateStatus = Field(default=PaperCandidateStatus.proposed, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class PaperOrder(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: UUID = Field(foreign_key="paperaccount.id", index=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    strategy_id: str = Field(default="deterministic_watchlist_v1", index=True)
    ticker: str = Field(index=True)
    side: PaperOrderSide = Field(index=True)
    order_type: str = "market"
    quantity: float
    status: PaperOrderStatus = Field(default=PaperOrderStatus.filled, index=True)
    fill_price: Optional[float] = None
    realized_pnl: float = 0.0
    rejection_reason: Optional[str] = None
    core_order_id: Optional[str] = Field(default=None, index=True)
    core_intent_id: Optional[str] = Field(default=None, index=True)
    risk_status: Optional[str] = Field(default=None, index=True)
    risk_code: Optional[str] = Field(default=None, index=True)
    risk_reason: Optional[str] = None
    state_history_json: str = "[]"
    submitted_at: datetime = Field(default_factory=utc_now)
    filled_at: Optional[datetime] = None


class PaperPosition(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: UUID = Field(foreign_key="paperaccount.id", index=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: str = Field(index=True)
    quantity: float
    average_cost: float
    last_price: Optional[float] = None
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    updated_at: datetime = Field(default_factory=utc_now)


class PaperReview(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: UUID = Field(foreign_key="paperaccount.id", index=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    trading_day: str = Field(index=True)
    equity: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int
    win_rate: float
    average_win: float
    average_loss: float
    expectancy: float
    readiness: PaperReadiness = Field(default=PaperReadiness.collecting, index=True)
    notes: str
    created_at: datetime = Field(default_factory=utc_now)


class PaperRiskSetting(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    mode: PaperTradingMode = Field(default=PaperTradingMode.paper, index=True)
    max_order_notional: float = 2000.0
    max_position_weight: float = 0.1
    max_daily_orders: int = 5
    source: str = "default"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PaperRun(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    account_id: Optional[UUID] = Field(default=None, foreign_key="paperaccount.id", index=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    review_id: Optional[UUID] = Field(default=None, foreign_key="paperreview.id", index=True)
    trading_day: str = Field(index=True)
    trigger: PaperRunTrigger = Field(default=PaperRunTrigger.manual, index=True)
    status: PaperRunStatus = Field(default=PaperRunStatus.started, index=True)
    candidates_count: int = 0
    orders_count: int = 0
    positions_count: int = 0
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None


class StrategyLifecycleState(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    strategy_id: str = Field(index=True)
    current_stage: str = Field(default="paper", index=True)
    transition_reason: str = ""
    auto_transition_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ShadowObservation(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    strategy_id: str = Field(default="deterministic_watchlist_v1", index=True)
    trading_day: str = Field(index=True)
    status: str = Field(default="blocked", index=True)
    can_request_shadow_review: bool = False
    observed_intent_count: int = 0
    would_route_order_count: int = 0
    event_chain_count: int = 0
    residual_risk_count: int = 0
    blocked_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class StrategyAlphaSnapshot(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    strategy_id: str = Field(default="deterministic_watchlist_v1", index=True)
    trading_day: str = Field(index=True)
    alpha_ready: bool = Field(default=False, index=True)
    validation_level: str = Field(default="collecting", index=True)
    blockers_json: str = "[]"
    review_day_count: int = 0
    consecutive_positive_expectancy_days: int = 0
    filled_order_count: int = 0
    closed_trade_count: int = 0
    event_chain_count: int = 0
    latest_expectancy: float = 0.0
    average_expectancy: float = 0.0
    max_drawdown: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StrategyCompetitionSnapshot(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    trading_day: str = Field(index=True)
    status: str = Field(default="collecting", index=True)
    selected_strategy_id: Optional[str] = Field(default=None, index=True)
    strategy_count: int = 0
    allocatable_strategy_count: int = 0
    competition_ready: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StrategyCompetitionEntry(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(foreign_key="strategycompetitionsnapshot.id", index=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    strategy_id: str = Field(index=True)
    name: str
    version: str
    source: str = Field(index=True)
    execution_mode: str = Field(index=True)
    status: str = Field(index=True)
    rank: int
    ranking_score: float = 0.0
    allocation_weight: float = 0.0
    eligible_for_allocation: bool = Field(default=False, index=True)
    recommended_action: str = Field(default="collect_more_evidence", index=True)
    blockers_json: str = "[]"
    readiness: str = Field(index=True)
    promotion_gate: str
    sample_size: int = 0
    filled_order_count: int = 0
    observed_pnl: float = 0.0
    primary_regime: str = ""
    signal_quality_score: float = 0.0
    supports_live: bool = False
    supports_hot_swap: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class StrategyVersionRecord(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    strategy_id: str = Field(index=True)
    version: str = Field(index=True)
    parameters_json: str = "{}"
    status: str = Field(default="registered", index=True)
    created_at: datetime = Field(default_factory=utc_now)


class StrategyActiveBinding(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    strategy_id: str = Field(index=True)
    active_version: str = Field(index=True)
    previous_version: Optional[str] = Field(default=None, index=True)
    activation_reason: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class CoreEventLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    run_id: Optional[UUID] = Field(default=None, foreign_key="paperrun.id", index=True)
    event_id: str = Field(index=True)
    topic: str = Field(index=True)
    sequence: int
    correlation_id: str = Field(index=True)
    causation_id: Optional[str] = Field(default=None, index=True)
    payload_json: str
    published_at: datetime = Field(default_factory=utc_now)
