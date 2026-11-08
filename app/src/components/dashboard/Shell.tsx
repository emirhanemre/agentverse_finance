"use client";

import { Icon, Logo, ThemeToggle, cx } from "../ui";
import { AuditSwitch } from "../Provenance";

export type NavId = "overview" | "protections" | "risks" | "backtest" | "activity" | "sources" | "settings";

export const NAV: { id: NavId; label: string; icon: Parameters<typeof Icon>[0]["name"] }[] = [
  { id: "overview", label: "Overview", icon: "grid" },
  { id: "protections", label: "Protections", icon: "shield" },
  { id: "risks", label: "Risks", icon: "alert" },
  { id: "backtest", label: "Backtest", icon: "layers" },
  { id: "activity", label: "Activity", icon: "activity" },
  { id: "sources", label: "Data sources", icon: "plug" },
  { id: "settings", label: "Settings", icon: "settings" },
];

export function Sidebar({
  nav,
  onNav,
  pubName,
  place,
  owner,
}: {
  nav: NavId;
  onNav: (n: NavId) => void;
  pubName: string;
  place: string;
  owner: string;
}) {
  const initials = pubName
    .replace(/^the\s+/i, "")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const ownerInitials = owner.replace(/[^A-Za-z ]/g, "")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-[var(--surface-solid)] md:flex">
      <div className="flex h-14 items-center border-b border-line px-4">
        <Logo />
      </div>
      <div className="p-2">
        <button type="button" className="press flex w-full items-center gap-3 rounded px-2 py-2 text-left hover:bg-surface-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-3 text-xs font-medium text-fg-2">
            {initials}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-fg">{pubName}</span>
            <span className="block truncate text-xs text-fg-3">{place}</span>
          </span>
          <Icon name="chevron-down" size={14} className="text-fg-3" />
        </button>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 px-2">
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => onNav(n.id)}
            aria-current={nav === n.id ? "page" : undefined}
            className={cx(
              "press flex h-10 w-full items-center gap-3 rounded px-3 text-sm",
              nav === n.id ? "bg-surface-3 font-medium text-fg" : "text-fg-2 hover:bg-surface-2 hover:text-fg"
            )}
          >
            <Icon name={n.icon} size={15} className={nav === n.id ? "text-accent" : "text-fg-3"} />
            {n.label}
          </button>
        ))}
      </nav>
      <div className="flex items-center gap-3 border-t border-line px-4 py-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-3 text-xs font-medium text-fg-2">
          {ownerInitials}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm text-fg">{owner}</span>
          <span className="block text-xs text-fg-3">Owner</span>
        </span>
      </div>
    </aside>
  );
}

export type View = "simple" | "advanced";

/** Simple for the owner, Advanced for the full working. Same switch shape as "Show sources". */
export function ViewSwitch({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  const on = view === "advanced";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label="Advanced view"
      onClick={() => onChange(on ? "simple" : "advanced")}
      data-testid="view-switch"
      className="hit press flex h-8 items-center gap-2 whitespace-nowrap rounded-pill px-3 text-xs text-fg-2 hover:bg-surface-3 hover:text-fg"
    >
      <span
        aria-hidden
        className={cx("relative h-4 w-6 shrink-0 rounded-pill transition-colors", on ? "bg-accent-fill" : "bg-surface-3 shadow-[inset_0_0_0_1px_var(--field-edge)]")}
      >
        <span className={cx("absolute top-0.5 h-3 w-3 rounded-full transition-transform", on ? "translate-x-[10px] bg-accent-ink" : "translate-x-0.5 bg-fg-3")} />
      </span>
      <span className="hidden sm:inline">Advanced</span>
    </button>
  );
}

export function TopBar({ title, right }: { title: React.ReactNode; right?: React.ReactNode }) {
  return (
    <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line bg-bg px-4 py-2 sm:px-6">
      <h1 className="min-w-0 font-display text-lg font-medium">{title}</h1>
      <div className="flex items-center gap-1 sm:gap-3">
        {right}
        <AuditSwitch />
        <ThemeToggle />
      </div>
    </header>
  );
}

export function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th className={cx("h-10 px-6 text-xs font-medium text-fg-3", right ? "text-right" : "text-left")}>
      {children}
    </th>
  );
}

export function Td({ children, right, mono, className }: { children: React.ReactNode; right?: boolean; mono?: boolean; className?: string }) {
  return (
    <td className={cx("h-10 px-6 text-sm", right && "text-right", mono && "font-mono text-xs", className)}>{children}</td>
  );
}

/** Under md the sidebar folds into this scrollable row of the same destinations. */
export function MobileNav({ nav, onNav }: { nav: NavId; onNav: (n: NavId) => void }) {
  return (
    <nav aria-label="Sections" className="flex shrink-0 gap-1 overflow-x-auto border-b border-line px-2 py-2 md:hidden">
      {NAV.map((n) => (
        <button
          key={n.id}
          onClick={() => onNav(n.id)}
          aria-current={nav === n.id ? "page" : undefined}
          className={cx("press h-9 shrink-0 rounded-pill px-3 text-sm", nav === n.id ? "bg-surface-3 font-medium text-fg" : "text-fg-2 hover:bg-surface-2")}
        >
          {n.label}
        </button>
      ))}
    </nav>
  );
}
