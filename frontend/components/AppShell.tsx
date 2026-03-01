import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-bg">
      <div className="app-noise" aria-hidden="true" />
      <main className="app-shell">{children}</main>
    </div>
  );
}
