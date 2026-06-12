import json
from pathlib import Path

from pydantic import BaseModel, Field


API_ROOT = Path(__file__).resolve().parents[2]
LEAN_WORKSPACE_ROOT = API_ROOT / "lean-workspace"
DEFAULT_CATALOG_PATH = LEAN_WORKSPACE_ROOT / "strategies.json"


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
        }


def load_enabled_strategies(catalog_path: Path = DEFAULT_CATALOG_PATH) -> list[StrategyDefinition]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    strategies: list[StrategyDefinition] = []
    for item in payload.get("strategies", []):
        strategy = StrategyDefinition(**item)
        if strategy.enabled:
            if not strategy.project_path.is_absolute():
                strategy.project_path = catalog_path.parent / strategy.project_path
            strategies.append(strategy)
    return strategies


def get_strategy_by_id(strategy_id: str, catalog_path: Path = DEFAULT_CATALOG_PATH) -> StrategyDefinition:
    normalized = strategy_id.strip()
    for strategy in load_enabled_strategies(catalog_path=catalog_path):
        if strategy.id == normalized:
            return strategy
    raise ValueError(f"Unknown strategy_id: {normalized}")
