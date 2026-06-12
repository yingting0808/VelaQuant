import type { ReactNode } from "react";
import {
  Bell,
  BookOpenText,
  ChartNoAxesCombined,
  Database,
  LayoutDashboard,
  ListChecks,
  Settings,
  Star
} from "lucide-react";
import { AiSidecar } from "./ai-sidecar";

const navItems = [
  { label: "总览", icon: LayoutDashboard, active: true },
  { label: "自选股", icon: Star, active: false },
  { label: "组合", icon: ChartNoAxesCombined, active: false },
  { label: "预警", icon: Bell, active: false },
  { label: "研究笔记", icon: BookOpenText, active: false },
  { label: "数据导入", icon: Database, active: false },
  { label: "设置", icon: Settings, active: false }
];

type AppShellProps = {
  children: ReactNode;
  prompts: string[];
};

export function AppShell({ children, prompts }: AppShellProps) {
  return (
    <main className="app-shell">
      <nav className="left-nav" aria-label="Primary navigation">
        <div className="brand-block">
          <div className="brand-mark">
            <ListChecks size={18} aria-hidden="true" />
          </div>
          <div>
            <h1>AI 美股</h1>
            <p>Research Ops</p>
          </div>
        </div>

        <div className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <a
                aria-current={item.active ? "page" : undefined}
                className={item.active ? "nav-item active" : "nav-item"}
                href="#"
                key={item.label}
              >
                <Icon size={17} aria-hidden="true" />
                <span>{item.label}</span>
              </a>
            );
          })}
        </div>
      </nav>

      <section className="workspace">{children}</section>

      <AiSidecar prompts={prompts} />
    </main>
  );
}
