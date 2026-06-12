import json
from pathlib import Path

import pytest

from app.services import strategy_catalog
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
    with pytest.raises(strategy_catalog.UnknownStrategyError, match="Unknown strategy_id"):
        get_strategy_by_id("not_real")


def test_get_strategy_by_id_strips_strategy_id_whitespace():
    strategy = get_strategy_by_id(" moving_average_cross ")

    assert strategy.id == "moving_average_cross"


def test_public_payload_omits_project_path():
    strategy = load_enabled_strategies()[0]

    assert "project_path" not in strategy.public_payload()


def test_catalog_filters_disabled_strategies(tmp_path: Path):
    catalog = tmp_path / "strategies.json"
    (tmp_path / "EnabledOne").mkdir()
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


def test_catalog_rejects_project_path_that_escapes_catalog_root(tmp_path: Path):
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()
    (tmp_path / "outside").mkdir()
    catalog = catalog_root / "strategies.json"
    catalog.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "escaped_one",
                        "name": "EscapedOne",
                        "description": "Escaped fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": "../outside",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="project_path"):
        load_enabled_strategies(catalog_path=catalog)


def test_catalog_rejects_absolute_project_path(tmp_path: Path):
    absolute_project = tmp_path / "AbsoluteProject"
    absolute_project.mkdir()
    catalog = tmp_path / "strategies.json"
    catalog.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "absolute_one",
                        "name": "AbsoluteOne",
                        "description": "Absolute fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": str(absolute_project),
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="project_path"):
        load_enabled_strategies(catalog_path=catalog)


def test_catalog_rejects_missing_project_directory(tmp_path: Path):
    catalog = tmp_path / "strategies.json"
    catalog.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "missing_one",
                        "name": "MissingOne",
                        "description": "Missing fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": "MissingOne",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="project_path"):
        load_enabled_strategies(catalog_path=catalog)
