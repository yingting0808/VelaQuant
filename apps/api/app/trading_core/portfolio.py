from pydantic import BaseModel, ConfigDict, Field, field_validator


class PortfolioPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    market_value: float = Field(ge=0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized


class PortfolioState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash: float = Field(ge=0)
    equity: float = Field(gt=0)
    positions: list[PortfolioPosition] = Field(default_factory=list)
    orders_today: int = Field(default=0, ge=0)

    def position_value(self, ticker: str) -> float:
        normalized = ticker.strip().upper()
        return round(sum(position.market_value for position in self.positions if position.ticker == normalized), 2)

    def has_position(self, ticker: str) -> bool:
        return self.position_value(ticker) > 0
