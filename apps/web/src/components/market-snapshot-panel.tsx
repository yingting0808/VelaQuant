"use client";

import { FormEvent, useEffect, useState } from "react";
import { getMarketSnapshot, type MarketSnapshotPayload } from "@/lib/client-api";

const defaultTickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META"];

function formatCurrency(value: number | null, currency: string): string {
  if (value === null) {
    return "不可用";
  }
  return new Intl.NumberFormat("en-US", {
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
    style: "currency"
  }).format(value);
}

function formatLargeNumber(value: number | null): string {
  if (value === null) {
    return "不可用";
  }
  if (Math.abs(value) >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (Math.abs(value) >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  return value.toLocaleString("en-US");
}

function formatPercent(value: number | null): string {
  return value === null ? "不可用" : `${(value * 100).toFixed(2)}%`;
}

export function MarketSnapshotPanel() {
  const [tickerInput, setTickerInput] = useState("NVDA");
  const [selectedTicker, setSelectedTicker] = useState("NVDA");
  const [snapshot, setSnapshot] = useState<MarketSnapshotPayload | null>(null);

  useEffect(() => {
    let active = true;
    getMarketSnapshot(selectedTicker).then((payload) => {
      if (active) {
        setSnapshot(payload);
      }
    });
    return () => {
      active = false;
    };
  }, [selectedTicker]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectedTicker(tickerInput.trim().toUpperCase() || "NVDA");
  }

  const quote = snapshot?.quote;
  const fundamentals = snapshot?.fundamentals;

  return (
    <section className="data-panel market-panel" aria-label="市场快照">
      <div className="panel-heading market-heading">
        <div>
          <h3>市场快照</h3>
          <p>OpenBB / yfinance 优先，离线时清楚标注 fallback</p>
        </div>
        <form className="ticker-form" onSubmit={handleSubmit}>
          <label htmlFor="ticker-query">Ticker</label>
          <input
            id="ticker-query"
            value={tickerInput}
            onChange={(event) => setTickerInput(event.target.value)}
            spellCheck={false}
          />
          <button type="submit">查询</button>
        </form>
      </div>

      <div className="ticker-strip" aria-label="默认股票">
        {defaultTickers.map((ticker) => (
          <button
            key={ticker}
            type="button"
            onClick={() => {
              setTickerInput(ticker);
              setSelectedTicker(ticker);
            }}
          >
            {ticker}
          </button>
        ))}
      </div>

      <div className="market-grid">
        <article className="market-card">
          <span className="market-label">{snapshot?.ticker ?? selectedTicker}</span>
          <strong>{formatCurrency(quote?.price ?? null, quote?.currency ?? "USD")}</strong>
          <p>{quote?.message ?? "正在加载市场数据"}</p>
          <span className={quote?.is_fallback ? "state-warn" : "state-ok"}>{quote?.source ?? "加载中"}</span>
        </article>

        <article className="market-card">
          <span className="market-label">Change</span>
          <strong>{formatPercent(quote?.change_percent ?? null)}</strong>
          <p>Volume: {quote?.volume?.toLocaleString("en-US") ?? "不可用"}</p>
        </article>

        <article className="market-card">
          <span className="market-label">Market Cap</span>
          <strong>{formatLargeNumber(fundamentals?.market_cap ?? null)}</strong>
          <p>
            PE: {fundamentals?.pe_ratio ?? "不可用"} · EPS: {fundamentals?.eps ?? "不可用"}
          </p>
        </article>
      </div>

      <div className="module-list compact-history">
        {(snapshot?.history ?? []).slice(-3).map((bar) => (
          <article className="module-row" key={`${bar.ticker}-${bar.date}`}>
            <div>
              <strong>{bar.date}</strong>
              <p>{bar.source}</p>
            </div>
            <span>{formatCurrency(bar.close, quote?.currency ?? "USD")}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
