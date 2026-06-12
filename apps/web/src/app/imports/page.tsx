import { AppShell } from "@/components/app-shell";
import { ImportsWorkspace } from "@/components/imports-workspace";
import { sampleDashboard } from "@/lib/sample-data";

export default function ImportsPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <ImportsWorkspace />
    </AppShell>
  );
}
