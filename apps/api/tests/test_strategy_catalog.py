import json
from pathlib import Path

import pytest

from app.services.strategy_catalog import (
    StrategyDefinition,
    get_strategy_by_id,
    load_enabled_strategies,
)


def test_load_enabled_strategies_returns_checked_in_moving_average_strategy():
    strategies = load_enabled_strategies()

    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy.id == "moving_average_cross"
    assert strategy.name == "MovingAverageCross"
    assert strategy.language == "Python"
    assert strategy.default_symbol == "AAPL"
    assert strategy.enabled is True
    assert strategy.project_path.name == "MovingAverageCross"


def test_get_strategy_by_id_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown strategy_id"):
        get_strategy_by_id("not_real")


def test_catalog_filters_disabled_strategies(tmp_path: Path):
    catalog = tmp_path / "strategies.json"
    catalog.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "enabled_one",
                        "name": "EnabledOne",
                        "description": "Enabled fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": "EnabledOne",
                        "enabled": True,
                    },
                    {
                        "id": "disabled_one",
                        "name": "DisabledOne",
                        "description": "Disabled fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "MSFT",
                        "resolution": "Daily",
                        "project_path": "DisabledOne",
                        "enabled": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    strategies = load_enabled_strategies(catalog_path=catalog)

    assert [strategy.id for strategy in strategies] == ["enabled_one"]
    assert isinstance(strategies[0], StrategyDefinition)
