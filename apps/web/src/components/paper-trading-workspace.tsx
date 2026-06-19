"use client";

import { useEffect, useState } from "react";
import { CalendarClock, Play, ShoppingCart, Wrench } from "lucide-react";
import {
  getAIStatus,
  getMarketHistory,
  getPaperDailyReport,
  getPaperEventLedger,
  getPaperExecutionDiagnostics,
  getPaperOperationsHistory,
  getPaperOperationsStatus,
  getPaperRiskProfile,
  getPaperRiskLimitReview,
  getPaperSchedulerStatus,
  getPaperMarketSession,
  getPaperMarketEvents,
  getPaperRuns,
  getPaperReviewTrend,
  getPaperStrategyReviews,
  getPaperTradingSummary,
  getStrategyRegistry,
  getAlphaGateProgress,
  getAlphaValidationForecast,
  getPaperActionPlan,
  executePaperPrimaryAction,
  applyPaperRiskLimitRecommendation,
  quarantineLegacyPaperRuns,
  repairPaperEventLedger,
  runPaperSimulationLab,
  runPaperTradingDailyLoop,
  submitPaperOrder,
  type AIStatusPayload,
  type PaperEventLedgerPayload,
  type PaperCandidatePayload,
  type PaperDailyReportPayload,
  type PaperExecutionDiagnosticsPayload,
  type PaperOperationsHistoryPayload,
  type PaperOperationsRepairPayload,
  type PaperOperationsStatusPayload,
  type PaperRiskProfilePayload,
  type PaperRiskLimitApplyPayload,
  type PaperRiskLimitReviewPayload,
  type PaperMarketSessionPayload,
  type PaperMarketEventsPayload,
  type PaperReviewTrendPayload,
  type PaperRunPayload,
  type PaperSchedulerStatusPayload,
  type PaperSimulationPayload,
  type PaperStrategyReviewsPayload,
  type PaperTradingSummaryPayload,
  type StrategyRegistryPayload,
  type AlphaGateProgressPayload,
  type AlphaValidationForecastPayload,
  type PaperActionPlanPayload,
  type PriceHistoryBarPayload
} from "@/lib/client-api";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  currency: "USD",
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
  style: "currency"
});

const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 4
});

const percentFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
  minimumFractionDigits: 1,
  style: "percent"
});

const readinessLabels: Record<string, string> = {
  collecting: "收集样本",
  negative_expectancy: "期望不达标",
  paper_ready: "模拟盘达标",
  watch: "继续观察"
};

function formatCurrency(value: number): string {
  return currencyFormatter.format(value);
}

function formatNumber(value: number): string {
  return numberFormatter.format(value);
}

function candidateRankingScoreLabel(evidence: string[] | undefined): string | null {
  const finalScore = evidence?.find((item) => item.startsWith("final_score="));
  if (!finalScore) {
    return null;
  }
  const rawValue = finalScore.split("=", 2)[1];
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) {
    return rawValue || null;
  }
  return formatNumber(parsed);
}

function readinessLabel(value: string | undefined): string {
  if (!value) {
    return "未复盘";
  }
  return readinessLabels[value] ?? value;
}

function formatTimestamp(value: string | null | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function operationBlockerLabel(value: string): string {
  const labels: Record<string, string> = {
    api_unavailable: "API 不可用",
    daily_run_missing: "今日未运行",
    event_ledger_not_replayable: "事件链缺失",
    latest_run_failed: "最新运行失败",
    review_missing: "复盘缺失"
  };
  return labels[value] ?? value;
}

function dataQualityWarningLabel(value: string): string {
  const labels: Record<string, string> = {
    future_runs_excluded_from_as_of_report: "未来模拟运行已从当前日报排除",
    legacy_manual_future_runs_detected: "检测到早期手动未来日期运行"
  };
  return labels[value] ?? value;
}

function exitTriggerLabel(value: string): string {
  const labels: Record<string, string> = {
    stop_loss: "止损",
    take_profit: "止盈"
  };
  return labels[value] ?? value;
}

function schedulerGateLabel(value: PaperSchedulerStatusPayload | null): string {
  if (!value) {
    return "未同步";
  }
  if (value.can_run_now) {
    return "允许执行";
  }
  const labels: Record<string, string> = {
    api_unavailable: "API 不可用",
    market_closed: "休市跳过",
    waiting_for_close: "等待收盘"
  };
  return labels[value.execution_gate] ?? value.execution_gate;
}

function nextSchedulerRunLabel(value: PaperSchedulerStatusPayload | null): string {
  if (!value || value.next_run_will_execute === null) {
    return "未知";
  }
  if (value.next_run_will_execute) {
    return "会采样";
  }
  const labels: Record<string, string> = {
    api_unavailable: "API 不可用",
    market_closed: "仅守门",
    waiting_for_close: "等待收盘"
  };
  return labels[value.next_run_execution_gate ?? ""] ?? "不会采样";
}

function normalizeTicker(value: string | null | undefined): string | null {
  const ticker = value?.trim().toUpperCase();
  return ticker ? ticker : null;
}

function compactId(value: string | null | undefined): string {
  if (!value) {
    return "无";
  }
  if (value.length <= 13) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function eventTopicLabel(value: string): string {
  const labels: Record<string, string> = {
    market_event: "MarketEvent 市场事件",
    strategy_input: "StrategyInput 策略输入",
    trade_intent: "TradeIntent 交易意图",
    risk_decision: "RiskDecision 风控裁决",
    order_state: "OrderState 订单状态",
    trade_explanation: "TradeExplanation 解释",
    execution_report: "ExecutionReport 执行回报"
  };
  return labels[value] ?? value;
}

function riskDecisionLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    approved: "风控通过",
    rejected: "风控拒绝"
  };
  return value ? labels[value] ?? value : "未进入风控";
}

function orderStateLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    filled: "已成交",
    rejected: "已拒绝",
    sent: "已发送",
    validated: "已校验"
  };
  return value ? labels[value] ?? value : "未形成订单";
}

function formatEventPayload(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function payloadText(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function payloadNumber(payload: Record<string, unknown>, key: string): number | null {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nestedRecord(payload: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = payload[key];
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

type ReadableEvidenceItem = {
  title: string;
  summary: string;
  source: string;
  source_url: string;
  observed_at: string;
};

function payloadEvidenceItems(payload: Record<string, unknown>): ReadableEvidenceItem[] {
  const value = payload.evidence_items;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null && !Array.isArray(item))
    .map((item) => ({
      title: payloadText(item, "title") ?? "未命名证据",
      summary: payloadText(item, "summary") ?? "无摘要",
      source: payloadText(item, "source") ?? "unknown",
      source_url: payloadText(item, "source_url") ?? "",
      observed_at: payloadText(item, "observed_at") ?? "未知时间"
    }));
}

function traceEvidenceItems(event: PaperMarketEventsPayload["events"][number] | null): ReadableEvidenceItem[] {
  return (event?.evidence_items ?? []).map((item) => ({
    title: item.title ?? "未命名证据",
    summary: item.summary ?? "无摘要",
    source: item.source ?? "unknown",
    source_url: item.source_url ?? "",
    observed_at: item.observed_at ?? "未知时间"
  }));
}

function payloadEvidenceCountLabel(payload: Record<string, unknown>): string | null {
  const evidence = payload.evidence;
  if (!Array.isArray(evidence)) {
    return null;
  }
  return evidence.find((item): item is string => typeof item === "string" && item.startsWith("evidence_count=")) ?? null;
}

function eventReadableTitle(topic: string, payload: Record<string, unknown>): string {
  const ticker = payloadText(payload, "ticker") ?? payloadText(nestedRecord(payload, "market_event"), "ticker");
  if (topic === "market_event") {
    return `${ticker ?? "UNKNOWN"} 市场事件`;
  }
  if (topic === "strategy_input") {
    return `${ticker ?? "组合"} 进入策略判断`;
  }
  if (topic === "trade_intent") {
    return `${ticker ?? "UNKNOWN"} 生成交易意图`;
  }
  if (topic === "risk_decision") {
    return `${ticker ?? "UNKNOWN"} 风控裁决`;
  }
  if (topic === "order_state") {
    return `${ticker ?? "UNKNOWN"} 订单状态`;
  }
  if (topic === "trade_explanation") {
    return `${ticker ?? "UNKNOWN"} 交易解释`;
  }
  return eventTopicLabel(topic);
}

function eventReadableSummary(topic: string, payload: Record<string, unknown>): string {
  if (topic === "market_event") {
    const summary = payloadText(payload, "summary") ?? "系统记录了一条市场输入。";
    const eventType = payloadText(payload, "event_type");
    const sentiment = payloadText(payload, "sentiment");
    const confidence = payloadNumber(payload, "confidence");
    const impact = payloadNumber(payload, "impact_score");
    const metadata = nestedRecord(payload, "metadata");
    const price = payloadNumber(metadata, "quote_price");
    const evidenceCount = payloadNumber(metadata, "evidence_count");
    return [
      summary,
      eventType ? `类型：${eventType}` : null,
      sentiment ? `情绪：${sentiment}` : null,
      confidence !== null ? `置信度：${percentFormatter.format(confidence)}` : null,
      impact !== null ? `影响分：${percentFormatter.format(impact)}` : null,
      price !== null ? `参考价：${formatCurrency(price)}` : null,
      evidenceCount !== null ? `证据数量：${formatNumber(evidenceCount)}` : null
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (topic === "strategy_input") {
    const marketEvent = nestedRecord(payload, "market_event");
    const portfolio = nestedRecord(payload, "portfolio");
    const cash = payloadNumber(portfolio, "cash");
    const equity = payloadNumber(portfolio, "equity");
    return [
      "策略收到市场事件和当时组合状态。",
      payloadText(marketEvent, "summary"),
      cash !== null ? `现金：${formatCurrency(cash)}` : null,
      equity !== null ? `权益：${formatCurrency(equity)}` : null
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (topic === "trade_intent") {
    const side = payloadText(payload, "side");
    const notional = payloadNumber(payload, "notional");
    const reason = payloadText(payload, "reason");
    return [
      side ? `方向：${side}` : null,
      notional !== null ? `名义金额：${formatCurrency(notional)}` : null,
      reason ? `原因：${reason}` : null
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (topic === "risk_decision") {
    const status = payloadText(payload, "status") ?? payloadText(payload, "code");
    const reason = payloadText(payload, "reason");
    return [`结果：${riskDecisionLabel(status)}`, reason ? `原因：${reason}` : null].filter(Boolean).join(" · ");
  }
  if (topic === "order_state") {
    const state = payloadText(payload, "state") ?? payloadText(payload, "current_state");
    const quantity = payloadNumber(payload, "quantity");
    const fillPrice = payloadNumber(payload, "fill_price") ?? payloadNumber(payload, "price");
    return [
      `状态：${orderStateLabel(state)}`,
      quantity !== null ? `数量：${formatNumber(quantity)}` : null,
      fillPrice !== null ? `价格：${formatCurrency(fillPrice)}` : null
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (topic === "trade_explanation") {
    const explanation = payloadText(payload, "explanation");
    const decision = payloadText(payload, "decision");
    const evidence = Array.isArray(payload.evidence)
      ? payload.evidence.filter((item): item is string => typeof item === "string")
      : [];
    const evidenceItems = payloadEvidenceItems(payload);
    return [
      decision ? `决策：${decision}` : null,
      explanation ?? "系统记录了一条交易解释。",
      evidenceItems.length ? `具体证据：${evidenceItems.length} 条` : null,
      evidence.length ? `证据：${evidence.slice(0, 4).join(" / ")}` : null
    ]
      .filter(Boolean)
      .join(" · ");
  }
  return "系统记录了一条运行事件。";
}

function historyBarDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

type NumericHistoryBar = PriceHistoryBarPayload & {
  open: number;
  high: number;
  low: number;
  close: number;
};

type PaperWorkspaceView = "overview" | "events" | "trading" | "risk" | "operations";

const paperWorkspaceViews: { id: PaperWorkspaceView; label: string; description: string }[] = [
  { id: "overview", label: "总览", description: "今天状态和首要动作" },
  { id: "events", label: "事件与AI", description: "市场事件、AI分析、K线和追溯" },
  { id: "trading", label: "候选与模拟", description: "候选、订单、持仓和多日模拟" },
  { id: "risk", label: "风控与复盘", description: "Alpha门禁、风险限额和策略复盘" },
  { id: "operations", label: "运行维护", description: "调度、健康、账本修复" }
];

function isNumericHistoryBar(value: PriceHistoryBarPayload): value is NumericHistoryBar {
  return (
    typeof value.open === "number" &&
    Number.isFinite(value.open) &&
    typeof value.high === "number" &&
    Number.isFinite(value.high) &&
    typeof value.low === "number" &&
    Number.isFinite(value.low) &&
    typeof value.close === "number" &&
    Number.isFinite(value.close)
  );
}

function historyChangePercent(bars: NumericHistoryBar[]): number | null {
  if (bars.length < 2) {
    return null;
  }
  const first = bars[0].close;
  const last = bars[bars.length - 1].close;
  if (first === 0) {
    return null;
  }
  return (last - first) / first;
}

function MiniCandlestickChart({
  averageCost,
  bars,
  ticker
}: {
  averageCost: number | null;
  bars: PriceHistoryBarPayload[];
  ticker: string;
}) {
  const chartBars = bars.filter(isNumericHistoryBar).slice(-60);
  if (!chartBars.length) {
    return (
      <div className="kline-empty">
        <strong>{ticker}</strong>
        <span>暂无可绘制的 OHLC 历史行情。</span>
      </div>
    );
  }

  const width = 680;
  const height = 260;
  const left = 42;
  const right = 18;
  const top = 18;
  const bottom = 34;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const lows = chartBars.map((bar) => bar.low);
  const highs = chartBars.map((bar) => bar.high);
  const minLow = Math.min(...lows);
  const maxHigh = Math.max(...highs);
  const padding = Math.max((maxHigh - minLow) * 0.08, maxHigh * 0.004, 0.5);
  const minValue = minLow - padding;
  const maxValue = maxHigh + padding;
  const valueRange = Math.max(maxValue - minValue, 1);
  const xStep = chartWidth / chartBars.length;
  const candleWidth = Math.max(3, Math.min(12, xStep * 0.56));
  const yForValue = (value: number) => top + ((maxValue - value) / valueRange) * chartHeight;
  const averageCostY =
    typeof averageCost === "number" && Number.isFinite(averageCost) && averageCost >= minValue && averageCost <= maxValue
      ? yForValue(averageCost)
      : null;
  const lastBar = chartBars[chartBars.length - 1];

  return (
    <div className="kline-chart">
      <svg aria-label={`${ticker} 最近 ${chartBars.length} 根日 K`} role="img" viewBox={`0 0 ${width} ${height}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = top + ratio * chartHeight;
          const value = maxValue - ratio * valueRange;
          return (
            <g key={`grid-${ratio}`}>
              <line className="kline-grid-line" x1={left} x2={width - right} y1={y} y2={y} />
              <text className="kline-axis-label" x={8} y={y + 4}>
                {value.toFixed(1)}
              </text>
            </g>
          );
        })}
        {averageCostY !== null ? (
          <g>
            <line className="kline-cost-line" x1={left} x2={width - right} y1={averageCostY} y2={averageCostY} />
            <text className="kline-cost-label" x={width - right - 108} y={averageCostY - 6}>
              平均成本 {formatCurrency(averageCost ?? 0)}
            </text>
          </g>
        ) : null}
        {chartBars.map((bar, index) => {
          const x = left + index * xStep + xStep / 2;
          const openY = yForValue(bar.open);
          const closeY = yForValue(bar.close);
          const highY = yForValue(bar.high);
          const lowY = yForValue(bar.low);
          const isUp = bar.close >= bar.open;
          return (
            <g className={isUp ? "kline-candle up" : "kline-candle down"} key={`${bar.date}-${index}`}>
              <title>
                {bar.date} O {bar.open.toFixed(2)} H {bar.high.toFixed(2)} L {bar.low.toFixed(2)} C{" "}
                {bar.close.toFixed(2)}
              </title>
              <line x1={x} x2={x} y1={highY} y2={lowY} />
              <rect
                height={Math.max(2, Math.abs(openY - closeY))}
                rx="1"
                width={candleWidth}
                x={x - candleWidth / 2}
                y={Math.min(openY, closeY)}
              />
            </g>
          );
        })}
        <text className="kline-date-label" x={left} y={height - 10}>
          {historyBarDate(chartBars[0].date)}
        </text>
        <text className="kline-date-label" textAnchor="end" x={width - right} y={height - 10}>
          {historyBarDate(lastBar.date)}
        </text>
      </svg>
    </div>
  );
}

export function PaperTradingWorkspace() {
  const [summary, setSummary] = useState<PaperTradingSummaryPayload | null>(null);
  const [dailyReport, setDailyReport] = useState<PaperDailyReportPayload | null>(null);
  const [scheduler, setScheduler] = useState<PaperSchedulerStatusPayload | null>(null);
  const [marketSession, setMarketSession] = useState<PaperMarketSessionPayload | null>(null);
  const [operations, setOperations] = useState<PaperOperationsStatusPayload | null>(null);
  const [operationsHistory, setOperationsHistory] = useState<PaperOperationsHistoryPayload | null>(null);
  const [reviewTrend, setReviewTrend] = useState<PaperReviewTrendPayload | null>(null);
  const [runs, setRuns] = useState<PaperRunPayload[]>([]);
  const [eventLedger, setEventLedger] = useState<PaperEventLedgerPayload | null>(null);
  const [marketEvents, setMarketEvents] = useState<PaperMarketEventsPayload | null>(null);
  const [executionDiagnostics, setExecutionDiagnostics] = useState<PaperExecutionDiagnosticsPayload | null>(null);
  const [riskProfile, setRiskProfile] = useState<PaperRiskProfilePayload | null>(null);
  const [riskLimitReview, setRiskLimitReview] = useState<PaperRiskLimitReviewPayload | null>(null);
  const [riskLimitApply, setRiskLimitApply] = useState<PaperRiskLimitApplyPayload | null>(null);
  const [alphaGateProgress, setAlphaGateProgress] = useState<AlphaGateProgressPayload | null>(null);
  const [alphaForecast, setAlphaForecast] = useState<AlphaValidationForecastPayload | null>(null);
  const [actionPlan, setActionPlan] = useState<PaperActionPlanPayload | null>(null);
  const [strategyReviews, setStrategyReviews] = useState<PaperStrategyReviewsPayload | null>(null);
  const [strategyRegistry, setStrategyRegistry] = useState<StrategyRegistryPayload | null>(null);
  const [aiStatus, setAIStatus] = useState<AIStatusPayload | null>(null);
  const [repairResult, setRepairResult] = useState<PaperOperationsRepairPayload | null>(null);
  const [simulationResult, setSimulationResult] = useState<PaperSimulationPayload | null>(null);
  const [selectedTicker, setSelectedTicker] = useState("SPCX");
  const [marketHistory, setMarketHistory] = useState<PriceHistoryBarPayload[]>([]);
  const [isLoadingMarketHistory, setIsLoadingMarketHistory] = useState(false);
  const [marketHistoryMessage, setMarketHistoryMessage] = useState("正在读取行情。");
  const [activeView, setActiveView] = useState<PaperWorkspaceView>("events");
  const [message, setMessage] = useState("正在读取模拟盘。");
  const [isExecutingPrimaryAction, setIsExecutingPrimaryAction] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isRepairing, setIsRepairing] = useState(false);
  const [isQuarantining, setIsQuarantining] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isApplyingRiskLimit, setIsApplyingRiskLimit] = useState(false);
  const [orderingTicker, setOrderingTicker] = useState<string | null>(null);

  async function refreshSummary(nextMessage?: string) {
    const [
      payload,
      reportPayload,
      marketSessionPayload,
      operationsPayload,
      historyPayload,
      reviewTrendPayload,
      executionDiagnosticsPayload,
      riskProfilePayload,
      riskLimitReviewPayload,
      alphaGateProgressPayload,
      alphaForecastPayload,
      actionPlanPayload,
      strategyReviewsPayload,
      strategyRegistryPayload,
      aiStatusPayload,
      runPayload,
      ledgerPayload,
      marketEventsPayload
    ] = await Promise.all([
      getPaperTradingSummary(),
      getPaperDailyReport(),
      getPaperMarketSession(),
      getPaperOperationsStatus(),
      getPaperOperationsHistory(),
      getPaperReviewTrend(),
      getPaperExecutionDiagnostics(),
      getPaperRiskProfile(),
      getPaperRiskLimitReview(),
      getAlphaGateProgress(),
      getAlphaValidationForecast(),
      getPaperActionPlan(),
      getPaperStrategyReviews(),
      getStrategyRegistry(),
      getAIStatus(),
      getPaperRuns(),
      getPaperEventLedger(),
      getPaperMarketEvents(selectedTicker)
    ]);
    setSummary(payload);
    setDailyReport(reportPayload);
    setMarketSession(marketSessionPayload);
    setOperations(operationsPayload);
    setOperationsHistory(historyPayload);
    setReviewTrend(reviewTrendPayload);
    setExecutionDiagnostics(executionDiagnosticsPayload);
    setRiskProfile(riskProfilePayload);
    setRiskLimitReview(riskLimitReviewPayload);
    setAlphaGateProgress(alphaGateProgressPayload);
    setAlphaForecast(alphaForecastPayload);
    setActionPlan(actionPlanPayload);
    setStrategyReviews(strategyReviewsPayload);
    setStrategyRegistry(strategyRegistryPayload);
    setAIStatus(aiStatusPayload);
    setRuns(runPayload.runs);
    setEventLedger(ledgerPayload);
    setMarketEvents(marketEventsPayload);
    setMessage(nextMessage ?? "模拟盘已同步。");
  }

  useEffect(() => {
    let active = true;
    const requests = [
      getPaperTradingSummary().then((payload) => active && setSummary(payload)),
      getPaperDailyReport().then((payload) => active && setDailyReport(payload)),
      getPaperSchedulerStatus().then((payload) => active && setScheduler(payload)),
      getPaperMarketSession().then((payload) => active && setMarketSession(payload)),
      getPaperOperationsStatus().then((payload) => active && setOperations(payload)),
      getPaperOperationsHistory().then((payload) => active && setOperationsHistory(payload)),
      getPaperReviewTrend().then((payload) => active && setReviewTrend(payload)),
      getPaperExecutionDiagnostics().then((payload) => active && setExecutionDiagnostics(payload)),
      getPaperRiskProfile().then((payload) => active && setRiskProfile(payload)),
      getPaperRiskLimitReview().then((payload) => active && setRiskLimitReview(payload)),
      getAlphaGateProgress().then((payload) => active && setAlphaGateProgress(payload)),
      getAlphaValidationForecast().then((payload) => active && setAlphaForecast(payload)),
      getPaperActionPlan().then((payload) => active && setActionPlan(payload)),
      getPaperStrategyReviews().then((payload) => active && setStrategyReviews(payload)),
      getStrategyRegistry().then((payload) => active && setStrategyRegistry(payload)),
      getAIStatus().then((payload) => active && setAIStatus(payload)),
      getPaperRuns().then((payload) => active && setRuns(payload.runs)),
      getPaperEventLedger().then((payload) => active && setEventLedger(payload)),
      getPaperMarketEvents(selectedTicker).then((payload) => active && setMarketEvents(payload))
    ];
    Promise.allSettled(requests).then(() => {
      if (active) {
        setMessage("模拟盘已同步。");
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getPaperMarketEvents(selectedTicker).then((payload) => active && setMarketEvents(payload));
    return () => {
      active = false;
    };
  }, [selectedTicker]);

  async function handleDailyRun() {
    if (operations && !operations.can_retry_today) {
      setMessage("今日模拟已完成，等待下一交易日。");
      return;
    }
    setIsRunning(true);
    setMessage("正在运行今日模拟。");
    try {
      const payload = await runPaperTradingDailyLoop();
      const [
        reportPayload,
        marketSessionPayload,
        operationsPayload,
        historyPayload,
        reviewTrendPayload,
        executionDiagnosticsPayload,
        riskProfilePayload,
        riskLimitReviewPayload,
        alphaGateProgressPayload,
        alphaForecastPayload,
        actionPlanPayload,
        strategyReviewsPayload,
        strategyRegistryPayload,
        aiStatusPayload,
        runPayload,
        ledgerPayload
      ] =
        await Promise.all([
        getPaperDailyReport(),
        getPaperMarketSession(),
        getPaperOperationsStatus(),
        getPaperOperationsHistory(),
        getPaperReviewTrend(),
        getPaperExecutionDiagnostics(),
        getPaperRiskProfile(),
        getPaperRiskLimitReview(),
        getAlphaGateProgress(),
        getAlphaValidationForecast(),
        getPaperActionPlan(),
        getPaperStrategyReviews(),
        getStrategyRegistry(),
        getAIStatus(),
        getPaperRuns(),
        getPaperEventLedger()
      ]);
      setSummary(payload);
      setDailyReport(reportPayload);
      setMarketSession(marketSessionPayload);
      setOperations(operationsPayload);
      setOperationsHistory(historyPayload);
      setReviewTrend(reviewTrendPayload);
      setExecutionDiagnostics(executionDiagnosticsPayload);
      setRiskProfile(riskProfilePayload);
      setRiskLimitReview(riskLimitReviewPayload);
      setAlphaGateProgress(alphaGateProgressPayload);
      setAlphaForecast(alphaForecastPayload);
      setActionPlan(actionPlanPayload);
      setStrategyReviews(strategyReviewsPayload);
      setStrategyRegistry(strategyRegistryPayload);
      setAIStatus(aiStatusPayload);
      setRuns(runPayload.runs);
      setEventLedger(ledgerPayload);
      setMessage("今日模拟已完成。");
    } finally {
      setIsRunning(false);
    }
  }

  async function handleBuy(candidate: PaperCandidatePayload) {
    setOrderingTicker(candidate.ticker);
    setMessage(`正在模拟买入 ${candidate.ticker}。`);
    try {
      const order = await submitPaperOrder({
        candidate_id: candidate.id,
        order_type: "market",
        quantity: candidate.proposed_quantity,
        side: "buy",
        strategy_id: candidate.strategy_id,
        ticker: candidate.ticker
      });
      if (!order) {
        setMessage(`模拟买入 ${candidate.ticker} 失败，请检查现金或报价。`);
        return;
      }
      await refreshSummary(`已模拟买入 ${candidate.ticker}。`);
    } finally {
      setOrderingTicker(null);
    }
  }

  async function handleRepairLedger() {
    setIsRepairing(true);
    setMessage("正在修复历史事件链。");
    try {
      const repair = await repairPaperEventLedger();
      setRepairResult(repair);
      await refreshSummary(`事件链修复完成：修复 ${repair.repaired_runs} 条运行记录。`);
    } finally {
      setIsRepairing(false);
    }
  }

  async function handleQuarantineLegacyRuns() {
    setIsQuarantining(true);
    setMessage("正在标记旧运行。");
    try {
      const quarantine = await quarantineLegacyPaperRuns();
      await refreshSummary(`旧运行已标记：${quarantine.quarantined_runs} 条改为 simulation。`);
    } finally {
      setIsQuarantining(false);
    }
  }

  async function handleSimulation() {
    setIsSimulating(true);
    setMessage("正在运行 5 日多日模拟。");
    try {
      const result = await runPaperSimulationLab({ days: 5, scenario: "bullish" });
      setSimulationResult(result);
      await refreshSummary(`多日模拟完成：${result.days_completed}/${result.days_requested} 天。`);
    } finally {
      setIsSimulating(false);
    }
  }

  async function handleApplyRiskLimitRecommendation() {
    setIsApplyingRiskLimit(true);
    setMessage("正在应用 Paper 风险限额建议。");
    try {
      const result = await applyPaperRiskLimitRecommendation();
      setRiskLimitApply(result);
      await refreshSummary(result.summary);
    } finally {
      setIsApplyingRiskLimit(false);
    }
  }

  async function handleExecutePrimaryAction() {
    setIsExecutingPrimaryAction(true);
    setMessage("正在执行首要行动。");
    try {
      const result = await executePaperPrimaryAction();
      const nextMessage = result.queued ? `${result.summary} 后台运行中，可在运行记录查看状态。` : result.summary;
      await refreshSummary(nextMessage);
    } finally {
      setIsExecutingPrimaryAction(false);
    }
  }

  const account = summary?.account;
  const review = summary?.latest_review;
  const candidates = summary?.candidates ?? [];
  const orders = summary?.orders ?? [];
  const positions = summary?.positions ?? [];
  const schedulerLabel = scheduler?.enabled ? (scheduler.running ? "运行中" : "已启用") : "未启用";
  const schedulerGate = schedulerGateLabel(scheduler);
  const nextRunLabel = nextSchedulerRunLabel(scheduler);
  const canRunDaily = operations?.can_retry_today ?? true;
  const dailyRunLabel = isRunning ? "运行中" : canRunDaily ? "运行今日模拟" : "今日已完成";
  const simulationRunLabel = isSimulating ? "模拟中" : "运行 5 日模拟";
  const primaryActionLabel = isExecutingPrimaryAction ? "执行中" : "执行首要动作";
  const canApplyRiskLimitRecommendation =
    riskLimitReview?.status === "review_required" &&
    (riskLimitReview?.recommended_paper_max_daily_orders ?? 0) > (riskLimitReview?.current_max_daily_orders ?? 0) &&
    riskLimitReview.live_change_allowed === false;
  const hasRepairableLedger = (operationsHistory?.items ?? []).some((item) =>
    item.blockers.includes("event_ledger_not_replayable")
  );
  const hasLegacyManualFutureRuns = (operations?.legacy_manual_future_run_count ?? 0) > 0;
  const replayChain =
    eventLedger?.latest_replay?.chains.find((chain) => chain.order_states.length > 0) ??
    eventLedger?.latest_replay?.chains[0] ??
    null;
  const topicSummary =
    eventLedger?.latest_topic_counts.map((item) => `${item.topic} ${item.count}`).join(" / ") ?? "暂无事件";
  const ledgerIntegrityReady = eventLedger?.integrity_ready ?? eventLedger?.replay_ready ?? false;
  const ledgerWarnings =
    eventLedger?.integrity_warnings?.length ? eventLedger.integrity_warnings : eventLedger?.warnings ?? [];
  const chainWarnings = replayChain?.integrity_warnings ?? [];
  const tradeExplanation = replayChain?.trade_explanation ?? null;
  const backtestReturn = tradeExplanation?.backtest.total_net_profit;
  const candidateRankingScore = candidateRankingScoreLabel(tradeExplanation?.evidence);
  const activeStrategy = strategyRegistry?.entries.find(
    (entry) => entry.strategy_id === strategyRegistry.active_strategy_id
  );
  const paperStrategies = strategyRegistry?.entries.filter((entry) => entry.execution_mode === "paper") ?? [];
  const paperStrategyLabel = paperStrategies.length
    ? paperStrategies.map((entry) => entry.strategy_id).join(" / ")
    : "正在读取";
  const runtimeTickerOptions = Array.from(
    new Set(
      [
        ...positions.map((position) => position.ticker),
        ...candidates.map((candidate) => candidate.ticker),
        ...orders.map((order) => order.ticker),
        replayChain?.ticker
      ]
        .map(normalizeTicker)
        .filter((ticker): ticker is string => Boolean(ticker))
    )
  );
  const tickerOptions = Array.from(new Set([...runtimeTickerOptions, "SPCX", "INTC"]));
  const tickerOptionKey = tickerOptions.join("|");

  useEffect(() => {
    const options = tickerOptionKey.split("|").filter(Boolean);
    if (options.length && !options.includes(selectedTicker)) {
      setSelectedTicker(options[0]);
    }
  }, [selectedTicker, tickerOptionKey]);

  useEffect(() => {
    let active = true;
    setIsLoadingMarketHistory(true);
    setMarketHistoryMessage(`正在读取 ${selectedTicker} 日线行情。`);
    getMarketHistory(selectedTicker)
      .then((payload) => {
        if (!active) {
          return;
        }
        setMarketHistory(payload);
        setMarketHistoryMessage(
          payload.length ? `${selectedTicker} 已同步 ${payload.length} 根日线。` : `${selectedTicker} 暂无历史行情。`
        );
      })
      .finally(() => {
        if (active) {
          setIsLoadingMarketHistory(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selectedTicker]);

  const eventTopics = replayChain?.topics.length
    ? replayChain.topics
    : eventLedger?.latest_topic_counts.map((item) => item.topic) ?? [];
  const selectedMarketEvents = marketEvents?.events ?? [];
  const latestMarketEvent = selectedMarketEvents[0] ?? null;
  const latestMarketEventEvidenceItems = traceEvidenceItems(latestMarketEvent);
  const marketEventTopics = latestMarketEvent?.topics ?? [];
  const marketEventSummary =
    marketEvents?.summary ?? `${selectedTicker} 暂无市场事件；先运行模拟盘或等待调度采样。`;
  const numericMarketHistory = marketHistory.filter(isNumericHistoryBar);
  const latestMarketBar = numericMarketHistory.length ? numericMarketHistory[numericMarketHistory.length - 1] : null;
  const marketHistoryChange = historyChangePercent(numericMarketHistory);
  const marketHistorySource = marketHistory.find((bar) => bar.source)?.source ?? "未同步";
  const selectedPosition = positions.find((position) => position.ticker === selectedTicker) ?? null;
  const selectedTickerUnrealizedPnl = selectedPosition?.unrealized_pnl ?? 0;
  const llmStatusLabel = aiStatus?.research_llm.available
    ? "LLM 可用"
    : aiStatus?.research_llm.configured
      ? "LLM 已配置待恢复"
      : "LLM 未配置";
  const aiExecutionBlocked =
    aiStatus &&
    !aiStatus.execution_path.ai_generates_trade_intent &&
    !aiStatus.execution_path.ai_influences_risk &&
    !aiStatus.execution_path.ai_calls_execution;

  return (
    <div className="module-view paper-trading-module" data-active-paper-view={activeView}>
      <header className="page-header">
        <div>
          <p>候选、解释、纸面成交、PnL 与复盘</p>
          <h2>模拟盘</h2>
        </div>
        <div className="status-pill neutral">{readinessLabel(review?.readiness)}</div>
      </header>

      <nav className="paper-workspace-tabs" aria-label="模拟盘分类">
        {paperWorkspaceViews.map((view) => (
          <button
            key={view.id}
            type="button"
            className={activeView === view.id ? "active" : ""}
            onClick={() => setActiveView(view.id)}
          >
            <strong>{view.label}</strong>
            <span>{view.description}</span>
          </button>
        ))}
      </nav>

      <section className="data-panel workspace-panel operations-visibility-panel paper-view-section paper-view-events" aria-label="运行可视化">
        <div className="panel-heading">
          <div>
            <h3>运行可视化</h3>
            <p>把 Trading Core 事件链、AI/研究解释和模拟盘行情放在同一屏，方便先看发生了什么。</p>
          </div>
          <span className={ledgerIntegrityReady ? "status-pill success" : "status-pill warning"}>
            {ledgerIntegrityReady ? "事件可追溯" : "事件待修复"}
          </span>
        </div>
        <div className="operations-visibility-grid">
          <article className="operations-observer-card" aria-label="具体事件流">
            <div className="observer-card-heading">
              <div>
                <span>Event Ledger</span>
                <strong>具体事件流</strong>
              </div>
              <span className="status-pill neutral">{eventLedger?.latest_run_event_count ?? 0} events</span>
            </div>
            <div className="event-trace-meta">
              <span>run {compactId(eventLedger?.latest_run_id)}</span>
              <span>corr {compactId(replayChain?.correlation_id)}</span>
              <span>{replayChain?.ticker ?? "UNKNOWN"}</span>
            </div>
            <ol className="event-flow-list">
              {eventTopics.length ? (
                eventTopics.map((topic, index) => (
                  <li key={`${topic}-${index}`}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>{eventTopicLabel(topic)}</strong>
                      <p>
                        {topic === "trade_intent"
                          ? "策略输出意图，后续必须经过风控。"
                          : topic === "risk_decision"
                            ? "RiskEngine 作为硬门禁裁决。"
                            : topic === "order_state"
                              ? `订单状态机：${replayChain?.order_states.join(" -> ") || "未记录"}`
                              : topic === "trade_explanation"
                                ? "记录候选/交易解释，用于复盘，不直接下单。"
                                : "已写入 CoreEventLog，可按 correlation_id 追溯。"}
                      </p>
                    </div>
                  </li>
                ))
              ) : (
                <li>
                  <span>0</span>
                  <div>
                    <strong>暂无运行事件</strong>
                    <p>先运行今日模拟或等待调度完成后，这里会显示 MarketEvent 到 OrderState 的链路。</p>
                  </div>
                </li>
              )}
            </ol>
            <div className="observer-footnote">
              <strong>{topicSummary}</strong>
              <p>账本警告 {ledgerWarnings.join(" / ") || "无"} · 链路警告 {chainWarnings.join(" / ") || "无"}</p>
            </div>
          </article>

          <article className="operations-observer-card market-events-card" aria-label="市场事件中心">
            <div className="observer-card-heading">
              <div>
                <span>Market Events</span>
                <strong>市场事件中心</strong>
              </div>
              <span className="status-pill neutral">
                {marketEvents?.filtered_event_count ?? 0}/{marketEvents?.total_event_count ?? 0}
              </span>
            </div>
            <div className="market-event-focus">
              <span>{selectedTicker} 最新事件</span>
              <strong>{latestMarketEvent?.summary ?? "暂无市场事件"}</strong>
              <p>
                策略 {latestMarketEvent?.strategy_id ?? "未触发"} · corr {compactId(latestMarketEvent?.correlation_id)} ·{" "}
                {formatTimestamp(latestMarketEvent?.published_at, "无时间")}
              </p>
            </div>
            <div className="market-event-decision-grid">
              <div>
                <span>置信度</span>
                <strong>{latestMarketEvent?.confidence === null || latestMarketEvent?.confidence === undefined ? "-" : percentFormatter.format(latestMarketEvent.confidence)}</strong>
              </div>
              <div>
                <span>影响分</span>
                <strong>{latestMarketEvent?.impact_score === null || latestMarketEvent?.impact_score === undefined ? "-" : percentFormatter.format(latestMarketEvent.impact_score)}</strong>
              </div>
              <div>
                <span>交易意图</span>
                <strong>{latestMarketEvent?.trade_intent_side ?? "未生成"}</strong>
              </div>
              <div>
                <span>风控</span>
                <strong>{riskDecisionLabel(latestMarketEvent?.risk_decision)}</strong>
              </div>
              <div>
                <span>订单</span>
                <strong>{orderStateLabel(latestMarketEvent?.order_state)}</strong>
              </div>
              <div>
                <span>来源</span>
                <strong>{latestMarketEvent?.source ?? "未标注"}</strong>
              </div>
            </div>
            <div className="market-event-chain">
              {marketEventTopics.length ? (
                marketEventTopics.map((topic, index) => (
                  <span key={`${latestMarketEvent?.correlation_id}-${topic}-${index}`}>{eventTopicLabel(topic)}</span>
                ))
              ) : (
                <span>暂无可追溯链路</span>
              )}
            </div>
            <div className="market-event-explanation">
              <span>解释与证据</span>
              <p>{latestMarketEvent?.explanation ?? latestMarketEvent?.trade_intent_reason ?? "暂无解释；产生候选或订单后会写入 trade_explanation。"}</p>
              <p>{latestMarketEvent?.evidence.join(" / ") || "暂无证据标签"}</p>
            </div>
            <div className="readable-evidence-list market-event-source-list">
              <span>本事件依据</span>
              {latestMarketEventEvidenceItems.length ? (
                latestMarketEventEvidenceItems.map((item, index) => (
                  <div key={`${latestMarketEvent?.event_id}-source-${index}`} className="readable-evidence-item">
                    <strong>{item.title}</strong>
                    <p>{item.summary}</p>
                    <small>
                      来源 {item.source} · 观察时间 {item.observed_at}
                      {item.source_url ? ` · ${item.source_url}` : ""}
                    </small>
                  </div>
                ))
              ) : (
                <p>这条历史市场事件没有保存结构化来源明细；可在下方具体事件内容中查看 payload，新的模拟盘事件会优先写入本事件依据。</p>
              )}
            </div>
            <div className="market-event-payloads">
              <span>具体事件内容</span>
              {latestMarketEvent?.chain_events.length ? (
                latestMarketEvent.chain_events.map((event) => (
                  <article key={`${event.event_id}-${event.sequence}`} className="readable-event-card">
                    <div className="readable-event-heading">
                      <span>{event.sequence}</span>
                      <div>
                        <strong>{eventReadableTitle(event.topic, event.payload)}</strong>
                        <small>
                          {eventTopicLabel(event.topic)} · event {compactId(event.event_id)}
                          {event.causation_id ? ` · caused by ${compactId(event.causation_id)}` : ""}
                        </small>
                      </div>
                    </div>
                    <p>{eventReadableSummary(event.topic, event.payload)}</p>
                    {payloadEvidenceItems(event.payload).length ? (
                      <div className="readable-evidence-list">
                        <span>证据来源与内容</span>
                        {payloadEvidenceItems(event.payload).map((item, index) => (
                          <div key={`${event.event_id}-evidence-${index}`} className="readable-evidence-item">
                            <strong>{item.title}</strong>
                            <p>{item.summary}</p>
                            <small>
                              来源 {item.source} · 观察时间 {item.observed_at}
                              {item.source_url ? ` · ${item.source_url}` : ""}
                            </small>
                          </div>
                        ))}
                      </div>
                    ) : event.topic === "trade_explanation" ? (
                      <div className="readable-evidence-list missing-evidence-detail">
                        <span>证据来源与内容</span>
                        <p>
                          这条历史解释事件只落库了证据标签
                          {payloadEvidenceCountLabel(event.payload) ? `（${payloadEvidenceCountLabel(event.payload)}）` : ""}
                          ，没有保存每条证据的标题、来源、链接和摘要。新产生的模拟盘事件会写入证据明细。
                        </p>
                      </div>
                    ) : null}
                    <details>
                      <summary>原始数据</summary>
                      <pre>{formatEventPayload(event.payload)}</pre>
                    </details>
                  </article>
                ))
              ) : (
                <p>暂无 payload。运行模拟盘产生 MarketEvent 后会显示原始事件内容。</p>
              )}
            </div>
            <div className="market-event-list">
              {selectedMarketEvents.length ? (
                selectedMarketEvents.slice(0, 5).map((event) => (
                  <button key={event.event_id} type="button" className="market-event-row">
                    <span>{event.ticker ?? "UNKNOWN"}</span>
                    <strong>{event.summary ?? event.event_type ?? "market_event"}</strong>
                    <small>
                      {orderStateLabel(event.order_state)} · {riskDecisionLabel(event.risk_decision)} · {compactId(event.correlation_id)}
                    </small>
                  </button>
                ))
              ) : (
                <div className="market-event-empty">
                  <strong>{selectedTicker} 暂无市场事件</strong>
                  <p>先把标的加入自选股并运行模拟盘；系统产生 MarketEvent 后，这里会显示事件、解释、风控和订单追溯。</p>
                </div>
              )}
            </div>
            <p className="kline-message">{marketEventSummary}</p>
          </article>

          <article className="operations-observer-card" aria-label="AI分析过程">
            <div className="observer-card-heading">
              <div>
                <span>AI / Research</span>
                <strong>AI分析过程</strong>
              </div>
              <span className={aiExecutionBlocked ? "status-pill success" : "status-pill warning"}>
                {aiExecutionBlocked ? "不参与执行" : "需审计"}
              </span>
            </div>
            <div className="ai-process-status">
              <div>
                <span>LangGraph</span>
                <strong>{aiStatus?.langgraph.available ? "可用" : "未确认"}</strong>
                <p>{aiStatus?.langgraph.message ?? "正在读取研究 workflow 状态。"}</p>
              </div>
              <div>
                <span>Research LLM</span>
                <strong>{llmStatusLabel}</strong>
                <p>{aiStatus?.research_llm.message ?? "正在读取 LLM 配置状态。"}</p>
              </div>
              <div>
                <span>执行权限</span>
                <strong>{aiExecutionBlocked ? "只解释不交易" : "存在执行影响"}</strong>
                <p>AI 不应生成 TradeIntent、影响 RiskEngine 或直接调用 ExecutionEngine。</p>
              </div>
            </div>
            <div className="ai-explanation-card">
              <span>最新解释事件</span>
              <strong>
                {tradeExplanation
                  ? `${tradeExplanation.ticker ?? "UNKNOWN"} · ${tradeExplanation.decision ?? "decision_unknown"}`
                  : "暂无 trade_explanation"}
              </strong>
              <p>{tradeExplanation?.explanation ?? "运行产生候选或订单后，解释事件会展示候选理由、证据和回测字段。"}</p>
              <p>
                策略 {tradeExplanation?.strategy_id ?? activeStrategy?.strategy_id ?? "未同步"} · 候选{" "}
                {compactId(tradeExplanation?.candidate_id)}
              </p>
              <p>证据 {(tradeExplanation?.evidence ?? []).slice(0, 4).join(" / ") || "无"}</p>
              <p>
                回测收益{" "}
                {typeof backtestReturn === "string" || typeof backtestReturn === "number" ? backtestReturn : "n/a"}
                {candidateRankingScore ? ` · 排序分数 ${candidateRankingScore}` : ""}
              </p>
            </div>
          </article>

          <article className="operations-observer-card kline-observer-card" aria-label="模拟盘K线">
            <div className="observer-card-heading">
              <div>
                <span>Paper Market</span>
                <strong>模拟盘K线</strong>
              </div>
              <label className="ticker-selector">
                <span>标的</span>
                <select value={selectedTicker} onChange={(event) => setSelectedTicker(event.target.value)}>
                  {tickerOptions.map((ticker) => (
                    <option key={ticker} value={ticker}>
                      {ticker}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <MiniCandlestickChart
              averageCost={selectedPosition?.average_cost ?? null}
              bars={marketHistory}
              ticker={selectedTicker}
            />
            <div className="kline-stat-grid">
              <div>
                <span>最新收盘</span>
                <strong>{latestMarketBar ? formatCurrency(latestMarketBar.close) : "-"}</strong>
              </div>
              <div>
                <span>区间变化</span>
                <strong>{marketHistoryChange === null ? "-" : percentFormatter.format(marketHistoryChange)}</strong>
              </div>
              <div>
                <span>数据源</span>
                <strong>{isLoadingMarketHistory ? "读取中" : marketHistorySource}</strong>
              </div>
              <div>
                <span>模拟持仓</span>
                <strong>{selectedPosition ? `${formatNumber(selectedPosition.quantity)} 股` : "未持仓"}</strong>
              </div>
              <div>
                <span>平均成本</span>
                <strong>{selectedPosition ? formatCurrency(selectedPosition.average_cost) : "-"}</strong>
              </div>
              <div>
                <span>未实现PnL</span>
                <strong>{selectedPosition ? formatCurrency(selectedTickerUnrealizedPnl) : "-"}</strong>
              </div>
            </div>
            <p className="kline-message">{marketHistoryMessage}</p>
          </article>
        </div>
      </section>

      <section className="data-panel workspace-panel user-flow-panel paper-view-section paper-view-overview" aria-label="SPCX INTC 上手向导">
        <div className="panel-heading">
          <div>
            <h3>用 SPCX / INTC 举例：先选目的</h3>
            <p>不是每只股票都必须盯盘、模拟、回测、追溯全走一遍；按你现在想解决的问题进对应入口。</p>
          </div>
          <span className="status-pill neutral">新手优先看这里</span>
        </div>
        <div className="user-flow-grid">
          <article className="user-flow-step">
            <span>1</span>
            <strong>只是持续关注</strong>
            <p>
              到自选股页添加 <b>SPCX</b> 和 <b>INTC</b>，写清楚关注理由。这样系统会把它们纳入研究和候选上下文。
            </p>
            <a className="guide-action-link" href="/watchlist">
              打开自选股
            </a>
          </article>
          <article className="user-flow-step">
            <span>2</span>
            <strong>想让系统判断今天是否值得动</strong>
            <p>看“今日简报”和“候选池”。SPCX/INTC 只有在策略、数据和风控都通过时才会出现；没出现就代表今天没有进入模拟条件。</p>
            <a className="guide-action-link" href="#paper-candidates">
              看候选池
            </a>
          </article>
          <article className="user-flow-step">
            <span>3</span>
            <strong>想验证历史表现</strong>
            <p>
              到策略实验室跑单票或候选池回测。候选池可填 <b>SPCX, INTC</b>，重点看收益、Sharpe、回撤、数据质量和排名理由。
            </p>
            <a className="guide-action-link" href="/strategy-lab">
              打开策略实验室
            </a>
          </article>
          <article className="user-flow-step">
            <span>4</span>
            <strong>已经出候选或下过模拟单</strong>
            <p>这时再追溯。候选理由在“候选池”；完整链路在“事件账本”，包括 trade_explanation、candidate_id、风控和订单状态。</p>
            <a className="guide-action-link" href="#paper-ledger">
              看事件账本
            </a>
          </article>
        </div>
        <div className="operator-focus-row" aria-label="按目的选择区域">
          <span>按目的看：</span>
          <strong>是否该动：今日简报 / 候选池</strong>
          <strong>是否已动：模拟订单 / 持仓</strong>
          <strong>为什么动：候选理由 / 事件账本</strong>
          <strong>历史是否支持：策略实验室</strong>
        </div>
      </section>

      <section className="data-panel workspace-panel strategy-origin-panel paper-view-section paper-view-overview" aria-label="当前模拟盘策略来源">
        <div className="panel-heading">
          <div>
            <h3>当前模拟盘策略从哪里来</h3>
            <p>当前策略是可验证的工程基线，不是已经证明能赚钱的成熟 Alpha；任何新策略都必须先进入 Registry 再验证。</p>
          </div>
          <span className="status-pill neutral">{activeStrategy?.strategy_id ?? "读取中"}</span>
        </div>
        <div className="strategy-origin-grid">
          <article>
            <span>当前主策略</span>
            <strong>{activeStrategy?.name ?? "正在读取 Strategy Registry"}</strong>
            <p>{activeStrategy?.notes ?? "读取当前 paper runtime 的 active strategy、样本和门禁状态。"}</p>
          </article>
          <article>
            <span>已接入模拟盘</span>
            <strong>{paperStrategyLabel}</strong>
            <p>只有这些 Registry 允许的策略可以产生 paper candidate；策略可升级、调参、新增或淘汰，但不能绕过门禁。</p>
          </article>
          <article>
            <span>候选怎么产生</span>
            <strong>StrategyEngine 运行规则</strong>
            <p>自选股/组合标的进入策略宇宙，行情和研究数据形成 MarketEvent，规则通过后输出 TradeIntent。</p>
          </article>
          <article>
            <span>怎么验证变化</span>
            <strong>先回测，再模拟盘</strong>
            <p>LEAN/vectorbt 提供历史证据；真正能否留用或进入下一阶段，还要看 paper 样本、PnL、风控和事件账本。</p>
          </article>
        </div>
        <div className="strategy-evidence-note" aria-label="策略依据说明">
          <strong>依据和边界：</strong>
          <span>deterministic_watchlist_v1 基于自选股、正向事件、置信度、影响分和小额名义本金，是稳定跑通研究闭环的基线策略。</span>
          <span>moving_average_cross 基于快慢均线交叉，是常见趋势跟随基线，用来验证历史数据、回测引擎和 paper runtime 接入。</span>
          <span>它们不是最终赚钱策略；是否有 Alpha 要靠回测、连续模拟盘样本、闭环交易、回撤和归因一起证明。</span>
        </div>
      </section>

      <section className="metric-grid paper-view-section paper-view-overview" aria-label="模拟盘指标">
        <div className="metric-card">
          <div className="metric-label">账户权益</div>
          <strong>{formatCurrency(account?.equity ?? 0)}</strong>
        </div>
        <div className="metric-card">
          <div className="metric-label">现金</div>
          <strong>{formatCurrency(account?.cash ?? 0)}</strong>
        </div>
        <div className="metric-card">
          <div className="metric-label">账户复盘期望</div>
          <strong>{formatCurrency(review?.expectancy ?? 0)}</strong>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-overview" aria-label="模拟盘控制台">
        <div className="panel-heading">
          <div>
            <h3>{account?.name ?? "默认模拟盘"}</h3>
            <p>默认 paper-only；净期望未稳定前不进入实盘。</p>
          </div>
          <button className="primary-action" type="button" onClick={handleDailyRun} disabled={isRunning || !canRunDaily}>
            <Play size={15} aria-hidden="true" />
            {dailyRunLabel}
          </button>
        </div>
        <p className="workspace-message" aria-live="polite">
          {message}
        </p>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-overview" aria-label="市场交易日">
        <div className="panel-heading">
          <div>
            <h3>
              <CalendarClock size={17} aria-hidden="true" />
              市场交易日
            </h3>
            <p>按 NYSE 日历确定复盘与调度口径。</p>
          </div>
          <span
            className={
              marketSession?.session_closed
                ? "status-pill success"
                : marketSession?.is_market_session
                  ? "status-pill warning"
                  : "status-pill neutral"
            }
          >
            {marketSession?.session_closed ? "已收盘" : marketSession?.is_market_session ? "未收盘" : "休市"}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>生效交易日</span>
            <strong>{marketSession?.trading_day ?? "未同步"}</strong>
          </div>
          <div>
            <span>市场日期</span>
            <strong>{marketSession?.market_date ?? "未同步"}</strong>
          </div>
          <div>
            <span>原因</span>
            <strong>{marketSession?.reason ?? "unknown"}</strong>
          </div>
          <div>
            <span>日历源</span>
            <strong>{marketSession?.calendar_provider ?? "unknown"}</strong>
          </div>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-overview" aria-label="今日简报">
        <div className="panel-heading">
          <div>
            <h3>今日简报</h3>
            <p>{dailyReport?.summary ?? "正在生成今日简报。"}</p>
          </div>
          <span className={dailyReport?.health_status === "ready" ? "status-pill success" : "status-pill warning"}>
            {dailyReport?.health_status ?? "blocked"}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>交易日</span>
            <strong>{dailyReport?.trading_day ?? "未同步"}</strong>
          </div>
          <div>
            <span>运行</span>
            <strong>{dailyReport?.run_state ?? "not_started"}</strong>
          </div>
          <div>
            <span>建议</span>
            <strong>{dailyReport?.recommended_action ?? "run_daily_paper_trading"}</strong>
          </div>
          <div>
            <span>可下单 / 订单</span>
            <strong>
              {dailyReport?.actionable_candidate_count ?? 0} / {dailyReport?.order_count ?? 0}
              <small>
                总候选 {dailyReport?.candidate_count ?? 0} · 过滤{" "}
                {dailyReport?.dismissed_candidate_count ?? 0}
              </small>
            </strong>
          </div>
          <div>
            <span>权益</span>
            <strong>{formatCurrency(dailyReport?.account_equity ?? 0)}</strong>
          </div>
          <div>
            <span>今日 PnL</span>
            <strong>
              {formatCurrency(dailyReport?.daily_pnl ?? 0)} · {percentFormatter.format(dailyReport?.daily_return ?? 0)}
            </strong>
          </div>
          <div>
            <span>Alpha</span>
            <strong>{dailyReport?.alpha_ready ? "已达标" : "未达标"}</strong>
          </div>
          <div>
            <span>有效采样</span>
            <strong>
              {formatTimestamp(dailyReport?.scheduler_next_actionable_run_at, "未计划")}
              <small>{dailyReport?.scheduler_next_actionable_trading_day ?? "无交易日"}</small>
            </strong>
          </div>
          <div>
            <span>Alpha 剩余</span>
            <strong>
              {dailyReport?.estimated_sessions_to_alpha_ready === null ||
              dailyReport?.estimated_sessions_to_alpha_ready === undefined
                ? "未知"
                : `${dailyReport.estimated_sessions_to_alpha_ready} 次`}
              <small>{dailyReport?.limiting_alpha_gate ?? "无门禁"}</small>
            </strong>
          </div>
        </div>
        <div className="import-result">
          <strong>
            策略Alpha期望 {formatCurrency(dailyReport?.latest_expectancy ?? 0)} · 连续正期望{" "}
            {dailyReport?.consecutive_positive_expectancy_days ?? 0} 天
          </strong>
          <p>
            已实现 {formatCurrency(dailyReport?.realized_pnl ?? 0)} · 未实现{" "}
            {formatCurrency(dailyReport?.unrealized_pnl ?? 0)} · 事件链{" "}
            {dailyReport?.event_ledger_ready ? "可回放" : "缺失"}
          </p>
          <p>
            下次 cron {formatTimestamp(dailyReport?.scheduler_next_run_at, "未计划")} ·{" "}
            {dailyReport?.scheduler_next_run_will_execute ? "将执行" : "会守门"} ·{" "}
            {dailyReport?.scheduler_next_run_execution_gate ?? "未知"}
          </p>
          <p>
            门禁缺口{" "}
            {(dailyReport?.open_alpha_gates ?? [])
              .map(
                (item) =>
                  `${item.label} ${formatNumber(item.current)} / ${formatNumber(item.required)}，还差 ${formatNumber(
                    item.remaining
                  )}${item.unit}`
              )
              .join("；") || "无"}
          </p>
          <p>
            退出观察{" "}
            {(dailyReport?.exit_watchlist ?? [])
              .slice(0, 5)
              .map(
                (item) =>
                  `${item.ticker} ${exitTriggerLabel(item.trigger)} ${percentFormatter.format(
                    item.return_pct
                  )} · 下次 ${formatNumber(item.next_exit_quantity)}`
              )
              .join("；") || "无"}
          </p>
          <p>阻断 {(dailyReport?.alpha_blockers ?? []).join(" / ") || "无"}</p>
          <p>数据警告 {(dailyReport?.data_quality_warnings ?? []).map(dataQualityWarningLabel).join(" / ") || "无"}</p>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-trading" aria-label="多日模拟">
        <div className="panel-heading">
          <div>
            <h3>多日模拟</h3>
            <p>{simulationResult?.summary ?? "使用推荐默认场景加速收集纸面交易样本。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={simulationResult?.alpha_ready ? "status-pill success" : "status-pill neutral"}>
              {simulationResult?.alpha_ready ? "Alpha 达标" : "Lab"}
            </span>
            <button className="ghost-action" type="button" onClick={handleSimulation} disabled={isSimulating}>
              <Play size={14} aria-hidden="true" />
              {simulationRunLabel}
            </button>
          </div>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>完成</span>
            <strong>
              {simulationResult?.days_completed ?? 0} / {simulationResult?.days_requested ?? 5}
            </strong>
          </div>
          <div>
            <span>正期望</span>
            <strong>{simulationResult?.consecutive_positive_expectancy_days ?? 0} 天</strong>
          </div>
          <div>
            <span>最新期望</span>
            <strong>{formatCurrency(simulationResult?.latest_expectancy ?? 0)}</strong>
          </div>
          <div>
            <span>平均期望</span>
            <strong>{formatCurrency(simulationResult?.average_expectancy ?? 0)}</strong>
          </div>
          <div>
            <span>事件</span>
            <strong>{simulationResult?.event_chain_count ?? 0}</strong>
          </div>
          <div>
            <span>跳过</span>
            <strong>{simulationResult?.days_skipped ?? 0}</strong>
          </div>
        </div>
        <div className="import-result">
          <strong>
            场景 {simulationResult?.scenario ?? "bullish"} · 起始日 {simulationResult?.start_date ?? "待运行"}
          </strong>
          <p>阻断 {(simulationResult?.blockers ?? []).join(" / ") || "无"}</p>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-operations" aria-label="运行健康">
        <div className="panel-heading">
          <div>
            <h3>运行健康</h3>
            <p>{operations?.summary ?? "正在读取每日运行健康。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={operations?.health_status === "ready" ? "status-pill success" : "status-pill warning"}>
              {operations?.health_status ?? "blocked"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleQuarantineLegacyRuns}
              disabled={isQuarantining || !hasLegacyManualFutureRuns}
            >
              <Wrench size={14} aria-hidden="true" />
              {isQuarantining ? "标记中" : "标记旧运行"}
            </button>
          </div>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>交易日</span>
            <strong>{operations?.trading_day ?? "未同步"}</strong>
          </div>
          <div>
            <span>今日状态</span>
            <strong>{operations?.run_state ?? "not_started"}</strong>
          </div>
          <div>
            <span>建议动作</span>
            <strong>{operations?.recommended_action ?? "run_daily_paper_trading"}</strong>
          </div>
          <div>
            <span>调度决策</span>
            <strong>
              {operations?.latest_scheduler_decision
                ? `${operations.latest_scheduler_decision} · ${
                    operations.latest_scheduler_decision_trading_day ?? "无交易日"
                  }`
                : "未记录"}
            </strong>
          </div>
        </div>
        <div className="import-result">
          <strong>{operations?.event_ledger_ready ? "事件链可回放" : "事件链缺失"}</strong>
          <p>
            事件 {operations?.latest_run_event_count ?? 0} · 可重跑{" "}
            {operations?.can_retry_today ? "是" : "否"} · 最新错误 {operations?.latest_error ?? "无"}
          </p>
          {operations?.latest_scheduler_decision ? (
            <p>
              调度 {formatTimestamp(operations.latest_scheduler_decision_at, "未同步")} · 原因{" "}
              {operations.latest_scheduler_decision_reason ?? "未知"} ·{" "}
              {operations.latest_scheduler_decision_summary ?? "无摘要"}
            </p>
          ) : null}
          <p>阻断 {(operations?.blockers ?? []).map(operationBlockerLabel).join(" / ") || "无"}</p>
          {(operations?.data_quality_warnings ?? []).length ? (
            <p>
              数据质量 {(operations?.data_quality_warnings ?? []).map(dataQualityWarningLabel).join(" / ")} ·{" "}
              数量 {operations?.legacy_manual_future_run_count ?? 0} · 最新{" "}
              {operations?.latest_legacy_manual_future_trading_day ?? "无"}
            </p>
          ) : null}
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-operations" aria-label="稳定趋势">
        <div className="panel-heading">
          <div>
            <h3>稳定趋势</h3>
            <p>{operationsHistory?.summary ?? "正在读取近几次模拟运行趋势。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={operationsHistory?.latest_health_status === "ready" ? "status-pill success" : "status-pill warning"}>
              {operationsHistory?.latest_health_status ?? "blocked"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleRepairLedger}
              disabled={isRepairing || !hasRepairableLedger}
            >
              <Wrench size={14} aria-hidden="true" />
              {isRepairing ? "修复中" : "修复事件链"}
            </button>
          </div>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>完成率</span>
            <strong>{percentFormatter.format(operationsHistory?.completion_rate ?? 0)}</strong>
          </div>
          <div>
            <span>回放率</span>
            <strong>{percentFormatter.format(operationsHistory?.replay_rate ?? 0)}</strong>
          </div>
          <div>
            <span>样本窗口</span>
            <strong>{operationsHistory?.window_size ?? 0} 次</strong>
          </div>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>阻断</span>
            <strong>{operationsHistory?.blocked_days ?? 0}</strong>
          </div>
          <div>
            <span>失败</span>
            <strong>{operationsHistory?.failed_days ?? 0}</strong>
          </div>
          <div>
            <span>已复盘</span>
            <strong>{operationsHistory?.review_days ?? 0}</strong>
          </div>
        </div>
        {repairResult ? (
          <div className="import-result">
            <strong>{repairResult.summary}</strong>
            <p>
              扫描 {repairResult.scanned_runs} · 修复 {repairResult.repaired_runs} · 跳过 {repairResult.skipped_runs}
            </p>
          </div>
        ) : null}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">交易日</th>
                <th scope="col">健康</th>
                <th scope="col">状态</th>
                <th className="numeric" scope="col">
                  事件
                </th>
                <th scope="col">阻断</th>
              </tr>
            </thead>
            <tbody>
              {(operationsHistory?.items ?? []).map((item) => (
                <tr key={item.run_id}>
                  <td>{item.trading_day}</td>
                  <td>
                    <span className={`state-token run-${item.health_status}`}>{item.health_status}</span>
                  </td>
                  <td>{item.status}</td>
                  <td className="numeric">{item.event_count}</td>
                  <td>{item.blockers.map(operationBlockerLabel).join(" / ") || "无"}</td>
                </tr>
              ))}
              {!(operationsHistory?.items ?? []).length ? (
                <tr>
                  <td colSpan={5}>暂无稳定趋势样本。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="净期望趋势">
        <div className="panel-heading">
          <div>
            <h3>净期望趋势</h3>
            <p>{reviewTrend?.summary ?? "正在读取复盘趋势。"}</p>
          </div>
          <span className={reviewTrend?.latest_expectancy && reviewTrend.latest_expectancy > 0 ? "status-pill success" : "status-pill warning"}>
            {readinessLabel(reviewTrend?.latest_readiness)}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>样本数</span>
            <strong>{reviewTrend?.sample_size ?? 0}</strong>
          </div>
          <div>
            <span>连续正期望</span>
            <strong>{reviewTrend?.consecutive_positive_expectancy_days ?? 0} 天</strong>
          </div>
          <div>
            <span>正期望天数</span>
            <strong>{reviewTrend?.positive_expectancy_days ?? 0}</strong>
          </div>
          <div>
            <span>最新期望</span>
            <strong>{formatCurrency(reviewTrend?.latest_expectancy ?? 0)}</strong>
          </div>
          <div>
            <span>平均期望</span>
            <strong>{formatCurrency(reviewTrend?.average_expectancy ?? 0)}</strong>
          </div>
          <div>
            <span>累计 PnL</span>
            <strong>{formatCurrency((reviewTrend?.total_realized_pnl ?? 0) + (reviewTrend?.total_unrealized_pnl ?? 0))}</strong>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">交易日</th>
                <th className="numeric" scope="col">
                  权益
                </th>
                <th className="numeric" scope="col">
                  日 PnL
                </th>
                <th className="numeric" scope="col">
                  日收益
                </th>
                <th className="numeric" scope="col">
                  期望
                </th>
                <th className="numeric" scope="col">
                  胜率
                </th>
                <th scope="col">状态</th>
              </tr>
            </thead>
            <tbody>
              {(reviewTrend?.items ?? []).map((item) => (
                <tr key={item.trading_day}>
                  <td>{item.trading_day}</td>
                  <td className="numeric">{formatCurrency(item.equity)}</td>
                  <td className="numeric">{formatCurrency(item.daily_pnl)}</td>
                  <td className="numeric">{percentFormatter.format(item.daily_return)}</td>
                  <td className="numeric">{formatCurrency(item.expectancy)}</td>
                  <td className="numeric">{percentFormatter.format(item.win_rate)}</td>
                  <td>{readinessLabel(item.readiness)}</td>
                </tr>
              ))}
              {!(reviewTrend?.items ?? []).length ? (
                <tr>
                  <td colSpan={7}>暂无复盘样本。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-trading" aria-label="执行诊断">
        <div className="panel-heading">
          <div>
            <h3>执行诊断</h3>
            <p>{executionDiagnostics?.summary ?? "正在读取执行诊断。"}</p>
          </div>
          <span className={executionDiagnostics?.rejected_order_count ? "status-pill warning" : "status-pill success"}>
            {executionDiagnostics?.latest_rejection_code ?? "执行正常"}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>订单</span>
            <strong>{executionDiagnostics?.order_count ?? 0}</strong>
          </div>
          <div>
            <span>成交率</span>
            <strong>{percentFormatter.format(executionDiagnostics?.fill_rate ?? 0)}</strong>
          </div>
          <div>
            <span>拒单率</span>
            <strong>{percentFormatter.format(executionDiagnostics?.rejection_rate ?? 0)}</strong>
          </div>
          <div>
            <span>闭环交易</span>
            <strong>{executionDiagnostics?.closed_trade_count ?? 0}</strong>
          </div>
          <div>
            <span>已实现 PnL</span>
            <strong>{formatCurrency(executionDiagnostics?.realized_pnl ?? 0)}</strong>
          </div>
          <div>
            <span>日限拒单</span>
            <strong>
              {executionDiagnostics?.max_daily_order_rejections ?? 0}
              <small>
                买 {executionDiagnostics?.max_daily_order_buy_rejections ?? 0} / 卖{" "}
                {executionDiagnostics?.max_daily_order_sell_rejections ?? 0}
              </small>
            </strong>
          </div>
        </div>
        <div className="import-result">
          <strong>
            filled {executionDiagnostics?.filled_order_count ?? 0} · rejected{" "}
            {executionDiagnostics?.rejected_order_count ?? 0} · sell {executionDiagnostics?.sell_order_count ?? 0}
          </strong>
          <p>
            拒单原因{" "}
            {(executionDiagnostics?.rejection_reasons ?? [])
              .map((item) => `${item.risk_code} ${item.count}`)
              .join(" / ") || "无"}
          </p>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="Alpha 门禁">
        <div className="panel-heading">
          <div>
            <h3>Alpha 门禁</h3>
            <p>{alphaGateProgress?.summary ?? "正在读取 Alpha 门禁进度。"}</p>
          </div>
          <span className={alphaGateProgress?.alpha_ready ? "status-pill success" : "status-pill warning"}>
            {alphaGateProgress?.validation_level ?? "collecting"}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>通过</span>
            <strong>
              {alphaGateProgress?.passed_gates ?? 0} / {alphaGateProgress?.total_gates ?? 0}
            </strong>
          </div>
          {(alphaGateProgress?.items ?? []).slice(0, 5).map((item) => (
            <div key={item.gate}>
              <span>{item.label}</span>
              <strong>
                {formatNumber(item.current)} / {formatNumber(item.required)} {item.unit}
              </strong>
            </div>
          ))}
        </div>
        <div className="import-result">
          <strong>{alphaGateProgress?.alpha_ready ? "门禁已通过" : "继续收集样本"}</strong>
          <p>
            剩余{" "}
            {(alphaGateProgress?.items ?? [])
              .filter((item) => !item.passed)
              .map((item) => `${item.label} ${formatNumber(item.remaining)} ${item.unit}`)
              .join(" / ") || "无"}
          </p>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="Alpha 预测">
        <div className="panel-heading">
          <div>
            <h3>Alpha 预测</h3>
            <p>{alphaForecast?.summary ?? "正在预测 Alpha 验证进度。"}</p>
          </div>
          <span className={alphaForecast?.alpha_ready ? "status-pill success" : "status-pill neutral"}>
            {alphaForecast?.status ?? "loading"}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>预计还需</span>
            <strong>
              {alphaForecast?.estimated_sessions_to_alpha_ready === null ||
              alphaForecast?.estimated_sessions_to_alpha_ready === undefined
                ? "未知"
                : `${alphaForecast.estimated_sessions_to_alpha_ready} 次`}
            </strong>
          </div>
          <div>
            <span>限制门禁</span>
            <strong>{alphaForecast?.limiting_gate ?? "无"}</strong>
          </div>
          {(alphaForecast?.items ?? [])
            .filter((item) => !item.passed)
            .slice(0, 4)
            .map((item) => (
              <div key={item.gate}>
                <span>{item.label}</span>
                <strong>
                  {item.estimated_sessions === null ? "未知" : `${item.estimated_sessions} 次`} · 剩余{" "}
                  {formatNumber(item.remaining)} {item.unit}
                </strong>
              </div>
            ))}
        </div>
        <div className="import-result">
          <strong>{alphaForecast?.alpha_ready ? "已满足模拟盘 Alpha 门禁" : "继续用模拟盘收集证据"}</strong>
          <p>
            {(alphaForecast?.items ?? [])
              .filter((item) => !item.passed)
              .map((item) => `${item.label}: ${item.reason}`)
              .join(" / ") || "无阻断"}
          </p>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-overview" aria-label="行动计划">
        <div className="panel-heading">
          <div>
            <h3>行动计划</h3>
            <p>{actionPlan?.summary ?? "正在生成行动计划。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className="status-pill neutral">{actionPlan?.primary_action ?? "loading"}</span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleExecutePrimaryAction}
              disabled={isExecutingPrimaryAction || !actionPlan}
            >
              <Play size={14} aria-hidden="true" />
              {primaryActionLabel}
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">优先级</th>
                <th scope="col">动作</th>
                <th scope="col">说明</th>
              </tr>
            </thead>
            <tbody>
              {(actionPlan?.items ?? []).map((item) => (
                <tr key={`${item.priority}-${item.action_code}`}>
                  <td>{item.priority}</td>
                  <td>
                    <strong>{item.title}</strong>
                    <p className="table-note">{item.action_code}</p>
                  </td>
                  <td>
                    {item.detail}
                    {item.projected_gate_impacts?.length ? (
                      <div className="action-impact-list">
                        {item.projected_gate_impacts.map((impact) => (
                          <span key={`${item.action_code}-${impact.gate}`}>
                            {impact.label} +{formatNumber(impact.projected_increment)}
                            {impact.unit}，剩余 {formatNumber(impact.current_remaining)} 到{" "}
                            {formatNumber(impact.projected_remaining)}
                            {impact.unit}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <p className="table-note">{item.evidence.join(" / ") || "无"}</p>
                  </td>
                </tr>
              ))}
              {!(actionPlan?.items ?? []).length ? (
                <tr>
                  <td colSpan={3}>暂无行动项。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="策略复盘记录">
        <div className="panel-heading">
          <div>
            <h3>策略复盘记录</h3>
            <p>{strategyReviews?.summary ?? "正在读取策略复盘记录。"}</p>
          </div>
          <span className={(strategyReviews?.review_count ?? 0) > 0 ? "status-pill warning" : "status-pill success"}>
            {(strategyReviews?.review_count ?? 0) > 0 ? "需复盘" : "无待处理"}
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">时间</th>
                <th scope="col">动作</th>
                <th scope="col">状态</th>
                <th scope="col">标的</th>
                <th scope="col">证据</th>
              </tr>
            </thead>
            <tbody>
              {(strategyReviews?.items ?? []).slice(0, 5).map((item) => (
                <tr key={item.event_id}>
                  <td>{formatTimestamp(item.created_at, "未记录")}</td>
                  <td>
                    <strong>{item.title}</strong>
                    <p className="table-note">{item.action_code}</p>
                  </td>
                  <td>{item.review_status}</td>
                  <td>{item.inverted_tickers.join(", ") || "未知"}</td>
                  <td>
                    {item.detail}
                    <p className="table-note">{item.evidence.join(" / ") || "无"}</p>
                  </td>
                </tr>
              ))}
              {!(strategyReviews?.items ?? []).length ? (
                <tr>
                  <td colSpan={5}>暂无策略复盘审计记录。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="风险配置">
        <div className="panel-heading">
          <div>
            <h3>风险配置</h3>
            <p>{riskProfile?.summary ?? "正在读取纸面风控配置。"}</p>
          </div>
          <span className="status-pill neutral">{riskProfile?.risk_engine ?? "Trading Core RiskEngine"}</span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>单笔上限</span>
            <strong>{formatCurrency(riskProfile?.max_order_notional ?? 0)}</strong>
          </div>
          <div>
            <span>仓位权重</span>
            <strong>{percentFormatter.format(riskProfile?.max_position_weight ?? 0)}</strong>
          </div>
          <div>
            <span>日订单</span>
            <strong>{riskProfile?.max_daily_orders ?? 0} 笔</strong>
          </div>
          <div>
            <span>止盈</span>
            <strong>{percentFormatter.format(riskProfile?.exit_take_profit_pct ?? 0)}</strong>
          </div>
          <div>
            <span>止损</span>
            <strong>{percentFormatter.format(riskProfile?.exit_stop_loss_pct ?? 0)}</strong>
          </div>
          <div>
            <span>模式</span>
            <strong>paper-only</strong>
          </div>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="风险限额评审">
        <div className="panel-heading">
          <div>
            <h3>风险限额评审</h3>
            <p>{riskLimitReview?.summary ?? "正在生成风险限额评审。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={riskLimitReview?.status === "review_required" ? "status-pill warning" : "status-pill success"}>
              {riskLimitReview?.status ?? "loading"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleApplyRiskLimitRecommendation}
              disabled={isApplyingRiskLimit || !canApplyRiskLimitRecommendation}
            >
              <Wrench size={14} aria-hidden="true" />
              {isApplyingRiskLimit ? "应用中" : "应用 Paper 建议"}
            </button>
          </div>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>Paper 建议</span>
            <strong>
              {riskLimitReview?.current_max_daily_orders ?? 0} →{" "}
              {riskLimitReview?.recommended_paper_max_daily_orders ?? 0}
            </strong>
          </div>
          <div>
            <span>Live</span>
            <strong>{riskLimitReview?.live_change_allowed ? "需审批" : "Live 不变"}</strong>
          </div>
          <div>
            <span>日限拒单</span>
            <strong>
              {riskLimitReview?.max_daily_order_rejections ?? 0}
              <small>
                买 {riskLimitReview?.max_daily_order_buy_rejections ?? 0} / 卖{" "}
                {riskLimitReview?.max_daily_order_sell_rejections ?? 0}
              </small>
            </strong>
          </div>
          <div>
            <span>成交 / 闭环</span>
            <strong>
              {riskLimitReview?.filled_order_count ?? 0} / {riskLimitReview?.closed_trade_count ?? 0}
            </strong>
          </div>
        </div>
        <div className="import-result">
          <strong>{riskLimitReview?.sample_collection_blocked ? "样本收集受限" : "维持当前限额"}</strong>
          <p>阻断 {(riskLimitReview?.blockers ?? []).join(" / ") || "无"}</p>
        </div>
        {riskLimitApply ? (
          <div className="import-result">
            <strong>{riskLimitApply.summary}</strong>
            <p>
              Paper {riskLimitApply.previous_max_daily_orders} → {riskLimitApply.applied_max_daily_orders} ·{" "}
              {riskLimitApply.live_change_allowed ? "Live 需审批" : "Live 不变"} ·{" "}
              {riskLimitApply.audit_event_created ? "审计已记录" : "无审计事件"}
            </p>
          </div>
        ) : null}
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-operations" aria-label="每日调度">
        <div className="panel-heading">
          <div>
            <h3>每日调度</h3>
            <p>APScheduler 只在 NYSE 交易日收盘后触发同一条模拟盘链路。</p>
          </div>
          <div className="panel-heading-actions">
            <span className={scheduler?.can_run_now ? "status-pill success" : "status-pill neutral"}>
              {schedulerGate}
            </span>
            <span className={scheduler?.running ? "status-pill success" : "status-pill neutral"}>{schedulerLabel}</span>
          </div>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>CRON</span>
            <strong>{scheduler?.cron ?? "30 6 * * *"}</strong>
          </div>
          <div>
            <span>时区</span>
            <strong>{scheduler?.timezone ?? "Asia/Shanghai"}</strong>
          </div>
          <div>
            <span>任务数</span>
            <strong>{scheduler?.job_count ?? 0}</strong>
          </div>
          <div>
            <span>Job</span>
            <strong>{scheduler?.job_id ?? "paper_trading_daily_run"}</strong>
          </div>
          <div>
            <span>下次运行</span>
            <strong>{formatTimestamp(scheduler?.next_run_at, "未计划")}</strong>
          </div>
          <div>
            <span>下次采样</span>
            <strong>{nextRunLabel}</strong>
          </div>
          <div>
            <span>下次交易日</span>
            <strong>{scheduler?.next_run_trading_day ?? "未同步"}</strong>
          </div>
          <div>
            <span>下次有效采样</span>
            <strong>
              {formatTimestamp(scheduler?.next_actionable_run_at, "未找到")}
              <small>{scheduler?.next_actionable_trading_day ?? "无交易日"}</small>
            </strong>
          </div>
          <div>
            <span>检查时间</span>
            <strong>{formatTimestamp(scheduler?.last_checked_at, "未同步")}</strong>
          </div>
          <div>
            <span>调度交易日</span>
            <strong>{scheduler?.trading_day ?? "未同步"}</strong>
          </div>
          <div>
            <span>守门原因</span>
            <strong>{scheduler?.gate_reason ?? "unknown"}</strong>
          </div>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-operations" aria-label="运行账本">
        <div className="panel-heading">
          <div>
            <h3>运行账本</h3>
            <p>记录每日模拟是否执行、跳过或失败</p>
          </div>
          <span className="status-pill neutral">{runs.length} 条记录</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">交易日</th>
                <th scope="col">触发</th>
                <th scope="col">状态</th>
                <th className="numeric" scope="col">
                  候选
                </th>
                <th className="numeric" scope="col">
                  订单
                </th>
                <th className="numeric" scope="col">
                  持仓
                </th>
                <th scope="col">结果</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.trading_day}</td>
                  <td>{run.trigger}</td>
                  <td>
                    <span className={`state-token run-${run.status}`}>{run.status}</span>
                  </td>
                  <td className="numeric">{run.candidates_count}</td>
                  <td className="numeric">订单 {run.orders_count}</td>
                  <td className="numeric">{run.positions_count}</td>
                  <td>
                    <strong>{run.error_message ?? (run.review_id ? "已关联复盘" : "未生成复盘")}</strong>
                    <p className="table-note">{run.finished_at ?? run.started_at}</p>
                  </td>
                </tr>
              ))}
              {!runs.length ? (
                <tr>
                  <td colSpan={7}>暂无运行记录。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-events" id="paper-ledger" aria-label="事件账本">
        <div className="panel-heading">
          <div>
            <h3>事件账本</h3>
            <p>{eventLedger?.summary ?? "正在读取 CoreEventLog。"}</p>
          </div>
          <span className={ledgerIntegrityReady ? "status-pill success" : "status-pill warning"}>
            {ledgerIntegrityReady ? "完整" : "需修复"}
          </span>
        </div>
        <div className="scheduler-grid">
          <div>
            <span>总事件</span>
            <strong>{eventLedger?.total_event_count ?? 0}</strong>
          </div>
          <div>
            <span>最新运行事件</span>
            <strong>{eventLedger?.latest_run_event_count ?? 0}</strong>
          </div>
          <div>
            <span>Correlation</span>
            <strong>{eventLedger?.latest_correlation_count ?? 0}</strong>
          </div>
          <div>
            <span>完整链</span>
            <strong>{eventLedger?.complete_order_chain_count ?? 0}</strong>
          </div>
          <div>
            <span>断链</span>
            <strong>{eventLedger?.broken_chain_count ?? 0}</strong>
          </div>
          <div>
            <span>链路率</span>
            <strong>{Math.round((eventLedger?.traceability_ratio ?? 0) * 100)}%</strong>
          </div>
          <div>
            <span>完整性</span>
            <strong>{ledgerIntegrityReady ? "通过" : "阻断"}</strong>
          </div>
        </div>
        <div className="import-result">
          <strong>{replayChain ? `${replayChain.ticker ?? "UNKNOWN"} · ${replayChain.terminal_state ?? "open"}` : "暂无可回放链路"}</strong>
          <p>
            {topicSummary} · 状态序列{" "}
            {replayChain?.order_states.length ? replayChain.order_states.join(" → ") : "未记录"}
          </p>
          <p>账本警告 {ledgerWarnings.join(" / ") || "无"}</p>
          <p>链路警告 {chainWarnings.join(" / ") || "无"}</p>
        </div>
        {tradeExplanation ? (
          <div className="import-result">
            <strong>候选解释</strong>
            <p>
              {tradeExplanation.decision ?? "decision_unknown"} ·{" "}
              {tradeExplanation.strategy_id ?? "strategy_unknown"}
            </p>
            {tradeExplanation.candidate_id ? <p>候选 ID {tradeExplanation.candidate_id}</p> : null}
            <p>{tradeExplanation.explanation ?? "暂无解释摘要"}</p>
            {candidateRankingScore ? <p>排序分数 {candidateRankingScore}</p> : null}
            <p>证据 {tradeExplanation.evidence.join(" / ") || "无"}</p>
            <p>回测收益 {typeof backtestReturn === "string" || typeof backtestReturn === "number" ? backtestReturn : "n/a"}</p>
          </div>
        ) : null}
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-trading" id="paper-candidates" aria-label="候选池">
        <div className="panel-heading">
          <div>
            <h3>候选池</h3>
            <p>按证据、报价可用性和组合分散度排序</p>
          </div>
          <span className="status-pill neutral">{candidates.length} 个候选</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">策略</th>
                <th scope="col">动作</th>
                <th className="numeric" scope="col">
                  置信度
                </th>
                <th className="numeric" scope="col">
                  数量
                </th>
                <th scope="col">原因</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => {
                const actionDisabled = orderingTicker === candidate.ticker || candidate.status !== "proposed";
                const actionLabel =
                  candidate.status === "ordered"
                    ? `已模拟 ${candidate.ticker}`
                    : candidate.status === "dismissed"
                      ? `已排除 ${candidate.ticker}`
                      : `模拟买入 ${candidate.ticker}`;
                return (
                  <tr key={candidate.id}>
                    <td>
                      <span className="ticker-chip">{candidate.ticker}</span>
                    </td>
                    <td>
                      <span className="status-pill neutral">{candidate.strategy_id}</span>
                    </td>
                    <td>{candidate.action}</td>
                    <td className="numeric">{percentFormatter.format(candidate.confidence)}</td>
                    <td className="numeric">{formatNumber(candidate.proposed_quantity)}</td>
                    <td>
                      <strong>{candidate.evidence_summary}</strong>
                      <p className="table-note">{candidate.risk_notes}</p>
                    </td>
                    <td>
                      <button
                        className="ghost-action"
                        type="button"
                        onClick={() => handleBuy(candidate)}
                        disabled={actionDisabled}
                      >
                        <ShoppingCart size={14} aria-hidden="true" />
                        {actionLabel}
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!candidates.length ? (
                <tr>
                  <td colSpan={7}>点击运行今日模拟生成候选。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-trading" aria-label="模拟订单">
        <div className="panel-heading">
          <div>
            <h3>模拟订单</h3>
            <p>同步市价模拟成交，不触达券商接口</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">方向</th>
                <th className="numeric" scope="col">
                  数量
                </th>
                <th className="numeric" scope="col">
                  成交价
                </th>
                <th scope="col">状态</th>
                <th scope="col">风控</th>
                <th scope="col">核心状态机</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.ticker}</td>
                  <td>{order.side}</td>
                  <td className="numeric">{formatNumber(order.quantity)}</td>
                  <td className="numeric">{order.fill_price === null ? "-" : formatCurrency(order.fill_price)}</td>
                  <td>{order.status}</td>
                  <td>
                    <strong>{order.risk_status ?? "legacy"}</strong>
                    <p className="table-note">{order.risk_code ?? "未记录"}</p>
                  </td>
                  <td>
                    <div className="state-chain">
                      {order.state_history.length ? (
                        order.state_history.map((item) => (
                          <span className="state-token" key={`${order.id}-${item.state}-${item.recorded_at}`}>
                            {item.state}
                          </span>
                        ))
                      ) : (
                        <span className="state-token muted">未记录</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {!orders.length ? (
                <tr>
                  <td colSpan={7}>暂无模拟订单。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-trading" aria-label="模拟持仓">
        <div className="panel-heading">
          <div>
            <h3>模拟持仓</h3>
            <p>按最新报价估算市值和未实现 PnL</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th className="numeric" scope="col">
                  数量
                </th>
                <th className="numeric" scope="col">
                  平均成本
                </th>
                <th className="numeric" scope="col">
                  市值
                </th>
                <th className="numeric" scope="col">
                  未实现 PnL
                </th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.id}>
                  <td>{position.ticker}</td>
                  <td className="numeric">{formatNumber(position.quantity)}</td>
                  <td className="numeric">{formatCurrency(position.average_cost)}</td>
                  <td className="numeric">{formatCurrency(position.market_value)}</td>
                  <td className="numeric">{formatCurrency(position.unrealized_pnl)}</td>
                </tr>
              ))}
              {!positions.length ? (
                <tr>
                  <td colSpan={5}>暂无模拟持仓。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel paper-view-section paper-view-risk" aria-label="复盘策略">
        <div className="panel-heading">
          <div>
            <h3>复盘策略</h3>
            <p>{review ? `${review.trading_day} · ${readinessLabel(review.readiness)}` : "尚未生成复盘"}</p>
          </div>
        </div>
        <div className="import-result">
          <strong>{review?.notes ?? "运行今日模拟后生成复盘。"}</strong>
          <p>
            已关闭交易 {review?.trade_count ?? 0} 笔 · 胜率 {percentFormatter.format(review?.win_rate ?? 0)} · 已实现 PnL{" "}
            {formatCurrency(account?.realized_pnl ?? 0)} · 未实现 PnL {formatCurrency(account?.unrealized_pnl ?? 0)}
          </p>
        </div>
      </section>
    </div>
  );
}
