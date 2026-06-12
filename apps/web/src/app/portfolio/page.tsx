import { AppShell } from "@/components/app-shell";
import { PortfolioWorkspace } from "@/components/portfolio-workspace";
import { sampleDashboard } from "@/lib/sample-data";

export default function PortfolioPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <PortfolioWorkspace />
    </AppShell>
  );
}
