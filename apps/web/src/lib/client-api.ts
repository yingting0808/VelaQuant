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

export type MarketQuotePayload = {
  ticker: string;
  price: number | null;
  currency: string;
  source: string;
  updated_at: string;
  change: number | null;
  change_percent: number | null;
  volume: number | null;
  is_fallback: boolean;
  message: string;
};

export type PriceHistoryBarPayload = {
  ticker: string;
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  source: string;
};

export type FundamentalSnapshotPayload = {
  ticker: string;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  price_to_sales: number | null;
  price_to_book: number | null;
  gross_margin: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  debt_to_equity: number | null;
  source: string;
  period_ending: string | null;
  updated_at: string;
  is_fallback: boolean;
  message: string;
};

export type MarketSnapshotPayload = {
  ticker: string;
  quote: MarketQuotePayload;
  fundamentals: FundamentalSnapshotPayload;
  history: PriceHistoryBarPayload[];
  provider_mode: string;
  data_sources: ProviderStatusPayload[];
};

function fallbackMarketSnapshot(ticker: string): MarketSnapshotPayload {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  return {
    ticker: normalizedTicker,
    quote: {
      ticker: normalizedTicker,
      price: null,
      currency: "USD",
      source: "offline",
      updated_at: "local",
      change: null,
      change_percent: null,
      volume: null,
      is_fallback: true,
      message: "后端 API 暂不可用，无法确认真实行情。"
    },
    fundamentals: {
      ticker: normalizedTicker,
      market_cap: null,
      pe_ratio: null,
      eps: null,
      price_to_sales: null,
      price_to_book: null,
      gross_margin: null,
      profit_margin: null,
      operating_margin: null,
      debt_to_equity: null,
      source: "offline",
      period_ending: null,
      updated_at: "local",
      is_fallback: true,
      message: "后端 API 暂不可用，无法确认基本面。"
    },
    history: [],
    provider_mode: "hybrid",
    data_sources: fallbackDataSourcesStatus.data_sources
  };
}

function isNullableNumber(value: unknown): value is number | null {
  return typeof value === "number" || value === null;
}

function isMarketQuotePayload(value: unknown): value is MarketQuotePayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isNullableNumber(value.price) &&
    typeof value.currency === "string" &&
    typeof value.source === "string" &&
    typeof value.updated_at === "string" &&
    isNullableNumber(value.change) &&
    isNullableNumber(value.change_percent) &&
    isNullableNumber(value.volume) &&
    typeof value.is_fallback === "boolean" &&
    typeof value.message === "string"
  );
}

function isPriceHistoryBarPayload(value: unknown): value is PriceHistoryBarPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.date === "string" &&
    isNullableNumber(value.open) &&
    isNullableNumber(value.high) &&
    isNullableNumber(value.low) &&
    isNullableNumber(value.close) &&
    isNullableNumber(value.volume) &&
    typeof value.source === "string"
  );
}

function isFundamentalSnapshotPayload(value: unknown): value is FundamentalSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isNullableNumber(value.market_cap) &&
    isNullableNumber(value.pe_ratio) &&
    isNullableNumber(value.eps) &&
    isNullableNumber(value.price_to_sales) &&
    isNullableNumber(value.price_to_book) &&
    isNullableNumber(value.gross_margin) &&
    isNullableNumber(value.profit_margin) &&
    isNullableNumber(value.operating_margin) &&
    isNullableNumber(value.debt_to_equity) &&
    typeof value.source === "string" &&
    (typeof value.period_ending === "string" || value.period_ending === null) &&
    typeof value.updated_at === "string" &&
    typeof value.is_fallback === "boolean" &&
    typeof value.message === "string"
  );
}

function isMarketSnapshotPayload(value: unknown): value is MarketSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isMarketQuotePayload(value.quote) &&
    isFundamentalSnapshotPayload(value.fundamentals) &&
    Array.isArray(value.history) &&
    value.history.every(isPriceHistoryBarPayload) &&
    typeof value.provider_mode === "string" &&
    Array.isArray(value.data_sources) &&
    value.data_sources.every(isProviderStatus)
  );
}

export async function getMarketSnapshot(ticker: string): Promise<MarketSnapshotPayload> {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/market/snapshot/${normalizedTicker}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackMarketSnapshot(normalizedTicker);
    }
    const payload: unknown = await response.json();
    return isMarketSnapshotPayload(payload) ? payload : fallbackMarketSnapshot(normalizedTicker);
  } catch {
    return fallbackMarketSnapshot(normalizedTicker);
  }
}

export type StrategyDefinitionPayload = {
  id: string;
  name: string;
  description: string;
  language: string;
  asset_class: string;
  default_symbol: string;
  resolution: string;
  enabled: boolean;
  parameters: StrategyParameterDefinitionPayload[];
};

export type StrategyParameterDefinitionPayload = {
  name: string;
  label: string;
  kind: "ticker" | "date" | "integer" | "number";
  default: string;
  min?: number | null;
  max?: number | null;
  required: boolean;
};

export type StrategyListPayload = {
  strategies: StrategyDefinitionPayload[];
};

export type BacktestStatisticsPayload = {
  total_net_profit: string | null;
  compounding_annual_return: string | null;
  sharpe_ratio: string | null;
  drawdown: string | null;
  win_rate: string | null;
  total_trades: string | null;
};

export type EquityPointPayload = {
  time: string;
  value: number;
};

export type BacktestResultPayload = {
  run_id: string;
  strategy_id: string;
  status: "success" | "unavailable" | "failed" | "timeout" | "malformed_result";
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  message: string;
  parameters: BacktestParametersPayload;
  statistics: BacktestStatisticsPayload;
  equity: EquityPointPayload[];
  logs: string[];
  output_directory: string;
};

export type LatestBacktestPayload = {
  latest: BacktestResultPayload | null;
};

export type BacktestParametersPayload = Record<string, string>;

export type BacktestHistoryItemPayload = {
  run_id: string;
  strategy_id: string;
  status: BacktestResultPayload["status"];
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  parameters: BacktestParametersPayload;
  statistics: BacktestStatisticsPayload;
};

export type BacktestHistoryPayload = {
  history: BacktestHistoryItemPayload[];
};

const backtestResultStatuses: BacktestResultPayload["status"][] = [
  "success",
  "unavailable",
  "failed",
  "timeout",
  "malformed_result"
];

const fallbackStrategies: StrategyListPayload = {
  strategies: [
    {
      id: "moving_average_cross",
      name: "MovingAverageCross",
      description: "AAPL 日线均线交叉示例策略，用于本地 LEAN 回测验证。",
      language: "Python",
      asset_class: "US Equity",
      default_symbol: "AAPL",
      resolution: "Daily",
      enabled: true,
      parameters: [
        { name: "symbol", label: "Ticker", kind: "ticker", default: "AAPL", required: true },
        { name: "start_date", label: "Start Date", kind: "date", default: "2020-01-01", required: true },
        { name: "end_date", label: "End Date", kind: "date", default: "2021-01-01", required: true },
        { name: "cash", label: "Initial Cash", kind: "number", default: "100000", min: 1000, max: 1000000000, required: true },
        { name: "fast_period", label: "Fast SMA", kind: "integer", default: "20", min: 2, max: 400, required: true },
        { name: "slow_period", label: "Slow SMA", kind: "integer", default: "50", min: 3, max: 600, required: true }
      ]
    }
  ]
};

function fallbackBacktestResult(
  strategyId: string,
  parameters: BacktestParametersPayload = {}
): BacktestResultPayload {
  const now = new Date().toISOString();
  return {
    run_id: `offline-${strategyId}`,
    strategy_id: strategyId,
    status: "unavailable",
    started_at: now,
    completed_at: now,
    duration_seconds: 0,
    message: "后端 API 暂不可用，无法运行 LEAN 回测。",
    parameters,
    statistics: {
      total_net_profit: null,
      compounding_annual_return: null,
      sharpe_ratio: null,
      drawdown: null,
      win_rate: null,
      total_trades: null
    },
    equity: [],
    logs: ["请确认后端 API、Docker 和 LEAN CLI 状态。"],
    output_directory: "local"
  };
}

function failedBacktestResult(
  strategyId: string,
  message: string,
  parameters: BacktestParametersPayload = {}
): BacktestResultPayload {
  const now = new Date().toISOString();
  return {
    run_id: `failed-${strategyId || "strategy"}`,
    strategy_id: strategyId,
    status: "failed",
    started_at: now,
    completed_at: now,
    duration_seconds: 0,
    message,
    parameters,
    statistics: {
      total_net_profit: null,
      compounding_annual_return: null,
      sharpe_ratio: null,
      drawdown: null,
      win_rate: null,
      total_trades: null
    },
    equity: [],
    logs: [message],
    output_directory: "local"
  };
}

function stringifyErrorDetail(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value === null || value === undefined) {
    return "后端未返回错误详情。";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

async function readResponseErrorDetail(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.clone().json();
    if (isRecord(payload) && "detail" in payload) {
      return stringifyErrorDetail(payload.detail);
    }
    return stringifyErrorDetail(payload);
  } catch {
    try {
      const text = await response.text();
      return text.trim() || response.statusText || "后端未返回错误详情。";
    } catch {
      return response.statusText || "后端未返回错误详情。";
    }
  }
}

function isStrategyDefinition(value: unknown): value is StrategyDefinitionPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.description === "string" &&
    typeof value.language === "string" &&
    typeof value.asset_class === "string" &&
    typeof value.default_symbol === "string" &&
    typeof value.resolution === "string" &&
    typeof value.enabled === "boolean" &&
    Array.isArray(value.parameters) &&
    value.parameters.every(isStrategyParameterDefinition)
  );
}

function isStrategyParameterDefinition(value: unknown): value is StrategyParameterDefinitionPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.label === "string" &&
    ["ticker", "date", "integer", "number"].includes(String(value.kind)) &&
    typeof value.default === "string" &&
    (typeof value.min === "number" || value.min === null || value.min === undefined) &&
    (typeof value.max === "number" || value.max === null || value.max === undefined) &&
    typeof value.required === "boolean"
  );
}

function isStrategyListPayload(value: unknown): value is StrategyListPayload {
  return isRecord(value) && Array.isArray(value.strategies) && value.strategies.every(isStrategyDefinition);
}

function isBacktestStatistics(value: unknown): value is BacktestStatisticsPayload {
  return (
    isRecord(value) &&
    (typeof value.total_net_profit === "string" || value.total_net_profit === null) &&
    (typeof value.compounding_annual_return === "string" || value.compounding_annual_return === null) &&
    (typeof value.sharpe_ratio === "string" || value.sharpe_ratio === null) &&
    (typeof value.drawdown === "string" || value.drawdown === null) &&
    (typeof value.win_rate === "string" || value.win_rate === null) &&
    (typeof value.total_trades === "string" || value.total_trades === null)
  );
}

function isEquityPoint(value: unknown): value is EquityPointPayload {
  return isRecord(value) && typeof value.time === "string" && typeof value.value === "number";
}

function isBacktestParameters(value: unknown): value is BacktestParametersPayload {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}

function isBacktestResultPayload(value: unknown): value is BacktestResultPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.status === "string" &&
    backtestResultStatuses.includes(value.status as BacktestResultPayload["status"]) &&
    typeof value.started_at === "string" &&
    typeof value.completed_at === "string" &&
    typeof value.duration_seconds === "number" &&
    typeof value.message === "string" &&
    isBacktestParameters(value.parameters) &&
    isBacktestStatistics(value.statistics) &&
    Array.isArray(value.equity) &&
    value.equity.every(isEquityPoint) &&
    Array.isArray(value.logs) &&
    value.logs.every((item) => typeof item === "string") &&
    typeof value.output_directory === "string"
  );
}

function isLatestBacktestPayload(value: unknown): value is LatestBacktestPayload {
  return isRecord(value) && (value.latest === null || isBacktestResultPayload(value.latest));
}

function isBacktestHistoryItem(value: unknown): value is BacktestHistoryItemPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.status === "string" &&
    backtestResultStatuses.includes(value.status as BacktestResultPayload["status"]) &&
    typeof value.started_at === "string" &&
    typeof value.completed_at === "string" &&
    typeof value.duration_seconds === "number" &&
    isBacktestParameters(value.parameters) &&
    isBacktestStatistics(value.statistics)
  );
}

function isBacktestHistoryPayload(value: unknown): value is BacktestHistoryPayload {
  return isRecord(value) && Array.isArray(value.history) && value.history.every(isBacktestHistoryItem);
}

export async function getStrategyCatalog(): Promise<StrategyListPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/strategies`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategies;
    }
    const payload: unknown = await response.json();
    return isStrategyListPayload(payload) ? payload : fallbackStrategies;
  } catch {
    return fallbackStrategies;
  }
}

export async function getLatestBacktest(): Promise<LatestBacktestPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests/latest`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return { latest: null };
    }
    const payload: unknown = await response.json();
    return isLatestBacktestPayload(payload) ? payload : { latest: null };
  } catch {
    return { latest: null };
  }
}

export async function getBacktestHistory(limit = 10): Promise<BacktestHistoryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests/history?limit=${limit}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return { history: [] };
    }
    const payload: unknown = await response.json();
    return isBacktestHistoryPayload(payload) ? payload : { history: [] };
  } catch {
    return { history: [] };
  }
}

export async function runStrategyBacktest(
  strategyId: string,
  parameters: BacktestParametersPayload = {}
): Promise<BacktestResultPayload> {
  const normalizedStrategyId = strategyId.trim();
  if (!normalizedStrategyId) {
    return failedBacktestResult("", "请选择策略后再运行回测。", parameters);
  }

  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests`, {
      body: JSON.stringify({ strategy_id: normalizedStrategyId, parameters }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      const detail = await readResponseErrorDetail(response);
      const message = `请求失败（${response.status}）：${detail}`;
      return failedBacktestResult(normalizedStrategyId, message, parameters);
    }
    const payload: unknown = await response.json();
    return isBacktestResultPayload(payload) ? payload : fallbackBacktestResult(normalizedStrategyId, parameters);
  } catch {
    return fallbackBacktestResult(normalizedStrategyId, parameters);
  }
}

export type WorkspaceSummaryPayload = {
  team_id: string;
  team_name: string;
  portfolio_id: string;
  portfolio_name: string;
  position_count: number;
  watchlist_count: number;
  note_count: number;
};

export type PositionPayload = {
  id: string;
  ticker: string;
  quantity: number;
  average_cost: number;
  currency: string;
  price: number | null;
  market_value: number;
  weight: number;
  updated_at: string;
};

export type PortfolioPayload = {
  id: string;
  name: string;
  base_currency: string;
  total_market_value: number;
  positions: PositionPayload[];
};

export type PositionInputPayload = {
  ticker: string;
  quantity: number;
  average_cost: number;
  currency?: string;
};

export type PositionImportPayload = {
  imported_count: number;
  errors: Array<{ field: string; message: string; row: number }>;
  portfolio: PortfolioPayload | null;
};

export type WatchlistItemPayload = {
  id: string;
  ticker: string;
  thesis: string;
  created_at: string;
};

export type WatchlistPayload = {
  items: WatchlistItemPayload[];
};

export type WatchlistInputPayload = {
  ticker: string;
  thesis: string;
};

export type NotePayload = {
  id: string;
  ticker: string | null;
  title: string;
  body: string;
  created_at: string;
};

export type NotesPayload = {
  notes: NotePayload[];
};

export type NoteInputPayload = {
  ticker?: string | null;
  title: string;
  body: string;
};

export type ResearchNotePayload = {
  ai_run_id: string;
  note: NotePayload;
};

const fallbackPortfolio: PortfolioPayload = {
  id: "offline-portfolio",
  name: "主组合",
  base_currency: "USD",
  total_market_value: 0,
  positions: []
};

function isPositionPayload(value: unknown): value is PositionPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.ticker === "string" &&
    typeof value.quantity === "number" &&
    typeof value.average_cost === "number" &&
    typeof value.currency === "string" &&
    isNullableNumber(value.price) &&
    typeof value.market_value === "number" &&
    typeof value.weight === "number" &&
    typeof value.updated_at === "string"
  );
}

function isPortfolioPayload(value: unknown): value is PortfolioPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.base_currency === "string" &&
    typeof value.total_market_value === "number" &&
    Array.isArray(value.positions) &&
    value.positions.every(isPositionPayload)
  );
}

function isImportPayload(value: unknown): value is PositionImportPayload {
  return (
    isRecord(value) &&
    typeof value.imported_count === "number" &&
    Array.isArray(value.errors) &&
    value.errors.every(
      (item) =>
        isRecord(item) &&
        typeof item.row === "number" &&
        typeof item.field === "string" &&
        typeof item.message === "string"
    ) &&
    (value.portfolio === null || isPortfolioPayload(value.portfolio))
  );
}

function isWatchlistItem(value: unknown): value is WatchlistItemPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.ticker === "string" &&
    typeof value.thesis === "string" &&
    typeof value.created_at === "string"
  );
}

function isWatchlistPayload(value: unknown): value is WatchlistPayload {
  return isRecord(value) && Array.isArray(value.items) && value.items.every(isWatchlistItem);
}

function isNotePayload(value: unknown): value is NotePayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    (typeof value.ticker === "string" || value.ticker === null) &&
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.created_at === "string"
  );
}

function isNotesPayload(value: unknown): value is NotesPayload {
  return isRecord(value) && Array.isArray(value.notes) && value.notes.every(isNotePayload);
}

function isResearchNotePayload(value: unknown): value is ResearchNotePayload {
  return isRecord(value) && typeof value.ai_run_id === "string" && isNotePayload(value.note);
}

export async function getPortfolio(): Promise<PortfolioPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPortfolio;
    }
    const payload: unknown = await response.json();
    return isPortfolioPayload(payload) ? payload : fallbackPortfolio;
  } catch {
    return fallbackPortfolio;
  }
}

export async function upsertPosition(input: PositionInputPayload): Promise<PositionPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio/positions`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "PUT"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isPositionPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function deletePosition(ticker: string): Promise<boolean> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio/positions/${ticker.trim().toUpperCase()}`, {
      method: "DELETE"
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function importPositionsCsv(content: string): Promise<PositionImportPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio/import`, {
      body: JSON.stringify({ content }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      const detail = await readResponseErrorDetail(response);
      return { imported_count: 0, errors: [{ row: 0, field: "request", message: detail }], portfolio: null };
    }
    const payload: unknown = await response.json();
    return isImportPayload(payload) ? payload : { imported_count: 0, errors: [], portfolio: null };
  } catch {
    return { imported_count: 0, errors: [{ row: 0, field: "network", message: "后端 API 暂不可用。" }], portfolio: null };
  }
}

export async function getWatchlist(): Promise<WatchlistPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/watchlist`, { cache: "no-store" });
    if (!response.ok) {
      return { items: [] };
    }
    const payload: unknown = await response.json();
    return isWatchlistPayload(payload) ? payload : { items: [] };
  } catch {
    return { items: [] };
  }
}

export async function upsertWatchlistItem(input: WatchlistInputPayload): Promise<WatchlistItemPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/watchlist`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isWatchlistItem(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function deleteWatchlistItem(ticker: string): Promise<boolean> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/watchlist/${ticker.trim().toUpperCase()}`, {
      method: "DELETE"
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function getNotes(): Promise<NotesPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/notes`, { cache: "no-store" });
    if (!response.ok) {
      return { notes: [] };
    }
    const payload: unknown = await response.json();
    return isNotesPayload(payload) ? payload : { notes: [] };
  } catch {
    return { notes: [] };
  }
}

export async function createNote(input: NoteInputPayload): Promise<NotePayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/notes`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isNotePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function saveResearchResultAsNote(
  prompt: string,
  result: ResearchResultPayload
): Promise<ResearchNotePayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/research/notes`, {
      body: JSON.stringify({ prompt, result }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isResearchNotePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}
