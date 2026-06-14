from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _python_files() -> list[Path]:
    return sorted(path for path in APP_ROOT.rglob("*.py") if path.is_file())


def _relative(path: Path) -> str:
    return path.relative_to(APP_ROOT.parent).as_posix()


def test_trading_engine_cannot_be_constructed_with_bare_strategy_engine_in_production_code():
    offenders = [
        _relative(path)
        for path in _python_files()
        if "TradingEngine(strategy_engine=" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_deterministic_strategy_instantiation_is_registry_only_in_production_code():
    allowed = {"app/services/strategy_registry.py"}
    offenders = [
        _relative(path)
        for path in _python_files()
        if "DeterministicWatchlistStrategy(" in path.read_text(encoding="utf-8") and _relative(path) not in allowed
    ]

    assert offenders == []


def test_paper_execution_submit_requires_persisted_core_event_context():
    paper_trading = APP_ROOT / "services" / "paper_trading.py"
    source = paper_trading.read_text(encoding="utf-8")
    helper_start = source.index("def _submit_core_order(")
    helper_source = source[helper_start : source.index("\ndef _new_paper_order(", helper_start)]

    assert "if core_context is None:" in helper_source
    assert "Execution requires a persisted core event context." in helper_source
    assert helper_source.index("Execution requires a persisted core event context.") < helper_source.index("submit_intent(")
