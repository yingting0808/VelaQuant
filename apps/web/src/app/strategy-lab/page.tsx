import { AppShell } from "@/components/app-shell";
import { StrategyBacktestPanel } from "@/components/strategy-backtest-panel";
import { StrategyLabStatusPanel } from "@/components/strategy-lab-status-panel";
import { sampleDashboard } from "@/lib/sample-data";

export default function StrategyLabPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-view">
        <header className="page-header">
          <div>
            <p>LEAN 回测预备环境与数据源就绪度</p>
            <h2>策略实验室</h2>
          </div>
          <div className="status-pill neutral">预备</div>
        </header>

        <StrategyLabStatusPanel />
        <StrategyBacktestPanel />
      </div>
    </AppShell>
  );
}
