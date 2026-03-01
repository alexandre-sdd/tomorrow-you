import { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <main className="app-shell">
      <div className="app-shell__backdrop" aria-hidden="true" />
      <section className="app-shell__content">{children}</section>
    </main>
  );
}
