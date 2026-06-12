import { AppShell } from "@/components/app-shell";
import { MarketSnapshotPanel } from "@/components/market-snapshot-panel";
import { ModuleView } from "@/components/module-view";
import { sampleDashboard } from "@/lib/sample-data";

export default function WatchlistPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-stack">
        <ModuleView module="watchlist" />
        <MarketSnapshotPanel />
      </div>
    </AppShell>
  );
}
