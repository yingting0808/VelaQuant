"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save, Trash2 } from "lucide-react";
import {
  deletePosition,
  getPortfolio,
  upsertPosition,
  type PortfolioPayload
} from "@/lib/client-api";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  currency: "USD",
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
  style: "currency"
});

const percentFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
  style: "percent"
});

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 4
  }).format(value);
}

export function PortfolioWorkspace() {
  const [portfolio, setPortfolio] = useState<PortfolioPayload | null>(null);
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [averageCost, setAverageCost] = useState("");
  const [message, setMessage] = useState("正在读取组合。");
  const [isSaving, setIsSaving] = useState(false);

  async function refreshPortfolio() {
    const payload = await getPortfolio();
    setPortfolio(payload);
    setMessage(payload.positions.length ? "组合持仓已同步。" : "暂无持仓，先添加一个 Ticker。");
  }

  useEffect(() => {
    let active = true;
    getPortfolio().then((payload) => {
      if (!active) {
        return;
      }
      setPortfolio(payload);
      setMessage(payload.positions.length ? "组合持仓已同步。" : "暂无持仓，先添加一个 Ticker。");
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTicker = ticker.trim().toUpperCase();
    const parsedQuantity = Number(quantity);
    const parsedAverageCost = Number(averageCost);

    if (!normalizedTicker || !Number.isFinite(parsedQuantity) || !Number.isFinite(parsedAverageCost)) {
      setMessage("请填写有效的 Ticker、数量和平均成本。");
      return;
    }

    setIsSaving(true);
    setMessage("正在保存持仓。");
    try {
      const saved = await upsertPosition({
        average_cost: parsedAverageCost,
        currency: "USD",
        quantity: parsedQuantity,
        ticker: normalizedTicker
      });
      if (!saved) {
        setMessage("保存失败，请检查后端 API。");
        return;
      }
      setTicker("");
      setQuantity("");
      setAverageCost("");
      await refreshPortfolio();
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(positionTicker: string) {
    setMessage(`正在删除 ${positionTicker}。`);
    const deleted = await deletePosition(positionTicker);
    if (!deleted) {
      setMessage(`删除 ${positionTicker} 失败。`);
      return;
    }
    await refreshPortfolio();
  }

  const positions = portfolio?.positions ?? [];

  return (
    <div className="module-view">
      <header className="page-header">
        <div>
          <p>本地组合账本与暴露监控</p>
          <h2>组合</h2>
        </div>
        <div className="status-pill neutral">{positions.length} 个持仓</div>
      </header>

      <section className="data-panel workspace-panel" aria-label="组合持仓">
        <div className="panel-heading">
          <div>
            <h3>持仓</h3>
            <p>{portfolio ? `${portfolio.name} · ${portfolio.base_currency}` : "正在加载本地组合"}</p>
          </div>
          <strong>{currencyFormatter.format(portfolio?.total_market_value ?? 0)}</strong>
        </div>

        <form className="workspace-form" onSubmit={handleSubmit}>
          <label className="workspace-field">
            <span>Ticker</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value.toUpperCase())}
              placeholder="AAPL"
              spellCheck={false}
            />
          </label>
          <label className="workspace-field">
            <span>数量</span>
            <input
              inputMode="decimal"
              type="number"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="10"
            />
          </label>
          <label className="workspace-field">
            <span>平均成本</span>
            <input
              inputMode="decimal"
              type="number"
              value={averageCost}
              onChange={(event) => setAverageCost(event.target.value)}
              placeholder="165"
              step="0.01"
            />
          </label>
          <button className="primary-action" type="submit" disabled={isSaving}>
            <Save size={15} aria-hidden="true" />
            {isSaving ? "保存中" : "保存持仓"}
          </button>
        </form>

        <p className="workspace-message" aria-live="polite">
          {message}
        </p>

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
                  权重
                </th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.ticker}>
                  <td>
                    <span className="ticker-chip">{position.ticker}</span>
                  </td>
                  <td className="numeric">{formatNumber(position.quantity)}</td>
                  <td className="numeric">{currencyFormatter.format(position.average_cost)}</td>
                  <td className="numeric">{currencyFormatter.format(position.market_value)}</td>
                  <td className="numeric">{percentFormatter.format(position.weight)}</td>
                  <td>
                    <button className="ghost-action danger" type="button" onClick={() => handleDelete(position.ticker)}>
                      <Trash2 size={14} aria-hidden="true" />
                      删除 {position.ticker}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
