import { DataSourceStatusPanel } from "@/components/data-source-status-panel";
import { AppShell } from "@/components/app-shell";
import { ModuleView } from "@/components/module-view";
import { sampleDashboard } from "@/lib/sample-data";

export default function SettingsPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-stack">
        <ModuleView module="settings" />
        <DataSourceStatusPanel />
      </div>
    </AppShell>
  );
}
