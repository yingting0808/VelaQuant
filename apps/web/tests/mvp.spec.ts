import { expect, test, type Page } from "@playwright/test";
import {
  runStrategyBacktest,
  type AlphaGateProgressPayload,
  type AlphaValidationSnapshotHistoryPayload,
  type AlphaValidationSnapshotPayload,
  type AlphaValidationForecastPayload,
  type LiveSmallReviewPayload,
  type PaperActionPlanPayload,
  type PaperDailyReportPayload,
  type PaperEventLedgerPayload,
  type PaperExecutionDiagnosticsPayload,
  type PaperMarketEventsPayload,
  type PaperOperationsHistoryPayload,
  type PaperOperationsStatusPayload,
  type PaperRiskLimitApplyPayload,
  type PaperRiskLimitReviewPayload,
  type PaperRiskProfilePayload,
  type PaperReviewTrendPayload,
  type PaperSchedulerStatusPayload,
  type PaperSimulationPayload,
  type PaperTradingSummaryPayload,
  type PositionPayload,
  type RuntimeSettingsPayload,
  type RuntimeSettingsUpdatePayload,
  type ShadowDailyReportPayload,
  type ShadowObservationHealthPayload,
  type ShadowObservationPayload,
  type ShadowObservationSummaryPayload,
  type ShadowReviewPayload,
  type ShadowValidationPayload,
  type StrategyCompetitionSnapshotHistoryPayload,
  type StrategyCompetitionPayload,
  type StrategyLifecycleAuditPayload,
  type TradingSystemReadinessPayload
} from "../src/lib/client-api";

const movingAverageParameters = [
  { name: "symbol", label: "Ticker", kind: "ticker", default: "AAPL", required: true },
  { name: "start_date", label: "Start Date", kind: "date", default: "2020-01-01", required: true },
  { name: "end_date", label: "End Date", kind: "date", default: "2021-01-01", required: true },
  { name: "cash", label: "Initial Cash", kind: "number", default: "100000", min: 1000, max: 1000000000, required: true },
  { name: "fast_period", label: "Fast SMA", kind: "integer", default: "20", min: 2, max: 400, required: true },
  { name: "slow_period", label: "Slow SMA", kind: "integer", default: "50", min: 3, max: 600, required: true }
];

const paperMarketSession = {
  market_date: "2026-06-13",
  trading_day: "2026-06-12",
  is_market_session: false,
  session_closed: false,
  calendar_provider: "pandas_market_calendars",
  reason: "market_closed"
};

const paperSchedulerStatus: PaperSchedulerStatusPayload = {
  enabled: true,
  running: true,
  job_count: 1,
  job_id: "paper_trading_daily_run",
  cron: "30 6 * * *",
  timezone: "Asia/Shanghai",
  next_run_at: "2026-06-14T06:30:00+08:00",
  next_run_will_execute: false,
  next_run_execution_gate: "market_closed",
  next_run_trading_day: "2026-06-12",
  next_run_gate_reason: "market_closed",
  next_actionable_run_at: "2026-06-16T06:30:00+08:00",
  next_actionable_trading_day: "2026-06-15",
  next_actionable_execution_gate: "ready_to_run",
  next_actionable_gate_reason: "current_session_closed",
  last_checked_at: "2026-06-13T00:00:00Z",
  can_run_now: false,
  execution_gate: "market_closed",
  market_date: "2026-06-13",
  trading_day: "2026-06-12",
  is_market_session: false,
  session_closed: false,
  calendar_provider: "pandas_market_calendars",
  gate_reason: "market_closed"
};

async function gotoDashboard(page: Page) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
}

async function openAiAssistant(page: Page) {
  const expandButton = page.getByRole("button", { name: "展开 AI 助手" });
  if (await expandButton.isVisible()) {
    await expandButton.click();
  }
  await expect(page.getByRole("heading", { name: "AI 助手" })).toBeVisible();
}

test("dashboard renders portfolio, alerts, and AI sidecar", async ({ page }) => {
  await gotoDashboard(page);

  await expect(page).toHaveTitle("VelaQuant");
  await expect(page.getByRole("heading", { name: "VelaQuant" })).toBeVisible();
  await expect(page.getByText("星舵智投")).toBeVisible();
  await expect(page.getByRole("heading", { name: "主组合" })).toBeVisible();
  await expect(page.getByText("组合市值")).toBeVisible();
  await expect(page.getByRole("table").getByText("AAPL")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "市值" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "权重" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "事件预警" })).toBeVisible();
  await expect(page.getByText("AAPL 10-Q filed")).toBeVisible();
  await expect(page.getByRole("button", { name: "展开 AI 助手" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI 助手" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "识别组合风险" })).not.toBeVisible();
  const gridColumnCount = await page.locator(".app-shell").evaluate((element) =>
    getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length
  );
  expect(gridColumnCount).toBe(2);
});

test("navigation links route to module workspaces", async ({ page }) => {
  await page.route("**/api/mvp/watchlist", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        items: [
          {
            created_at: "2026-06-13T00:00:00Z",
            id: "watch-nvda",
            thesis: "AI 基础设施龙头 · 关注估值",
            ticker: "NVDA"
          }
        ]
      }
    });
  });

  await gotoDashboard(page);

  await page.getByRole("link", { name: "自选股" }).click();

  await expect(page).toHaveURL("/watchlist");
  await expect(page.getByRole("link", { name: "自选股" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("当前模块：自选股")).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "自选股" })).toBeVisible();
  await expect(page.getByRole("region", { name: "自选股工作区" }).getByText("NVDA", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "主组合" })).not.toBeVisible();
});

test("paper trading workbench runs daily loop and simulates a buy", async ({ page }) => {
  const baseSummary: PaperTradingSummaryPayload = {
    account: {
      id: "paper-account",
      name: "默认模拟盘",
      mode: "paper",
      starting_cash: 100000,
      cash: 100000,
      realized_pnl: 0,
      unrealized_pnl: 0,
      equity: 100000,
      updated_at: "2026-06-13T00:00:00Z"
    },
    candidates: [],
    orders: [],
    positions: [],
    latest_review: null
  };
  const candidate = {
    id: "paper-candidate-nvda",
    strategy_id: "deterministic_watchlist_v1",
    ticker: "NVDA",
    action: "buy",
    rank: 1,
    confidence: 0.9,
    thesis: "NVDA 候选买入：3 条证据支持继续跟踪 NVDA。",
    risk_notes: "模拟结果不能直接代表实盘。",
    evidence_summary: "3 条证据支持继续跟踪 NVDA",
    proposed_quantity: 40,
    status: "proposed",
    created_at: "2026-06-13T00:00:00Z"
  };
  const rejectedCandidate = {
    ...candidate,
    id: "paper-candidate-amzn",
    ticker: "AMZN",
    thesis: "AMZN 回测未通过，不进入模拟买入。",
    risk_notes: "回测风控：真实历史数据；收益未通过；Sharpe 0.03；回撤 17.20%；交易 8 笔；结论 reject。",
    evidence_summary: "7 条证据支持继续跟踪 AMZN；回测 收益 -1.46%，Sharpe 0.03，回撤 17.20%，交易 8 笔",
    proposed_quantity: 8,
    status: "dismissed"
  };
  const dailySummary: PaperTradingSummaryPayload = {
    ...baseSummary,
    candidates: [candidate, rejectedCandidate],
    latest_review: {
      id: "paper-review",
      trading_day: "2026-06-13",
      equity: 100000,
      cash: 100000,
      realized_pnl: 0,
      unrealized_pnl: 0,
      trade_count: 0,
      win_rate: 0,
      average_win: 0,
      average_loss: 0,
      expectancy: 0,
      readiness: "collecting",
      notes: "正在收集模拟盘样本。",
      created_at: "2026-06-13T00:00:00Z"
    }
  };
  const filledSummary: PaperTradingSummaryPayload = {
    ...dailySummary,
    account: { ...dailySummary.account, cash: 98000, equity: 100000 },
    orders: [
      {
        id: "paper-order-nvda",
        strategy_id: "deterministic_watchlist_v1",
        candidate_id: "paper-candidate-nvda",
        ticker: "NVDA",
        side: "buy",
        order_type: "market",
        quantity: 40,
        status: "filled",
        fill_price: 50,
        realized_pnl: 0,
        rejection_reason: null,
        core_order_id: "core-order-nvda",
        core_intent_id: "core-intent-nvda",
        risk_status: "approved",
        risk_code: "approved",
        risk_reason: "Risk engine approved intent.",
        state_history: [
          { state: "new", recorded_at: "2026-06-13T00:01:00Z", reason: "Order created." },
          { state: "validated", recorded_at: "2026-06-13T00:01:01Z", reason: "Intent passed execution payload validation." },
          { state: "risk_approved", recorded_at: "2026-06-13T00:01:02Z", reason: "Risk engine approved intent." },
          { state: "sent", recorded_at: "2026-06-13T00:01:03Z", reason: "Sent to mock execution adapter." },
          { state: "filled", recorded_at: "2026-06-13T00:01:04Z", reason: "Synchronously filled by mock execution adapter." }
        ],
        submitted_at: "2026-06-13T00:01:00Z",
        filled_at: "2026-06-13T00:01:00Z"
      }
    ],
    positions: [
      {
        id: "paper-position-nvda",
        ticker: "NVDA",
        quantity: 40,
        average_cost: 50,
        last_price: 50,
        market_value: 2000,
        unrealized_pnl: 0,
        realized_pnl: 0,
        updated_at: "2026-06-13T00:01:00Z"
      }
    ]
  };
  const emptyLedger: PaperEventLedgerPayload = {
    total_event_count: 0,
    latest_run_id: null,
    latest_run_status: null,
    latest_run_event_count: 0,
    latest_topic_counts: [],
    latest_correlation_count: 0,
    integrity_ready: false,
    integrity_warnings: ["missing_core_events"],
    traceable_chain_count: 0,
    complete_order_chain_count: 0,
    broken_chain_count: 0,
    traceability_ratio: 0,
    replay_ready: false,
    warnings: ["missing_core_events"],
    summary: "No paper runs found; event replay is not available.",
    latest_replay: null
  };
  const filledLedger: PaperEventLedgerPayload = {
    total_event_count: 9,
    latest_run_id: "paper-run-today",
    latest_run_status: "completed",
    latest_run_event_count: 9,
    latest_topic_counts: [
      { topic: "market_event", count: 1 },
      { topic: "order_state", count: 5 },
      { topic: "risk_decision", count: 1 },
      { topic: "strategy_input", count: 1 },
      { topic: "trade_explanation", count: 1 },
      { topic: "trade_intent", count: 1 }
    ],
    latest_correlation_count: 1,
    integrity_ready: true,
    integrity_warnings: [],
    traceable_chain_count: 1,
    complete_order_chain_count: 1,
    broken_chain_count: 0,
    traceability_ratio: 1,
    replay_ready: true,
    warnings: [],
    summary: "Latest paper run is completed with 9 replayable core events across 1 chains.",
    latest_replay: {
      run_id: "paper-run-today",
      event_count: 9,
      chain_count: 1,
      chains: [
        {
          correlation_id: "core-chain",
          ticker: "NVDA",
          topics: ["market_event", "strategy_input", "trade_intent", "trade_explanation", "risk_decision", "order_state"],
          order_states: ["new", "validated", "risk_approved", "sent", "filled"],
          terminal_state: "filled",
          event_count: 10,
          integrity_warnings: [],
          trade_explanation: {
            ticker: "NVDA",
            strategy_id: "deterministic_watchlist_v1",
            candidate_id: "paper-candidate-nvda",
            decision: "candidate",
            explanation: "NVDA promoted by real backtest evidence.",
            evidence: ["positive expectancy", "source=openbb_yfinance", "base_score=0.85", "final_score=1034.97"],
            backtest: {
              run_id: "bt-nvda",
              total_net_profit: "38.60%",
              sharpe_ratio: "1.42",
              drawdown: "-4.10%",
              total_trades: "12"
            }
          }
        }
      ]
    }
  };
  const paperMarketEvents: PaperMarketEventsPayload = {
    total_event_count: 1,
    filtered_event_count: 1,
    summary: "Market event center has 1 event.",
    events: [
      {
        event_id: "market-event-nvda",
        run_id: "paper-run-today",
        trading_day: "2026-06-13",
        published_at: "2026-06-13T00:01:00Z",
        correlation_id: "core-chain",
        ticker: "NVDA",
        strategy_id: "deterministic_watchlist_v1",
        event_type: "news",
        summary: "NVDA 3 条证据支持继续跟踪。",
        confidence: 0.9,
        impact_score: 0.72,
        source: "mock_provider",
        topics: ["market_event", "strategy_input", "trade_intent", "risk_decision", "order_state", "trade_explanation"],
        trade_intent_side: "buy",
        trade_intent_reason: "NVDA positive news event: 3 supporting evidence items.",
        risk_decision: "approved",
        risk_reason: "within paper risk limits",
        order_state: "filled",
        explanation: "NVDA promoted by real backtest evidence.",
        evidence: ["evidence_count=3", "source=mock_provider", "final_score=1034.97"],
        evidence_items: [
          {
            ticker: "NVDA",
            title: "NVDA provider evidence 1",
            summary: "Provider says NVDA has fixture evidence 1.",
            source: "mock_provider",
            source_url: "https://example.test/nvda-evidence",
            observed_at: "2026-06-13T00:00:00Z",
            form: null,
            filing_date: null,
            accession_number: null
          }
        ],
        chain_events: [
          {
            event_id: "market-event-nvda",
            topic: "market_event",
            sequence: 1,
            causation_id: null,
            payload: {
              ticker: "NVDA",
              event_type: "news",
              summary: "NVDA 3 条证据支持继续跟踪。",
              sentiment: "positive",
              confidence: 0.9,
              impact_score: 0.72,
              evidence_items: [
                {
                  ticker: "NVDA",
                  title: "NVDA provider evidence 1",
                  summary: "Provider says NVDA has fixture evidence 1.",
                  source: "mock_provider",
                  source_url: "https://example.test/nvda-evidence",
                  observed_at: "2026-06-13T00:00:00Z"
                }
              ],
              metadata: {
                strategy_id: "deterministic_watchlist_v1",
                source: "mock_provider",
                quote_price: 50,
                evidence_count: 3
              }
            }
          },
          {
            event_id: "strategy-input-nvda",
            topic: "strategy_input",
            sequence: 2,
            causation_id: "market-event-nvda",
            payload: {
              market_event: {
                ticker: "NVDA",
                summary: "NVDA 3 条证据支持继续跟踪。",
                evidence_items: [
                  {
                    ticker: "NVDA",
                    title: "NVDA provider evidence 1",
                    summary: "Provider says NVDA has fixture evidence 1.",
                    source: "mock_provider",
                    source_url: "https://example.test/nvda-evidence",
                    observed_at: "2026-06-13T00:00:00Z"
                  }
                ],
                metadata: {
                  source: "mock_provider"
                }
              },
              portfolio: {
                cash: 100000,
                equity: 100000,
                positions: []
              }
            }
          },
          {
            event_id: "intent-nvda",
            topic: "trade_intent",
            sequence: 3,
            causation_id: "strategy-input-nvda",
            payload: {
              ticker: "NVDA",
              side: "buy",
              notional: 2000,
              reason: "NVDA positive news event: 3 supporting evidence items."
            }
          },
          {
            event_id: "risk-nvda",
            topic: "risk_decision",
            sequence: 4,
            causation_id: "intent-nvda",
            payload: {
              ticker: "NVDA",
              status: "approved",
              code: "approved",
              reason: "within paper risk limits"
            }
          },
          {
            event_id: "order-nvda",
            topic: "order_state",
            sequence: 5,
            causation_id: "risk-nvda",
            payload: {
              ticker: "NVDA",
              state: "filled",
              quantity: 40,
              fill_price: 50
            }
          },
          {
            event_id: "explain-nvda",
            topic: "trade_explanation",
            sequence: 6,
            causation_id: "intent-nvda",
            payload: {
              ticker: "NVDA",
              strategy_id: "deterministic_watchlist_v1",
              decision: "candidate",
              explanation: "NVDA promoted by real backtest evidence.",
              evidence: ["evidence_count=3", "source=mock_provider", "final_score=1034.97"],
              evidence_items: [
                {
                  ticker: "NVDA",
                  title: "NVDA provider evidence 1",
                  summary: "Provider says NVDA has fixture evidence 1.",
                  source: "mock_provider",
                  source_url: "https://example.test/nvda-evidence",
                  observed_at: "2026-06-13T00:00:00Z"
                }
              ],
              backtest: {
                total_net_profit: "38.60%",
                sharpe_ratio: "1.42",
                total_trades: "12"
              }
            }
          }
        ]
      }
    ]
  };
  const blockedOperations = {
    trading_day: "2026-06-13",
    run_state: "not_started",
    health_status: "blocked",
    latest_run_id: null,
    latest_run_trading_day: null,
    latest_run_status: null,
    today_run_id: null,
    review_id: null,
    latest_error: null,
    can_retry_today: true,
    event_ledger_ready: false,
    latest_run_event_count: 0,
    legacy_manual_future_run_count: 0,
    latest_legacy_manual_future_trading_day: null,
    data_quality_warnings: [],
    latest_scheduler_decision: "failed",
    latest_scheduler_decision_at: "2026-06-13T06:30:00+08:00",
    latest_scheduler_decision_trading_day: "2026-06-12",
    latest_scheduler_decision_reason: "current_session_closed",
    latest_scheduler_decision_summary: "Scheduled paper trading failed: paper loop failed.",
    blockers: ["daily_run_missing"],
    recommended_action: "run_daily_paper_trading",
    summary: "Daily paper pipeline has not run for this trading day."
  };
  const readyOperations = {
    ...blockedOperations,
    health_status: "ready",
    event_ledger_ready: true,
    latest_run_event_count: 8,
    blockers: [],
    recommended_action: "hold_until_next_session",
    summary: "Daily paper pipeline is complete for the trading day."
  };
  const blockedOperationsHistory: PaperOperationsHistoryPayload = {
    window_size: 0,
    completed_days: 0,
    failed_days: 0,
    blocked_days: 0,
    replayable_days: 0,
    review_days: 0,
    completion_rate: 0,
    replay_rate: 0,
    latest_health_status: "blocked",
    items: [],
    summary: "No paper operations history is available yet."
  };
  const readyOperationsHistory: PaperOperationsHistoryPayload = {
    window_size: 1,
    completed_days: 1,
    failed_days: 0,
    blocked_days: 0,
    replayable_days: 1,
    review_days: 1,
    completion_rate: 1,
    replay_rate: 1,
    latest_health_status: "ready",
    items: [
      {
        trading_day: "2026-06-13",
        run_id: "paper-run-today",
        status: "skipped",
        health_status: "ready",
        event_count: 8,
        has_review: true,
        candidates_count: 3,
        orders_count: 1,
        positions_count: 1,
        blockers: [],
        error_message: null,
        started_at: "2026-06-13T00:02:00Z",
        finished_at: "2026-06-13T00:02:03Z"
      }
    ],
    summary: "Last 1 paper runs are operationally healthy; completion 100%, replay 100%."
  };
  const emptyReviewTrend: PaperReviewTrendPayload = {
    sample_size: 0,
    positive_expectancy_days: 0,
    consecutive_positive_expectancy_days: 0,
    average_expectancy: 0,
    latest_expectancy: 0,
    total_realized_pnl: 0,
    total_unrealized_pnl: 0,
    latest_readiness: "collecting",
    items: [],
    summary: "No paper reviews are available yet."
  };
  const readyReviewTrend: PaperReviewTrendPayload = {
    sample_size: 1,
    positive_expectancy_days: 0,
    consecutive_positive_expectancy_days: 0,
    average_expectancy: 0,
    latest_expectancy: 0,
    total_realized_pnl: 0,
    total_unrealized_pnl: 0,
    latest_readiness: "collecting",
    items: [
      {
        trading_day: "2026-06-13",
        equity: 100000,
        daily_pnl: 125.5,
        daily_return: 0.0013,
        cash: 94936.42,
        realized_pnl: 0,
        unrealized_pnl: 0,
        trade_count: 0,
        win_rate: 0,
        expectancy: 0,
        readiness: "collecting"
      }
    ],
    summary: "Paper review trend is not validated: latest expectancy 0.00, average 0.00, consecutive positive days 0."
  };
  const blockedDailyReport: PaperDailyReportPayload = {
    trading_day: "2026-06-13",
    run_state: "not_started",
    health_status: "blocked",
    recommended_action: "run_daily_paper_trading",
    scheduler_running: true,
    scheduler_next_run_at: "2026-06-14T06:30:00+08:00",
    scheduler_next_run_will_execute: false,
    scheduler_next_run_execution_gate: "market_closed",
    scheduler_next_actionable_run_at: "2026-06-15T06:30:00+08:00",
    scheduler_next_actionable_trading_day: "2026-06-14",
    scheduler_next_actionable_execution_gate: "ready_to_run",
    estimated_sessions_to_alpha_ready: 4,
    limiting_alpha_gate: "review_day_sample",
    account_equity: 100000,
    cash: 100000,
    realized_pnl: 0,
    unrealized_pnl: 0,
    daily_pnl: 0,
    daily_return: 0,
    candidate_count: 0,
    actionable_candidate_count: 0,
    ordered_candidate_count: 0,
    dismissed_candidate_count: 0,
    order_count: 0,
    open_position_count: 0,
    latest_expectancy: 0,
    average_expectancy: 0,
    consecutive_positive_expectancy_days: 0,
    review_latest_expectancy: 0,
    review_average_expectancy: 0,
    review_consecutive_positive_expectancy_days: 0,
    event_ledger_ready: false,
    alpha_ready: false,
    alpha_blockers: ["review_day_sample"],
    open_alpha_gates: [
      {
        gate: "filled_order_sample",
        label: "成交订单",
        current: 10,
        required: 30,
        remaining: 20,
        unit: "笔",
        comparison: "at_least",
        passed: false
      },
      {
        gate: "closed_trade_sample",
        label: "闭环交易",
        current: 6,
        required: 10,
        remaining: 4,
        unit: "笔",
        comparison: "at_least",
        passed: false
      }
    ],
    exit_watchlist: [
      {
        ticker: "AAPL",
        quantity: 2,
        return_pct: 0.15,
        unrealized_pnl: 30,
        trigger: "take_profit",
        triggered: true,
        threshold_pct: 0.1,
        distance_to_trigger_pct: 0,
        next_exit_quantity: 2
      },
      {
        ticker: "MSFT",
        quantity: 1,
        return_pct: -0.1,
        unrealized_pnl: -20,
        trigger: "stop_loss",
        triggered: true,
        threshold_pct: -0.05,
        distance_to_trigger_pct: 0,
        next_exit_quantity: 1
      }
    ],
    data_quality_warnings: [],
    summary: "Daily paper report: operations blocked, run not_started, latest strategy Alpha expectancy 0.00; continue paper validation before live capital."
  };
  const readyDailyReport: PaperDailyReportPayload = {
    ...blockedDailyReport,
    run_state: "skipped",
    health_status: "ready",
    recommended_action: "hold_until_next_session",
    cash: 94936.42,
    candidate_count: 3,
    actionable_candidate_count: 2,
    ordered_candidate_count: 1,
    dismissed_candidate_count: 0,
    order_count: 1,
    open_position_count: 1,
    daily_pnl: 125.5,
    daily_return: 0.0013,
    review_latest_expectancy: 0,
    review_average_expectancy: 0,
    review_consecutive_positive_expectancy_days: 0,
    event_ledger_ready: true,
    summary: "Daily paper report: operations ready, run skipped, latest strategy Alpha expectancy 0.00; continue paper validation before live capital."
  };
  const emptyExecutionDiagnostics: PaperExecutionDiagnosticsPayload = {
    order_count: 0,
    filled_order_count: 0,
    rejected_order_count: 0,
    buy_order_count: 0,
    sell_order_count: 0,
    closed_trade_count: 0,
    fill_rate: 0,
    rejection_rate: 0,
    realized_pnl: 0,
    average_realized_pnl: 0,
    latest_rejection_code: null,
    max_daily_order_rejections: 0,
    max_daily_order_buy_rejections: 0,
    max_daily_order_sell_rejections: 0,
    rejection_reasons: [],
    summary: "No paper execution orders are available yet."
  };
  const readyExecutionDiagnostics: PaperExecutionDiagnosticsPayload = {
    order_count: 1,
    filled_order_count: 1,
    rejected_order_count: 0,
    buy_order_count: 1,
    sell_order_count: 0,
    closed_trade_count: 0,
    fill_rate: 1,
    rejection_rate: 0,
    realized_pnl: 0,
    average_realized_pnl: 0,
    latest_rejection_code: null,
    max_daily_order_rejections: 0,
    max_daily_order_buy_rejections: 0,
    max_daily_order_sell_rejections: 0,
    rejection_reasons: [],
    summary: "Paper execution diagnostics: 1 filled, 0 rejected, 0 closed trades, realized PnL 0.00."
  };
  let riskProfile: PaperRiskProfilePayload = {
    risk_engine: "Trading Core RiskEngine",
    max_order_notional: 2000,
    max_position_weight: 0.1,
    max_daily_orders: 5,
    exit_take_profit_pct: 0.1,
    exit_stop_loss_pct: -0.05,
    summary: "Paper risk profile: max_order_notional 2000.00, max_position_weight 10.00%, max_daily_orders 5."
  };
  const riskLimitReview: PaperRiskLimitReviewPayload = {
    status: "review_required",
    current_max_daily_orders: 5,
    recommended_paper_max_daily_orders: 6,
    live_change_allowed: false,
    max_daily_order_rejections: 26,
    max_daily_order_buy_rejections: 6,
    max_daily_order_sell_rejections: 20,
    filled_order_count: 42,
    closed_trade_count: 20,
    sample_collection_blocked: true,
    blockers: ["filled_order_sample", "closed_trade_sample", "max_daily_orders"],
    summary: "Paper risk limit review: paper-only review required; max_daily_orders 5 -> 6."
  };
  const appliedRiskProfile: PaperRiskProfilePayload = {
    ...riskProfile,
    max_daily_orders: 6,
    summary: "Paper risk profile: max_order_notional 2000.00, max_position_weight 10.00%, max_daily_orders 6."
  };
  let activeRiskLimitReview = riskLimitReview;
  const appliedRiskLimitReview: PaperRiskLimitReviewPayload = {
    ...riskLimitReview,
    status: "hold",
    current_max_daily_orders: 6,
    recommended_paper_max_daily_orders: 6,
    sample_collection_blocked: false,
    blockers: [],
    summary: "Paper risk limit review: hold max_daily_orders at 6; no paper-only capacity change is recommended."
  };
  const riskLimitApply: PaperRiskLimitApplyPayload = {
    applied: true,
    previous_max_daily_orders: 5,
    applied_max_daily_orders: 6,
    live_change_allowed: false,
    audit_event_created: true,
    summary: "Paper risk limit recommendation applied: max_daily_orders 5 -> 6; live limits unchanged."
  };
  const alphaGates: AlphaGateProgressPayload = {
    alpha_ready: false,
    validation_level: "collecting",
    passed_gates: 5,
    total_gates: 9,
    items: [
      {
        gate: "closed_trade_sample",
        label: "闭环交易",
        current: 9,
        required: 10,
        remaining: 1,
        unit: "笔",
        comparison: "at_least",
        passed: false
      },
      {
        gate: "real_market_backtest",
        label: "真实历史回测",
        current: 0,
        required: 1,
        remaining: 1,
        unit: "次",
        comparison: "at_least",
        passed: false
      }
    ],
    summary: "Alpha gate progress: 5/9 gates passed; validation level collecting."
  };
  const alphaForecast: AlphaValidationForecastPayload = {
    alpha_ready: false,
    status: "forecastable",
    estimated_sessions_to_alpha_ready: 5,
    limiting_gate: "filled_order_sample",
    items: [
      {
        gate: "filled_order_sample",
        label: "成交订单",
        current: 20,
        required: 30,
        remaining: 10,
        unit: "笔",
        passed: false,
        estimated_per_session: 2,
        estimated_sessions: 5,
        reason: "按当前样本速度估算。"
      }
    ],
    summary: "Alpha validation needs about 5 more paper sessions if current sample rates continue."
  };
  const riskApplyActionPlan: PaperActionPlanPayload = {
    readiness: "ready",
    primary_action: "apply_paper_risk_limit_recommendation",
    items: [
      {
        priority: 2,
        action_code: "apply_paper_risk_limit_recommendation",
        title: "应用 Paper 限额建议",
        detail: "按默认推荐提高模拟盘样本采集容量：max_daily_orders 5 -> 6；Live 不变。",
        evidence: ["rejected=26"]
      }
    ],
    summary: "Paper action plan primary action: apply_paper_risk_limit_recommendation; 1 actions available."
  };
  const collectSampleActionPlan: PaperActionPlanPayload = {
    readiness: "ready",
    primary_action: "collect_post_limit_sample",
    items: [
      {
        priority: 2,
        action_code: "collect_post_limit_sample",
        title: "收集新限额样本",
        detail: "Paper 风险限额已更新到 max_daily_orders=6；等待下一次真实 paper 运行后再判断是否需要继续调整。",
        evidence: ["filled=42", "closed=20", "rejected=26"]
      }
    ],
    summary: "Paper action plan primary action: collect_post_limit_sample; 1 actions available."
  };
  const simulationResult: PaperSimulationPayload = {
    scenario: "bullish",
    start_date: "2026-06-14",
    days_requested: 5,
    days_completed: 5,
    days_skipped: 0,
    review_day_count: 5,
    consecutive_positive_expectancy_days: 2,
    latest_expectancy: 12.5,
    average_expectancy: 4.2,
    event_chain_count: 40,
    alpha_ready: false,
    blockers: ["closed_trade_sample"],
    items: [
      {
        trading_day: "2026-06-14",
        run_status: "completed",
        orders_count: 1,
        candidates_count: 5,
        positions_count: 1,
        review_id: "review-1"
      }
    ],
    summary: "Paper simulation completed 5/5 days under bullish; latest expectancy is positive."
  };
  const strategyReviews = {
    review_count: 1,
    items: [
      {
        event_id: "paper_action:review_score_pnl_inversion:AAPL,NVDA:2:strategy_review",
        action_code: "review_score_pnl_inversion",
        title: "复盘评分背离",
        detail: "AAPL/NVDA 评分与盈亏反向。",
        evidence: ["inverted_tickers=AAPL,NVDA", "score_pnl_inversion_count=2"],
        inverted_tickers: ["AAPL", "NVDA"],
        review_status: "required",
        created_at: "2026-06-15T01:02:03Z"
      }
    ],
    summary: "Strategy reviews: 1 recorded; latest review_score_pnl_inversion covers AAPL,NVDA."
  };
  let summary = baseSummary;
  let dailyReport = blockedDailyReport;
  let ledger = emptyLedger;
  let operations = blockedOperations;
  let operationsHistory = blockedOperationsHistory;
  let reviewTrend = emptyReviewTrend;
  let executionDiagnostics = emptyExecutionDiagnostics;
  let actionPlan = riskApplyActionPlan;

  await page.route("**/api/mvp/paper-trading/summary", async (route) => {
    await route.fulfill({ contentType: "application/json", json: summary });
  });
  await page.route("**/api/mvp/paper-trading/daily-report", async (route) => {
    await route.fulfill({ contentType: "application/json", json: dailyReport });
  });
  await page.route("**/api/mvp/paper-trading/daily-run", async (route) => {
    expect(route.request().method()).toBe("POST");
    summary = dailySummary;
    await route.fulfill({ contentType: "application/json", json: dailySummary });
  });
  await page.route("**/api/mvp/paper-trading/orders", async (route) => {
    expect(route.request().method()).toBe("POST");
    const payload = route.request().postDataJSON() as { quantity?: number; side?: string; ticker?: string };
    expect(payload).toEqual({
      candidate_id: "paper-candidate-nvda",
      order_type: "market",
      quantity: 40,
      side: "buy",
      strategy_id: "deterministic_watchlist_v1",
      ticker: "NVDA"
    });
    summary = filledSummary;
    dailyReport = readyDailyReport;
    ledger = filledLedger;
    operations = readyOperations;
    operationsHistory = readyOperationsHistory;
    reviewTrend = readyReviewTrend;
    executionDiagnostics = readyExecutionDiagnostics;
    await route.fulfill({ contentType: "application/json", json: filledSummary.orders[0] });
  });
  await page.route("**/api/mvp/paper-trading/scheduler", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: paperSchedulerStatus
    });
  });
  await page.route("**/api/mvp/paper-trading/market-session", async (route) => {
    await route.fulfill({ contentType: "application/json", json: paperMarketSession });
  });
  await page.route("**/api/mvp/paper-trading/runs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        runs: [
          {
            id: "paper-run-today",
            trading_day: "2026-06-13",
            trigger: "manual",
            status: "skipped",
            candidates_count: 3,
            orders_count: 1,
            positions_count: 1,
            review_id: "paper-review",
            error_message: null,
            started_at: "2026-06-13T00:02:00Z",
            finished_at: "2026-06-13T00:02:03Z"
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/event-ledger", async (route) => {
    await route.fulfill({ contentType: "application/json", json: ledger });
  });
  await page.route("**/api/mvp/paper-trading/market-events?**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: paperMarketEvents });
  });
  await page.route("**/api/mvp/paper-trading/operations", async (route) => {
    await route.fulfill({ contentType: "application/json", json: operations });
  });
  await page.route("**/api/mvp/paper-trading/operations/history", async (route) => {
    await route.fulfill({ contentType: "application/json", json: operationsHistory });
  });
  await page.route("**/api/mvp/paper-trading/review-trend", async (route) => {
    await route.fulfill({ contentType: "application/json", json: reviewTrend });
  });
  await page.route("**/api/mvp/paper-trading/simulation/run", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toEqual({ days: 5, scenario: "bullish" });
    await route.fulfill({ contentType: "application/json", json: simulationResult });
  });
  await page.route("**/api/mvp/paper-trading/execution-diagnostics", async (route) => {
    await route.fulfill({ contentType: "application/json", json: executionDiagnostics });
  });
  await page.route("**/api/mvp/paper-trading/risk-profile", async (route) => {
    await route.fulfill({ contentType: "application/json", json: riskProfile });
  });
  await page.route("**/api/mvp/paper-trading/risk-limit-review", async (route) => {
    await route.fulfill({ contentType: "application/json", json: activeRiskLimitReview });
  });
  await page.route("**/api/mvp/paper-trading/risk-limit-review/apply-paper-recommendation", async (route) => {
    expect(route.request().method()).toBe("POST");
    riskProfile = appliedRiskProfile;
    activeRiskLimitReview = appliedRiskLimitReview;
    await route.fulfill({ contentType: "application/json", json: riskLimitApply });
  });
  await page.route("**/api/mvp/paper-trading/action-plan/execute-primary", async (route) => {
    expect(route.request().method()).toBe("POST");
    riskProfile = appliedRiskProfile;
    activeRiskLimitReview = appliedRiskLimitReview;
    actionPlan = collectSampleActionPlan;
    await route.fulfill({
      contentType: "application/json",
      json: {
        executed: true,
        action_code: "apply_paper_risk_limit_recommendation",
        next_primary_action: "collect_post_limit_sample",
        result: riskLimitApply,
        summary:
          "Executed primary action apply_paper_risk_limit_recommendation; next action collect_post_limit_sample."
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/alpha-gates", async (route) => {
    await route.fulfill({ contentType: "application/json", json: alphaGates });
  });
  await page.route("**/api/mvp/strategy-lab/alpha-forecast", async (route) => {
    await route.fulfill({ contentType: "application/json", json: alphaForecast });
  });
  await page.route("**/api/mvp/paper-trading/action-plan", async (route) => {
    await route.fulfill({ contentType: "application/json", json: actionPlan });
  });
  await page.route("**/api/mvp/paper-trading/strategy-reviews", async (route) => {
    await route.fulfill({ contentType: "application/json", json: strategyReviews });
  });

  await gotoDashboard(page);
  await page.getByRole("link", { name: "模拟盘" }).click();

  await expect(page).toHaveURL("/paper-trading");
  await expect(page.getByRole("heading", { level: 2, name: "模拟盘" })).toBeVisible();
  await expect(page.getByText("默认模拟盘")).toBeVisible();
  const marketSessionPanel = page.getByRole("region", { name: "市场交易日" });
  await expect(marketSessionPanel.getByText("生效交易日")).toBeVisible();
  await expect(marketSessionPanel.getByText("2026-06-12")).toBeVisible();
  await expect(marketSessionPanel.getByText("市场日期")).toBeVisible();
  await expect(marketSessionPanel.getByText("2026-06-13")).toBeVisible();
  await expect(marketSessionPanel.getByText("market_closed")).toBeVisible();
  await expect(marketSessionPanel.getByText("pandas_market_calendars")).toBeVisible();
  const dailyReportPanel = page.getByRole("region", { name: "今日简报" });
  await expect(dailyReportPanel.getByText("Daily paper report: operations blocked")).toBeVisible();
  await expect(dailyReportPanel.getByText("成交订单 10 / 30，还差 20笔")).toBeVisible();
  await expect(dailyReportPanel.getByText("闭环交易 6 / 10，还差 4笔")).toBeVisible();
  await expect(dailyReportPanel.getByText("AAPL 止盈 15.0% · 下次 2")).toBeVisible();
  await expect(dailyReportPanel.getByText("MSFT 止损 -10.0% · 下次 1")).toBeVisible();
  await expect(dailyReportPanel.getByText("阻断 review_day_sample")).toBeVisible();
  const operationsPanel = page.getByRole("region", { name: "运行健康" });
  await expect(operationsPanel.getByText("blocked", { exact: true })).toBeVisible();
  await expect(operationsPanel.getByText("run_daily_paper_trading")).toBeVisible();
  await expect(operationsPanel.getByText("调度决策")).toBeVisible();
  await expect(operationsPanel.getByText("failed · 2026-06-12")).toBeVisible();
  await expect(operationsPanel.getByText("Scheduled paper trading failed: paper loop failed.")).toBeVisible();
  await expect(operationsPanel.getByText("事件链缺失", { exact: true })).toBeVisible();
  const stabilityPanel = page.getByRole("region", { name: "稳定趋势" });
  await expect(stabilityPanel.getByText("No paper operations history is available yet.")).toBeVisible();
  await expect(stabilityPanel.getByText("0.0%")).toHaveCount(2);
  const reviewTrendPanel = page.getByRole("region", { name: "净期望趋势" });
  await expect(reviewTrendPanel.getByText("No paper reviews are available yet.")).toBeVisible();
  const executionPanel = page.getByRole("region", { name: "执行诊断" });
  await expect(executionPanel.getByText("No paper execution orders are available yet.")).toBeVisible();
  const riskPanel = page.getByRole("region", { name: "风险配置" });
  await expect(riskPanel.getByText("Trading Core RiskEngine")).toBeVisible();
  await expect(riskPanel.getByText("5 笔")).toBeVisible();
  const riskLimitReviewPanel = page.getByRole("region", { name: "风险限额评审" });
  await expect(riskLimitReviewPanel.getByText("Paper risk limit review: paper-only review required")).toBeVisible();
  await expect(riskLimitReviewPanel.getByText("5 → 6")).toBeVisible();
  await expect(riskLimitReviewPanel.getByText("Live 不变")).toBeVisible();
  const actionPlanPanel = page.getByRole("region", { name: "行动计划" });
  await expect(
    actionPlanPanel.getByText("Paper action plan primary action: apply_paper_risk_limit_recommendation")
  ).toBeVisible();
  await expect(actionPlanPanel.getByText("应用 Paper 限额建议")).toBeVisible();
  const strategyReviewsPanel = page.getByRole("region", { name: "策略复盘记录" });
  await expect(strategyReviewsPanel.getByText("Strategy reviews: 1 recorded")).toBeVisible();
  await expect(strategyReviewsPanel.getByText("AAPL, NVDA")).toBeVisible();
  await expect(strategyReviewsPanel.getByText("required")).toBeVisible();
  await actionPlanPanel.getByRole("button", { name: "执行首要动作" }).click();
  await expect(
    page.getByText("Executed primary action apply_paper_risk_limit_recommendation; next action collect_post_limit_sample.")
  ).toBeVisible();
  await expect(actionPlanPanel.getByText("Paper action plan primary action: collect_post_limit_sample")).toBeVisible();
  await expect(actionPlanPanel.getByText("收集新限额样本")).toBeVisible();
  await expect(riskLimitReviewPanel.getByText("6 → 6")).toBeVisible();
  await expect(riskPanel.getByText("6 笔")).toBeVisible();
  const alphaGatePanel = page.getByRole("region", { name: "Alpha 门禁" });
  await expect(alphaGatePanel.getByText("Alpha gate progress: 5/9 gates passed")).toBeVisible();
  await expect(alphaGatePanel.getByText("5 / 9")).toBeVisible();
  await expect(alphaGatePanel.getByText("闭环交易", { exact: true })).toBeVisible();
  await expect(alphaGatePanel.getByText("真实历史回测", { exact: true })).toBeVisible();
  const alphaForecastPanel = page.getByRole("region", { name: "Alpha 预测" });
  await expect(alphaForecastPanel.getByText("Alpha validation needs about 5 more paper sessions")).toBeVisible();
  await expect(alphaForecastPanel.getByText("5 次", { exact: true })).toBeVisible();
  await expect(alphaForecastPanel.getByText("filled_order_sample")).toBeVisible();
  const simulationPanel = page.getByRole("region", { name: "多日模拟" });
  await expect(simulationPanel.getByText("多日模拟")).toBeVisible();
  await page.getByRole("button", { name: "运行 5 日模拟" }).click();
  await expect(simulationPanel.getByText("Paper simulation completed 5/5 days under bullish")).toBeVisible();
  await expect(simulationPanel.getByText("5 / 5")).toBeVisible();
  await expect(simulationPanel.getByText("closed_trade_sample")).toBeVisible();
  const schedulerPanel = page.getByRole("region", { name: "每日调度" });
  await expect(schedulerPanel.getByText("休市跳过")).toBeVisible();
  await expect(schedulerPanel.getByText("运行中")).toBeVisible();
  await expect(page.getByText("30 6 * * *")).toBeVisible();
  await expect(schedulerPanel.getByText("paper_trading_daily_run")).toBeVisible();
  await expect(schedulerPanel.getByText("下次运行")).toBeVisible();
  await expect(schedulerPanel.getByText("下次采样")).toBeVisible();
  await expect(schedulerPanel.getByText("仅守门")).toBeVisible();
  await expect(schedulerPanel.getByText("下次交易日")).toBeVisible();
  await expect(
    schedulerPanel.locator(".scheduler-grid > div", { hasText: "下次交易日" }).getByText("2026-06-12")
  ).toBeVisible();
  await expect(schedulerPanel.getByText("下次有效采样")).toBeVisible();
  await expect(schedulerPanel.getByText("2026-06-15")).toBeVisible();
  await expect(page.getByRole("region", { name: "运行账本" }).getByText("skipped")).toBeVisible();
  await expect(page.getByRole("region", { name: "运行账本" }).getByText("manual")).toBeVisible();
  await expect(page.getByRole("region", { name: "运行账本" }).getByText("订单 1")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("需修复")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("missing_core_events")).toBeVisible();

  await page.getByRole("button", { name: "运行今日模拟" }).click();

  await expect(page.getByRole("region", { name: "候选池" }).getByText("NVDA", { exact: true })).toBeVisible();
  await expect(page.getByText("3 条证据支持继续跟踪 NVDA")).toBeVisible();
  await expect(page.getByText("回测 收益 -1.46%")).toBeVisible();
  await expect(page.getByRole("button", { name: "已排除 AMZN" })).toBeDisabled();
  await expect(page.getByText("正在收集模拟盘样本。")).toBeVisible();

  await page.getByRole("button", { name: "模拟买入 NVDA" }).click();

  await expect(page.getByText("已模拟买入 NVDA。")).toBeVisible();
  await expect(dailyReportPanel.getByText("Daily paper report: operations ready")).toBeVisible();
  await expect(dailyReportPanel.getByText("hold_until_next_session")).toBeVisible();
  await expect(dailyReportPanel.getByText("今日 PnL")).toBeVisible();
  await expect(dailyReportPanel.getByText("$125.50 · 0.1%")).toBeVisible();
  await expect(operationsPanel.getByText("ready", { exact: true })).toBeVisible();
  await expect(operationsPanel.getByText("hold_until_next_session")).toBeVisible();
  await expect(operationsPanel.getByText("事件链可回放")).toBeVisible();
  await expect(stabilityPanel.getByText("100.0%")).toHaveCount(2);
  await expect(stabilityPanel.getByText("2026-06-13")).toBeVisible();
  await expect(reviewTrendPanel.getByText("Paper review trend is not validated")).toBeVisible();
  await expect(reviewTrendPanel.getByText("2026-06-13")).toBeVisible();
  await expect(reviewTrendPanel.getByText("日 PnL")).toBeVisible();
  await expect(reviewTrendPanel.getByText("$125.50")).toBeVisible();
  await expect(reviewTrendPanel.getByText("0.1%")).toBeVisible();
  await expect(executionPanel.getByText("Paper execution diagnostics: 1 filled, 0 rejected")).toBeVisible();
  await expect(executionPanel.getByText("100.0%")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("完整", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("NVDA · filled")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("order_state 5")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("完整链")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("断链")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("链路率")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("100%")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("链路警告 无")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("候选解释")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("candidate · deterministic_watchlist_v1")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("候选 ID paper-candidate-nvda")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "事件账本" }).getByText("NVDA promoted by real backtest evidence.")
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("排序分数 1,034.97")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("回测收益 38.60%")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "事件账本" }).getByText("new → validated → risk_approved → sent → filled")
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "模拟订单" }).getByRole("cell", { name: "filled", exact: true })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "模拟订单" }).getByRole("cell", { name: "approved approved" })
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "模拟订单" }).getByText("risk_approved")).toBeVisible();
  await expect(page.getByRole("region", { name: "模拟持仓" }).getByText("NVDA", { exact: true })).toBeVisible();
});

test("paper trading disables daily run when today's operations are complete", async ({ page }) => {
  await page.route("**/api/mvp/paper-trading/summary", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        account: {
          id: "paper-account",
          name: "默认模拟盘",
          mode: "paper",
          starting_cash: 100000,
          cash: 98000,
          realized_pnl: 0,
          unrealized_pnl: 0,
          equity: 100000,
          updated_at: "2026-06-13T00:00:00Z"
        },
        candidates: [],
        orders: [],
        positions: [],
        latest_review: null
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/daily-report", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        trading_day: "2026-06-13",
        run_state: "skipped",
        health_status: "ready",
        recommended_action: "hold_until_next_session",
        scheduler_running: true,
        scheduler_next_run_at: "2026-06-14T06:30:00+08:00",
        scheduler_next_run_will_execute: false,
        scheduler_next_run_execution_gate: "market_closed",
        scheduler_next_actionable_run_at: "2026-06-15T06:30:00+08:00",
        scheduler_next_actionable_trading_day: "2026-06-14",
        scheduler_next_actionable_execution_gate: "ready_to_run",
        estimated_sessions_to_alpha_ready: 4,
        limiting_alpha_gate: "review_day_sample",
        account_equity: 100000,
        cash: 98000,
        realized_pnl: 0,
        unrealized_pnl: 0,
        daily_pnl: 0,
        daily_return: 0,
        candidate_count: 0,
        actionable_candidate_count: 0,
        ordered_candidate_count: 0,
        dismissed_candidate_count: 0,
        order_count: 0,
        open_position_count: 0,
        latest_expectancy: 0,
        average_expectancy: 0,
        consecutive_positive_expectancy_days: 0,
        review_latest_expectancy: 0,
        review_average_expectancy: 0,
        review_consecutive_positive_expectancy_days: 0,
        event_ledger_ready: true,
        alpha_ready: false,
        alpha_blockers: ["review_day_sample"],
        open_alpha_gates: [],
        exit_watchlist: [],
        data_quality_warnings: [],
        summary: "Daily paper report: operations ready, run skipped, latest strategy Alpha expectancy 0.00; continue paper validation before live capital."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/scheduler", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: paperSchedulerStatus
    });
  });
  await page.route("**/api/mvp/paper-trading/operations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        trading_day: "2026-06-13",
        run_state: "skipped",
        health_status: "ready",
        latest_run_id: "paper-run-today",
        latest_run_trading_day: "2026-06-13",
        latest_run_status: "skipped",
        today_run_id: "paper-run-today",
        review_id: "paper-review",
        latest_error: null,
        can_retry_today: false,
        event_ledger_ready: true,
        latest_run_event_count: 1,
        legacy_manual_future_run_count: 0,
        latest_legacy_manual_future_trading_day: null,
        data_quality_warnings: [],
        latest_scheduler_decision: "skipped",
        latest_scheduler_decision_at: "2026-06-13T06:30:00+08:00",
        latest_scheduler_decision_trading_day: "2026-06-13",
        latest_scheduler_decision_reason: "market_closed",
        latest_scheduler_decision_summary: "Market is closed; scheduled paper trading skipped.",
        blockers: [],
        recommended_action: "hold_until_next_session",
        summary: "Daily paper pipeline is complete for the trading day."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/operations/history", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        window_size: 1,
        completed_days: 1,
        failed_days: 0,
        blocked_days: 0,
        replayable_days: 1,
        review_days: 1,
        completion_rate: 1,
        replay_rate: 1,
        latest_health_status: "ready",
        items: [
          {
            trading_day: "2026-06-13",
            run_id: "paper-run-today",
            status: "skipped",
            health_status: "ready",
            event_count: 1,
            has_review: true,
            candidates_count: 0,
            orders_count: 0,
            positions_count: 0,
            blockers: [],
            error_message: null,
            started_at: "2026-06-13T00:00:00Z",
            finished_at: "2026-06-13T00:01:00Z"
          }
        ],
        summary: "Last 1 paper runs are operationally healthy; completion 100%, replay 100%."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/review-trend", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        sample_size: 1,
        positive_expectancy_days: 0,
        consecutive_positive_expectancy_days: 0,
        average_expectancy: 0,
        latest_expectancy: 0,
        total_realized_pnl: 0,
        total_unrealized_pnl: 0,
        latest_readiness: "collecting",
        items: [],
        summary: "Paper review trend is not validated: latest expectancy 0.00, average 0.00, consecutive positive days 0."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/market-session", async (route) => {
    await route.fulfill({ contentType: "application/json", json: paperMarketSession });
  });
  await page.route("**/api/mvp/paper-trading/runs", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { runs: [] } });
  });
  await page.route("**/api/mvp/paper-trading/event-ledger", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        total_event_count: 1,
        latest_run_id: "paper-run-today",
        latest_run_status: "skipped",
        latest_run_event_count: 1,
        latest_topic_counts: [{ topic: "run_audit", count: 1 }],
        latest_correlation_count: 1,
        replay_ready: true,
        warnings: [],
        summary: "Latest paper run is skipped with 1 replayable core event across 1 chains.",
        latest_replay: null
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/action-plan", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        readiness: "ready",
        primary_action: "hold_until_next_session",
        items: [
          {
            priority: 5,
            action_code: "hold_until_next_session",
            title: "等待下一次调度",
            detail:
              "当前交易日 Alpha 验证快照已记录，等待下一交易日继续收集样本。预计还需 4 次有效 paper sessions；下一次有效采样 2026-06-16T06:30:00+08:00，交易日 2026-06-15。",
            evidence: [
              "Alpha validation needs about 4 more paper sessions.",
              "estimated_sessions_to_alpha_ready=4",
              "limiting_gate=review_day_sample",
              "next_actionable_trading_day=2026-06-15"
            ]
          }
        ],
        summary: "Paper action plan primary action: hold_until_next_session; 1 actions available."
      }
    });
  });

  await page.goto("/paper-trading");

  await expect(page.getByRole("button", { name: "今日已完成" })).toBeDisabled();
  await expect(page.getByRole("region", { name: "运行健康" }).getByText("hold_until_next_session")).toBeVisible();
  await expect(page.getByRole("region", { name: "稳定趋势" }).getByText("100.0%")).toHaveCount(2);
  const actionPlanPanel = page.getByRole("region", { name: "行动计划" });
  await expect(actionPlanPanel.getByText("预计还需 4 次有效 paper sessions")).toBeVisible();
  await expect(actionPlanPanel.getByText("下一次有效采样 2026-06-16T06:30:00+08:00")).toBeVisible();
  await expect(actionPlanPanel.getByText("limiting_gate=review_day_sample")).toBeVisible();
});

test("paper trading shows daily report before slower summary endpoints finish", async ({ page }) => {
  await page.route("**/api/mvp/paper-trading/summary", async (route) => {
    await new Promise((resolve) => {
      setTimeout(resolve, 10_000);
    });
    await route.fulfill({
      contentType: "application/json",
      json: {
        account: {
          id: "paper-account",
          name: "默认模拟盘",
          mode: "paper",
          starting_cash: 100000,
          cash: 100000,
          realized_pnl: 0,
          unrealized_pnl: 0,
          equity: 100000,
          updated_at: "2026-06-12T21:00:00Z"
        },
        candidates: [],
        orders: [],
        positions: [],
        latest_review: null
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/daily-report", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        trading_day: "2026-06-12",
        run_state: "completed",
        health_status: "ready",
        recommended_action: "hold_until_next_session",
        scheduler_running: true,
        scheduler_next_run_at: "2026-06-15T06:30:00+08:00",
        scheduler_next_run_will_execute: false,
        scheduler_next_run_execution_gate: "market_closed",
        scheduler_next_actionable_run_at: "2026-06-16T06:30:00+08:00",
        scheduler_next_actionable_trading_day: "2026-06-15",
        scheduler_next_actionable_execution_gate: "ready_to_run",
        estimated_sessions_to_alpha_ready: 4,
        limiting_alpha_gate: "review_day_sample",
        account_equity: 104931.08,
        cash: 80613.94,
        realized_pnl: 1256.86,
        unrealized_pnl: 3674.22,
        daily_pnl: 0,
        daily_return: 0,
        candidate_count: 6,
        actionable_candidate_count: 3,
        ordered_candidate_count: 0,
        dismissed_candidate_count: 3,
        order_count: 51,
        open_position_count: 6,
        latest_expectancy: 151.4,
        average_expectancy: 151.4,
        consecutive_positive_expectancy_days: 1,
        event_ledger_ready: true,
        alpha_ready: false,
        alpha_blockers: ["review_day_sample"],
        open_alpha_gates: [],
        exit_watchlist: [
          {
            ticker: "AAPL",
            quantity: 29,
            return_pct: 0.118,
            unrealized_pnl: 891.11,
            trigger: "take_profit",
            triggered: true,
            threshold_pct: 0.1,
            distance_to_trigger_pct: 0,
            next_exit_quantity: 6
          }
        ],
        data_quality_warnings: [],
        summary:
          "Daily paper report: operations ready, run completed, latest strategy Alpha expectancy 151.40; continue paper validation before live capital."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/scheduler", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        enabled: true,
        running: true,
        cron: "30 6 * * *",
        timezone: "Asia/Shanghai",
        next_run_at: "2026-06-15T06:30:00+08:00",
        next_run_will_execute: false,
        next_run_execution_gate: "market_closed",
        next_run_trading_day: "2026-06-12",
        next_actionable_run_at: "2026-06-16T06:30:00+08:00",
        next_actionable_trading_day: "2026-06-15",
        next_actionable_execution_gate: "ready_to_run",
        summary: "scheduler"
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/market-session", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        mode: "market_calendar",
        now: "2026-06-15T00:00:00+08:00",
        timezone: "Asia/Shanghai",
        market_date: "2026-06-12",
        effective_trading_day: "2026-06-12",
        execution_gate: "market_closed",
        is_open_now: false,
        source: "pandas_market_calendars",
        summary: "market closed"
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/operations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        trading_day: "2026-06-12",
        run_state: "completed",
        health_status: "ready",
        latest_run_id: "run-1",
        latest_run_trading_day: "2026-06-12",
        latest_run_status: "completed",
        today_run_id: "run-1",
        review_id: "review-1",
        latest_error: null,
        can_retry_today: false,
        event_ledger_ready: true,
        latest_run_event_count: 1,
        legacy_manual_future_run_count: 0,
        latest_legacy_manual_future_trading_day: null,
        data_quality_warnings: [],
        latest_scheduler_decision: "skipped",
        latest_scheduler_decision_at: "2026-06-15T06:30:00+08:00",
        latest_scheduler_decision_trading_day: "2026-06-12",
        latest_scheduler_decision_reason: "market_closed",
        latest_scheduler_decision_summary: "skipped",
        blockers: [],
        recommended_action: "hold_until_next_session",
        summary: "ready"
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/operations/history", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        window_size: 0,
        completed_days: 0,
        failed_days: 0,
        blocked_days: 0,
        replayable_days: 0,
        review_days: 0,
        completion_rate: 0,
        replay_rate: 0,
        latest_health_status: "ready",
        items: [],
        summary: "No paper operations history is available yet."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/review-trend", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        sample_size: 0,
        positive_expectancy_days: 0,
        consecutive_positive_expectancy_days: 0,
        average_expectancy: 0,
        latest_expectancy: 0,
        items: [],
        summary: "No paper reviews are available yet."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/execution-diagnostics", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        order_count: 0,
        filled_order_count: 0,
        rejected_order_count: 0,
        buy_order_count: 0,
        sell_order_count: 0,
        closed_trade_count: 0,
        fill_rate: 0,
        rejection_rate: 0,
        realized_pnl: 0,
        average_realized_pnl: 0,
        latest_rejection_code: null,
        max_daily_order_rejections: 0,
        max_daily_order_buy_rejections: 0,
        max_daily_order_sell_rejections: 0,
        rejection_reasons: [],
        summary: "No paper execution orders are available yet."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/risk-profile", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        risk_engine: "Trading Core RiskEngine",
        max_order_notional: 2000,
        max_position_weight: 0.1,
        max_daily_orders: 5,
        exit_take_profit_pct: 0.1,
        exit_stop_loss_pct: -0.05,
        summary: "risk"
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/risk-limit-review", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        status: "stable",
        current_max_daily_orders: 5,
        recommended_paper_max_daily_orders: 5,
        live_change_allowed: false,
        max_daily_order_rejections: 0,
        max_daily_order_buy_rejections: 0,
        max_daily_order_sell_rejections: 0,
        filled_order_count: 0,
        closed_trade_count: 0,
        sample_collection_blocked: false,
        blockers: [],
        summary: "stable"
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/alpha-gates", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        alpha_ready: false,
        validation_level: "collecting",
        passed_gates: 0,
        total_gates: 0,
        items: [],
        summary: "Alpha gate progress: 0/0 gates passed"
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/alpha-forecast", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        alpha_ready: false,
        status: "blocked",
        estimated_sessions_to_alpha_ready: null,
        limiting_gate: null,
        items: [],
        summary: "forecast"
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/action-plan", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        readiness: "ready",
        primary_action: "hold_until_next_session",
        items: [],
        summary: "hold"
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/runs", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { runs: [] } });
  });
  await page.route("**/api/mvp/paper-trading/event-ledger", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        total_event_count: 0,
        latest_run_id: null,
        latest_run_status: null,
        latest_run_event_count: 0,
        latest_topic_counts: [],
        latest_correlation_count: 0,
        replay_ready: true,
        warnings: [],
        summary: "ledger",
        latest_replay: null
      }
    });
  });

  await page.goto("/paper-trading");

  const dailyReportPanel = page.getByRole("region", { name: "今日简报" });
  await expect(dailyReportPanel.getByText("AAPL 止盈 11.8% · 下次 6")).toBeVisible({ timeout: 3000 });
});

test("paper trading can repair missing historical event ledgers", async ({ page }) => {
  const summary = {
    account: {
      id: "paper-account",
      name: "默认模拟盘",
      mode: "paper",
      starting_cash: 100000,
      cash: 98000,
      realized_pnl: 0,
      unrealized_pnl: 0,
      equity: 100000,
      updated_at: "2026-06-13T00:00:00Z"
    },
    candidates: [],
    orders: [],
    positions: [],
    latest_review: null
  };
  let operations: PaperOperationsStatusPayload = {
    trading_day: "2026-06-13",
    run_state: "skipped",
    health_status: "ready",
    latest_run_id: "paper-run-today",
    latest_run_trading_day: "2026-06-13",
    latest_run_status: "skipped",
    today_run_id: "paper-run-today",
    review_id: "paper-review",
    latest_error: null,
    can_retry_today: false,
    event_ledger_ready: true,
    latest_run_event_count: 1,
    legacy_manual_future_run_count: 1,
    latest_legacy_manual_future_trading_day: "2026-06-30",
    data_quality_warnings: ["legacy_manual_future_runs_detected"],
    latest_scheduler_decision: "skipped",
    latest_scheduler_decision_at: "2026-06-13T06:30:00+08:00",
    latest_scheduler_decision_trading_day: "2026-06-13",
    latest_scheduler_decision_reason: "market_closed",
    latest_scheduler_decision_summary: "Market is closed; scheduled paper trading skipped.",
    blockers: [],
    recommended_action: "hold_until_next_session",
    summary:
      "Daily paper pipeline is complete for the trading day. Data quality warning: legacy manual future-dated runs detected."
  };
  const missingHistory = {
    window_size: 2,
    completed_days: 1,
    failed_days: 0,
    blocked_days: 1,
    replayable_days: 1,
    review_days: 2,
    completion_rate: 0.5,
    replay_rate: 0.5,
    latest_health_status: "ready",
    items: [
      {
        trading_day: "2026-06-13",
        run_id: "paper-run-today",
        status: "skipped",
        health_status: "ready",
        event_count: 1,
        has_review: true,
        candidates_count: 5,
        orders_count: 2,
        positions_count: 2,
        blockers: [],
        error_message: null,
        started_at: "2026-06-13T00:02:00Z",
        finished_at: "2026-06-13T00:02:03Z"
      },
      {
        trading_day: "2026-06-12",
        run_id: "paper-run-old",
        status: "skipped",
        health_status: "blocked",
        event_count: 0,
        has_review: true,
        candidates_count: 5,
        orders_count: 2,
        positions_count: 2,
        blockers: ["event_ledger_not_replayable"],
        error_message: null,
        started_at: "2026-06-12T00:02:00Z",
        finished_at: "2026-06-12T00:02:03Z"
      }
    ],
    summary: "Last 2 paper runs include 1 blocked and 0 failed runs; completion 50%, replay 50%."
  };
  const repairedHistory = {
    ...missingHistory,
    completed_days: 2,
    blocked_days: 0,
    replayable_days: 2,
    completion_rate: 1,
    replay_rate: 1,
    items: missingHistory.items.map((item) => ({ ...item, health_status: "ready", event_count: 1, blockers: [] })),
    summary: "Last 2 paper runs are operationally healthy; completion 100%, replay 100%."
  };
  const dailyReport: PaperDailyReportPayload = {
    trading_day: "2026-06-13",
    run_state: "skipped",
    health_status: "ready",
    recommended_action: "hold_until_next_session",
    scheduler_running: true,
    scheduler_next_run_at: "2026-06-14T06:30:00+08:00",
    scheduler_next_run_will_execute: false,
    scheduler_next_run_execution_gate: "market_closed",
    scheduler_next_actionable_run_at: "2026-06-15T06:30:00+08:00",
    scheduler_next_actionable_trading_day: "2026-06-14",
    scheduler_next_actionable_execution_gate: "ready_to_run",
    estimated_sessions_to_alpha_ready: 4,
    limiting_alpha_gate: "review_day_sample",
    account_equity: 100000,
    cash: 98000,
    realized_pnl: 0,
    unrealized_pnl: 0,
    daily_pnl: 30,
    daily_return: 0.0003,
    candidate_count: 0,
    actionable_candidate_count: 0,
    ordered_candidate_count: 0,
    dismissed_candidate_count: 0,
    order_count: 0,
    open_position_count: 0,
    latest_expectancy: 1,
    average_expectancy: 0.5,
    consecutive_positive_expectancy_days: 1,
    review_latest_expectancy: 1,
    review_average_expectancy: 0.5,
    review_consecutive_positive_expectancy_days: 1,
    event_ledger_ready: true,
    alpha_ready: false,
    alpha_blockers: ["review_day_sample"],
    open_alpha_gates: [],
    exit_watchlist: [],
    data_quality_warnings: ["future_runs_excluded_from_as_of_report"],
    summary: "Daily paper report: operations ready, run skipped, latest strategy Alpha expectancy 1.00; continue paper validation before live capital."
  };
  const actionPlan: PaperActionPlanPayload = {
    readiness: "ready",
    primary_action: "quarantine_legacy_manual_future_runs",
    items: [
      {
        priority: 1,
        action_code: "quarantine_legacy_manual_future_runs",
        title: "标记旧运行",
        detail: "检测到 1 条旧 manual 未来日期运行；先标记为 simulation，避免继续污染纸面账户复盘。",
        evidence: ["legacy_manual_future_run_count=1", "latest_legacy_trading_day=2026-06-30"]
      }
    ],
    summary: "Paper action plan primary action: quarantine_legacy_manual_future_runs; 1 actions available."
  };
  let history = missingHistory;

  await page.route("**/api/mvp/paper-trading/summary", async (route) => {
    await route.fulfill({ contentType: "application/json", json: summary });
  });
  await page.route("**/api/mvp/paper-trading/daily-report", async (route) => {
    await route.fulfill({ contentType: "application/json", json: dailyReport });
  });
  await page.route("**/api/mvp/paper-trading/scheduler", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: paperSchedulerStatus
    });
  });
  await page.route("**/api/mvp/paper-trading/operations", async (route) => {
    await route.fulfill({ contentType: "application/json", json: operations });
  });
  await page.route("**/api/mvp/paper-trading/operations/history", async (route) => {
    await route.fulfill({ contentType: "application/json", json: history });
  });
  await page.route("**/api/mvp/paper-trading/review-trend", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        sample_size: 2,
        positive_expectancy_days: 1,
        consecutive_positive_expectancy_days: 1,
        average_expectancy: 0.5,
        latest_expectancy: 1,
        total_realized_pnl: 10,
        total_unrealized_pnl: 20,
        latest_readiness: "watch",
        items: [],
        summary: "Paper review trend is positive: latest expectancy 1.00, average 0.50, consecutive positive days 1."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/operations/repair-ledger", async (route) => {
    expect(route.request().method()).toBe("POST");
    history = repairedHistory;
    await route.fulfill({
      contentType: "application/json",
      json: {
        scanned_runs: 2,
        repaired_runs: 1,
        skipped_runs: 1,
        items: [
          {
            run_id: "paper-run-old",
            trading_day: "2026-06-12",
            status: "skipped",
            event_created: true,
            topic: "run_audit",
            reason: "audit_event_created"
          }
        ],
        summary: "Scanned 2 paper runs; repaired 1 missing event ledgers and skipped 1."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/operations/quarantine-legacy-runs", async (route) => {
    expect(route.request().method()).toBe("POST");
    operations = {
      ...operations,
      legacy_manual_future_run_count: 0,
      latest_legacy_manual_future_trading_day: null,
      data_quality_warnings: [],
      summary: "Daily paper pipeline is complete for the trading day."
    };
    await route.fulfill({
      contentType: "application/json",
      json: {
        scanned_runs: 1,
        quarantined_runs: 1,
        skipped_runs: 0,
        items: [
          {
            run_id: "paper-run-future",
            trading_day: "2026-06-30",
            status: "completed",
            previous_trigger: "manual",
            new_trigger: "simulation",
            audit_event_created: true,
            reason: "manual_future_dated_run_reclassified_as_simulation"
          }
        ],
        summary: "Scanned 1 legacy manual future-dated runs; quarantined 1 as simulation and skipped 0."
      }
    });
  });
  await page.route("**/api/mvp/paper-trading/action-plan", async (route) => {
    await route.fulfill({ contentType: "application/json", json: actionPlan });
  });
  await page.route("**/api/mvp/paper-trading/runs", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { runs: [] } });
  });
  await page.route("**/api/mvp/paper-trading/event-ledger", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        total_event_count: 2,
        latest_run_id: "paper-run-today",
        latest_run_status: "skipped",
        latest_run_event_count: 1,
        latest_topic_counts: [{ topic: "run_audit", count: 1 }],
        latest_correlation_count: 1,
        replay_ready: true,
        warnings: [],
        summary: "Latest paper run is skipped with 1 replayable core event across 1 chains.",
        latest_replay: null
      }
    });
  });

  await page.goto("/paper-trading");

  await expect(page.getByText("数据警告 未来模拟运行已从当前日报排除")).toBeVisible();
  await expect(page.getByText("数据质量 检测到早期手动未来日期运行 · 数量 1 · 最新 2026-06-30")).toBeVisible();
  await expect(page.getByRole("region", { name: "行动计划" }).getByText("标记旧运行")).toBeVisible();
  await expect(page.getByRole("button", { name: "标记旧运行" })).toBeEnabled();
  await page.getByRole("button", { name: "标记旧运行" }).click();
  await expect(page.getByText("旧运行已标记：1 条改为 simulation。")).toBeVisible();
  await expect(page.getByText("数据质量 检测到早期手动未来日期运行 · 数量 1 · 最新 2026-06-30")).not.toBeVisible();
  const stabilityPanel = page.getByRole("region", { name: "稳定趋势" });
  await expect(stabilityPanel.getByText("50.0%")).toHaveCount(2);
  await expect(stabilityPanel.getByText("事件链缺失")).toBeVisible();
  await expect(page.getByRole("button", { name: "修复事件链" })).toBeEnabled();

  await page.getByRole("button", { name: "修复事件链" }).click();

  await expect(page.getByText("事件链修复完成：修复 1 条运行记录。")).toBeVisible();
  await expect(stabilityPanel.getByText("100.0%")).toHaveCount(2);
  await expect(stabilityPanel.getByText("Scanned 2 paper runs; repaired 1 missing event ledgers and skipped 1.")).toBeVisible();
  await expect(page.getByRole("button", { name: "修复事件链" })).toBeDisabled();
});

test("AI prompts return a visible research result after click", async ({ page }) => {
  await page.route("**/api/mvp/ai/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        langgraph: {
          available: true,
          mode: "research_workflow",
          message: "LangGraph is used for research workflow orchestration only."
        },
        research_llm: {
          provider: "openai_responses_or_chat_completions",
          mode: "research_only",
          configured: true,
          available: true,
          model: "gpt-5.5",
          base_url: "https://api.openai.com/v1",
          message: "OpenAI-compatible research LLM is configured for research explanations only."
        },
        execution_path: {
          ai_generates_trade_intent: false,
          ai_influences_risk: false,
          ai_calls_execution: false
        }
      }
    });
  });
  await page.route("**/api/mvp/research", async (route) => {
    await route.fulfill({
      contentType: "application/json",
        json: {
          ticker: "AAPL",
        status: "complete_llm",
          summary: "AAPL: 模拟组合风险研究结果。",
        bull_case: "服务收入韧性支持多头观点。",
        bear_case: "估值压缩仍是主要风险。",
        watch_items: ["复核 filing 趋势", "检查组合集中度"],
        evidence_count: 2,
        trade_plan_draft: {
          entry_condition: "人工复核确认投资假设。",
          invalidation_condition: "新的 filing 与证据相矛盾。",
          risk_notes: ["这不是可直接执行的订单建议。", "必须经过人工审批。"]
        }
      }
    });
  });

  await gotoDashboard(page);
  await openAiAssistant(page);
  await expect(page.getByLabel("AI 助手").getByText("LLM 可用")).toBeVisible();
  await page.getByRole("button", { name: "识别组合风险" }).click();

  await expect(page.getByText("AAPL: 模拟组合风险研究结果。")).toBeVisible();
  await expect(page.getByText("LLM 已生成")).toBeVisible();
  await expect(page.getByText("必须经过人工审批。")).toBeVisible();
  await expect(page.getByText("多头观点", { exact: true })).toBeVisible();
  await expect(page.getByText("空头风险", { exact: true })).toBeVisible();
  await expect(page.getByText("风控提示", { exact: true })).toBeVisible();
});

test("AI sidecar shows local workflow when LLM is not configured", async ({ page }) => {
  await page.route("**/api/mvp/ai/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        langgraph: {
          available: true,
          mode: "research_workflow",
          message: "LangGraph is used for research workflow orchestration only."
        },
        research_llm: {
          provider: "openai_responses_or_chat_completions",
          mode: "research_only",
          configured: false,
          available: false,
          model: "gpt-5.5",
          base_url: "https://api.openai.com/v1",
          message: "OpenAI-compatible research LLM is not configured; set AI_STOCKS_OPENAI_API_KEY or OPENAI_API_KEY."
        },
        execution_path: {
          ai_generates_trade_intent: false,
          ai_influences_risk: false,
          ai_calls_execution: false
        }
      }
    });
  });
  await page.route("**/api/mvp/research", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "AAPL",
        status: "complete",
        summary: "AAPL: 本地规则研究结果。",
        bull_case: "已有证据支持继续观察。",
        bear_case: "估值仍需人工复核。",
        watch_items: ["复核 filing 趋势"],
        evidence_count: 2,
        trade_plan_draft: {
          entry_condition: "人工复核确认。",
          invalidation_condition: "证据失效。",
          risk_notes: ["这不是可直接执行的订单建议。"],
          requires_human_review: true
        }
      }
    });
  });

  await gotoDashboard(page);
  await openAiAssistant(page);

  const sidecar = page.getByRole("complementary", { name: "AI 助手" });
  await expect(sidecar.getByText("本地规则")).toBeVisible();
  await expect(sidecar.getByText("配置 OpenAI 后才会显示 LLM 已生成。")).toBeVisible();
  await page.getByRole("button", { name: "识别组合风险" }).click();

  await expect(sidecar.getByText("AAPL: 本地规则研究结果。")).toBeVisible();
  await expect(sidecar.locator(".sidecar-status")).toHaveText("本地规则");
});

test("AI sidecar collapses, expands, and keeps research actions usable", async ({ page }) => {
  let researchCallCount = 0;
  await page.route("**/api/mvp/ai/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        langgraph: {
          available: true,
          mode: "research_workflow",
          message: "LangGraph is used for research workflow orchestration only."
        },
        research_llm: {
          provider: "openai_responses_or_chat_completions",
          mode: "research_only",
          configured: false,
          available: false,
          model: "gpt-5.5",
          base_url: "https://api.openai.com/v1",
          message: "OpenAI-compatible research LLM is not configured."
        },
        execution_path: {
          ai_generates_trade_intent: false,
          ai_influences_risk: false,
          ai_calls_execution: false
        }
      }
    });
  });
  await page.route("**/api/mvp/research", async (route) => {
    researchCallCount += 1;
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "AAPL",
        status: "complete",
        summary: "AAPL: 收起展开后仍可用的研究结果。",
        bull_case: "服务收入韧性支持多头观点。",
        bear_case: "估值压缩仍是主要风险。",
        watch_items: ["复核 filing 趋势"],
        evidence_count: 2,
        trade_plan_draft: {
          entry_condition: "人工复核确认。",
          invalidation_condition: "证据失效。",
          risk_notes: ["这不是可直接执行的订单建议。"],
          requires_human_review: true
        }
      }
    });
  });

  await page.goto("/paper-trading");
  const sidecar = page.getByRole("complementary", { name: "AI 助手" });
  await expect(sidecar).toHaveClass(/collapsed/);
  await expect(page.getByRole("button", { name: "展开 AI 助手" })).toBeVisible();
  await expect(sidecar.getByRole("button", { name: "识别组合风险" })).not.toBeVisible();

  await page.getByRole("button", { name: "展开 AI 助手" }).click();
  await expect(sidecar).not.toHaveClass(/collapsed/);
  await sidecar.getByRole("button", { name: "识别组合风险" }).click();

  await expect(sidecar.getByText("AAPL: 收起展开后仍可用的研究结果。")).toBeVisible();
  expect(researchCallCount).toBe(1);

  await page.getByRole("button", { name: "收起 AI 助手" }).click();
  await expect(sidecar).toHaveClass(/collapsed/);
  await expect(sidecar.getByRole("button", { name: "识别组合风险" })).not.toBeVisible();
});

test("AI prompts wait for slower LLM research responses", async ({ page }) => {
  await page.route("**/api/mvp/research", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2200));
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "AAPL",
        status: "complete_llm",
        summary: "AAPL: 延迟返回的 LLM 研究结果。",
        bull_case: "真实 LLM 响应可以超过本地模板延迟。",
        bear_case: "仍需人工复核。",
        watch_items: ["检查响应延迟"],
        evidence_count: 1,
        trade_plan_draft: {
          entry_condition: "人工复核确认。",
          invalidation_condition: "证据失效。",
          risk_notes: ["必须经过人工审批。"],
          requires_human_review: true
        }
      }
    });
  });

  await gotoDashboard(page);
  await openAiAssistant(page);
  await page.getByRole("button", { name: "识别组合风险" }).click();

  await expect(page.getByText("AAPL: 延迟返回的 LLM 研究结果。")).toBeVisible({ timeout: 5000 });
  await expect(page.getByText("LLM 已生成", { exact: true })).toBeVisible();
});

test("AI research result can be saved as a note", async ({ page }) => {
  const savedRequest: { prompt?: string; result?: { ticker?: string } } = {};
  await page.route("**/api/mvp/research", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "AAPL",
        status: "complete",
        summary: "AAPL: 模拟组合风险研究结果。",
        bull_case: "服务收入韧性支持多头观点。",
        bear_case: "估值压缩仍是主要风险。",
        watch_items: ["复核 filing 趋势"],
        evidence_count: 2,
        trade_plan_draft: {
          entry_condition: "人工复核确认投资假设。",
          invalidation_condition: "新的 filing 与证据相矛盾。",
          risk_notes: ["必须经过人工审批。"],
          requires_human_review: true
        }
      }
    });
  });
  await page.route("**/api/mvp/research/notes", async (route) => {
    Object.assign(savedRequest, route.request().postDataJSON() as { prompt?: string; result?: { ticker?: string } });
    await route.fulfill({
      contentType: "application/json",
      json: {
        ai_run_id: "run-aapl",
        note: {
          id: "note-aapl",
          ticker: "AAPL",
          title: "AI 研究 - AAPL - 识别组合风险",
          body: "AAPL: 模拟组合风险研究结果。",
          created_at: "2026-06-13T00:00:00Z"
        }
      }
    });
  });

  await gotoDashboard(page);
  await openAiAssistant(page);
  await page.getByRole("button", { name: "识别组合风险" }).click();
  await page.getByRole("button", { name: "保存为笔记" }).click();

  expect(savedRequest.prompt).toBe("识别组合风险");
  expect(savedRequest.result?.ticker).toBe("AAPL");
  await expect(page.getByText("已保存到研究笔记")).toBeVisible();
  await expect(page.getByText("AI 研究 - AAPL - 识别组合风险")).toBeVisible();
});

test("AI prompts fall back when the research API fails", async ({ page }) => {
  await page.route("**/api/mvp/research", async (route) => {
    await route.abort();
  });

  await gotoDashboard(page);
  await openAiAssistant(page);
  await page.getByRole("button", { name: "识别组合风险" }).click();

  await expect(page.getByText(/本地 API 暂不可用/)).toBeVisible({ timeout: 4000 });
});

test("settings renders data source status", async ({ page }) => {
  await page.route("**/api/mvp/data-sources/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        provider_mode: "hybrid",
        data_sources: [
          {
            name: "Mock",
            mode: "mock",
            available: true,
            message: "Deterministic local fallback data is available.",
            checked_at: "2026-06-12T00:00:00Z",
            version: "local"
          },
          {
            name: "SEC EDGAR",
            mode: "sec_edgar",
            available: true,
            message: "SEC submissions adapter is configured.",
            checked_at: "2026-06-12T00:00:00Z",
            version: "data.sec.gov"
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/ai/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        langgraph: {
          available: true,
          mode: "research_workflow",
          message: "LangGraph is used for research workflow orchestration only."
        },
        research_llm: {
          provider: "openai_responses_or_chat_completions",
          mode: "research_only",
          configured: true,
          available: true,
          model: "gpt-5.5",
          base_url: "https://api.openai.com/v1",
          message: "OpenAI-compatible research LLM is configured for research explanations only."
        },
        execution_path: {
          ai_generates_trade_intent: false,
          ai_influences_risk: false,
          ai_calls_execution: false
        }
      }
    });
  });
  let runtimeSettings: RuntimeSettingsPayload = {
    source: "defaults",
    data_mode: "hybrid",
    lean_backtest_timeout_seconds: 600,
    paper_scheduler_enabled: true,
    paper_scheduler_cron: "30 6 * * *",
    paper_scheduler_timezone: "Asia/Shanghai",
    event_bus_mode: "redis",
    redis_stream_name: "trading:events",
    redis_configured: true,
    openai_research_enabled: true,
    openai_research_model: "gpt-5.5",
    openai_base_url: "https://api.openai.com/v1",
    openai_timeout_seconds: 20,
    openai_api_key_configured: false,
    openai_api_key_source: null,
    sec_user_agent: "VelaQuant research app contact@example.com"
  };
  let lastRuntimeUpdate: Record<string, unknown> | null = null;
  await page.route("**/api/mvp/runtime-settings", async (route) => {
    if (route.request().method() === "PUT") {
      const update = route.request().postDataJSON() as Partial<RuntimeSettingsUpdatePayload>;
      lastRuntimeUpdate = update;
      runtimeSettings = { ...runtimeSettings, ...update, source: "database" };
      if (typeof update.openai_api_key === "string" && update.openai_api_key.length > 0) {
        runtimeSettings.openai_api_key_configured = true;
        runtimeSettings.openai_api_key_source = "runtime_database";
      }
    }
    await route.fulfill({
      contentType: "application/json",
      json: runtimeSettings
    });
  });

  await page.goto("/settings");

  const firstSettingsSurface = page.locator(".module-stack > *").first();
  await expect(firstSettingsSurface.getByRole("heading", { name: "运行配置" })).toBeVisible();

  const dataSourcePanel = page.getByLabel("数据源状态");
  await expect(dataSourcePanel.getByRole("heading", { name: "数据源状态" })).toBeVisible();
  await expect(dataSourcePanel.getByText("hybrid", { exact: true })).toBeVisible();
  await expect(dataSourcePanel.getByText("SEC EDGAR", { exact: true })).toBeVisible();
  await expect(dataSourcePanel.getByText("Deterministic local fallback data is available.")).toBeVisible();
  await expect(dataSourcePanel.getByText("SEC submissions adapter is configured.")).toBeVisible();
  await expect(dataSourcePanel.getByText("data.sec.gov")).toBeVisible();
  const aiStatusPanel = page.getByLabel("AI / LLM 状态");
  await expect(aiStatusPanel.getByRole("heading", { name: "AI / LLM 状态" })).toBeVisible();
  await expect(aiStatusPanel.getByText("LangGraph", { exact: true })).toBeVisible();
  await expect(aiStatusPanel.getByText("OpenAI-compatible LLM", { exact: true })).toBeVisible();
  await expect(aiStatusPanel.getByText("gpt-5.5")).toBeVisible();
  await expect(aiStatusPanel.getByText("AI 不进入交易执行链", { exact: true })).toBeVisible();
  const runtimeSettingsPanel = page.getByLabel("运行配置");
  await expect(runtimeSettingsPanel.getByRole("heading", { name: "运行配置" })).toBeVisible();
  await expect(runtimeSettingsPanel.getByText("API Key", { exact: true })).toBeVisible();
  await expect(runtimeSettingsPanel.getByText("未配置", { exact: true })).toBeVisible();
  await expect(runtimeSettingsPanel.getByLabel("数据模式")).toHaveValue("hybrid");
  await expect(runtimeSettingsPanel.getByLabel("LEAN 超时秒数")).toHaveValue("600");
  await expect(runtimeSettingsPanel.getByText("每日调度")).toBeVisible();
  await expect(runtimeSettingsPanel.getByText("30 6 * * * · Asia/Shanghai")).toBeVisible();
  await expect(runtimeSettingsPanel.getByText("Event Bus")).toBeVisible();
  await expect(runtimeSettingsPanel.getByText("redis · trading:events")).toBeVisible();
  await expect(runtimeSettingsPanel.getByLabel("模型")).toHaveValue("gpt-5.5");
  const openaiKeyInput = runtimeSettingsPanel.getByRole("textbox", { name: "OpenAI API Key" });
  await expect(openaiKeyInput).toHaveValue("");
  await expect(runtimeSettingsPanel.getByLabel("SEC User-Agent")).toHaveValue("VelaQuant research app contact@example.com");
  await runtimeSettingsPanel.getByLabel("数据模式").selectOption("openbb_optional");
  await runtimeSettingsPanel.getByLabel("LEAN 超时秒数").fill("900");
  await runtimeSettingsPanel.getByLabel("模型").fill("gpt-5.4");
  await runtimeSettingsPanel.getByLabel("Base URL").fill("https://api.openai.example/v1");
  await runtimeSettingsPanel.getByLabel("OpenAI 超时秒数").fill("15");
  await openaiKeyInput.fill("sk-runtime-test");
  await runtimeSettingsPanel.getByLabel("SEC User-Agent").fill("VelaQuant prod ops@example.com");
  await runtimeSettingsPanel.getByRole("button", { name: "保存设置" }).click();
  await expect(runtimeSettingsPanel.locator("form").getByText("已保存", { exact: true })).toBeVisible();
  await expect(runtimeSettingsPanel.getByLabel("数据模式")).toHaveValue("openbb_optional");
  await expect(runtimeSettingsPanel.getByLabel("LEAN 超时秒数")).toHaveValue("900");
  await expect(runtimeSettingsPanel.getByText("runtime_database")).toBeVisible();
  await expect(openaiKeyInput).toHaveValue("");
  expect(lastRuntimeUpdate).toMatchObject({
    openai_api_key: "sk-runtime-test",
    sec_user_agent: "VelaQuant prod ops@example.com"
  });
});

test("strategy lab renders readiness status", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: false,
        summary: "Strategy Lab is partially configured; review unavailable tools before running LEAN backtests.",
        tools: [
          {
            name: "Docker CLI",
            available: true,
            version: "Docker version 29.5.3",
            message: "Docker CLI is available."
          },
          {
            name: "LEAN CLI",
            available: false,
            version: null,
            message: "LEAN CLI is not installed or is not on PATH."
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/evaluation", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategy_id: "deterministic_watchlist_v1",
        strategy_name: "Deterministic Watchlist Strategy",
        sample_size: 21,
        filled_order_count: 21,
        rejected_order_count: 1,
        closed_trade_count: 5,
        signal_precision: 0.7143,
        expectancy: 4.2,
        max_drawdown: 0.08,
        stability_score: 0.69,
        readiness: "watch",
        promotion_gate: "keep_paper_running",
        event_chain_count: 80,
        notes: "策略已有正期望迹象，但样本数或回撤约束仍需继续观察。"
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/attribution", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategy_id: "deterministic_watchlist_v1",
        strategy_name: "Deterministic Watchlist Strategy",
        signal_quality: {
          market_event_count: 12,
          trade_intent_count: 6,
          actionable_signal_rate: 0.5,
          average_confidence: 0.72,
          false_positive_rate: 0.25
        },
        expectancy_decomposition: {
          realized_pnl: 80,
          unrealized_pnl: -20,
          closed_trade_component: 80,
          open_trade_component: -20,
          total_observed_pnl: 60,
          components: [
            { name: "trend_component", value: 0, basis: "环境代理。" },
            { name: "volatility_component", value: 12, basis: "高波动市场贡献。" },
            { name: "timing_component", value: -20, basis: "开放持仓浮亏。" },
            { name: "risk_component", value: -1, basis: "风控摩擦。" },
            { name: "noise_component", value: -20, basis: "信号噪声。" }
          ]
        },
        ticker_diagnostics: [
          {
            ticker: "NVDA",
            market_event_count: 8,
            trade_intent_count: 4,
            candidate_score_count: 2,
            average_candidate_score: 0.74,
            latest_candidate_score: 0.82,
            score_pnl_alignment: "aligned",
            filled_order_count: 3,
            false_positive_count: 1,
            false_positive_rate: 0.3333,
            average_confidence: 0.74,
            realized_pnl: 80,
            unrealized_pnl: -20,
            observed_pnl: 60
          }
        ],
        signal_decay: {
          threshold_days: 5,
          open_position_count: 2,
          stale_open_position_count: 1,
          stale_tickers: ["NVDA"],
          average_holding_days: 6.5,
          basis: "开放持仓超过 5 天。"
        },
        regime: {
          regime: "drawdown_pressure",
          basis: "复盘权益曲线从峰值回撤超过 10%。",
          review_count: 5,
          equity_change: -0.04
        },
        regime_breakdown: {
          primary_regime: "trend_market",
          items: [
            {
              regime: "trend_market",
              ticker_count: 1,
              observed_pnl: 60,
              average_return: 0.08,
              average_volatility: 0.01,
              sample_count: 2,
              sharpe_proxy: 3.2,
              tickers: ["NVDA"],
              basis: "趋势市场表现。"
            },
            {
              regime: "range_market",
              ticker_count: 0,
              observed_pnl: 0,
              average_return: 0,
              average_volatility: 0,
              sample_count: 0,
              sharpe_proxy: 0,
              tickers: [],
              basis: "震荡市场表现。"
            },
            {
              regime: "high_volatility",
              ticker_count: 0,
              observed_pnl: 0,
              average_return: 0,
              average_volatility: 0,
              sample_count: 0,
              sharpe_proxy: 0,
              tickers: [],
              basis: "高波动市场表现。"
            },
            {
              regime: "insufficient_data",
              ticker_count: 0,
              observed_pnl: 0,
              average_return: 0,
              average_volatility: 0,
              sample_count: 0,
              sharpe_proxy: 0,
              tickers: [],
              basis: "行情不足。"
            }
          ],
          basis: "按行情历史拆分。"
        },
        drawdown: {
          source: "open_position_pressure",
          max_drawdown: 0.1161,
          basis: "开放头寸浮亏。",
          contributors: [
            { name: "market_driven", value: 0.1161, basis: "权益曲线回撤。" },
            { name: "signal_failure", value: -20, basis: "负盈亏。" },
            { name: "execution_lag", value: 0, basis: "同步执行。" },
            { name: "risk_overreach", value: 1, basis: "风控拒单。" }
          ]
        },
        data_quality_warnings: ["market_regime_is_proxy"],
        summary: "可行动信号率 50.00%，误报率 25.00%。"
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/registry", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        active_strategy_id: "deterministic_watchlist_v1",
        entries: [
          {
            strategy_id: "deterministic_watchlist_v1",
            name: "Deterministic Watchlist Strategy",
            version: "v1",
            source: "paper_core",
            execution_mode: "paper",
            status: "active",
            rank: 1,
            ranking_score: 74,
            readiness: "watch",
            promotion_gate: "keep_paper_running",
            sample_size: 21,
            filled_order_count: 21,
            observed_pnl: 60,
            primary_regime: "trend_market",
            signal_quality_score: 0.5,
            backtest_status: null,
            supports_live: false,
            supports_hot_swap: false,
            notes: "fixture"
          },
          {
            strategy_id: "moving_average_cross",
            name: "MovingAverageCross",
            version: "catalog",
            source: "lean_catalog",
            execution_mode: "backtest",
            status: "available",
            rank: 2,
            ranking_score: 0,
            readiness: "backtest_only",
            promotion_gate: "not_connected_to_paper_runtime",
            sample_size: 0,
            filled_order_count: 0,
            observed_pnl: 0,
            primary_regime: "backtest_only",
            signal_quality_score: 0,
            backtest_status: "failed",
            supports_live: false,
            supports_hot_swap: false,
            notes: "fixture"
          }
        ],
        missing_capabilities: [
          "strategy_versioning_persistence",
          "multi_strategy_parallel_runtime",
          "strategy_competition_runtime",
          "hot_swap_execution_binding",
          "automatic_lifecycle_actions"
        ],
        summary: "Registry is read-only: 1 active paper strategy, 1 backtest catalog strategy, no lifecycle automation."
      }
    });
  });
  let strategyCompetition: StrategyCompetitionPayload = {
    trading_day: "2026-06-14",
    status: "allocation_ready",
    active_strategy_id: "deterministic_watchlist_v1",
    selected_strategy_id: "deterministic_watchlist_v1",
    strategy_count: 2,
    allocatable_strategy_count: 1,
    competition_ready: false,
    entries: [
      {
        strategy_id: "deterministic_watchlist_v1",
        name: "Deterministic Watchlist Strategy",
        version: "v1",
        source: "paper_core",
        execution_mode: "paper",
        status: "active",
        rank: 1,
        ranking_score: 80,
        allocation_weight: 1,
        eligible_for_allocation: true,
        recommended_action: "allocate_paper_capital",
        blockers: [],
        readiness: "paper_ready",
        promotion_gate: "eligible_for_shadow",
        sample_size: 42,
        filled_order_count: 40,
        filled_order_remaining: 0,
        observed_pnl: 125,
        primary_regime: "range_market",
        signal_quality_score: 0.7,
        supports_live: false,
        supports_hot_swap: true
      },
      {
        strategy_id: "moving_average_cross",
        name: "MovingAverageCross",
        version: "catalog",
        source: "lean_catalog",
        execution_mode: "backtest",
        status: "available",
        rank: 2,
        ranking_score: 0,
        allocation_weight: 0,
        eligible_for_allocation: false,
        recommended_action: "keep_in_lab",
        blockers: ["not_connected_to_paper_runtime"],
        readiness: "backtest_only",
        promotion_gate: "not_connected_to_paper_runtime",
        sample_size: 0,
        filled_order_count: 0,
        filled_order_remaining: 30,
        observed_pnl: 0,
        primary_regime: "backtest_only",
        signal_quality_score: 0,
        supports_live: false,
        supports_hot_swap: false
      }
    ],
    summary: "Strategy competition fixture."
  };
  await page.route("**/api/mvp/strategy-lab/competition", async (route) => {
    await route.fulfill({ contentType: "application/json", json: strategyCompetition });
  });
  await page.route("**/api/mvp/strategy-lab/competition/snapshot", async (route) => {
    expect(route.request().method()).toBe("POST");
    await route.fulfill({
      contentType: "application/json",
      json: {
        ...strategyCompetition,
        id: "competition-snapshot-1",
        team_id: "team-1",
        created_at: "2026-06-14T00:00:00+00:00",
        updated_at: "2026-06-14T00:00:00+00:00"
      }
    });
  });
  const strategyCompetitionHistory: StrategyCompetitionSnapshotHistoryPayload = {
    snapshot_count: 1,
    latest: {
      ...strategyCompetition,
      id: "competition-snapshot-1",
      team_id: "team-1",
      created_at: "2026-06-14T00:00:00+00:00",
      updated_at: "2026-06-14T00:00:00+00:00"
    },
    items: [
      {
        ...strategyCompetition,
        id: "competition-snapshot-1",
        team_id: "team-1",
        created_at: "2026-06-14T00:00:00+00:00",
        updated_at: "2026-06-14T00:00:00+00:00"
      }
    ],
    summary: "Strategy competition snapshots: 1 days recorded, latest selected strategy deterministic_watchlist_v1."
  };
  await page.route("**/api/mvp/strategy-lab/competition/snapshots", async (route) => {
    await route.fulfill({ contentType: "application/json", json: strategyCompetitionHistory });
  });
  let lifecycle = {
    strategy_id: "deterministic_watchlist_v1",
    strategy_name: "Deterministic Watchlist Strategy",
    current_stage: "shadow",
    recommended_stage: "shadow",
    recommended_action: "hold_current_stage",
    gate_status: "watch",
    promotion_gate: "keep_paper_running",
    can_promote: false,
    can_kill: false,
    auto_actions_enabled: false,
    rules: [
      {
        name: "minimum_filled_orders",
        passed: false,
        severity: "blocker",
        actual: "21 filled orders",
        required: ">= 30 filled orders",
        message: "More filled orders required."
      },
      {
        name: "positive_expectancy",
        passed: true,
        severity: "blocker",
        actual: "4.20",
        required: "> 0.00 expectancy",
        message: "Positive expectancy."
      },
      {
        name: "drawdown_limit",
        passed: true,
        severity: "blocker",
        actual: "8.00%",
        required: "<= 15.00%",
        message: "Drawdown is acceptable."
      },
      {
        name: "event_ledger_populated",
        passed: true,
        severity: "blocker",
        actual: "80 chains",
        required: "> 0 chains",
        message: "Event ledger has replayable trade chains."
      },
      {
        name: "closed_trade_sample",
        passed: false,
        severity: "blocker",
        actual: "5 closed trades",
        required: ">= 10 closed trades",
        message: "More closed trades required."
      },
      {
        name: "alpha_validation_ready",
        passed: false,
        severity: "blocker",
        actual: "not ready",
        required: "paper alpha validation passed",
        message: "Alpha validation is not ready."
      }
    ],
    missing_capabilities: [
      "lifecycle_state_persistence",
      "manual_promotion_approval",
      "shadow_account_adapter",
      "live_small_account_adapter",
      "kill_switch_audit_trail"
    ],
    summary: "Strategy is in Shadow but paper alpha validation is still collecting evidence."
  };
  await page.route("**/api/mvp/strategy-lab/lifecycle", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: lifecycle
    });
  });
  let lifecycleAudit: StrategyLifecycleAuditPayload = {
    strategy_id: "deterministic_watchlist_v1",
    items: [
      {
        id: "lifecycle-audit-1",
        action: "strategy_shadow_approved",
        entity_type: "strategy",
        entity_id: "deterministic_watchlist_v1",
        approved_by: "operator",
        reason: "Paper gates reviewed.",
        previous_stage: "paper",
        current_stage: "shadow",
        auto_promotion_enabled: false,
        created_at: "2026-06-13T00:00:00Z"
      }
    ],
    summary: "1 lifecycle audit entries recorded for this strategy."
  };
  await page.route("**/api/mvp/strategy-lab/lifecycle/audit", async (route) => {
    await route.fulfill({ contentType: "application/json", json: lifecycleAudit });
  });
  let systemReadiness: TradingSystemReadinessPayload = {
    status: "blocked",
    scheduler_running: true,
    scheduler_next_run_at: "2026-06-14T06:30:00+08:00",
    lifecycle_stage: "shadow",
    alpha_ready: false,
    event_bus_mode: "redis",
    event_bus_ready: true,
    event_bus_stream_length: 42,
    event_ledger_replay_ready: true,
    event_ledger_traceable_chain_count: 80,
    event_ledger_complete_order_chain_count: 80,
    event_ledger_broken_chain_count: 0,
    event_ledger_traceability_ratio: 1,
    shadow_can_record: true,
    shadow_remaining_observations: 4,
    live_small_review_ready: false,
    live_or_broker_execution_enabled: false,
    manual_override_isolated: true,
    manual_override_order_count: 2,
    manual_override_event_chain_count: 2,
    alpha_filtered_event_chain_count: 80,
    blockers: ["lifecycle_stage_ahead_of_alpha_validation"],
    pending_gates: ["paper_alpha_validation", "shadow_validation_sample", "live_small_manual_review"],
    summary: "Trading system readiness is blocked by lifecycle_stage_ahead_of_alpha_validation."
  };
  await page.route("**/api/mvp/strategy-lab/system-readiness", async (route) => {
    await route.fulfill({ contentType: "application/json", json: systemReadiness });
  });
  await page.route("**/api/mvp/strategy-lab/lifecycle/reconcile", async (route) => {
    expect(route.request().method()).toBe("POST");
    lifecycle = {
      ...lifecycle,
      current_stage: "paper",
      recommended_stage: "paper",
      recommended_action: "keep_paper_running",
      summary: "Positive expectancy is emerging, but paper-stage gates still need more evidence."
    };
    systemReadiness = {
      ...systemReadiness,
      status: "attention",
      lifecycle_stage: "paper",
      blockers: [],
      pending_gates: [
        "paper_alpha_validation",
        "shadow_stage",
        "shadow_validation_sample",
        "live_small_manual_review"
      ],
      summary:
        "Trading system is operational for controlled daily runs; pending gates: paper_alpha_validation, shadow_stage, shadow_validation_sample, live_small_manual_review."
    };
    lifecycleAudit = {
      strategy_id: "deterministic_watchlist_v1",
      items: [
        {
          id: "lifecycle-audit-2",
          action: "strategy_lifecycle_reconciled",
          entity_type: "strategy",
          entity_id: "deterministic_watchlist_v1",
          approved_by: "system_reconcile",
          reason: "Alpha validation is not ready.",
          previous_stage: "shadow",
          current_stage: "paper",
          auto_promotion_enabled: false,
          execution_enabled: false,
          created_at: "2026-06-13T00:05:00Z"
        },
        ...lifecycleAudit.items
      ],
      summary: "2 lifecycle audit entries recorded for this strategy."
    };
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategy_id: "deterministic_watchlist_v1",
        previous_stage: "shadow",
        current_stage: "paper",
        reconciled: true,
        reconciled_by: "system_reconcile",
        reason: "Alpha validation is not ready.",
        alpha_ready: false,
        auto_promotion_enabled: false,
        execution_enabled: false,
        summary: "Strategy deterministic_watchlist_v1 reconciled from shadow to paper."
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/alpha-validation", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategy_id: "deterministic_watchlist_v1",
        alpha_ready: false,
        validation_level: "collecting",
        blockers: ["consecutive_positive_expectancy", "closed_trade_sample"],
        has_real_market_backtest: false,
        review_day_count: 3,
        consecutive_positive_expectancy_days: 1,
        filled_order_count: 21,
        closed_trade_count: 5,
        event_chain_count: 80,
        latest_expectancy: 4.2,
        average_expectancy: 1.7,
        max_drawdown: 0.08,
        summary: "Paper alpha validation is collecting evidence."
      }
    });
  });
  const alphaSnapshot: AlphaValidationSnapshotPayload = {
    id: "alpha-snapshot-1",
    team_id: "team-1",
    strategy_id: "deterministic_watchlist_v1",
    trading_day: "2026-06-14",
    alpha_ready: false,
    validation_level: "collecting",
    blockers: ["closed_trade_sample"],
    has_real_market_backtest: true,
    review_day_count: 3,
    consecutive_positive_expectancy_days: 1,
    filled_order_count: 21,
    closed_trade_count: 5,
    event_chain_count: 80,
    latest_expectancy: 4.2,
    average_expectancy: 1.7,
    max_drawdown: 0.08,
    created_at: "2026-06-14T00:00:00+00:00",
    updated_at: "2026-06-14T00:00:00+00:00"
  };
  let alphaSnapshotHistory: AlphaValidationSnapshotHistoryPayload = {
    strategy_id: "deterministic_watchlist_v1",
    snapshot_count: 1,
    ready_snapshot_count: 0,
    positive_expectancy_snapshot_count: 1,
    positive_expectancy_streak: 2,
    ready_streak: 0,
    latest_blockers: ["closed_trade_sample"],
    blocker_counts: [
      { blocker: "closed_trade_sample", count: 2 },
      { blocker: "filled_order_sample", count: 1 }
    ],
    latest: alphaSnapshot,
    items: [alphaSnapshot],
    summary: "Alpha validation snapshots: 1 days recorded, 1 positive-expectancy days, 0 ready days."
  };
  await page.route("**/api/mvp/strategy-lab/alpha-snapshots**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: alphaSnapshotHistory });
  });
  await page.route("**/api/mvp/strategy-lab/alpha-snapshots/record", async (route) => {
    expect(route.request().method()).toBe("POST");
    alphaSnapshotHistory = {
      ...alphaSnapshotHistory,
      latest: alphaSnapshot,
      items: [alphaSnapshot],
      summary: "Alpha validation snapshots: 1 days recorded, 1 positive-expectancy days, 0 ready days."
    };
    await route.fulfill({ contentType: "application/json", json: alphaSnapshot });
  });
  const shadowReview: ShadowReviewPayload = {
    status: "blocked",
    strategy_id: "deterministic_watchlist_v1",
    can_request_shadow_review: false,
    recommended_stage: "paper",
    auto_promotion_enabled: false,
    checklist: [
      {
        code: "alpha_gates_passed",
        label: "Alpha 门禁通过",
        passed: false,
        evidence: ["Alpha gate progress: 7/9 gates passed."]
      },
      {
        code: "event_ledger_replayable",
        label: "事件账本可回放",
        passed: true,
        evidence: ["80 events"]
      }
    ],
    residual_risks: [
      {
        code: "paper_to_shadow_gap",
        severity: "info",
        detail: "模拟盘门禁通过只允许进入 Shadow 人工评审，不代表可以实盘交易。",
        evidence: ["auto_promotion_enabled=false"]
      }
    ],
    summary: "Shadow review packet is blocked; continue paper validation before manual review."
  };
  await page.route("**/api/mvp/strategy-lab/shadow-review", async (route) => {
    await route.fulfill({ contentType: "application/json", json: shadowReview });
  });
  const shadowObservation: ShadowObservationPayload = {
    id: "shadow-observation-1",
    team_id: "team-1",
    strategy_id: "deterministic_watchlist_v1",
    trading_day: "2026-06-30",
    status: "observing",
    can_request_shadow_review: true,
    observed_intent_count: 6,
    would_route_order_count: 6,
    event_chain_count: 6,
    residual_risk_count: 2,
    blocked_reason: null,
    created_at: "2026-06-13T00:00:00Z"
  };
  let shadowObservationSummary: ShadowObservationSummaryPayload = {
    can_record_shadow_observation: true,
    latest: null,
    items: [],
    summary: "No shadow observations have been recorded yet."
  };
  let shadowValidation: ShadowValidationPayload = {
    strategy_id: "deterministic_watchlist_v1",
    shadow_ready: false,
    status: "collecting",
    observation_count: 0,
    observing_count: 0,
    blocked_count: 0,
    latest_trading_day: null,
    min_observations_required: 5,
    remaining_observations: 5,
    residual_risk_count: 0,
    blockers: ["shadow_observation_sample"],
    summary: "Shadow validation is collecting observations; 5 more observing samples required."
  };
  await page.route("**/api/mvp/strategy-lab/shadow-observations", async (route) => {
    await route.fulfill({ contentType: "application/json", json: shadowObservationSummary });
  });
  let shadowObservationHealth: ShadowObservationHealthPayload = {
    strategy_id: "deterministic_watchlist_v1",
    status: "collecting",
    sample_ready: false,
    observation_count: 0,
    observing_count: 0,
    blocked_count: 0,
    consecutive_observing_count: 0,
    latest_trading_day: null,
    average_would_route_order_count: 0,
    average_event_chain_count: 0,
    average_residual_risk_count: 0,
    warnings: ["sample_not_ready"],
    summary: "Shadow observation health is collecting samples; 0/5 observations recorded."
  };
  await page.route("**/api/mvp/strategy-lab/shadow-observation-health", async (route) => {
    await route.fulfill({ contentType: "application/json", json: shadowObservationHealth });
  });
  await page.route("**/api/mvp/strategy-lab/shadow-validation", async (route) => {
    await route.fulfill({ contentType: "application/json", json: shadowValidation });
  });
  let shadowDailyReport: ShadowDailyReportPayload = {
    strategy_id: "deterministic_watchlist_v1",
    trading_day: null,
    status: "collecting",
    observation_status: "not_recorded",
    health_status: "collecting",
    validation_status: "collecting",
    live_small_status: "blocked",
    observed_intent_count: 0,
    would_route_order_count: 0,
    event_chain_count: 0,
    residual_risk_count: 0,
    remaining_observations: 5,
    warnings: ["sample_not_ready"],
    blockers: ["shadow_observation_sample"],
    next_actions: [
      {
        priority: 1,
        action_code: "record_shadow_observation",
        title: "记录 Shadow 观察",
        detail: "当前没有 Shadow 观察记录；先记录一条观察样本，再进入健康与验证判断。",
        evidence: ["No shadow observations have been recorded yet."]
      }
    ],
    live_or_broker_execution_enabled: false,
    summary: "Shadow daily report is waiting for the first observation record."
  };
  await page.route("**/api/mvp/strategy-lab/shadow-daily-report", async (route) => {
    await route.fulfill({ contentType: "application/json", json: shadowDailyReport });
  });
  const liveSmallReview: LiveSmallReviewPayload = {
    status: "blocked",
    strategy_id: "deterministic_watchlist_v1",
    can_request_live_small_review: false,
    recommended_stage: "shadow",
    auto_promotion_enabled: false,
    checklist: [
      {
        code: "current_stage_shadow",
        label: "当前处于 Shadow",
        passed: false,
        evidence: ["current_stage=paper", "manual shadow approval required before live-small review"]
      },
      {
        code: "shadow_validation_passed",
        label: "Shadow 验证通过",
        passed: false,
        evidence: ["Shadow validation is collecting observations; 4 more observing samples required."]
      },
      {
        code: "shadow_health_stable",
        label: "Shadow 健康稳定",
        passed: false,
        evidence: ["Shadow observation health is collecting samples; 1/5 observations recorded."]
      }
    ],
    residual_risks: [
      {
        code: "live_small_requires_separate_manual_approval",
        severity: "info",
        detail: "Live-small 只能作为人工评审结论，不能由系统自动晋级或自动实盘下单。",
        evidence: ["auto_promotion_enabled=false"]
      }
    ],
    summary: "Live-small review packet is blocked; remain in Shadow or paper workflow until all gates pass."
  };
  await page.route("**/api/mvp/strategy-lab/live-small-review", async (route) => {
    await route.fulfill({ contentType: "application/json", json: liveSmallReview });
  });
  await page.route("**/api/mvp/strategy-lab/shadow-observations/record", async (route) => {
    expect(route.request().method()).toBe("POST");
    shadowObservationSummary = {
      can_record_shadow_observation: true,
      latest: shadowObservation,
      items: [shadowObservation],
      summary: "Shadow observation latest observing on 2026-06-30; 1 observations recorded, no broker orders created."
    };
    shadowValidation = {
      strategy_id: "deterministic_watchlist_v1",
      shadow_ready: false,
      status: "collecting",
      observation_count: 1,
      observing_count: 1,
      blocked_count: 0,
      latest_trading_day: "2026-06-30",
      min_observations_required: 5,
      remaining_observations: 4,
      residual_risk_count: 2,
      blockers: ["shadow_observation_sample"],
      summary: "Shadow validation is collecting observations; 4 more observing samples required."
    };
    shadowObservationHealth = {
      strategy_id: "deterministic_watchlist_v1",
      status: "collecting",
      sample_ready: false,
      observation_count: 1,
      observing_count: 1,
      blocked_count: 0,
      consecutive_observing_count: 1,
      latest_trading_day: "2026-06-30",
      average_would_route_order_count: 2,
      average_event_chain_count: 6,
      average_residual_risk_count: 2,
      warnings: ["sample_not_ready"],
      summary: "Shadow observation health is collecting samples; 1/5 observations recorded."
    };
    shadowDailyReport = {
      strategy_id: "deterministic_watchlist_v1",
      trading_day: "2026-06-30",
      status: "collecting",
      observation_status: "observing",
      health_status: "collecting",
      validation_status: "collecting",
      live_small_status: "blocked",
      observed_intent_count: 6,
      would_route_order_count: 2,
      event_chain_count: 6,
      residual_risk_count: 2,
      remaining_observations: 4,
      warnings: ["sample_not_ready"],
      blockers: ["shadow_observation_sample"],
      next_actions: [
        {
          priority: 1,
          action_code: "continue_shadow_observation",
          title: "继续记录 Shadow 观察",
          detail: "还需要 4 条 observing 样本，保持 broker 执行关闭。",
          evidence: ["Shadow validation is collecting observations; 4 more observing samples required."]
        }
      ],
      live_or_broker_execution_enabled: false,
      summary: "Shadow daily report is collecting observations; 4 more samples required."
    };
    await route.fulfill({ contentType: "application/json", json: shadowObservation });
  });

  await gotoDashboard(page);
  await page.getByRole("link", { name: "策略实验室" }).click();

  await expect(page).toHaveURL("/strategy-lab");
  await expect(page.getByRole("heading", { name: "策略实验室" })).toBeVisible();
  const statusPanel = page.getByRole("region", { name: "策略实验室状态" });
  await expect(
    statusPanel.getByText("Strategy Lab is partially configured; review unavailable tools before running LEAN backtests.")
  ).toBeVisible();
  await expect(statusPanel.getByText("Docker CLI", { exact: true })).toBeVisible();
  await expect(statusPanel.getByText("Docker version 29.5.3")).toBeVisible();
  await expect(statusPanel.getByText("LEAN CLI", { exact: true })).toBeVisible();
  await expect(statusPanel.getByText("LEAN CLI is not installed or is not on PATH.")).toBeVisible();
  await expect(page.getByText("不可回测")).toBeVisible();
  const readinessPanel = page.getByRole("region", { name: "交易系统运行态" });
  await expect(readinessPanel.getByText("blocked", { exact: true })).toBeVisible();
  await expect(readinessPanel.getByText("定时任务 运行中")).toBeVisible();
  await expect(readinessPanel.getByText("生命周期 shadow")).toBeVisible();
  await expect(readinessPanel.getByText("lifecycle_stage_ahead_of_alpha_validation", { exact: true })).toBeVisible();
  await readinessPanel.getByRole("button", { name: "纠偏到 Paper" }).click();
  await expect(readinessPanel.getByText("attention", { exact: true })).toBeVisible();
  await expect(readinessPanel.getByText("生命周期 paper")).toBeVisible();
  await expect(readinessPanel.getByText("lifecycle_stage_ahead_of_alpha_validation", { exact: true })).not.toBeVisible();
  await expect(readinessPanel.getByText("Event Bus redis")).toBeVisible();
  await expect(readinessPanel.getByText("Redis stream 42 events")).toBeVisible();
  await expect(readinessPanel.getByText("事件链完整率 100%")).toBeVisible();
  await expect(readinessPanel.getByText("完整链 80 · 断链 0 · 可追溯链 80")).toBeVisible();
  await expect(readinessPanel.getByText("Shadow 剩余 4")).toBeVisible();
  await expect(readinessPanel.getByText("手工覆盖 已隔离")).toBeVisible();
  await expect(readinessPanel.getByText("手工订单 2 · 手工链 2 · Alpha 链 80")).toBeVisible();
  await expect(readinessPanel.getByText("shadow_validation_sample", { exact: true })).toBeVisible();
  const alphaPanel = page.getByRole("region", { name: "Alpha 验证" });
  await expect(alphaPanel.getByText("collecting", { exact: true })).toBeVisible();
  await expect(alphaPanel.getByText("样本 21", { exact: true })).toBeVisible();
  await expect(alphaPanel.getByText("信号精度 71.43%")).toBeVisible();
  await expect(alphaPanel.getByText("最大回撤 8.00%")).toBeVisible();
  await expect(alphaPanel.getByText("keep_paper_running")).toBeVisible();
  await expect(alphaPanel.getByText("连续正期望 1 / 5 天")).toBeVisible();
  await expect(alphaPanel.getByText("验证阻断 consecutive_positive_expectancy / closed_trade_sample")).toBeVisible();
  await expect(alphaPanel.getByText("真实历史回测", { exact: true })).toBeVisible();
  await expect(alphaPanel.getByText("Alpha gate 需要至少一次同策略真实历史回测。")).toBeVisible();
  await expect(alphaPanel.getByText("快照账本 1 天")).toBeVisible();
  await expect(alphaPanel.getByText("正期望 1 · Ready 0 · 最新 2026-06-14")).toBeVisible();
  await expect(alphaPanel.getByText("连续正期望 2 天 · 连续 Ready 0 天")).toBeVisible();
  await expect(alphaPanel.getByText("主要阻断 closed_trade_sample ×2")).toBeVisible();
  await alphaPanel.getByRole("button", { name: "记录快照" }).click();
  await expect(alphaPanel.getByText("已记录 2026-06-14 Alpha 快照")).toBeVisible();
  const registryPanel = page.getByRole("region", { name: "策略注册表" });
  await expect(registryPanel.getByText("只读")).toBeVisible();
  await expect(registryPanel.getByText("评分 74.00")).toBeVisible();
  await expect(registryPanel.getByText("#1 Deterministic Watchlist Strategy")).toBeVisible();
  await expect(registryPanel.getByText("deterministic_watchlist_v1 · paper_core · paper")).toBeVisible();
  await expect(registryPanel.getByText("#2 MovingAverageCross")).toBeVisible();
  await expect(registryPanel.getByText("moving_average_cross · lean_catalog · backtest")).toBeVisible();
  await expect(registryPanel.getByText("控制缺口 5")).toBeVisible();
  await expect(registryPanel.getByText("实盘关闭")).toBeVisible();
  const competitionPanel = page.getByRole("region", { name: "策略竞争层" });
  await expect(competitionPanel.getByText("allocation_ready", { exact: true })).toBeVisible();
  await expect(competitionPanel.getByText("策略池 2")).toBeVisible();
  await expect(competitionPanel.getByText("可分配 1 · 选中 deterministic_watchlist_v1")).toBeVisible();
  await expect(competitionPanel.getByText("竞争账本 1 天")).toBeVisible();
  await expect(competitionPanel.getByText("最新 2026-06-14 · 可分配 1")).toBeVisible();
  await expect(competitionPanel.getByText("#1 Deterministic Watchlist Strategy")).toBeVisible();
  await expect(competitionPanel.getByText("deterministic_watchlist_v1 · paper_core · paper")).toBeVisible();
  await expect(competitionPanel.getByText("allocation 100.00%")).toBeVisible();
  await expect(competitionPanel.getByText("allocate_paper_capital")).toBeVisible();
  await expect(competitionPanel.getByText("成交 40/30 · 还差 0 笔 · 排名分 80.00")).toBeVisible();
  await expect(competitionPanel.getByText("#2 MovingAverageCross")).toBeVisible();
  await expect(competitionPanel.getByText("not_connected_to_paper_runtime")).toBeVisible();
  await expect(competitionPanel.getByText("keep_in_lab")).toBeVisible();
  await expect(competitionPanel.getByText("成交 0/30 · 还差 30 笔 · 排名分 0.00")).toBeVisible();
  await competitionPanel.getByRole("button", { name: "记录竞争快照" }).click();
  await expect(competitionPanel.getByText("已记录 2026-06-14 策略竞争快照")).toBeVisible();
  const lifecyclePanel = page.getByRole("region", { name: "策略生命周期" });
  await expect(lifecyclePanel.getByText("watch", { exact: true })).toBeVisible();
  await expect(lifecyclePanel.getByText("paper → paper")).toBeVisible();
  await expect(lifecyclePanel.getByText("keep_paper_running").first()).toBeVisible();
  await expect(lifecyclePanel.getByText("自动动作 关闭")).toBeVisible();
  await expect(lifecyclePanel.getByRole("button", { name: "停用策略" })).toBeDisabled();
  await expect(lifecyclePanel.getByText("禁止晋级")).toBeVisible();
  await expect(lifecyclePanel.getByText("通过 event_ledger_populated")).toBeVisible();
  await expect(lifecyclePanel.getByText("阻断 closed_trade_sample")).toBeVisible();
  await expect(lifecyclePanel.getByText("阻断 alpha_validation_ready")).toBeVisible();
  await expect(lifecyclePanel.getByText("生命周期缺口 5")).toBeVisible();
  const lifecycleAuditPanel = page.getByRole("region", { name: "生命周期审计" });
  await expect(lifecycleAuditPanel.getByText("2 lifecycle audit entries recorded")).toBeVisible();
  await expect(lifecycleAuditPanel.getByText("shadow → paper")).toBeVisible();
  await expect(lifecycleAuditPanel.getByText("strategy_lifecycle_reconciled · system_reconcile · Alpha validation is not ready.")).toBeVisible();
  await expect(lifecycleAuditPanel.getByText("paper → shadow")).toBeVisible();
  await expect(lifecycleAuditPanel.getByText("strategy_shadow_approved · operator · Paper gates reviewed.")).toBeVisible();
  await expect(lifecycleAuditPanel.getByText("manual")).toBeVisible();
  const shadowReviewPanel = page.getByRole("region", { name: "Shadow 评审包" });
  await expect(shadowReviewPanel.getByText("Shadow review packet is blocked")).toBeVisible();
  await expect(shadowReviewPanel.getByText("deterministic_watchlist_v1 → paper")).toBeVisible();
  await expect(shadowReviewPanel.getByText("自动晋级 关闭")).toBeVisible();
  await expect(shadowReviewPanel.getByRole("button", { name: "批准进入 Shadow" })).toBeDisabled();
  await expect(shadowReviewPanel.getByText("阻断 Alpha 门禁通过")).toBeVisible();
  await expect(shadowReviewPanel.getByText("模拟盘门禁通过只允许进入 Shadow 人工评审")).toBeVisible();
  const shadowObservationPanel = page.getByRole("region", { name: "Shadow 观察" });
  await expect(shadowObservationPanel.getByText("No shadow observations have been recorded yet.")).toBeVisible();
  await expect(shadowObservationPanel.getByText("可记录")).toBeVisible();
  await shadowObservationPanel.getByRole("button", { name: "记录观察" }).click();
  await expect(shadowObservationPanel.getByText("Shadow observation latest observing on 2026-06-30")).toBeVisible();
  await expect(shadowObservationPanel.getByText("intent 6 / would-route 6 / chain 6")).toBeVisible();
  const shadowDailyReportPanel = page.getByRole("region", { name: "Shadow 日报" });
  await expect(shadowDailyReportPanel.getByText("Shadow daily report is collecting observations; 4 more samples required.")).toBeVisible();
  await expect(shadowDailyReportPanel.getByText("交易日 2026-06-30 · observation observing")).toBeVisible();
  await expect(shadowDailyReportPanel.getByText("intent 6 / would-route 2 / chain 6")).toBeVisible();
  await expect(shadowDailyReportPanel.getByText("continue_shadow_observation", { exact: true })).toBeVisible();
  await expect(shadowDailyReportPanel.getByText("broker off", { exact: true })).toBeVisible();
  const shadowHealthPanel = page.getByRole("region", { name: "Shadow 健康" });
  await expect(shadowHealthPanel.getByText("Shadow observation health is collecting samples; 1/5 observations recorded.")).toBeVisible();
  await expect(shadowHealthPanel.getByText("样本 1 / 连续 1")).toBeVisible();
  await expect(shadowHealthPanel.getByText("平均 would-route 2.00")).toBeVisible();
  await expect(shadowHealthPanel.getByText("sample_not_ready", { exact: true })).toBeVisible();
  const shadowValidationPanel = page.getByRole("region", { name: "Shadow 验证" });
  await expect(shadowValidationPanel.getByText("Shadow validation is collecting observations; 4 more observing samples required.")).toBeVisible();
  await expect(shadowValidationPanel.getByText("观察样本 1 / 5")).toBeVisible();
  await expect(shadowValidationPanel.getByText("剩余 4 次 · 最新交易日 2026-06-30")).toBeVisible();
  await expect(shadowValidationPanel.getByText("shadow_observation_sample")).toBeVisible();
  const liveSmallReviewPanel = page.getByRole("region", { name: "Live-small 评审包" });
  await expect(liveSmallReviewPanel.getByText("Live-small review packet is blocked")).toBeVisible();
  await expect(liveSmallReviewPanel.getByText("deterministic_watchlist_v1 → shadow")).toBeVisible();
  await expect(liveSmallReviewPanel.getByText("自动晋级 关闭")).toBeVisible();
  await expect(liveSmallReviewPanel.getByRole("button", { name: "批准进入 Live-small" })).toBeDisabled();
  await expect(liveSmallReviewPanel.getByText("阻断 当前处于 Shadow")).toBeVisible();
  await expect(liveSmallReviewPanel.getByText("阻断 Shadow 健康稳定")).toBeVisible();
  await expect(liveSmallReviewPanel.getByText("Live-small 只能作为人工评审结论")).toBeVisible();
  const attributionPanel = page.getByRole("region", { name: "归因分析" });
  await expect(attributionPanel.getByText("drawdown_pressure")).toBeVisible();
  await expect(attributionPanel.getByText("可行动信号 50.00%")).toBeVisible();
  await expect(attributionPanel.getByText("误报率 25.00%", { exact: true })).toBeVisible();
  await expect(attributionPanel.getByText("open_position_pressure")).toBeVisible();
  await expect(attributionPanel.getByText("NVDA 贡献 $60.00")).toBeVisible();
  await expect(attributionPanel.getByText("衰减 1 / 2")).toBeVisible();
  await expect(attributionPanel.getByText("持仓 6.50 天")).toBeVisible();
  await expect(attributionPanel.getByText("timing_component -$20.00")).toBeVisible();
  await expect(attributionPanel.getByText("volatility_component $12.00")).toBeVisible();
  await expect(attributionPanel.getByText("risk_overreach 1.00")).toBeVisible();
  await expect(attributionPanel.getByText("市场环境 trend_market")).toBeVisible();
  await expect(attributionPanel.getByText("收益 8.00% / 波动 1.00% / Sharpe 3.20")).toBeVisible();
});

test("watchlist renders market snapshot from API", async ({ page }) => {
  await page.route("**/api/mvp/market/snapshot/NVDA", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "NVDA",
        quote: {
          ticker: "NVDA",
          price: 125.75,
          currency: "USD",
          source: "openbb_yfinance",
          updated_at: "2026-06-12T14:00:00Z",
          change: 2.4,
          change_percent: 0.019,
          volume: 55443322,
          is_fallback: false,
          message: "OpenBB yfinance quote loaded."
        },
        fundamentals: {
          ticker: "NVDA",
          market_cap: 3500000000000,
          pe_ratio: 42.1,
          eps: 2.45,
          price_to_sales: null,
          price_to_book: null,
          gross_margin: 0.74,
          profit_margin: null,
          operating_margin: null,
          debt_to_equity: null,
          source: "openbb_yfinance",
          period_ending: "2026-03-31",
          updated_at: "2026-06-12T14:00:00Z",
          is_fallback: false,
          message: "OpenBB yfinance fundamentals loaded."
        },
        history: [
          {
            ticker: "NVDA",
            date: "2026-06-10",
            open: 120,
            high: 126,
            low: 119,
            close: 125.75,
            volume: 1000,
            source: "openbb_yfinance"
          }
        ],
        provider_mode: "hybrid",
        data_sources: []
      }
    });
  });

  await page.goto("/watchlist");

  const panel = page.getByRole("region", { name: "市场快照" });
  const quoteCard = panel.locator(".market-card").first();
  await expect(page.getByRole("heading", { name: "市场快照" })).toBeVisible();
  await expect(quoteCard.getByText("NVDA", { exact: true })).toBeVisible();
  await expect(quoteCard.getByText("$125.75")).toBeVisible();
  await expect(quoteCard.getByText("openbb_yfinance")).toBeVisible();
  await expect(panel.getByText("Market Cap")).toBeVisible();
  await expect(panel.getByText("3.50T")).toBeVisible();
});

test("watchlist can query an arbitrary ticker and show unavailable fallback", async ({ page }) => {
  await page.route("**/api/mvp/market/snapshot/NVDA", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "NVDA",
        quote: {
          ticker: "NVDA",
          price: 125.75,
          currency: "USD",
          source: "mock",
          updated_at: "local",
          change: null,
          change_percent: null,
          volume: null,
          is_fallback: true,
          message: "本地 Mock fallback 数据，仅用于离线展示。"
        },
        fundamentals: {
          ticker: "NVDA",
          market_cap: null,
          pe_ratio: null,
          eps: null,
          price_to_sales: null,
          price_to_book: null,
          gross_margin: null,
          profit_margin: null,
          operating_margin: null,
          debt_to_equity: null,
          source: "mock",
          period_ending: null,
          updated_at: "local",
          is_fallback: true,
          message: "本地 Mock fallback 基本面，仅用于离线展示。"
        },
        history: [],
        provider_mode: "hybrid",
        data_sources: []
      }
    });
  });
  await page.route("**/api/mvp/market/snapshot/TSLA", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "TSLA",
        quote: {
          ticker: "TSLA",
          price: null,
          currency: "USD",
          source: "openbb_yfinance",
          updated_at: "local",
          change: null,
          change_percent: null,
          volume: null,
          is_fallback: false,
          message: "Ticker not found."
        },
        fundamentals: {
          ticker: "TSLA",
          market_cap: null,
          pe_ratio: null,
          eps: null,
          price_to_sales: null,
          price_to_book: null,
          gross_margin: null,
          profit_margin: null,
          operating_margin: null,
          debt_to_equity: null,
          source: "openbb_yfinance",
          period_ending: null,
          updated_at: "local",
          is_fallback: false,
          message: "Ticker not found."
        },
        history: [],
        provider_mode: "hybrid",
        data_sources: []
      }
    });
  });

  await page.goto("/watchlist");
  await page.getByLabel("Ticker", { exact: true }).fill("tsla");
  await page.getByRole("button", { name: "查询" }).click();

  await expect(page.getByText("TSLA", { exact: true })).toBeVisible();
  await expect(page.getByText("Ticker not found.")).toBeVisible();
});

test("portfolio workspace can save and delete a position", async ({ page }) => {
  let positions: PositionPayload[] = [
    {
      id: "position-aapl",
      ticker: "AAPL",
      quantity: 10,
      average_cost: 165,
      currency: "USD",
      price: 210.12,
      market_value: 2101.2,
      weight: 1,
      updated_at: "2026-06-13T00:00:00Z"
    }
  ];
  const portfolioPayload = () => ({
    id: "portfolio-main",
    name: "主组合",
    base_currency: "USD",
    total_market_value: positions.reduce((sum, position) => sum + position.market_value, 0),
    positions
  });

  await page.route("**/api/mvp/portfolio", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: portfolioPayload() });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/mvp/portfolio/positions", async (route) => {
    const body = route.request().postDataJSON() as { average_cost: number; quantity: number; ticker: string };
    positions = [
      ...positions,
      {
        id: "position-tsla",
        ticker: body.ticker.toUpperCase(),
        quantity: body.quantity,
        average_cost: body.average_cost,
        currency: "USD",
        price: null,
        market_value: body.quantity * body.average_cost,
        weight: 0,
        updated_at: "2026-06-13T00:00:00Z"
      }
    ];
    await route.fulfill({ contentType: "application/json", json: positions[positions.length - 1] });
  });
  await page.route("**/api/mvp/portfolio/positions/TSLA", async (route) => {
    positions = positions.filter((position) => position.ticker !== "TSLA");
    await route.fulfill({ contentType: "application/json", json: { ticker: "TSLA" } });
  });

  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "组合" })).toBeVisible();
  await page.getByLabel("Ticker").fill("tsla");
  await page.getByLabel("数量").fill("4");
  await page.getByLabel("平均成本").fill("181.25");
  await page.getByRole("button", { name: "保存持仓" }).click();
  await expect(page.getByText("TSLA", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "删除 TSLA" }).click();
  await expect(page.getByText("TSLA", { exact: true })).not.toBeVisible();
});

test("watchlist workspace can save and delete an item", async ({ page }) => {
  let items = [
    { id: "watch-nvda", ticker: "NVDA", thesis: "AI 基础设施", created_at: "2026-06-13T00:00:00Z" }
  ];
  await page.route("**/api/mvp/watchlist", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: { items } });
      return;
    }
    const body = route.request().postDataJSON() as { thesis: string; ticker: string };
    const saved = { id: "watch-tsla", ticker: body.ticker.toUpperCase(), thesis: body.thesis, created_at: "2026-06-13T00:00:00Z" };
    items = [...items, saved];
    await route.fulfill({ contentType: "application/json", json: saved });
  });
  await page.route("**/api/mvp/watchlist/TSLA", async (route) => {
    items = items.filter((item) => item.ticker !== "TSLA");
    await route.fulfill({ contentType: "application/json", json: { ticker: "TSLA" } });
  });
  await page.route("**/api/mvp/market/snapshot/NVDA", async (route) => {
    await route.abort();
  });

  await page.goto("/watchlist");
  await page.getByLabel("自选 Ticker").fill("tsla");
  await page.getByLabel("研究假设").fill("机器人和电动车弹性");
  await page.getByRole("button", { name: "保存自选股" }).click();
  await expect(page.getByText("机器人和电动车弹性")).toBeVisible();
  await page.getByRole("button", { name: "删除 TSLA" }).click();
  await expect(page.getByText("机器人和电动车弹性")).not.toBeVisible();
});

test("notes workspace can create a research note", async ({ page }) => {
  let notes = [
    { id: "note-aapl", ticker: "AAPL", title: "服务收入", body: "观察利润率。", created_at: "2026-06-13T00:00:00Z" }
  ];
  await page.route("**/api/mvp/notes", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: { notes } });
      return;
    }
    const body = route.request().postDataJSON() as { body: string; ticker: string; title: string };
    const saved = { id: "note-msft", ticker: body.ticker.toUpperCase(), title: body.title, body: body.body, created_at: "2026-06-13T00:00:00Z" };
    notes = [saved, ...notes];
    await route.fulfill({ contentType: "application/json", json: saved });
  });

  await page.goto("/notes");
  await page.getByLabel("Ticker").fill("msft");
  await page.getByLabel("标题").fill("Azure 需求");
  await page.getByLabel("正文").fill("跟踪云增速和 AI capex。");
  await page.getByRole("button", { name: "保存笔记" }).click();
  await expect(page.getByText("Azure 需求")).toBeVisible();
  await expect(page.getByText("跟踪云增速和 AI capex。")).toBeVisible();
});

test("imports workspace can import positions csv and show row errors", async ({ page }) => {
  await page.route("**/api/mvp/portfolio/import", async (route) => {
    const body = route.request().postDataJSON() as { content: string };
    expect(body.content).toContain("TSLA");
    await route.fulfill({
      contentType: "application/json",
      json: {
        imported_count: 1,
        errors: [{ row: 3, field: "ticker", message: "ticker is required" }],
        portfolio: null
      }
    });
  });

  await page.goto("/imports");
  await page.getByLabel("CSV 内容").fill("ticker,quantity,average_cost\nTSLA,2,190\n,1,10\n");
  await page.getByRole("button", { name: "导入持仓" }).click();
  await expect(page.getByText("已导入 1 条持仓")).toBeVisible();
  await expect(page.getByText("第 3 行 ticker：ticker is required")).toBeVisible();
});

test("strategy lab can run a cataloged LEAN backtest", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: true,
        summary: "Docker and LEAN are ready for local backtest preparation.",
        tools: [
          { name: "Docker CLI", available: true, version: "Docker version 29.5.3", message: "Docker CLI is available." },
          { name: "LEAN CLI", available: true, version: "lean, version 1.0.200", message: "LEAN CLI is available." }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/strategies", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategies: [
          {
            id: "moving_average_cross",
            name: "MovingAverageCross",
            description: "AAPL daily moving average crossover sample for local LEAN validation.",
            language: "Python",
            asset_class: "US Equity",
            default_symbol: "AAPL",
            resolution: "Daily",
            enabled: true,
            parameters: movingAverageParameters
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/latest", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { latest: null } });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/history**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        history: [
          {
            run_id: "20260612T101500Z-moving_average_cross",
            strategy_id: "moving_average_cross",
            status: "success",
            engine: "lean",
            data_source: "openbb_yfinance",
            data_quality: "real_market_data",
            uses_real_market_data: true,
            started_at: "2026-06-12T10:15:00Z",
            completed_at: "2026-06-12T10:16:15Z",
            duration_seconds: 75,
            parameters: {
              symbol: "MSFT",
              start_date: "2020-02-01",
              end_date: "2020-12-31",
              cash: "250000",
              fast_period: "10",
              slow_period: "30"
            },
            statistics: {
              total_net_profit: "12.34%",
              compounding_annual_return: "8.10%",
              sharpe_ratio: "0.72",
              drawdown: "15.20%",
              win_rate: "48%",
              total_trades: "24"
            }
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/backtests", async (route) => {
    expect(route.request().method()).toBe("POST");
    const requestBody = route.request().postDataJSON() as { parameters?: Record<string, string>; strategy_id?: unknown };
    expect(requestBody.strategy_id).toBe("moving_average_cross");
    expect(requestBody.parameters).toEqual({
      symbol: "MSFT",
      start_date: "2020-02-01",
      end_date: "2020-12-31",
      cash: "250000",
      fast_period: "10",
      slow_period: "30"
    });
    await route.fulfill({
      contentType: "application/json",
      json: {
        run_id: "20260612T101500Z-moving_average_cross",
        strategy_id: "moving_average_cross",
        status: "success",
        engine: "lean",
        data_source: "openbb_yfinance",
        data_quality: "real_market_data",
        uses_real_market_data: true,
        started_at: "2026-06-12T10:15:00Z",
        completed_at: "2026-06-12T10:16:15Z",
        duration_seconds: 75,
        message: "Backtest completed.",
        parameters: {
          symbol: "MSFT",
          start_date: "2020-02-01",
          end_date: "2020-12-31",
          cash: "250000",
          fast_period: "10",
          slow_period: "30"
        },
        statistics: {
          total_net_profit: "12.34%",
          compounding_annual_return: "8.10%",
          sharpe_ratio: "0.72",
          drawdown: "15.20%",
          win_rate: "48%",
          total_trades: "24"
        },
        equity: [{ time: "2020-01-01", value: 100000 }],
        logs: ["TRACE:: Backtest completed"],
        output_directory: "apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross"
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/candidate-backtests", async (route) => {
    expect(route.request().method()).toBe("POST");
    const requestBody = route.request().postDataJSON() as {
      parameters?: Record<string, string>;
      strategy_id?: unknown;
      tickers?: string[];
    };
    expect(requestBody.strategy_id).toBe("moving_average_cross");
    expect(requestBody.tickers).toEqual(["AAPL", "MSFT", "NVDA"]);
    expect(requestBody.parameters?.start_date).toBe("2020-02-01");
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategy_id: "moving_average_cross",
        candidate_count: 3,
        real_market_candidate_count: 3,
        best_ticker: "NVDA",
        items: [
          {
            rank: 1,
            ticker: "NVDA",
            recommendation: "candidate",
            score: 1.42,
            reason: "真实历史数据；收益为正；Sharpe 1.80；结论 candidate",
            run_id: "run-NVDA",
            status: "success",
            engine: "vectorbt",
            data_source: "openbb_yfinance",
            uses_real_market_data: true,
            total_net_profit: "42.00%",
            sharpe_ratio: "1.80",
            drawdown: "12.00%",
            total_trades: "9"
          },
          {
            rank: 2,
            ticker: "MSFT",
            recommendation: "candidate",
            score: 0.94,
            reason: "真实历史数据；收益为正；Sharpe 0.90；结论 candidate",
            run_id: "run-MSFT",
            status: "success",
            engine: "vectorbt",
            data_source: "openbb_yfinance",
            uses_real_market_data: true,
            total_net_profit: "18.00%",
            sharpe_ratio: "0.90",
            drawdown: "6.00%",
            total_trades: "5"
          },
          {
            rank: 3,
            ticker: "AAPL",
            recommendation: "reject",
            score: -0.22,
            reason: "真实历史数据；收益未通过；结论 reject",
            run_id: "run-AAPL",
            status: "success",
            engine: "vectorbt",
            data_source: "openbb_yfinance",
            uses_real_market_data: true,
            total_net_profit: "-3.00%",
            sharpe_ratio: "-0.20",
            drawdown: "9.00%",
            total_trades: "4"
          }
        ],
        summary: "Ranked 3 candidates; 2 passed, best ticker NVDA."
      }
    });
  });

  await page.goto("/strategy-lab");
  const panel = page.getByRole("region", { name: "LEAN 回测" });
  await expect(panel.getByLabel("策略列表").getByRole("button", { name: /MovingAverageCross/ })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await expect(panel.getByLabel("Ticker")).toHaveValue("AAPL");
  await expect(panel.getByLabel("Start Date")).toHaveValue("2020-01-01");
  await panel.getByLabel("Ticker").fill("msft");
  await panel.getByLabel("Start Date").fill("2020-02-01");
  await panel.getByLabel("End Date").fill("2020-12-31");
  await panel.getByLabel("Initial Cash").fill("250000");
  await panel.getByLabel("Fast SMA").fill("10");
  await panel.getByLabel("Slow SMA").fill("30");
  await page.getByRole("button", { name: "运行回测" }).click();

  await expect(page.getByText("MovingAverageCross")).toBeVisible();
  await expect(page.getByText("Backtest completed.")).toBeVisible();
  await expect(panel.locator(".backtest-metrics").getByText("12.34%")).toBeVisible();
  await expect(panel.locator(".backtest-metrics").getByText("Sharpe", { exact: true })).toBeVisible();
  await expect(page.getByText("TRACE:: Backtest completed")).toBeVisible();
  await expect(panel.getByLabel("回测数据质量").getByText("真实历史数据")).toBeVisible();
  await expect(panel.getByLabel("回测数据质量").getByText("可用于历史验证")).toBeVisible();
  await expect(panel.locator(".result-toolbar .status-pill")).toHaveText("回测完成");
  await expect(panel.getByRole("textbox", { name: "候选池" })).toHaveValue("AAPL,MSFT,NVDA");
  await page.getByRole("button", { name: "运行候选池回测" }).click();
  await expect(panel.getByText("Ranked 3 candidates; 2 passed, best ticker NVDA.")).toBeVisible();
  await expect(panel.getByText("#1 NVDA")).toBeVisible();
  await expect(panel.getByText("42.00% · Sharpe 1.80 · 回撤 12.00%")).toBeVisible();
  await expect(panel.getByText("真实历史数据；收益为正；Sharpe 1.80；结论 candidate")).toBeVisible();
  await expect(panel.getByRole("heading", { name: "历史记录" })).toBeVisible();
  await expect(panel.getByText("MSFT · 2020-02-01 到 2020-12-31")).toBeVisible();
  await expect(panel.getByText("10 / 30")).toBeVisible();
});

test("strategy lab displays LEAN backtest failures", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: false,
        summary: "Strategy Lab is partially configured.",
        tools: [{ name: "LEAN CLI", available: false, version: null, message: "LEAN CLI is not installed or is not on PATH." }]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/strategies", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategies: [
          {
            id: "moving_average_cross",
            name: "MovingAverageCross",
            description: "AAPL daily moving average crossover sample for local LEAN validation.",
            language: "Python",
            asset_class: "US Equity",
            default_symbol: "AAPL",
            resolution: "Daily",
            enabled: true,
            parameters: movingAverageParameters
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/latest", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { latest: null } });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/history**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { history: [] } });
  });
  await page.route("**/api/mvp/strategy-lab/backtests", async (route) => {
    expect(route.request().method()).toBe("POST");
    const requestBody = route.request().postDataJSON() as { parameters?: Record<string, string>; strategy_id?: unknown };
    expect(requestBody.strategy_id).toBe("moving_average_cross");
    expect(requestBody.parameters?.symbol).toBe("AAPL");
    await route.fulfill({
      contentType: "application/json",
      json: {
        run_id: "20260612T101500Z-moving_average_cross",
        strategy_id: "moving_average_cross",
        status: "unavailable",
        engine: "lean",
        data_source: null,
        data_quality: "unknown",
        uses_real_market_data: false,
        started_at: "2026-06-12T10:15:00Z",
        completed_at: "2026-06-12T10:15:01Z",
        duration_seconds: 1,
        message: "Strategy Lab is partially configured.",
        parameters: {
          symbol: "AAPL",
          start_date: "2020-01-01",
          end_date: "2021-01-01",
          cash: "100000",
          fast_period: "20",
          slow_period: "50"
        },
        statistics: {
          total_net_profit: null,
          compounding_annual_return: null,
          sharpe_ratio: null,
          drawdown: null,
          win_rate: null,
          total_trades: null
        },
        equity: [],
        logs: ["LEAN CLI is not installed or is not on PATH."],
        output_directory: "apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross"
      }
    });
  });

  await page.goto("/strategy-lab");
  const panel = page.getByRole("region", { name: "LEAN 回测" });
  await page.getByRole("button", { name: "运行回测" }).click();

  await expect(panel.locator(".result-toolbar .status-pill")).toHaveText("环境未就绪");
  await expect(panel.getByLabel("回测日志").getByText("LEAN CLI is not installed or is not on PATH.")).toBeVisible();
  await expect(panel.getByText("安装 QuantConnect LEAN CLI")).toBeVisible();
});

test("strategy lab shows an empty state when no strategies are cataloged", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: true,
        summary: "Docker and LEAN are ready for local backtest preparation.",
        tools: [{ name: "LEAN CLI", available: true, version: "lean, version 1.0.200", message: "LEAN CLI is available." }]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/strategies", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: { strategies: [] }
    });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/latest", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { latest: null } });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/history**", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { history: [] } });
  });

  await page.goto("/strategy-lab");

  const panel = page.getByRole("region", { name: "LEAN 回测" });
  await expect(panel.getByText("暂无可用策略")).toBeVisible();
  await expect(panel.getByText("请检查策略目录配置。")).toBeVisible();
  await expect(panel.getByText("策略目录为空，无法运行回测。")).toBeVisible();
  await expect(panel.getByRole("button", { name: "运行回测" })).toBeDisabled();
});

test("strategy backtest client preserves HTTP error detail", async () => {
  const originalFetch = globalThis.fetch;
  let postedStrategyId: string | null = null;
  globalThis.fetch = async (_input, init) => {
    const payload = JSON.parse(String(init?.body));
    postedStrategyId = payload.strategy_id;
    expect(payload.parameters).toEqual({});
    return new Response(JSON.stringify({ detail: "Unknown strategy_id: missing" }), {
      headers: { "Content-Type": "application/json" },
      status: 404
    });
  };

  try {
    const result = await runStrategyBacktest("  missing  ");

    expect(postedStrategyId).toBe("missing");
    expect(result.strategy_id).toBe("missing");
    expect(result.status).toBe("failed");
    expect(result.message).toBe("请求失败（404）：Unknown strategy_id: missing");
    expect(result.logs).toContain("请求失败（404）：Unknown strategy_id: missing");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("strategy backtest client rejects blank strategy id without request", async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = async () => {
    fetchCalled = true;
    return new Response(null, { status: 204 });
  };

  try {
    const result = await runStrategyBacktest("   ");

    expect(fetchCalled).toBe(false);
    expect(result.strategy_id).toBe("");
    expect(result.status).toBe("failed");
    expect(result.message).toBe("请选择策略后再运行回测。");
    expect(result.logs).toContain("请选择策略后再运行回测。");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
