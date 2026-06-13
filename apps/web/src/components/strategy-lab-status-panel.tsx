"use client";

import { useEffect, useState } from "react";
import {
  getStrategyEvaluation,
  getStrategyLabStatus,
  type StrategyEvaluationPayload,
  type StrategyLabStatusPayload
} from "@/lib/client-api";

export function StrategyLabStatusPanel() {
  const [status, setStatus] = useState<StrategyLabStatusPayload | null>(null);
  const [evaluation, setEvaluation] = useState<StrategyEvaluationPayload | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getStrategyLabStatus(), getStrategyEvaluation()]).then(([statusPayload, evaluationPayload]) => {
      if (active) {
        setStatus(statusPayload);
        setEvaluation(evaluationPayload);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const canRun = status?.can_run_backtests ?? false;
  const readiness = evaluation?.readiness ?? "insufficient_sample";

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
