import { AppShell } from "@/components/app-shell";
import { ModuleView } from "@/components/module-view";
import { sampleDashboard } from "@/lib/sample-data";

export default function NotesPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <ModuleView module="notes" />
    </AppShell>
  );
}
