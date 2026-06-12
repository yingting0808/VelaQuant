"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getLatestBacktest,
  getStrategyCatalog,
  runStrategyBacktest,
  type BacktestResultPayload,
  type StrategyDefinitionPayload
} from "@/lib/client-api";

const statusLabel: Record<BacktestResultPayload["status"], string> = {
  failed: "LEAN 返回失败",
  malformed_result: "结果不可解析",
  success: "回测完成",
  timeout: "回测超时",
  unavailable: "环境未就绪"
};

function metricRows(result: BacktestResultPayload | null) {
  return [
    ["Total Net Profit", result?.statistics.total_net_profit ?? "不可用"],
    ["Annual Return", result?.statistics.compounding_annual_return ?? "不可用"],
    ["Sharpe", result?.statistics.sharpe_ratio ?? "不可用"],
    ["Drawdown", result?.statistics.drawdown ?? "不可用"],
    ["Win Rate", result?.statistics.win_rate ?? "不可用"],
    ["Trades", result?.statistics.total_trades ?? "不可用"]
  ];
}

export function StrategyBacktestPanel() {
  const [strategies, setStrategies] = useState<StrategyDefinitionPayload[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState("moving_average_cross");
  const [result, setResult] = useState<BacktestResultPayload | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    let active = true;
    getStrategyCatalog().then((payload) => {
      if (!active) {
        return;
      }
      setStrategies(payload.strategies);
      if (payload.strategies[0]) {
        setSelectedStrategyId(payload.strategies[0].id);
      }
    });
    getLatestBacktest().then((payload) => {
      if (active) {
        setResult(payload.latest);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.id === selectedStrategyId) ?? strategies[0],
    [selectedStrategyId, strategies]
  );

  async function handleRun() {
    if (!selectedStrategy) {
      return;
    }
    setIsRunning(true);
    const payload = await runStrategyBacktest(selectedStrategy.id);
    setResult(payload);
    setIsRunning(false);
  }

  return (
    <section className="data-panel backtest-panel" aria-label="LEAN 回测">
      <div className="panel-heading">
        <div>
          <h3>LEAN 回测</h3>
          <p>运行白名单内置策略，结果仅用于研究验证</p>
        </div>
        <button className="primary-action" type="button" disabled={isRunning || !selectedStrategy} onClick={handleRun}>
          {isRunning ? "运行中" : "运行回测"}
        </button>
      </div>

      <div className="strategy-grid">
        <div className="strategy-list" aria-label="策略列表">
          {strategies.map((strategy) => (
            <button
              className={strategy.id === selectedStrategyId ? "strategy-option active" : "strategy-option"}
              key={strategy.id}
              type="button"
              onClick={() => setSelectedStrategyId(strategy.id)}
            >
              <strong>{strategy.name}</strong>
              <span>
                {strategy.default_symbol} · {strategy.resolution} · {strategy.language}
              </span>
              <p>{strategy.description}</p>
            </button>
          ))}
        </div>

        <div className="backtest-result">
          <div className="result-toolbar">
            <div>
              <span className="market-label">最近一次回测</span>
              <strong>{result ? statusLabel[result.status] : "尚未运行回测"}</strong>
            </div>
            {result ? (
              <span className={result.status === "success" ? "status-pill success" : "status-pill warning"}>
                {result.status}
              </span>
            ) : (
              <span className="status-pill neutral">等待</span>
            )}
          </div>

          <p className="result-message">{result?.message ?? "选择策略后点击运行回测。"}</p>

          <div className="backtest-metrics">
            {metricRows(result).map(([label, value]) => (
              <article className="market-card" key={label}>
                <span className="market-label">{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>

          <div className="log-box" aria-label="回测日志">
            {(result?.logs.length ? result.logs : ["暂无回测日志"]).map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
