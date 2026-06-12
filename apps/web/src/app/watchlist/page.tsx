import { AppShell } from "@/components/app-shell";
import { MarketSnapshotPanel } from "@/components/market-snapshot-panel";
import { WatchlistWorkspace } from "@/components/watchlist-workspace";
import { sampleDashboard } from "@/lib/sample-data";

export default function WatchlistPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-stack">
        <header className="page-header">
          <div>
            <p>候选股票、研究假设和行情快照</p>
            <h2>自选股</h2>
          </div>
        </header>
        <WatchlistWorkspace />
        <MarketSnapshotPanel />
      </div>
    </AppShell>
  );
}
