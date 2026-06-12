import { AppShell } from "@/components/app-shell";
import { NotesWorkspace } from "@/components/notes-workspace";
import { sampleDashboard } from "@/lib/sample-data";

export default function NotesPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <NotesWorkspace />
    </AppShell>
  );
}
