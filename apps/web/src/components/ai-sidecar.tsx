"use client";

import { Bot, ChevronRight, Save, Sparkles } from "lucide-react";
import { useState } from "react";
import { runResearchPrompt, saveResearchResultAsNote, type ResearchResultPayload } from "@/lib/client-api";

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
  const [isSaving, setIsSaving] = useState(false);
  const [savedTitle, setSavedTitle] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handlePromptClick(prompt: string) {
    setActivePrompt(prompt);
    setIsLoading(true);
    setResult(null);
    setSavedTitle(null);
    setSaveError(null);

    const nextResult = await runResearchPrompt(prompt);
    setResult(nextResult);
    setIsLoading(false);
  }

  async function handleSaveResult() {
    if (!result) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    const saved = await saveResearchResultAsNote(activePrompt ?? "AI 研究", result);
    if (saved) {
      setSavedTitle(saved.note.title);
    } else {
      setSaveError("保存失败，请检查后端 API。");
    }
    setIsSaving(false);
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
            <button className="primary-action sidecar-save" type="button" disabled={isSaving} onClick={handleSaveResult}>
              <Save size={15} aria-hidden="true" />
              {isSaving ? "保存中" : "保存为笔记"}
            </button>
            {savedTitle ? (
              <div className="save-feedback">
                <strong>已保存到研究笔记</strong>
                <p>{savedTitle}</p>
              </div>
            ) : null}
            {saveError ? <p className="save-feedback error">{saveError}</p> : null}
          </>
        ) : (
          <p>选择一个研究动作后，结果会在这里更新。</p>
        )}
      </section>
    </aside>
  );
}
