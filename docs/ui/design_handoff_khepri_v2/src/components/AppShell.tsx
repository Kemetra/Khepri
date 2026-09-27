import * as React from "react";

export interface AppShellProps {
  /** The navigation rail - normally a `Sidebar`. Sits on the inline-start edge (right in RTL). */
  sidebar: React.ReactNode;
  /** The top bar - normally a `TopBar`. */
  topbar?: React.ReactNode;
  /** Page content. */
  children?: React.ReactNode;
}

/**
 * Full-page application frame: sidebar rail on the inline-start edge, top bar, and a
 * scrollable main canvas. Wrap it in `KhepriProvider`.
 */
export function AppShell({ sidebar, topbar, children }: AppShellProps) {
  return (
    <div className="k-shell">
      <aside className="k-shell__sidebar">{sidebar}</aside>
      <div className="k-shell__body">
        {topbar ? <header className="k-shell__topbar">{topbar}</header> : null}
        <main className="k-shell__main">{children}</main>
      </div>
    </div>
  );
}
