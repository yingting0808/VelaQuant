"use client";

import { useEffect, useState } from "react";
import {
  getStrategyAttribution,
  getStrategyEvaluation,
  getStrategyLabStatus,
  type StrategyAttributionPayload,
  type StrategyEvaluationPayload,
  type StrategyLabStatusPayload
} from "@/lib/client-api";

export function StrategyLabStatusPanel() {
  const [status, setStatus] = useState<StrategyLabStatusPayload | null>(null);
  const [evaluation, setEvaluation] = useState<StrategyEvaluationPayload | null>(null);
  const [attribution, setAttribution] = useState<StrategyAttributionPayload | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getStrategyLabStatus(), getStrategyEvaluation(), getStrategyAttribution()]).then(
      ([statusPayload, evaluationPayload, attributionPayload]) => {
        if (active) {
          setStatus(statusPayload);
          setEvaluation(evaluationPayload);
          setAttribution(attributionPayload);
        }
      }
    );
    return () => {
      active = false;
    };
  }, []);

  const canRun = status?.can_run_backtests ?? false;
  const readiness = evaluation?.readiness ?? "insufficient_sample";
  const topTicker = attribution?.ticker_diagnostics[0] ?? null;
  const timingComponent =
    attribution?.expectancy_decomposition.components.find((item) => item.name === "timing_component") ?? null;
  const riskContributor = attribution?.drawdown.contributors.find((item) => item.name === "risk_overreach") ?? null;

  return (
    <>
      <section className="data-panel status-panel" aria-label="策略实验室状态">
        <div className="panel-heading">
          <div>
            <h3>回测环境</h3>
            <p>{status?.summary ?? "正在检查 Docker / Compose / LEAN 状态"}</p>
          </div>
          <span className={canRun ? "status-pill success" : "status-pill warning"}>
            {canRun ? "可回测" : "不可回测"}
          </span>
        </div>

        <div className="module-list">
          {(status?.tools ?? []).map((tool) => (
            <article className="module-row" key={tool.name}>
              <div>
                <strong>{tool.name}</strong>
                <p>{tool.message}</p>
              </div>
              <span className={tool.available ? "state-ok" : "state-warn"}>
                {tool.version ?? "未就绪"}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="归因分析">
        <div className="panel-heading">
          <div>
            <h3>归因分析</h3>
            <p>{attribution?.summary ?? "正在读取策略归因。"}</p>
          </div>
          <span className="status-pill warning">{attribution?.regime.regime ?? "insufficient_data"}</span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>可行动信号 {formatPercent(attribution?.signal_quality.actionable_signal_rate ?? 0)}</strong>
              <p>
                事件 {attribution?.signal_quality.market_event_count ?? 0} / 意图{" "}
                {attribution?.signal_quality.trade_intent_count ?? 0}
              </p>
            </div>
            <span className="state-ok">
              置信 {formatPercent(attribution?.signal_quality.average_confidence ?? 0)}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>误报率 {formatPercent(attribution?.signal_quality.false_positive_rate ?? 0)}</strong>
              <p>{attribution?.regime.basis ?? "等待复盘样本。"}</p>
            </div>
            <span className="state-warn">复盘 {attribution?.regime.review_count ?? 0}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>观测盈亏 {formatCurrency(attribution?.expectancy_decomposition.total_observed_pnl ?? 0)}</strong>
              <p>
                已实现 {formatCurrency(attribution?.expectancy_decomposition.realized_pnl ?? 0)} / 浮动{" "}
                {formatCurrency(attribution?.expectancy_decomposition.unrealized_pnl ?? 0)}
              </p>
            </div>
            <span className="state-ok">回撤 {formatPercent(attribution?.drawdown.max_drawdown ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>{attribution?.drawdown.source ?? "insufficient_data"}</strong>
              <p>{attribution?.drawdown.basis ?? "等待更多复盘样本。"}</p>
            </div>
            <span className="state-warn">警告 {attribution?.data_quality_warnings.length ?? 0}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                {topTicker?.ticker ?? "暂无 Ticker"} 贡献 {formatSignedCurrency(topTicker?.observed_pnl ?? 0)}
              </strong>
              <p>
                事件 {topTicker?.market_event_count ?? 0} / 意图 {topTicker?.trade_intent_count ?? 0} · 误报{" "}
                {formatPercent(topTicker?.false_positive_rate ?? 0)}
              </p>
            </div>
            <span className="state-ok">置信 {formatPercent(topTicker?.average_confidence ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                衰减 {attribution?.signal_decay.stale_open_position_count ?? 0} /{" "}
                {attribution?.signal_decay.open_position_count ?? 0}
              </strong>
              <p>{attribution?.signal_decay.basis ?? "等待持仓和订单样本。"}</p>
            </div>
            <span className="state-warn">
              持仓 {formatNumber(attribution?.signal_decay.average_holding_days ?? 0)} 天
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                {timingComponent?.name ?? "timing_component"} {formatSignedCurrency(timingComponent?.value ?? 0)}
              </strong>
              <p>{timingComponent?.basis ?? "等待时点组件样本。"}</p>
            </div>
            <span className="state-warn">
              {riskContributor?.name ?? "risk_overreach"} {formatNumber(riskContributor?.value ?? 0)}
            </span>
          </article>
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Alpha 验证">
        <div className="panel-heading">
          <div>
            <h3>Alpha 验证</h3>
            <p>{evaluation?.notes ?? "正在读取策略评价。"}</p>
          </div>
          <span className={readiness === "paper_ready" ? "status-pill success" : "status-pill warning"}>
            {readiness}
          </span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>{evaluation?.strategy_name ?? "Deterministic Watchlist Strategy"}</strong>
              <p>{evaluation?.promotion_gate ?? "blocked"}</p>
            </div>
            <span className="state-ok">样本 {evaluation?.sample_size ?? 0}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>信号精度 {formatPercent(evaluation?.signal_precision ?? 0)}</strong>
              <p>成交 {evaluation?.filled_order_count ?? 0} / 拒单 {evaluation?.rejected_order_count ?? 0}</p>
            </div>
            <span className="state-ok">期望 {formatNumber(evaluation?.expectancy ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>最大回撤 {formatPercent(evaluation?.max_drawdown ?? 0)}</strong>
              <p>事件链 {evaluation?.event_chain_count ?? 0} · 已平仓 {evaluation?.closed_trade_count ?? 0}</p>
            </div>
            <span className="state-ok">稳定 {formatPercent(evaluation?.stability_score ?? 0)}</span>
          </article>
        </div>
      </section>
    </>
  );
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number): string {
  return value.toFixed(2);
}

function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatSignedCurrency(value: number): string {
  if (value < 0) {
    return `-$${Math.abs(value).toFixed(2)}`;
  }
  return `$${value.toFixed(2)}`;
}
