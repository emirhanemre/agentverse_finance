"use client";

import { Icon, Logo, ThemeToggle, cx } from "../ui";
import type { Timeline } from "../../lib/dashboard-data";

export type NavId = "overview" | "protections" | "risks" | "activity" | "sources" | "settings";

export const NAV: { id: NavId; label: string; icon: Parameters<typeof Icon>[0]["name"] }[] = [
  { id: "overview", label: "Overview", icon: "grid" },
  { id: "protections", label: "Protections", icon: "shield" },
  { id: "risks", label: "Risks", icon: "alert" },
  { id: "activity", label: "Activity", icon: "activity" },
  { id: "sources", label: "Data sources", icon: "plug" },
  { id: "settings", label: "Settings", icon: "settings" },
];

export function Sidebar({
  nav,
  onNav,
  pubName,
  owner,
}: {
  nav: NavId;
  onNav: (n: NavId) => void;
  pubName: string;
  owner: string;
}) {
  const initials = owner
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
            OT
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] text-fg">{pubName}</span>
            <span className="block text-[11.5px] text-fg-3">SE22 · East Dulwich</span>
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
          {initials}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[12.5px] text-fg">{owner}</span>
          <span className="block text-[11.5px] text-fg-3">Owner</span>
        </span>
      </div>
    </aside>
  );
}

const TIMELINE: { id: Timeline; label: string }[] = [
  { id: "today", label: "Wed 9 Jul" },
  { id: "rain", label: "Sat 12 Jul · rain" },
  { id: "year", label: "12 months on" },
];

export function TopBar({
  title,
  timeline,
  onTimeline,
  alert,
}: {
  title: string;
  timeline: Timeline;
  onTimeline: (t: Timeline) => void;
  alert: boolean;
}) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-bg px-5">
      <h1 className="text-[15px] font-medium tracking-[-0.01em]">{title}</h1>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-fg-3">Demo timeline</span>
          <div role="tablist" className="flex rounded border border-line-strong bg-surface p-0.5">
            {TIMELINE.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={timeline === t.id}
                onClick={() => onTimeline(t.id)}
                className={cx(
                  "h-6 rounded-[3px] px-2.5 font-mono text-[11.5px] transition-colors",
                  timeline === t.id ? "bg-surface-3 text-fg" : "text-fg-2 hover:text-fg"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <ThemeToggle />
        <button aria-label="Notifications" className="relative flex h-8 w-8 items-center justify-center rounded text-fg-2 hover:bg-surface-2 hover:text-fg">
          <Icon name="bell" />
          {alert && <span className="absolute right-[7px] top-[7px] h-1.5 w-1.5 rounded-full bg-warning" />}
        </button>
      </div>
    </header>
  );
}

export function Feed({ rows, live }: { rows: { time: string; text: string; tone?: string }[]; live?: React.ReactNode }) {
  return (
    <ul className="divide-y divide-line">
      {live}
      {rows.map((r, i) => (
        <li key={`${r.time}-${i}`} className="grid grid-cols-[44px_1fr] gap-3 py-2">
          <span className="font-mono text-[11.5px] leading-5 text-fg-3">{r.time}</span>
          <span
            className={cx(
              "text-[12.5px] leading-5",
              r.tone === "positive" && "text-positive",
              r.tone === "warning" && "text-warning",
              r.tone === "negative" && "text-negative",
              r.tone === "accent" && "text-fg",
              !r.tone && "text-fg-2"
            )}
          >
            {r.text}
          </span>
        </li>
      ))}
    </ul>
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

export function Bar({ value, max, tone = "accent" }: { value: number; max: number; tone?: "accent" | "positive" | "warning" }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-surface-3">
      <div
        className={cx(
          "h-1.5 rounded-full",
          tone === "accent" && "bg-accent",
          tone === "positive" && "bg-positive",
          tone === "warning" && "bg-warning"
        )}
        style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
      />
    </div>
  );
}
