export type ResearchResultPayload = {
  ticker: string;
  status: string;
  summary: string;
  bull_case: string;
  bear_case: string;
  watch_items: string[];
  evidence_count: number;
  trade_plan_draft: {
    entry_condition: string;
    invalidation_condition: string;
    risk_notes: string[];
  };
};

export type ProviderStatusPayload = {
  name: string;
  mode: string;
  available: boolean;
  message: string;
  checked_at: string;
  version: string | null;
};

export type DataSourcesStatusPayload = {
  provider_mode: string;
  data_sources: ProviderStatusPayload[];
};

export type StrategyToolStatusPayload = {
  name: string;
  available: boolean;
  version: string | null;
  message: string;
};

export type StrategyLabStatusPayload = {
  can_run_backtests: boolean;
  summary: string;
  tools: StrategyToolStatusPayload[];
};

function getPublicApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function fallbackResearchResult(ticker: string, question: string): ResearchResultPayload {
  return {
    ticker,
    status: "offline_fallback",
    summary: `${ticker}: 本地 API 暂不可用，已生成离线占位分析。问题：${question}`,
    bull_case: "组合仍有可跟踪的基本面和事件线索，但需要接入实时数据后复核。",
    bear_case: "离线模式不能确认最新价格、新闻和公告，不能作为交易依据。",
    watch_items: ["启动后端 API", "接入真实数据源", "由人工复核结论"],
    evidence_count: 0,
    trade_plan_draft: {
      entry_condition: "仅在 API 和数据源恢复后，由人工确认研究结论。",
      invalidation_condition: "任何新公告、价格波动或数据缺口都应使该草稿失效。",
      risk_notes: ["这不是可直接执行的订单建议。", "必须经过人工审批。"]
    }
  };
}

const fallbackDataSourcesStatus: DataSourcesStatusPayload = {
  provider_mode: "hybrid",
  data_sources: [
    {
      name: "Mock",
      mode: "mock",
      available: true,
      message: "本地 Mock 数据可用。",
      checked_at: "local",
      version: "local"
    },
    {
      name: "SEC EDGAR",
      mode: "sec_edgar",
      available: false,
      message: "后端 API 暂不可用，无法确认 SEC EDGAR 状态。",
      checked_at: "local",
      version: null
    },
    {
      name: "OpenBB",
      mode: "openbb_optional",
      available: false,
      message: "OpenBB 为可选数据层，当前未确认。",
      checked_at: "local",
      version: null
    }
  ]
};

const fallbackStrategyLabStatus: StrategyLabStatusPayload = {
  can_run_backtests: false,
  summary: "后端 API 暂不可用，无法确认 Docker / LEAN 状态。",
  tools: [
    {
      name: "Docker CLI",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "Docker Compose",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "Docker engine",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "LEAN CLI",
      available: false,
      version: null,
      message: "状态未确认。"
    }
  ]
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isResearchResultPayload(value: unknown): value is ResearchResultPayload {
  if (!isRecord(value) || !isRecord(value.trade_plan_draft)) {
    return false;
  }

  return (
    typeof value.ticker === "string" &&
    typeof value.status === "string" &&
    typeof value.summary === "string" &&
    typeof value.bull_case === "string" &&
    typeof value.bear_case === "string" &&
    Array.isArray(value.watch_items) &&
    value.watch_items.every((item) => typeof item === "string") &&
    typeof value.evidence_count === "number" &&
    typeof value.trade_plan_draft.entry_condition === "string" &&
    typeof value.trade_plan_draft.invalidation_condition === "string" &&
    Array.isArray(value.trade_plan_draft.risk_notes) &&
    value.trade_plan_draft.risk_notes.every((item) => typeof item === "string")
  );
}

function isProviderStatus(value: unknown): value is ProviderStatusPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.mode === "string" &&
    typeof value.available === "boolean" &&
    typeof value.message === "string" &&
    typeof value.checked_at === "string" &&
    (typeof value.version === "string" || value.version === null)
  );
}

function isDataSourcesStatusPayload(value: unknown): value is DataSourcesStatusPayload {
  return (
    isRecord(value) &&
    typeof value.provider_mode === "string" &&
    Array.isArray(value.data_sources) &&
    value.data_sources.every(isProviderStatus)
  );
}

function isStrategyToolStatus(value: unknown): value is StrategyToolStatusPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.available === "boolean" &&
    (typeof value.version === "string" || value.version === null) &&
    typeof value.message === "string"
  );
}

function isStrategyLabStatusPayload(value: unknown): value is StrategyLabStatusPayload {
  return (
    isRecord(value) &&
    typeof value.can_run_backtests === "boolean" &&
    typeof value.summary === "string" &&
    Array.isArray(value.tools) &&
    value.tools.every(isStrategyToolStatus)
  );
}

export async function runResearchPrompt(question: string, ticker = "AAPL"): Promise<ResearchResultPayload> {
  const normalizedTicker = ticker.trim().toUpperCase() || "AAPL";
  const normalizedQuestion = question.trim() || "解释当前页面";
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), 1800);

  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/research`, {
      body: JSON.stringify({
        question: normalizedQuestion,
        ticker: normalizedTicker
      }),
      headers: {
        "Content-Type": "application/json"
      },
      method: "POST",
      signal: controller.signal
    });

    if (!response.ok) {
      return fallbackResearchResult(normalizedTicker, normalizedQuestion);
    }

    const payload: unknown = await response.json();
    return isResearchResultPayload(payload)
      ? payload
      : fallbackResearchResult(normalizedTicker, normalizedQuestion);
  } catch {
    return fallbackResearchResult(normalizedTicker, normalizedQuestion);
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export async function getDataSourcesStatus(): Promise<DataSourcesStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/data-sources/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackDataSourcesStatus;
    }
    const payload: unknown = await response.json();
    return isDataSourcesStatusPayload(payload) ? payload : fallbackDataSourcesStatus;
  } catch {
    return fallbackDataSourcesStatus;
  }
}

export async function getStrategyLabStatus(): Promise<StrategyLabStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyLabStatus;
    }
    const payload: unknown = await response.json();
    return isStrategyLabStatusPayload(payload) ? payload : fallbackStrategyLabStatus;
  } catch {
    return fallbackStrategyLabStatus;
  }
}
