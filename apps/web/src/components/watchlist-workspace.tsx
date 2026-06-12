"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save, Trash2 } from "lucide-react";
import {
  deleteWatchlistItem,
  getWatchlist,
  upsertWatchlistItem,
  type WatchlistItemPayload
} from "@/lib/client-api";

export function WatchlistWorkspace() {
  const [items, setItems] = useState<WatchlistItemPayload[]>([]);
  const [ticker, setTicker] = useState("");
  const [thesis, setThesis] = useState("");
  const [message, setMessage] = useState("正在读取自选股。");
  const [isSaving, setIsSaving] = useState(false);

  async function refreshWatchlist() {
    const payload = await getWatchlist();
    setItems(payload.items);
    setMessage(payload.items.length ? "自选股已同步。" : "暂无自选股。");
  }

  useEffect(() => {
    let active = true;
    getWatchlist().then((payload) => {
      if (!active) {
        return;
      }
      setItems(payload.items);
      setMessage(payload.items.length ? "自选股已同步。" : "暂无自选股。");
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTicker = ticker.trim().toUpperCase();
    const normalizedThesis = thesis.trim();
    if (!normalizedTicker || !normalizedThesis) {
      setMessage("请填写自选 Ticker 和研究假设。");
      return;
    }

    setIsSaving(true);
    setMessage("正在保存自选股。");
    try {
      const saved = await upsertWatchlistItem({ thesis: normalizedThesis, ticker: normalizedTicker });
      if (!saved) {
        setMessage("保存失败，请检查后端 API。");
        return;
      }
      setTicker("");
      setThesis("");
      await refreshWatchlist();
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(positionTicker: string) {
    setMessage(`正在删除 ${positionTicker}。`);
    const deleted = await deleteWatchlistItem(positionTicker);
    if (!deleted) {
      setMessage(`删除 ${positionTicker} 失败。`);
      return;
    }
    await refreshWatchlist();
  }

  return (
    <section className="data-panel workspace-panel" aria-label="自选股工作区">
      <div className="panel-heading">
        <div>
          <h3>自选股</h3>
          <p>保存候选股票和当前研究假设</p>
        </div>
        <div className="status-pill neutral">{items.length} 项</div>
      </div>

      <form className="workspace-form watchlist-form" onSubmit={handleSubmit}>
        <label className="workspace-field">
          <span>自选 Ticker</span>
          <input
            value={ticker}
            onChange={(event) => setTicker(event.target.value.toUpperCase())}
            placeholder="NVDA"
            spellCheck={false}
          />
        </label>
        <label className="workspace-field wide-field">
          <span>研究假设</span>
          <input
            value={thesis}
            onChange={(event) => setThesis(event.target.value)}
            placeholder="AI 基础设施龙头，关注估值与订单能见度"
          />
        </label>
        <button className="primary-action" type="submit" disabled={isSaving}>
          <Save size={15} aria-hidden="true" />
          {isSaving ? "保存中" : "保存自选股"}
        </button>
      </form>

      <p className="workspace-message" aria-live="polite">
        {message}
      </p>

      <div className="module-list">
        {items.map((item) => (
          <article className="module-row workspace-row" key={item.ticker}>
            <div>
              <strong>{item.ticker}</strong>
              <p>{item.thesis}</p>
            </div>
            <button className="ghost-action danger" type="button" onClick={() => handleDelete(item.ticker)}>
              <Trash2 size={14} aria-hidden="true" />
              删除 {item.ticker}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
