"use client";

import { useEffect, useState } from "react";
import { getAIStatus, type AIStatusPayload } from "@/lib/client-api";

export function AIStatusPanel() {
  const [status, setStatus] = useState<AIStatusPayload | null>(null);

  useEffect(() => {
    let active = true;
    getAIStatus().then((payload) => {
      if (active) {
        setStatus(payload);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const llm = status?.research_llm;
  const isolated =
    status !== null &&
    !status.execution_path.ai_generates_trade_intent &&
    !status.execution_path.ai_influences_risk &&
    !status.execution_path.ai_calls_execution;

  return (
    <section className="data-panel status-panel" aria-label="AI / LLM 状态">
      <div className="panel-heading">
        <div>
          <h3>AI / LLM 状态</h3>
          <p>区分 LangGraph workflow、OpenAI-compatible LLM 和交易执行边界</p>
        </div>
        <span className={llm?.available ? "status-pill success" : "status-pill neutral"}>
          {llm?.available ? "LLM 可用" : "LLM 未配置"}
        </span>
      </div>

      <div className="module-list">
        <article className="module-row">
          <div>
            <strong>LangGraph</strong>
            <p>{status?.langgraph.message ?? "加载中"}</p>
          </div>
          <span className={status?.langgraph.available ? "state-ok" : "state-warn"}>
            {status?.langgraph.mode ?? "加载中"}
          </span>
        </article>

        <article className="module-row">
          <div>
            <strong>OpenAI-compatible LLM</strong>
            <p>{llm?.message ?? "加载中"}</p>
          </div>
          <span className={llm?.available ? "state-ok" : "state-warn"}>
            {llm?.configured ? llm.model : "未配置"}
          </span>
        </article>

        <article className="module-row">
          <div>
            <strong>AI 不进入交易执行链</strong>
            <p>TradeIntent、RiskEngine、ExecutionEngine 仍由 Trading Core 主路径控制。</p>
          </div>
          <span className={isolated ? "state-ok" : "state-warn"}>{isolated ? "隔离" : "检查"}</span>
        </article>
      </div>
    </section>
  );
}
