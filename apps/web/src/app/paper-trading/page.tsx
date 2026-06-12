import { AppShell } from "@/components/app-shell";
import { PaperTradingWorkspace } from "@/components/paper-trading-workspace";
import { sampleDashboard } from "@/lib/sample-data";

export default function PaperTradingPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <PaperTradingWorkspace />
    </AppShell>
  );
}
