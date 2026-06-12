"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  getBacktestHistory,
  getLatestBacktest,
  getStrategyCatalog,
  runStrategyBacktest,
  type BacktestHistoryItemPayload,
  type BacktestParametersPayload,
  type BacktestResultPayload,
  type StrategyDefinitionPayload,
  type StrategyParameterDefinitionPayload
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

function defaultParameters(strategy: StrategyDefinitionPayload | undefined): BacktestParametersPayload {
  if (!strategy) {
    return {};
  }
  return Object.fromEntries(strategy.parameters.map((parameter) => [parameter.name, parameter.default]));
}

function inputType(parameter: StrategyParameterDefinitionPayload) {
  if (parameter.kind === "date") {
    return "date";
  }
  if (parameter.kind === "integer" || parameter.kind === "number") {
    return "number";
  }
  return "text";
}

function unavailableHints(result: BacktestResultPayload | null): string[] {
  if (result?.status !== "unavailable") {
    return [];
  }
  const joinedLogs = result.logs.join(" ").toLowerCase();
  const hints: string[] = [];
  if (joinedLogs.includes("lean")) {
    hints.push("安装 QuantConnect LEAN CLI，并确认 lean --version 可执行。");
  }
  if (joinedLogs.includes("engine")) {
    hints.push("启动 Docker Desktop，等待 Docker engine 就绪后重试。");
  }
  if (joinedLogs.includes("docker") || hints.length === 0) {
    hints.push("安装或启动 Docker Desktop，并确认 docker --version 可执行。");
  }
  return hints;
}

function historySubtitle(item: BacktestHistoryItemPayload) {
  const symbol = item.parameters.symbol ?? "未知标的";
  const start = item.parameters.start_date ?? "未知开始";
  const end = item.parameters.end_date ?? "未知结束";
  return `${symbol} · ${start} 到 ${end}`;
}

export function StrategyBacktestPanel() {
  const [strategies, setStrategies] = useState<StrategyDefinitionPayload[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState("moving_average_cross");
  const [parameterValues, setParameterValues] = useState<BacktestParametersPayload>({});
  const [result, setResult] = useState<BacktestResultPayload | null>(null);
  const [history, setHistory] = useState<BacktestHistoryItemPayload[]>([]);
  const [isCatalogLoaded, setIsCatalogLoaded] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    getStrategyCatalog()
      .then((payload) => {
        if (!mountedRef.current) {
          return;
        }
        setStrategies(payload.strategies);
        if (payload.strategies[0]) {
          setSelectedStrategyId(payload.strategies[0].id);
          setParameterValues(defaultParameters(payload.strategies[0]));
        }
      })
      .catch(() => {
        if (mountedRef.current) {
          setStrategies([]);
        }
      })
      .finally(() => {
        if (mountedRef.current) {
          setIsCatalogLoaded(true);
        }
      });
    getLatestBacktest().then((payload) => {
      if (!mountedRef.current) {
        return;
      }
      setResult(payload.latest);
    });
    getBacktestHistory().then((payload) => {
      if (!mountedRef.current) {
        return;
      }
      setHistory(payload.history);
    });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.id === selectedStrategyId) ?? strategies[0],
    [selectedStrategyId, strategies]
  );

  function handleSelectStrategy(strategy: StrategyDefinitionPayload) {
    setSelectedStrategyId(strategy.id);
    setParameterValues(defaultParameters(strategy));
  }

  function updateParameter(name: string, value: string) {
    setParameterValues((current) => ({ ...current, [name]: value }));
  }

  async function refreshHistory() {
    const payload = await getBacktestHistory();
    if (mountedRef.current) {
      setHistory(payload.history);
    }
  }

  async function handleRun() {
    if (!selectedStrategy) {
      return;
    }
    setIsRunning(true);
    try {
      const payload = await runStrategyBacktest(selectedStrategy.id, parameterValues);
      if (mountedRef.current) {
        setResult(payload);
      }
      await refreshHistory();
    } catch {
      // runStrategyBacktest normally returns a failed payload; this keeps the UI recoverable if it throws.
    } finally {
      if (mountedRef.current) {
        setIsRunning(false);
      }
    }
  }

  const hasEmptyCatalog = isCatalogLoaded && strategies.length === 0;
  const resultMessage = result?.message ?? (hasEmptyCatalog ? "策略目录为空，无法运行回测。" : "选择策略后点击运行回测。");
  const hints = unavailableHints(result);

  return (
    <section className="data-panel backtest-panel" aria-label="LEAN 回测">
      <div className="panel-heading">
        <div>
          <h3>LEAN 回测</h3>
          <p>运行白名单内置策略，结果仅用于研究验证</p>
        </div>
        <button className="primary-action" type="button" disabled={isRunning || !selectedStrategy} onClick={handleRun}>
          {isRunning ? "运行回测中" : "运行回测"}
        </button>
      </div>

      <div className="strategy-grid">
        <div className="strategy-list" aria-label="策略列表">
          {hasEmptyCatalog ? (
            <div className="strategy-empty">
              <strong>暂无可用策略</strong>
              <p>请检查策略目录配置。</p>
            </div>
          ) : null}
          {strategies.map((strategy) => (
            <button
              aria-pressed={strategy.id === selectedStrategyId}
              className={strategy.id === selectedStrategyId ? "strategy-option active" : "strategy-option"}
              key={strategy.id}
              type="button"
              onClick={() => handleSelectStrategy(strategy)}
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
          {selectedStrategy ? (
            <div className="parameter-form" aria-label="回测参数">
              <div className="parameter-grid">
                {selectedStrategy.parameters.map((parameter) => (
                  <label className="parameter-field" key={parameter.name}>
                    <span>{parameter.label}</span>
                    <input
                      aria-label={parameter.label}
                      max={parameter.max ?? undefined}
                      min={parameter.min ?? undefined}
                      required={parameter.required}
                      step={parameter.kind === "integer" ? 1 : undefined}
                      type={inputType(parameter)}
                      value={parameterValues[parameter.name] ?? parameter.default}
                      onChange={(event) =>
                        updateParameter(
                          parameter.name,
                          parameter.kind === "ticker" ? event.target.value.toUpperCase() : event.target.value
                        )
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          <div className="result-toolbar">
            <div>
              <span className="market-label">最近一次回测</span>
              <strong>{result ? statusLabel[result.status] : "尚未运行回测"}</strong>
            </div>
            {result ? (
              <span
                className={result.status === "success" ? "status-pill success" : "status-pill warning"}
                title={result.status}
              >
                {statusLabel[result.status]}
              </span>
            ) : (
              <span className="status-pill neutral">等待</span>
            )}
          </div>

          <p className="result-message">{resultMessage}</p>

          {hints.length ? (
            <ul className="action-hints" aria-label="环境行动提示">
              {hints.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          ) : null}

          <div className="backtest-metrics">
            {metricRows(result).map(([label, value]) => (
              <article className="market-card" key={label}>
                <span className="market-label">{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>

          <div className="log-box" aria-label="回测日志">
            {(result?.logs.length ? result.logs : ["暂无回测日志"]).map((line, index) => (
              <p key={`${line}-${index}`}>{line}</p>
            ))}
          </div>

          <section className="history-list" aria-label="回测历史">
            <h4>历史记录</h4>
            {history.length ? (
              history.map((item) => (
                <article className="history-item" key={item.run_id}>
                  <div>
                    <strong>{statusLabel[item.status]}</strong>
                    <p>{historySubtitle(item)}</p>
                  </div>
                  <span>{`${item.parameters.fast_period ?? "-"} / ${item.parameters.slow_period ?? "-"}`}</span>
                  <span>{item.statistics.total_net_profit ?? "不可用"}</span>
                </article>
              ))
            ) : (
              <p className="result-message">暂无历史记录</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
