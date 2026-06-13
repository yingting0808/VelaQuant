import { expect, test, type Page } from "@playwright/test";
import {
  runStrategyBacktest,
  type PaperEventLedgerPayload,
  type PaperTradingSummaryPayload,
  type PositionPayload
} from "../src/lib/client-api";

const movingAverageParameters = [
  { name: "symbol", label: "Ticker", kind: "ticker", default: "AAPL", required: true },
  { name: "start_date", label: "Start Date", kind: "date", default: "2020-01-01", required: true },
  { name: "end_date", label: "End Date", kind: "date", default: "2021-01-01", required: true },
  { name: "cash", label: "Initial Cash", kind: "number", default: "100000", min: 1000, max: 1000000000, required: true },
  { name: "fast_period", label: "Fast SMA", kind: "integer", default: "20", min: 2, max: 400, required: true },
  { name: "slow_period", label: "Slow SMA", kind: "integer", default: "50", min: 3, max: 600, required: true }
];

async function gotoDashboard(page: Page) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
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
  await expect(page.getByRole("heading", { name: "AI 助手" })).toBeVisible();
  await expect(page.getByRole("button", { name: "识别组合风险" })).toBeVisible();
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
  const dailySummary: PaperTradingSummaryPayload = {
    ...baseSummary,
    candidates: [candidate],
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
    replay_ready: false,
    warnings: ["missing_core_events"],
    summary: "No paper runs found; event replay is not available.",
    latest_replay: null
  };
  const filledLedger: PaperEventLedgerPayload = {
    total_event_count: 8,
    latest_run_id: "paper-run-today",
    latest_run_status: "completed",
    latest_run_event_count: 8,
    latest_topic_counts: [
      { topic: "market_event", count: 1 },
      { topic: "order_state", count: 5 },
      { topic: "strategy_input", count: 1 },
      { topic: "trade_intent", count: 1 }
    ],
    latest_correlation_count: 1,
    replay_ready: true,
    warnings: [],
    summary: "Latest paper run is completed with 8 replayable core events across 1 chains.",
    latest_replay: {
      run_id: "paper-run-today",
      event_count: 8,
      chain_count: 1,
      chains: [
        {
          correlation_id: "core-chain",
          ticker: "NVDA",
          topics: ["market_event", "strategy_input", "trade_intent", "order_state"],
          order_states: ["new", "validated", "risk_approved", "sent", "filled"],
          terminal_state: "filled",
          event_count: 8
        }
      ]
    }
  };
  let summary = baseSummary;
  let ledger = emptyLedger;

  await page.route("**/api/mvp/paper-trading/summary", async (route) => {
    await route.fulfill({ contentType: "application/json", json: summary });
  });
  await page.route("**/api/mvp/paper-trading/daily-run", async (route) => {
    expect(route.request().method()).toBe("POST");
    summary = dailySummary;
    await route.fulfill({ contentType: "application/json", json: dailySummary });
  });
  await page.route("**/api/mvp/paper-trading/orders", async (route) => {
    expect(route.request().method()).toBe("POST");
    const payload = route.request().postDataJSON() as { quantity?: number; side?: string; ticker?: string };
    expect(payload).toEqual({ order_type: "market", quantity: 40, side: "buy", ticker: "NVDA" });
    summary = filledSummary;
    ledger = filledLedger;
    await route.fulfill({ contentType: "application/json", json: filledSummary.orders[0] });
  });
  await page.route("**/api/mvp/paper-trading/scheduler", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        enabled: true,
        running: true,
        job_count: 1,
        cron: "30 6 * * *",
        timezone: "Asia/Shanghai"
      }
    });
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

  await gotoDashboard(page);
  await page.getByRole("link", { name: "模拟盘" }).click();

  await expect(page).toHaveURL("/paper-trading");
  await expect(page.getByRole("heading", { level: 2, name: "模拟盘" })).toBeVisible();
  await expect(page.getByText("默认模拟盘")).toBeVisible();
  await expect(page.getByRole("region", { name: "每日调度" }).getByText("运行中")).toBeVisible();
  await expect(page.getByText("30 6 * * *")).toBeVisible();
  await expect(page.getByRole("region", { name: "运行账本" }).getByText("skipped")).toBeVisible();
  await expect(page.getByRole("region", { name: "运行账本" }).getByText("manual")).toBeVisible();
  await expect(page.getByRole("region", { name: "运行账本" }).getByText("订单 1")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("不可回放")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("missing_core_events")).toBeVisible();

  await page.getByRole("button", { name: "运行今日模拟" }).click();

  await expect(page.getByRole("region", { name: "候选池" }).getByText("NVDA", { exact: true })).toBeVisible();
  await expect(page.getByText("3 条证据支持继续跟踪 NVDA")).toBeVisible();
  await expect(page.getByText("正在收集模拟盘样本。")).toBeVisible();

  await page.getByRole("button", { name: "模拟买入 NVDA" }).click();

  await expect(page.getByText("已模拟买入 NVDA。")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("可回放")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("NVDA · filled")).toBeVisible();
  await expect(page.getByRole("region", { name: "事件账本" }).getByText("order_state 5")).toBeVisible();
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

test("AI prompts return a visible research result after click", async ({ page }) => {
  await page.route("**/api/mvp/research", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "AAPL",
        status: "complete",
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
  await page.getByRole("button", { name: "识别组合风险" }).click();

  await expect(page.getByText("AAPL: 模拟组合风险研究结果。")).toBeVisible();
  await expect(page.getByText("必须经过人工审批。")).toBeVisible();
  await expect(page.getByText("多头观点", { exact: true })).toBeVisible();
  await expect(page.getByText("空头风险", { exact: true })).toBeVisible();
  await expect(page.getByText("风控提示", { exact: true })).toBeVisible();
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

  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "数据源状态" })).toBeVisible();
  await expect(page.getByText("hybrid")).toBeVisible();
  await expect(page.getByText("SEC EDGAR", { exact: true })).toBeVisible();
  await expect(page.getByText("Deterministic local fallback data is available.")).toBeVisible();
  await expect(page.getByText("SEC submissions adapter is configured.")).toBeVisible();
  await expect(page.getByText("data.sec.gov")).toBeVisible();
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
  await page.route("**/api/mvp/strategy-lab/lifecycle", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategy_id: "deterministic_watchlist_v1",
        strategy_name: "Deterministic Watchlist Strategy",
        current_stage: "paper",
        recommended_stage: "paper",
        recommended_action: "keep_paper_running",
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
            name: "event_ledger_populated",
            passed: true,
            severity: "blocker",
            actual: "80 events",
            required: "> 0 events",
            message: "Event ledger is populated."
          },
          {
            name: "closed_trade_sample",
            passed: false,
            severity: "blocker",
            actual: "5 closed trades",
            required: ">= 10 closed trades",
            message: "More closed trades required."
          }
        ],
        missing_capabilities: [
          "lifecycle_state_persistence",
          "manual_promotion_approval",
          "shadow_account_adapter",
          "live_small_account_adapter",
          "kill_switch_audit_trail"
        ],
        summary: "Positive expectancy is emerging, but paper-stage gates still need more evidence."
      }
    });
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
  const alphaPanel = page.getByRole("region", { name: "Alpha 验证" });
  await expect(alphaPanel.getByText("watch", { exact: true })).toBeVisible();
  await expect(alphaPanel.getByText("样本 21", { exact: true })).toBeVisible();
  await expect(alphaPanel.getByText("信号精度 71.43%")).toBeVisible();
  await expect(alphaPanel.getByText("最大回撤 8.00%")).toBeVisible();
  await expect(alphaPanel.getByText("keep_paper_running")).toBeVisible();
  const registryPanel = page.getByRole("region", { name: "策略注册表" });
  await expect(registryPanel.getByText("只读")).toBeVisible();
  await expect(registryPanel.getByText("评分 74.00")).toBeVisible();
  await expect(registryPanel.getByText("#1 Deterministic Watchlist Strategy")).toBeVisible();
  await expect(registryPanel.getByText("deterministic_watchlist_v1 · paper_core · paper")).toBeVisible();
  await expect(registryPanel.getByText("#2 MovingAverageCross")).toBeVisible();
  await expect(registryPanel.getByText("moving_average_cross · lean_catalog · backtest")).toBeVisible();
  await expect(registryPanel.getByText("控制缺口 5")).toBeVisible();
  await expect(registryPanel.getByText("实盘关闭")).toBeVisible();
  const lifecyclePanel = page.getByRole("region", { name: "策略生命周期" });
  await expect(lifecyclePanel.getByText("watch", { exact: true })).toBeVisible();
  await expect(lifecyclePanel.getByText("paper → paper")).toBeVisible();
  await expect(lifecyclePanel.getByText("keep_paper_running").first()).toBeVisible();
  await expect(lifecyclePanel.getByText("自动动作 关闭")).toBeVisible();
  await expect(lifecyclePanel.getByText("禁止晋级")).toBeVisible();
  await expect(lifecyclePanel.getByText("通过 event_ledger_populated")).toBeVisible();
  await expect(lifecyclePanel.getByText("阻断 closed_trade_sample")).toBeVisible();
  await expect(lifecyclePanel.getByText("生命周期缺口 5")).toBeVisible();
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
  await expect(panel.locator(".result-toolbar .status-pill")).toHaveText("回测完成");
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
