"use client";

import { forwardRef, useEffect, useState } from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
        <rect x="0.5" y="0.5" width="19" height="19" rx="6" fill="var(--surface-3)" stroke="var(--line-strong)" />
        <path d="M5 14V8.5L10 5l5 3.5V14" fill="none" stroke="var(--fg)" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M8 14v-3h4v3" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
      {!compact && <span className="font-display text-md font-medium tracking-[var(--tracking-display)]">Pub Hedge</span>}
    </div>
  );
}

type IconName =
  | "check"
  | "chevron-right"
  | "chevron-left"
  | "chevron-down"
  | "arrow-up-right"
  | "rain"
  | "trophy"
  | "receipt"
  | "bank"
  | "plug"
  | "shield"
  | "activity"
  | "grid"
  | "settings"
  | "bell"
  | "calendar"
  | "layers"
  | "search"
  | "alert"
  | "lock"
  | "spark"
  | "sun"
  | "moon"
  | "x";

const PATHS: Record<IconName, string> = {
  check: "M3.5 8.5l3 3 6-7",
  "chevron-right": "M6 3.5L10.5 8 6 12.5",
  "chevron-left": "M10 3.5L5.5 8 10 12.5",
  "chevron-down": "M3.5 6L8 10.5 12.5 6",
  "arrow-up-right": "M5 11L11 5M6 5h5v5",
  rain: "M4.5 9.5a3 3 0 01.4-6 4 4 0 017.6 1.2A2.5 2.5 0 0112 9.5H4.5M6 12l-.7 1.5M9 12l-.7 1.5M12 12l-.7 1.5",
  trophy: "M5 2.5h6v3a3 3 0 01-6 0v-3zM5 4H2.5a2 2 0 002.6 2.4M11 4h2.5a2 2 0 01-2.6 2.4M8 8.5v3M5.5 13.5h5",
  receipt: "M3.5 2v12l1.5-1 1.5 1 1.5-1 1.5 1 1.5-1 1.5 1V2zM6 5.5h4M6 8h4",
  bank: "M2 6l6-3.5L14 6M3 6.5v5M6.3 6.5v5M9.7 6.5v5M13 6.5v5M2 13.5h12",
  plug: "M6 2v3M10 2v3M4.5 5h7v2.5a3.5 3.5 0 01-7 0zM8 11v3",
  shield: "M8 2l5 2v4c0 3-2.2 5-5 6-2.8-1-5-3-5-6V4z",
  activity: "M2 8h2.5l2-4.5 3 9 2-4.5H14",
  grid: "M2.5 2.5h4.5v4.5H2.5zM9 2.5h4.5v4.5H9zM2.5 9h4.5v4.5H2.5zM9 9h4.5v4.5H9z",
  settings: "M8 5.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5zM8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4",
  bell: "M4 11V7a4 4 0 018 0v4l1.5 1.5h-11zM6.5 14h3",
  calendar: "M2.5 3.5h11v10h-11zM2.5 6.5h11M5.5 2v3M10.5 2v3",
  layers: "M8 2l6 3-6 3-6-3zM2 8l6 3 6-3M2 11l6 3 6-3",
  search: "M7 12a5 5 0 100-10 5 5 0 000 10zM10.5 10.5L14 14",
  alert: "M8 2l6.5 11.5h-13zM8 6.5v3M8 11.5v.5",
  lock: "M4 7.5h8v6H4zM5.5 7.5V5a2.5 2.5 0 015 0v2.5",
  spark: "M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M6 10l-2 2",
  sun: "M8 10.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1",
  moon: "M13.5 9.5A5.5 5.5 0 016.5 2.5a5.5 5.5 0 107 7z",
  x: "M4 4l8 8M12 4l-8 8",
};

export const THEME_KEY = "pubhedge.theme.dusk"; // new key: the old one stored "light" when light was the default

/** Dusk slate is the default; light is Dusk day. */
export function ThemeToggle() {
  const [dark, setDark] = useState(true);
  useEffect(() => setDark(document.documentElement.dataset.theme !== "light"), []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    if (next) delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = "light";
    try {
      localStorage.setItem(THEME_KEY, next ? "dark" : "light");
    } catch {}
  };
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
      className="hit press flex h-8 w-8 items-center justify-center rounded-pill text-fg-2 hover:bg-surface-3 hover:text-fg"
    >
      <Icon name={dark ? "sun" : "moon"} />
    </button>
  );
}

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <path d={PATHS[name]} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
};

/** Pills: one periwinkle primary, a ghost pill beside it, a bare ghost for back links. 40px (md) or 32px (sm), 44px hit target. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", className, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      className={cx(
        "hit press inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-pill font-semibold disabled:cursor-not-allowed disabled:opacity-[0.55]",
        size === "md" ? "h-10 px-4 text-sm" : "h-8 px-3 text-xs",
        variant === "primary" && "bg-accent-fill text-accent-ink shadow-[inset_0_1px_0_var(--line-strong)] hover:bg-accent-hi",
        variant === "secondary" && "bg-surface-2 text-fg shadow-[inset_0_0_0_1px_var(--line-strong)] hover:bg-surface-3",
        variant === "ghost" && "text-fg-2 hover:bg-surface-2 hover:text-fg",
        className
      )}
      {...rest}
    />
  );
});

/** The glass panel: a title in the display face, quiet actions on the right, rows split by hairlines. */
export function Panel({
  title,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cx("glass", className)}>
      {(title || actions) && (
        <header className="flex min-h-12 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-line px-4 py-2 sm:px-6">
          <h2 className="min-w-[10rem] max-w-none flex-1 font-display text-md font-medium text-fg">{title}</h2>
          {actions && <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-3">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName ?? "px-4 py-4 sm:px-6"}>{children}</div>
    </section>
  );
}

export type Tone = "neutral" | "accent" | "positive" | "negative" | "warning";

// State words: periwinkle is done or on, apricot is open, owed or blocked. Text and a mark, never a fill.
const TONE: Record<Tone, string> = {
  neutral: "text-fg-2",
  accent: "text-accent",
  positive: "text-positive",
  negative: "text-warning",
  warning: "text-warning",
};

export function Badge({ tone = "neutral", children, dot }: { tone?: Tone; children: React.ReactNode; dot?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-2 whitespace-nowrap text-xs font-medium", TONE[tone])}>
      {dot && <span className="h-2 w-2 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

export function Spinner({ size = 14, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" className={cx("keep-motion animate-spin", className)} aria-label="Working">
      <circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="1.5" />
      <path d="M8 1.75a6.25 6.25 0 016.25 6.25" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function KeyValue({ rows, className }: { rows: { label: string; value: React.ReactNode; mono?: boolean }[]; className?: string }) {
  return (
    <dl className={cx("divide-y divide-line", className)}>
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)] items-baseline gap-4 py-3">
          <dt className="text-xs text-fg-3">{r.label}</dt>
          <dd className={cx("text-sm text-fg", r.mono && "font-mono text-xs")}>{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A figure and its label. Shortfalls are apricot, never red. */
export function Metric({
  label,
  value,
  sub,
  tone,
  size = "md",
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "positive" | "negative" | "warning";
  size?: "md" | "lg";
}) {
  return (
    <div>
      <div className="text-xs text-fg-3">{label}</div>
      <div
        className={cx(
          "mt-1 font-display font-medium tracking-[var(--tracking-display)]",
          size === "lg" ? "text-3xl" : "text-xl",
          tone === "positive" && "text-positive",
          (tone === "negative" || tone === "warning") && "text-warning",
          !tone && "text-fg"
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-fg-3">{sub}</div>}
    </div>
  );
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: React.ReactNode }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-fg">
      <span
        className={cx(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
          checked ? "border-accent-fill bg-accent-fill text-accent-ink" : "border-field-edge bg-surface-2"
        )}
      >
        {checked && <Icon name="check" size={12} />}
      </span>
      <input type="checkbox" className="sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export const tooltipStyle = {
  contentStyle: {
    background: "var(--popover)",
    border: "0",
    borderRadius: "var(--radius-inner)",
    boxShadow: "var(--panel-hi), var(--panel-shadow)",
    fontSize: "var(--text-xs)",
    fontFamily: "var(--font-body)",
    padding: "var(--space-xs) var(--space-sm)",
    color: "var(--fg)",
  },
  labelStyle: { color: "var(--fg-3)", marginBottom: "var(--space-3xs)" },
  itemStyle: { padding: 0 },
};
