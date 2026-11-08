"use client";

import { Icon, Logo, ThemeToggle, cx } from "../ui";

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
    <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-12 items-center border-b border-line px-4">
        <Logo />
      </div>
      <div className="p-2">
        <button className="flex w-full items-center gap-2.5 rounded px-2 py-2 text-left hover:bg-surface-2">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-surface-3 font-mono text-[11px] text-fg-2">
            {initials}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] text-fg">{pubName}</span>
            <span className="block truncate text-[11.5px] text-fg-3">{place}</span>
          </span>
          <Icon name="chevron-down" size={14} className="text-fg-3" />
        </button>
      </div>
      <nav className="flex-1 px-2">
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => onNav(n.id)}
            aria-current={nav === n.id ? "page" : undefined}
            className={cx(
              "flex h-8 w-full items-center gap-2.5 rounded px-2 text-[13px] transition-colors",
              nav === n.id ? "bg-surface-3 text-fg" : "text-fg-2 hover:bg-surface-2 hover:text-fg"
            )}
          >
            <Icon name={n.icon} size={15} className={nav === n.id ? "text-accent" : "text-fg-3"} />
            {n.label}
          </button>
        ))}
      </nav>
      <div className="flex items-center gap-2.5 border-t border-line px-4 py-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-3 text-[11px] font-medium text-fg-2">
          {ownerInitials}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[12.5px] text-fg">{owner}</span>
          <span className="block text-[11.5px] text-fg-3">Owner</span>
        </span>
      </div>
    </aside>
  );
}

export function TopBar({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-bg px-5">
      <h1 className="text-[15px] font-medium tracking-[-0.01em]">{title}</h1>
      <div className="flex items-center gap-4">
        {right}
        <ThemeToggle />
      </div>
    </header>
  );
}

export function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th className={cx("h-8 px-4 text-[11px] font-medium uppercase tracking-[0.04em] text-fg-3", right ? "text-right" : "text-left")}>
      {children}
    </th>
  );
}

export function Td({ children, right, mono, className }: { children: React.ReactNode; right?: boolean; mono?: boolean; className?: string }) {
  return (
    <td className={cx("h-9 px-4 text-[12.5px]", right && "text-right", mono && "font-mono", className)}>{children}</td>
  );
}
