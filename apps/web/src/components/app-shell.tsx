import type { ReactNode } from "react";
import { AiSidecar } from "./ai-sidecar";
import { NavPanel } from "./nav-panel";

type AppShellProps = {
  children: ReactNode;
  prompts: string[];
};

export function AppShell({ children, prompts }: AppShellProps) {
  return (
    <main className="app-shell">
      <NavPanel />

      <section className="workspace">{children}</section>

      <AiSidecar prompts={prompts} />
    </main>
  );
}
