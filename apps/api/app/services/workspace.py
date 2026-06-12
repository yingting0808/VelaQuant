from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.data.providers.base import MarketDataProvider
from app.domain.models import Note, Portfolio, Position, Team, WatchlistItem
from app.services.imports import ImportResult, parse_positions_csv
from app.services.portfolio import PositionInput, calculate_exposure


DEFAULT_TEAM_NAME = "个人工作区"
DEFAULT_PORTFOLIO_NAME = "主组合"


class WorkspaceSummary(BaseModel):
    team_id: UUID
    team_name: str
    portfolio_id: UUID
    portfolio_name: str
    position_count: int
    watchlist_count: int
    note_count: int


class PositionPayload(BaseModel):
    id: UUID
    ticker: str
    quantity: float
    average_cost: float
    currency: str
    price: float | None
    market_value: float
    weight: float
    updated_at: datetime


class PortfolioPayload(BaseModel):
    id: UUID
    name: str
    base_currency: str
    total_market_value: float
    positions: list[PositionPayload]


class PositionUpsert(BaseModel):
    ticker: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    average_cost: float = Field(ge=0)
    currency: str = "USD"

    @field_validator("ticker", "currency")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


class WatchlistItemPayload(BaseModel):
    id: UUID
    ticker: str
    thesis: str
    created_at: datetime


class WatchlistUpsert(BaseModel):
    ticker: str = Field(min_length=1)
    thesis: str = ""

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized

    @field_validator("thesis")
    @classmethod
    def normalize_thesis(cls, value: str) -> str:
        return value.strip()


class NotePayload(BaseModel):
    id: UUID
    ticker: str | None
    title: str
    body: str
    created_at: datetime


class NoteCreate(BaseModel):
    ticker: str | None = None
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)

    @field_validator("ticker")
    @classmethod
    def normalize_optional_ticker(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("title", "body")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


class PositionImportPayload(BaseModel):
    imported_count: int
    errors: list[dict]
    portfolio: PortfolioPayload | None = None


@dataclass(frozen=True)
class DefaultWorkspace:
    team: Team
    portfolio: Portfolio


def get_or_create_default_workspace(session: Session) -> DefaultWorkspace:
    team = session.exec(select(Team).where(Team.name == DEFAULT_TEAM_NAME)).first()
    if team is None:
        team = Team(name=DEFAULT_TEAM_NAME)
        session.add(team)
        session.commit()
        session.refresh(team)

    portfolio = session.exec(
        select(Portfolio).where(Portfolio.team_id == team.id, Portfolio.name == DEFAULT_PORTFOLIO_NAME)
    ).first()
    if portfolio is None:
        portfolio = Portfolio(team_id=team.id, name=DEFAULT_PORTFOLIO_NAME)
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)

    _seed_positions_if_empty(session, portfolio)
    _seed_watchlist_if_empty(session, team)
    return DefaultWorkspace(team=team, portfolio=portfolio)


def get_workspace_summary(session: Session) -> WorkspaceSummary:
    workspace = get_or_create_default_workspace(session)
    return WorkspaceSummary(
        team_id=workspace.team.id,
        team_name=workspace.team.name,
        portfolio_id=workspace.portfolio.id,
        portfolio_name=workspace.portfolio.name,
        position_count=len(_portfolio_positions(session, workspace.portfolio)),
        watchlist_count=len(_team_watchlist(session, workspace.team)),
        note_count=len(_team_notes(session, workspace.team)),
    )


def get_portfolio_payload(session: Session, provider: MarketDataProvider) -> PortfolioPayload:
    workspace = get_or_create_default_workspace(session)
    positions = _portfolio_positions(session, workspace.portfolio)
    priced_positions: list[tuple[Position, float | None, float]] = []
    exposure_inputs: list[PositionInput] = []

    for position in positions:
        quote = provider.get_quote(position.ticker)
        price = quote.price if quote.price is not None else position.average_cost
        priced_positions.append((position, quote.price, price))
        exposure_inputs.append(PositionInput(ticker=position.ticker, quantity=position.quantity, price=price))

    exposure = calculate_exposure(exposure_inputs)
    exposure_by_ticker = {item.ticker: item for item in exposure.items}
    payload_positions = [
        PositionPayload(
            id=position.id,
            ticker=position.ticker,
            quantity=position.quantity,
            average_cost=position.average_cost,
            currency=position.currency,
            price=quote_price,
            market_value=round(exposure_by_ticker[position.ticker].market_value, 2),
            weight=exposure_by_ticker[position.ticker].weight,
            updated_at=position.updated_at,
        )
        for position, quote_price, _price in priced_positions
    ]
    return PortfolioPayload(
        id=workspace.portfolio.id,
        name=workspace.portfolio.name,
        base_currency=workspace.portfolio.base_currency,
        total_market_value=round(exposure.total_market_value, 2),
        positions=payload_positions,
    )


def upsert_position(session: Session, data: PositionUpsert) -> PositionPayload:
    workspace = get_or_create_default_workspace(session)
    position = _find_position(session, workspace.portfolio, data.ticker)
    if position is None:
        position = Position(
            portfolio_id=workspace.portfolio.id,
            ticker=data.ticker,
            quantity=data.quantity,
            average_cost=data.average_cost,
            currency=data.currency,
        )
        session.add(position)
    else:
        position.quantity = data.quantity
        position.average_cost = data.average_cost
        position.currency = data.currency
    session.commit()
    session.refresh(position)
    return _position_payload_without_quote(position)


def delete_position(session: Session, ticker: str) -> PositionPayload:
    workspace = get_or_create_default_workspace(session)
    normalized = ticker.strip().upper()
    position = _find_position(session, workspace.portfolio, normalized)
    if position is None:
        raise ValueError(f"Unknown position ticker: {normalized}")
    payload = _position_payload_without_quote(position)
    session.delete(position)
    session.commit()
    return payload


def import_positions_csv(session: Session, content: str, provider: MarketDataProvider | None = None) -> PositionImportPayload:
    parsed: ImportResult = parse_positions_csv(content)
    for position in parsed.positions:
        upsert_position(
            session,
            PositionUpsert(
                ticker=position.ticker,
                quantity=position.quantity,
                average_cost=position.average_cost,
                currency=position.currency,
            ),
        )
    portfolio = get_portfolio_payload(session, provider) if provider is not None else None
    return PositionImportPayload(imported_count=len(parsed.positions), errors=parsed.errors, portfolio=portfolio)


def list_watchlist_items(session: Session) -> list[WatchlistItemPayload]:
    workspace = get_or_create_default_workspace(session)
    return [_watchlist_payload(item) for item in _team_watchlist(session, workspace.team)]


def upsert_watchlist_item(session: Session, data: WatchlistUpsert) -> WatchlistItemPayload:
    workspace = get_or_create_default_workspace(session)
    item = session.exec(select(WatchlistItem).where(WatchlistItem.team_id == workspace.team.id, WatchlistItem.ticker == data.ticker)).first()
    if item is None:
        item = WatchlistItem(team_id=workspace.team.id, ticker=data.ticker, thesis=data.thesis)
        session.add(item)
    else:
        item.thesis = data.thesis
    session.commit()
    session.refresh(item)
    return _watchlist_payload(item)


def delete_watchlist_item(session: Session, ticker: str) -> WatchlistItemPayload:
    workspace = get_or_create_default_workspace(session)
    normalized = ticker.strip().upper()
    item = session.exec(select(WatchlistItem).where(WatchlistItem.team_id == workspace.team.id, WatchlistItem.ticker == normalized)).first()
    if item is None:
        raise ValueError(f"Unknown watchlist ticker: {normalized}")
    payload = _watchlist_payload(item)
    session.delete(item)
    session.commit()
    return payload


def list_notes(session: Session) -> list[NotePayload]:
    workspace = get_or_create_default_workspace(session)
    return [_note_payload(note) for note in _team_notes(session, workspace.team)]


def create_note(session: Session, data: NoteCreate) -> NotePayload:
    workspace = get_or_create_default_workspace(session)
    note = Note(team_id=workspace.team.id, ticker=data.ticker, title=data.title, body=data.body)
    session.add(note)
    session.commit()
    session.refresh(note)
    return _note_payload(note)


def _seed_positions_if_empty(session: Session, portfolio: Portfolio) -> None:
    if _portfolio_positions(session, portfolio):
        return
    session.add(Position(portfolio_id=portfolio.id, ticker="AAPL", quantity=10, average_cost=165.0))
    session.add(Position(portfolio_id=portfolio.id, ticker="MSFT", quantity=5, average_cost=310.0))
    session.commit()


def _seed_watchlist_if_empty(session: Session, team: Team) -> None:
    if _team_watchlist(session, team):
        return
    session.add(WatchlistItem(team_id=team.id, ticker="NVDA", thesis="AI 基础设施龙头，关注估值和毛利率。"))
    session.add(WatchlistItem(team_id=team.id, ticker="AMZN", thesis="云业务与零售利润率修复。"))
    session.add(WatchlistItem(team_id=team.id, ticker="META", thesis="广告周期与 capex 敏感性。"))
    session.commit()


def _portfolio_positions(session: Session, portfolio: Portfolio) -> list[Position]:
    return list(session.exec(select(Position).where(Position.portfolio_id == portfolio.id).order_by(Position.ticker)).all())


def _team_watchlist(session: Session, team: Team) -> list[WatchlistItem]:
    return list(session.exec(select(WatchlistItem).where(WatchlistItem.team_id == team.id).order_by(WatchlistItem.ticker)).all())


def _team_notes(session: Session, team: Team) -> list[Note]:
    return list(session.exec(select(Note).where(Note.team_id == team.id).order_by(Note.created_at.desc())).all())


def _find_position(session: Session, portfolio: Portfolio, ticker: str) -> Position | None:
    return session.exec(select(Position).where(Position.portfolio_id == portfolio.id, Position.ticker == ticker)).first()


def _position_payload_without_quote(position: Position) -> PositionPayload:
    return PositionPayload(
        id=position.id,
        ticker=position.ticker,
        quantity=position.quantity,
        average_cost=position.average_cost,
        currency=position.currency,
        price=None,
        market_value=round(position.quantity * position.average_cost, 2),
        weight=0,
        updated_at=position.updated_at,
    )


def _watchlist_payload(item: WatchlistItem) -> WatchlistItemPayload:
    return WatchlistItemPayload(id=item.id, ticker=item.ticker, thesis=item.thesis, created_at=item.created_at)


def _note_payload(note: Note) -> NotePayload:
    return NotePayload(id=note.id, ticker=note.ticker, title=note.title, body=note.body, created_at=note.created_at)
