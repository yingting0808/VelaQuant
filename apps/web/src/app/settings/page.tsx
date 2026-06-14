import { AIStatusPanel } from "@/components/ai-status-panel";
import { DataSourceStatusPanel } from "@/components/data-source-status-panel";
import { AppShell } from "@/components/app-shell";
import { ModuleView } from "@/components/module-view";
import { RuntimeSettingsPanel } from "@/components/runtime-settings-panel";
import { sampleDashboard } from "@/lib/sample-data";

export default function SettingsPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-stack">
        <ModuleView module="settings" />
        <RuntimeSettingsPanel />
        <DataSourceStatusPanel />
        <AIStatusPanel />
      </div>
    </AppShell>
  );
}
