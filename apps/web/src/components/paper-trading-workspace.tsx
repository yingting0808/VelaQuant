"use client";

import { useEffect, useState } from "react";
import { Play, ShoppingCart } from "lucide-react";
import {
  getPaperEventLedger,
  getPaperSchedulerStatus,
  getPaperRuns,
  getPaperTradingSummary,
  runPaperTradingDailyLoop,
  submitPaperOrder,
  type PaperEventLedgerPayload,
  type PaperCandidatePayload,
  type PaperRunPayload,
  type PaperSchedulerStatusPayload,
  type PaperTradingSummaryPayload
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

function readinessLabel(value: string | undefined): string {
  if (!value) {
    return "未复盘";
  }
  return readinessLabels[value] ?? value;
}

export function PaperTradingWorkspace() {
  const [summary, setSummary] = useState<PaperTradingSummaryPayload | null>(null);
  const [scheduler, setScheduler] = useState<PaperSchedulerStatusPayload | null>(null);
  const [runs, setRuns] = useState<PaperRunPayload[]>([]);
  const [eventLedger, setEventLedger] = useState<PaperEventLedgerPayload | null>(null);
  const [message, setMessage] = useState("正在读取模拟盘。");
  const [isRunning, setIsRunning] = useState(false);
  const [orderingTicker, setOrderingTicker] = useState<string | null>(null);

  async function refreshSummary(nextMessage?: string) {
    const [payload, runPayload, ledgerPayload] = await Promise.all([
      getPaperTradingSummary(),
      getPaperRuns(),
      getPaperEventLedger()
    ]);
    setSummary(payload);
    setRuns(runPayload.runs);
    setEventLedger(ledgerPayload);
    setMessage(nextMessage ?? "模拟盘已同步。");
  }

  useEffect(() => {
    let active = true;
    Promise.all([getPaperTradingSummary(), getPaperSchedulerStatus(), getPaperRuns(), getPaperEventLedger()]).then(
      ([payload, schedulerStatus, runPayload, ledgerPayload]) => {
        if (!active) {
          return;
        }
        setSummary(payload);
        setScheduler(schedulerStatus);
        setRuns(runPayload.runs);
        setEventLedger(ledgerPayload);
        setMessage("模拟盘已同步。");
      }
    );
    return () => {
      active = false;
    };
  }, []);

  async function handleDailyRun() {
    setIsRunning(true);
    setMessage("正在运行今日模拟。");
    try {
      const payload = await runPaperTradingDailyLoop();
      const [runPayload, ledgerPayload] = await Promise.all([getPaperRuns(), getPaperEventLedger()]);
      setSummary(payload);
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
        order_type: "market",
        quantity: candidate.proposed_quantity,
        side: "buy",
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

  const account = summary?.account;
  const review = summary?.latest_review;
  const candidates = summary?.candidates ?? [];
  const orders = summary?.orders ?? [];
  const positions = summary?.positions ?? [];
  const schedulerLabel = scheduler?.enabled ? (scheduler.running ? "运行中" : "已启用") : "未启用";
  const replayChain =
    eventLedger?.latest_replay?.chains.find((chain) => chain.order_states.length > 0) ??
    eventLedger?.latest_replay?.chains[0] ??
    null;
  const topicSummary =
    eventLedger?.latest_topic_counts.map((item) => `${item.topic} ${item.count}`).join(" / ") ?? "暂无事件";

  return (
    <div className="module-view">
      <header className="page-header">
        <div>
          <p>候选、解释、纸面成交、PnL 与复盘</p>
          <h2>模拟盘</h2>
        </div>
        <div className="status-pill neutral">{readinessLabel(review?.readiness)}</div>
      </header>

      <section className="metric-grid" aria-label="模拟盘指标">
        <div className="metric-card">
          <div className="metric-label">账户权益</div>
          <strong>{formatCurrency(account?.equity ?? 0)}</strong>
        </div>
        <div className="metric-card">
          <div className="metric-label">现金</div>
          <strong>{formatCurrency(account?.cash ?? 0)}</strong>
        </div>
        <div className="metric-card">
          <div className="metric-label">期望值</div>
          <strong>{formatCurrency(review?.expectancy ?? 0)}</strong>
        </div>
      </section>

      <section className="data-panel workspace-panel" aria-label="模拟盘控制台">
        <div className="panel-heading">
          <div>
            <h3>{account?.name ?? "默认模拟盘"}</h3>
            <p>默认 paper-only；净期望未稳定前不进入实盘。</p>
          </div>
          <button className="primary-action" type="button" onClick={handleDailyRun} disabled={isRunning}>
            <Play size={15} aria-hidden="true" />
            {isRunning ? "运行中" : "运行今日模拟"}
          </button>
        </div>
        <p className="workspace-message" aria-live="polite">
          {message}
        </p>
      </section>

      <section className="data-panel workspace-panel" aria-label="每日调度">
        <div className="panel-heading">
          <div>
            <h3>每日调度</h3>
            <p>Docker API 使用 APScheduler 触发同一条模拟盘链路</p>
          </div>
          <span className={scheduler?.running ? "status-pill success" : "status-pill neutral"}>{schedulerLabel}</span>
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
        </div>
      </section>

      <section className="data-panel workspace-panel" aria-label="运行账本">
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

      <section className="data-panel workspace-panel" aria-label="事件账本">
        <div className="panel-heading">
          <div>
            <h3>事件账本</h3>
            <p>{eventLedger?.summary ?? "正在读取 CoreEventLog。"}</p>
          </div>
          <span className={eventLedger?.replay_ready ? "status-pill success" : "status-pill warning"}>
            {eventLedger?.replay_ready ? "可回放" : "不可回放"}
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
        </div>
        <div className="import-result">
          <strong>{replayChain ? `${replayChain.ticker ?? "UNKNOWN"} · ${replayChain.terminal_state ?? "open"}` : "暂无可回放链路"}</strong>
          <p>
            {topicSummary} · 状态序列{" "}
            {replayChain?.order_states.length ? replayChain.order_states.join(" → ") : "未记录"}
          </p>
          <p>警告 {(eventLedger?.warnings ?? []).join(" / ") || "无"}</p>
        </div>
      </section>

      <section className="data-panel workspace-panel" aria-label="候选池">
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
              {candidates.map((candidate) => (
                <tr key={candidate.id}>
                  <td>
                    <span className="ticker-chip">{candidate.ticker}</span>
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
                      disabled={orderingTicker === candidate.ticker || candidate.status === "ordered"}
                    >
                      <ShoppingCart size={14} aria-hidden="true" />
                      {candidate.status === "ordered" ? "已模拟" : `模拟买入 ${candidate.ticker}`}
                    </button>
                  </td>
                </tr>
              ))}
              {!candidates.length ? (
                <tr>
                  <td colSpan={6}>点击运行今日模拟生成候选。</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-panel workspace-panel" aria-label="模拟订单">
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

      <section className="data-panel workspace-panel" aria-label="模拟持仓">
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

      <section className="data-panel workspace-panel" aria-label="复盘策略">
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
