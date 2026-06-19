import { Activity, AlertTriangle, BriefcaseBusiness } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { getDashboard } from "@/lib/api";

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

export default async function DashboardPage() {
  const dashboard = await getDashboard();
  const positions = dashboard.portfolio.positions;

  return (
    <AppShell prompts={dashboard.ai_prompts}>
      <div className="dashboard-stack">
        <header className="page-header">
          <div>
            <p>内部投研与组合监控</p>
            <h2>{dashboard.portfolio.name}</h2>
          </div>
          <div className="status-pill">
            <Activity size={15} aria-hidden="true" />
            实盘数据视图
          </div>
        </header>

        <section className="metric-grid" aria-label="组合摘要">
          <article className="metric-card">
            <div className="metric-label">
              <BriefcaseBusiness size={16} aria-hidden="true" />
              组合市值
            </div>
            <strong>{currencyFormatter.format(dashboard.portfolio.total_market_value)}</strong>
          </article>

          <article className="metric-card">
            <div className="metric-label">
              <Activity size={16} aria-hidden="true" />
              持仓数量
            </div>
            <strong>{positions.length}</strong>
          </article>

          <article className="metric-card">
            <div className="metric-label">
              <AlertTriangle size={16} aria-hidden="true" />
              待处理预警
            </div>
            <strong>{dashboard.alerts.length}</strong>
          </article>
        </section>

        <section className="data-panel">
          <div className="panel-heading">
            <div>
              <h3>组合暴露</h3>
              <p>按当前市值和权重监控集中度</p>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Ticker</th>
                  <th className="numeric" scope="col">
                    市值
                  </th>
                  <th className="numeric" scope="col">
                    权重
                  </th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => (
                  <tr key={position.ticker}>
                    <td>
                      <span className="ticker-chip">{position.ticker}</span>
                    </td>
                    <td className="numeric">{currencyFormatter.format(position.market_value)}</td>
                    <td className="numeric">{percentFormatter.format(position.weight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="data-panel compact-panel">
          <div className="panel-heading">
            <div>
              <h3>事件预警</h3>
              <p>与当前组合持仓匹配的待处理事件</p>
            </div>
          </div>
          <div className="alert-list">
            {dashboard.alerts.map((alert) => (
              <div className="alert-row" key={`${alert.ticker}-${alert.title}`}>
                <span className="ticker-chip">{alert.ticker}</span>
                <div>
                  <strong>{alert.title}</strong>
                  <p>
                    {alert.reason} · {alert.source}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
