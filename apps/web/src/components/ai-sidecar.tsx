"use client";

import { Bot, ChevronRight, Sparkles } from "lucide-react";
import { useState } from "react";
import { runResearchPrompt, type ResearchResultPayload } from "@/lib/client-api";

type AiSidecarProps = {
  prompts: string[];
};

function formatStatus(status: string): string {
  const labels: Record<string, string> = {
    complete: "已完成",
    insufficient_evidence: "证据不足",
    offline_fallback: "离线兜底"
  };

  return labels[status] ?? "已生成";
}

export function AiSidecar({ prompts }: AiSidecarProps) {
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [result, setResult] = useState<ResearchResultPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handlePromptClick(prompt: string) {
    setActivePrompt(prompt);
    setIsLoading(true);
    setResult(null);

    const nextResult = await runResearchPrompt(prompt);
    setResult(nextResult);
    setIsLoading(false);
  }

  return (
    <aside className="ai-sidecar" aria-label="AI 助手">
      <div className="sidecar-header">
        <div className="sidecar-icon">
          <Bot size={18} aria-hidden="true" />
        </div>
        <div>
          <h2>AI 助手</h2>
          <p>当前页面上下文</p>
        </div>
      </div>

      <div className="prompt-list">
        {prompts.map((prompt) => (
          <button
            aria-pressed={activePrompt === prompt}
            className="prompt-button"
            disabled={isLoading}
            key={prompt}
            onClick={() => void handlePromptClick(prompt)}
            type="button"
          >
            <Sparkles size={15} aria-hidden="true" />
            <span>{prompt}</span>
            <ChevronRight size={15} aria-hidden="true" />
          </button>
        ))}
      </div>

      <section className="research-result" aria-live="polite" aria-label="AI 研究结果">
        {isLoading ? (
          <p>正在分析 AAPL...</p>
        ) : result ? (
          <>
            <div className="result-heading">
              <span className="ticker-chip dark">{result.ticker}</span>
              <span>{formatStatus(result.status)}</span>
            </div>
            <p>{result.summary}</p>
            <dl>
              <dt>多头观点</dt>
              <dd>{result.bull_case}</dd>
              <dt>空头风险</dt>
              <dd>{result.bear_case}</dd>
              <dt>风控提示</dt>
              <dd>{result.trade_plan_draft.risk_notes.join(" ")}</dd>
            </dl>
          </>
        ) : (
          <p>选择一个研究动作后，结果会在这里更新。</p>
        )}
      </section>
    </aside>
  );
}
