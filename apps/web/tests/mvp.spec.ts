import { expect, test } from "@playwright/test";

test("dashboard renders portfolio, alerts, and AI sidecar", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Main Book" })).toBeVisible();
  await expect(page.getByText("组合市值")).toBeVisible();
  await expect(page.getByRole("table").getByText("AAPL")).toBeVisible();
  await expect(page.getByRole("heading", { name: "事件预警" })).toBeVisible();
  await expect(page.getByText("AAPL 10-Q filed")).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI 助手" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Find portfolio risks" })).toBeVisible();
});
