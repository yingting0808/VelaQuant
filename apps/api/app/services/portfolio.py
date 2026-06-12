from pydantic import BaseModel, Field


class PositionInput(BaseModel):
    ticker: str = Field(min_length=1)
    quantity: float
    price: float


class ExposureItem(BaseModel):
    ticker: str
    market_value: float
    weight: float


class ExposureResult(BaseModel):
    total_market_value: float
    items: list[ExposureItem]


def calculate_exposure(positions: list[PositionInput]) -> ExposureResult:
    for position in positions:
        if position.quantity < 0:
            raise ValueError(f"{position.ticker} quantity must be non-negative")
        if position.price < 0:
            raise ValueError(f"{position.ticker} price must be non-negative")

    market_values = [
        ExposureItem(
            ticker=position.ticker.upper(),
            market_value=position.quantity * position.price,
            weight=0,
        )
        for position in positions
    ]
    total = sum(item.market_value for item in market_values)
    if total == 0:
        return ExposureResult(total_market_value=0, items=market_values)

    weighted = [
        ExposureItem(
            ticker=item.ticker,
            market_value=item.market_value,
            weight=round(item.market_value / total, 6),
        )
        for item in market_values
    ]
    return ExposureResult(total_market_value=total, items=weighted)
