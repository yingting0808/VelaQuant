import { expect, test, type Page } from "@playwright/test";

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
  await gotoDashboard(page);

  await page.getByRole("link", { name: "自选股" }).click();

  await expect(page).toHaveURL("/watchlist");
  await expect(page.getByRole("link", { name: "自选股" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("当前模块：自选股")).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "自选股" })).toBeVisible();
  await expect(page.getByText("NVDA")).toBeVisible();
  await expect(page.getByRole("heading", { name: "主组合" })).not.toBeVisible();
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

  await gotoDashboard(page);
  await page.getByRole("link", { name: "策略实验室" }).click();

  await expect(page).toHaveURL("/strategy-lab");
  await expect(page.getByRole("heading", { name: "策略实验室" })).toBeVisible();
  await expect(
    page.getByText("Strategy Lab is partially configured; review unavailable tools before running LEAN backtests.")
  ).toBeVisible();
  await expect(page.getByText("Docker CLI", { exact: true })).toBeVisible();
  await expect(page.getByText("Docker version 29.5.3")).toBeVisible();
  await expect(page.getByText("LEAN CLI", { exact: true })).toBeVisible();
  await expect(page.getByText("LEAN CLI is not installed or is not on PATH.")).toBeVisible();
  await expect(page.getByText("不可回测")).toBeVisible();
});
