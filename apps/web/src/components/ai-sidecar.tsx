import { Bot, ChevronRight, Sparkles } from "lucide-react";

type AiSidecarProps = {
  prompts: string[];
};

export function AiSidecar({ prompts }: AiSidecarProps) {
  return (
    <aside className="ai-sidecar" aria-label="AI assistant">
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
          <button className="prompt-button" key={prompt} type="button">
            <Sparkles size={15} aria-hidden="true" />
            <span>{prompt}</span>
            <ChevronRight size={15} aria-hidden="true" />
          </button>
        ))}
      </div>
    </aside>
  );
}
