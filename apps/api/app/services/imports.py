import csv
from io import StringIO
from typing import Any

from pydantic import BaseModel


class ImportedPosition(BaseModel):
    ticker: str
    quantity: float
    average_cost: float
    currency: str = "USD"


class ImportResult(BaseModel):
    positions: list[ImportedPosition]
    errors: list[dict[str, Any]]


def _parse_float(
    value: str,
    row_number: int,
    field: str,
    errors: list[dict[str, Any]],
) -> float | None:
    try:
        return float(value)
    except ValueError:
        errors.append({"row": row_number, "field": field, "message": f"{field} must be a number"})
        return None


def parse_positions_csv(content: str) -> ImportResult:
    reader = csv.DictReader(StringIO(content))
    positions: list[ImportedPosition] = []
    errors: list[dict[str, Any]] = []

    for index, row in enumerate(reader, start=2):
        ticker = (row.get("ticker") or "").strip().upper()
        quantity_raw = (row.get("quantity") or "").strip()
        average_cost_raw = (row.get("average_cost") or "").strip()
        currency = (row.get("currency") or "USD").strip().upper()

        row_errors_before = len(errors)
        if not ticker:
            errors.append({"row": index, "field": "ticker", "message": "ticker is required"})
        quantity = _parse_float(quantity_raw, index, "quantity", errors)
        average_cost = _parse_float(average_cost_raw, index, "average_cost", errors)

        if len(errors) == row_errors_before and quantity is not None and average_cost is not None:
            positions.append(
                ImportedPosition(
                    ticker=ticker,
                    quantity=quantity,
                    average_cost=average_cost,
                    currency=currency,
                )
            )

    return ImportResult(positions=positions, errors=errors)
