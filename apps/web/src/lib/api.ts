import { sampleDashboard } from "./sample-data";

export type DashboardPayload = {
  portfolio: {
    name: string;
    total_market_value: number;
    positions: Array<{
      ticker: string;
      market_value: number;
      weight: number;
    }>;
  };
  alerts: Array<{
    ticker: string;
    title: string;
    reason: string;
    source: string;
  }>;
  ai_prompts: string[];
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isPosition(value: unknown): value is DashboardPayload["portfolio"]["positions"][number] {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.market_value === "number" &&
    typeof value.weight === "number"
  );
}

function isAlert(value: unknown): value is DashboardPayload["alerts"][number] {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.title === "string" &&
    typeof value.reason === "string" &&
    typeof value.source === "string"
  );
}

function isDashboardPayload(value: unknown): value is DashboardPayload {
  if (!isRecord(value) || !isRecord(value.portfolio)) {
    return false;
  }

  const { portfolio } = value;

  return (
    typeof portfolio.name === "string" &&
    typeof portfolio.total_market_value === "number" &&
    Array.isArray(portfolio.positions) &&
    portfolio.positions.every(isPosition) &&
    Array.isArray(value.alerts) &&
    value.alerts.every(isAlert) &&
    isStringArray(value.ai_prompts)
  );
}

export async function getDashboard(): Promise<DashboardPayload> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/mvp/dashboard`, {
      cache: "no-store"
    });

    if (!response.ok) {
      return sampleDashboard;
    }

    const payload: unknown = await response.json();
    return isDashboardPayload(payload) ? payload : sampleDashboard;
  } catch {
    return sampleDashboard;
  }
}
