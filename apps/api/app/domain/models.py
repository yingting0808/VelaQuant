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
