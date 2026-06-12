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

export async function getDashboard(): Promise<DashboardPayload> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/mvp/dashboard`, {
      cache: "no-store"
    });

    if (!response.ok) {
      return sampleDashboard;
    }

    return (await response.json()) as DashboardPayload;
  } catch {
    return sampleDashboard;
  }
}
