import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.lean_backtest import BacktestResult, run_lean_backtest
from app.services.strategy_control import DEFAULT_PAPER_STRATEGY_ID


CandidateRecommendation = Literal["candidate", "watch", "reject"]
BacktestRunner = Callable[..., BacktestResult]


class StrategyCandidateBacktestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    ticker: str
    recommendation: CandidateRecommendation
    score: float
    reason: str
    run_id: str
    status: str
    engine: str
    data_source: str | None
    uses_real_market_data: bool
    total_net_profit: str | None
    sharpe_ratio: str | None
    drawdown: str | None
    total_trades: str | None


class StrategyCandidateBacktestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    candidate_count: int
    real_market_candidate_count: int
    best_ticker: str | None
    items: list[StrategyCandidateBacktestItem] = Field(default_factory=list)
    summary: str


def run_strategy_candidate_backtests(
    *,
    strategy_id: str = DEFAULT_PAPER_STRATEGY_ID,
    tickers: list[str],
    parameter_overrides: dict[str, str] | None = None,
    market_data_provider: object | None = None,
    backtest_runner: BacktestRunner = run_lean_backtest,
) -> StrategyCandidateBacktestPayload:
    normalized_tickers = _normalize_tickers(tickers)
    if len(normalized_tickers) < 2:
        raise ValueError("Candidate backtest requires at least two unique tickers.")

    items: list[StrategyCandidateBacktestItem] = []
    for ticker in normalized_tickers:
        parameters = dict(parameter_overrides or {})
        parameters["symbol"] = ticker
        result = backtest_runner(
            strategy_id,
            parameter_overrides=parameters,
            market_data_provider=market_data_provider,
        )
        items.append(_candidate_item(ticker, result))

    ranked = sorted(
        items,
        key=lambda item: (
            item.uses_real_market_data,
            item.recommendation == "candidate",
            item.score,
        ),
        reverse=True,
    )
    ranked = [item.model_copy(update={"rank": index + 1}) for index, item in enumerate(ranked)]
    best = next((item.ticker for item in ranked if item.recommendation == "candidate"), None)
    real_count = sum(1 for item in ranked if item.uses_real_market_data)
    return StrategyCandidateBacktestPayload(
        strategy_id=strategy_id,
        candidate_count=len(ranked),
        real_market_candidate_count=real_count,
        best_ticker=best,
        items=ranked,
        summary=_summary(ranked, best),
    )


def _normalize_tickers(tickers: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        candidate = ticker.strip().upper()
        if not candidate:
            continue
        if not re.fullmatch(r"[A-Z0-9.-]{1,12}", candidate):
            raise ValueError(f"Invalid ticker: {ticker}")
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _candidate_item(ticker: str, result: BacktestResult) -> StrategyCandidateBacktestItem:
    profit = _parse_number(result.statistics.total_net_profit, percent=True)
    sharpe = _parse_number(result.statistics.sharpe_ratio)
    drawdown = _parse_number(result.statistics.drawdown, percent=True)
    trades = _parse_number(result.statistics.total_trades)
    score = _score(result, profit=profit, sharpe=sharpe, drawdown=drawdown, trades=trades)
    recommendation = _recommendation(
        result,
        profit=profit,
        sharpe=sharpe,
        drawdown=drawdown,
        trades=trades,
    )
    return StrategyCandidateBacktestItem(
        rank=0,
        ticker=ticker,
        recommendation=recommendation,
        score=round(score, 4),
        reason=_reason(result, recommendation, profit=profit, sharpe=sharpe, drawdown=drawdown, trades=trades),
        run_id=result.run_id,
        status=result.status,
        engine=result.engine,
        data_source=result.data_source,
        uses_real_market_data=result.uses_real_market_data,
        total_net_profit=result.statistics.total_net_profit,
        sharpe_ratio=result.statistics.sharpe_ratio,
        drawdown=result.statistics.drawdown,
        total_trades=result.statistics.total_trades,
    )


def _score(
    result: BacktestResult,
    *,
    profit: float | None,
    sharpe: float | None,
    drawdown: float | None,
    trades: float | None,
) -> float:
    if result.status != "success":
        return -10.0
    real_bonus = 1.0 if result.uses_real_market_data else -1.0
    profit_component = profit or 0.0
    sharpe_component = (sharpe or 0.0) * 0.35
    drawdown_penalty = (drawdown or 0.0) * 0.75
    trade_component = min(trades or 0.0, 20.0) * 0.01
    return real_bonus + profit_component + sharpe_component - drawdown_penalty + trade_component


def _recommendation(
    result: BacktestResult,
    *,
    profit: float | None,
    sharpe: float | None,
    drawdown: float | None,
    trades: float | None,
) -> CandidateRecommendation:
    if result.status != "success":
        return "reject"
    if not result.uses_real_market_data:
        return "watch"
    if (profit or 0.0) <= 0 or (sharpe or 0.0) <= 0 or (trades or 0.0) <= 0:
        return "reject"
    if (drawdown or 0.0) > 0.25:
        return "watch"
    return "candidate"


def _reason(
    result: BacktestResult,
    recommendation: CandidateRecommendation,
    *,
    profit: float | None,
    sharpe: float | None,
    drawdown: float | None,
    trades: float | None,
) -> str:
    reasons: list[str] = []
    if result.uses_real_market_data:
        reasons.append("真实历史数据")
    else:
        reasons.append("非真实历史数据，不作为候选")
    if result.status != "success":
        reasons.append(f"回测状态 {result.status}")
    if (profit or 0.0) > 0:
        reasons.append("收益为正")
    else:
        reasons.append("收益未通过")
    if (sharpe or 0.0) > 0:
        reasons.append(f"Sharpe {sharpe:.2f}")
    else:
        reasons.append("Sharpe 未通过")
    if drawdown is not None:
        reasons.append(f"回撤 {drawdown * 100:.2f}%")
    if trades is not None:
        reasons.append(f"交易 {int(trades)} 笔")
    reasons.append(f"结论 {recommendation}")
    return "；".join(reasons)


def _parse_number(value: str | None, *, percent: bool = False) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]
    try:
        number = float(text)
    except ValueError:
        return None
    if percent or is_percent:
        return number / 100.0
    return number


def _summary(items: list[StrategyCandidateBacktestItem], best_ticker: str | None) -> str:
    if best_ticker is None:
        return f"Ranked {len(items)} candidates; no ticker passed the real-market candidate gate."
    candidate_count = sum(1 for item in items if item.recommendation == "candidate")
    return f"Ranked {len(items)} candidates; {candidate_count} passed, best ticker {best_ticker}."
