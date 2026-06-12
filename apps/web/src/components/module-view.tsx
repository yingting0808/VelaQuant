import { AlertTriangle, FileSpreadsheet, NotebookTabs, ShieldCheck, SlidersHorizontal, Star } from "lucide-react";

type ModuleKey = "watchlist" | "portfolio" | "alerts" | "notes" | "imports" | "settings";

type ModuleConfig = {
  title: string;
  subtitle: string;
  icon: typeof Star;
  rows: Array<{
    label: string;
    meta: string;
    value: string;
  }>;
};

const modules: Record<ModuleKey, ModuleConfig> = {
  alerts: {
    icon: AlertTriangle,
    rows: [
      { label: "AAPL 10-Q filed", meta: "SEC filing · mock_sec", value: "高" },
      { label: "MSFT 财报日历更新", meta: "财报日历 · mock_events", value: "中" }
    ],
    subtitle: "集中处理组合相关事件和人工复核队列",
    title: "预警"
  },
  imports: {
    icon: FileSpreadsheet,
    rows: [
      { label: "positions.csv", meta: "字段：ticker、quantity、average_cost", value: "可导入" },
      { label: "watchlist.xlsx", meta: "字段：symbol、thesis、owner", value: "草稿" }
    ],
    subtitle: "导入持仓、自选股和研究笔记的结构化数据",
    title: "数据导入"
  },
  notes: {
    icon: NotebookTabs,
    rows: [
      { label: "AAPL 服务业务利润率", meta: "研究笔记 · 今日更新", value: "待处理" },
      { label: "MSFT Azure 需求", meta: "团队笔记 · 中性情景", value: "待复核" }
    ],
    subtitle: "沉淀投研假设、证据和复盘结论",
    title: "研究笔记"
  },
  portfolio: {
    icon: ShieldCheck,
    rows: [
      { label: "主组合", meta: "AAPL / MSFT · USD", value: "$4,253.95" },
      { label: "集中度", meta: "最大持仓权重", value: "50.61%" }
    ],
    subtitle: "查看组合暴露、集中度和人工审批状态",
    title: "组合"
  },
  settings: {
    icon: SlidersHorizontal,
    rows: [
      { label: "人工审批", meta: "AI 输出不能触发订单", value: "必需" },
      { label: "数据模式", meta: "Mock provider，预留混合数据源", value: "本地" }
    ],
    subtitle: "管理数据源、权限和 AI 输出边界",
    title: "设置"
  },
  watchlist: {
    icon: Star,
    rows: [
      { label: "NVDA", meta: "AI 基础设施龙头 · 关注估值", value: "观察" },
      { label: "AMZN", meta: "云业务与零售利润率修复", value: "待复核" },
      { label: "META", meta: "广告周期与 capex 敏感性", value: "跟踪" }
    ],
    subtitle: "跟踪候选股票、研究状态和下一步动作",
    title: "自选股"
  }
};

type ModuleViewProps = {
  module: ModuleKey;
};

export function ModuleView({ module }: ModuleViewProps) {
  const config = modules[module];
  const Icon = config.icon;

  return (
    <div className="module-view">
      <header className="page-header">
        <div>
          <p>{config.subtitle}</p>
          <h2>{config.title}</h2>
        </div>
        <div className="status-pill neutral">
          <Icon size={15} aria-hidden="true" />
          {config.rows.length} 项
        </div>
      </header>

      <section className="data-panel">
        <div className="panel-heading">
          <div>
            <h3>{config.title}工作区</h3>
            <p>当前模块已切换到独立工作区</p>
          </div>
        </div>

        <div className="module-list">
          {config.rows.map((row) => (
            <article className="module-row" key={row.label}>
              <div>
                <strong>{row.label}</strong>
                <p>{row.meta}</p>
              </div>
              <span>{row.value}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
