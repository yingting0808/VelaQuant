import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


API_ROOT = Path(__file__).resolve().parents[2]
LEAN_WORKSPACE_ROOT = API_ROOT / "lean-workspace"
DEFAULT_CATALOG_PATH = LEAN_WORKSPACE_ROOT / "strategies.json"


class UnknownStrategyError(ValueError):
    pass


class StrategyParameterDefinition(BaseModel):
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: Literal["ticker", "date", "integer", "number"]
    default: str = Field(min_length=1)
    min: float | None = None
    max: float | None = None
    required: bool = True


class StrategyDefinition(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    language: str = Field(min_length=1)
    asset_class: str = Field(min_length=1)
    default_symbol: str = Field(min_length=1)
    resolution: str = Field(min_length=1)
    project_path: Path
    enabled: bool = True
    parameters: list[StrategyParameterDefinition] = Field(default_factory=list)

    def public_payload(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "asset_class": self.asset_class,
            "default_symbol": self.default_symbol,
            "resolution": self.resolution,
            "enabled": self.enabled,
            "parameters": [parameter.model_dump() for parameter in self.parameters],
        }


def load_enabled_strategies(catalog_path: Path = DEFAULT_CATALOG_PATH) -> list[StrategyDefinition]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_root = catalog_path.parent.resolve()
    strategies: list[StrategyDefinition] = []
    for item in payload.get("strategies", []):
        if not item.get("enabled", True):
            continue

        strategy_payload = item.copy()
        strategy_payload["project_path"] = _resolve_project_path(strategy_payload["project_path"], catalog_root)
        strategies.append(StrategyDefinition(**strategy_payload))
    return strategies


def get_strategy_by_id(strategy_id: str, catalog_path: Path = DEFAULT_CATALOG_PATH) -> StrategyDefinition:
    normalized = strategy_id.strip()
    for strategy in load_enabled_strategies(catalog_path=catalog_path):
        if strategy.id == normalized:
            return strategy
    raise UnknownStrategyError(f"Unknown strategy_id: {normalized}")


def _resolve_project_path(raw_project_path: str, catalog_root: Path) -> Path:
    project_path = Path(raw_project_path)
    if project_path.is_absolute():
        raise ValueError(f"Invalid project_path: absolute paths are not allowed ({raw_project_path})")

    candidate = (catalog_root / project_path).resolve()
    try:
        candidate.relative_to(catalog_root)
    except ValueError as error:
        raise ValueError(f"Invalid project_path: path escapes catalog root ({raw_project_path})") from error

    if not candidate.is_dir():
        raise ValueError(f"Invalid project_path: directory does not exist ({raw_project_path})")

    return candidate
