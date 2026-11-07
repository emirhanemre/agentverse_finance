"use client";

import { forwardRef, useEffect, useState } from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
        <rect x="0.5" y="0.5" width="19" height="19" rx="4" fill="var(--surface-3)" stroke="var(--line-strong)" />
        <path d="M5 14V8.5L10 5l5 3.5V14" fill="none" stroke="var(--fg)" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M8 14v-3h4v3" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
      {!compact && <span className="text-[14px] font-medium tracking-[-0.01em]">Pub Hedge</span>}
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

export const THEME_KEY = "pubhedge.theme";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.dataset.theme === "dark"), []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    if (next) document.documentElement.dataset.theme = "dark";
    else delete document.documentElement.dataset.theme;
    try {
      localStorage.setItem(THEME_KEY, next ? "dark" : "light");
    } catch {}
  };
  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
      className="flex h-8 w-8 items-center justify-center rounded text-fg-2 transition-colors hover:bg-surface-2 hover:text-fg"
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

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", className, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40",
        size === "md" ? "h-8 px-3 text-[13px]" : "h-7 px-2.5 text-[12px]",
        variant === "primary" && "bg-accent-strong text-white hover:bg-accent",
        variant === "secondary" && "border border-line-strong bg-surface-2 text-fg hover:bg-surface-3",
        variant === "ghost" && "text-fg-2 hover:bg-surface-2 hover:text-fg",
        className
      )}
      {...rest}
    />
  );
});

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
    <section className={cx("rounded-md border border-line bg-surface", className)}>
      {(title || actions) && (
        <header className="flex h-10 items-center justify-between border-b border-line px-4">
          <h2 className="text-[13px] font-medium text-fg">{title}</h2>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cx("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export type Tone = "neutral" | "accent" | "positive" | "negative" | "warning";

const TONE: Record<Tone, string> = {
  neutral: "bg-surface-3 text-fg-2",
  accent: "bg-accent-wash text-accent",
  positive: "bg-positive-wash text-positive",
  negative: "bg-negative-wash text-negative",
  warning: "bg-warning-wash text-warning",
};

export function Badge({ tone = "neutral", children, dot }: { tone?: Tone; children: React.ReactNode; dot?: boolean }) {
  return (
    <span className={cx("inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded px-1.5 text-[11.5px] font-medium", TONE[tone])}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function Spinner({ size = 14, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" className={cx("animate-spin", className)} aria-label="Working">
      <circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="1.5" />
      <path d="M8 1.75a6.25 6.25 0 016.25 6.25" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function KeyValue({ rows, className }: { rows: { label: string; value: React.ReactNode; mono?: boolean }[]; className?: string }) {
  return (
    <dl className={cx("divide-y divide-line", className)}>
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[180px_1fr] items-baseline gap-4 py-2.5">
          <dt className="text-[12.5px] text-fg-2">{r.label}</dt>
          <dd className={cx("text-[13px] text-fg", r.mono && "font-mono text-[12.5px]")}>{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

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
      <div className="text-[12px] text-fg-2">{label}</div>
      <div
        className={cx(
          "mt-1 font-mono font-medium tracking-[-0.02em]",
          size === "lg" ? "text-[30px] leading-[36px]" : "text-[20px] leading-[28px]",
          tone === "positive" && "text-positive",
          tone === "negative" && "text-negative",
          tone === "warning" && "text-warning",
          !tone && "text-fg"
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-0.5 text-[12px] text-fg-3">{sub}</div>}
    </div>
  );
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: React.ReactNode }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-fg">
      <span
        className={cx(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px] border transition-colors",
          checked ? "border-accent-strong bg-accent-strong text-white" : "border-line-strong bg-surface-2"
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
    background: "var(--surface-2)",
    border: "1px solid var(--line-strong)",
    borderRadius: 4,
    fontSize: 12,
    fontFamily: "var(--font-mono)",
    padding: "6px 10px",
    color: "var(--fg)",
  },
  labelStyle: { color: "var(--fg-2)", marginBottom: 2 },
  itemStyle: { padding: 0 },
};
