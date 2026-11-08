export function gbp(n: number, opts: { sign?: boolean; pence?: boolean } = {}) {
  const digits = opts.pence ? 2 : 0;
  const abs = Math.abs(n).toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (n < 0) return `−£${abs}`;
  return `${opts.sign ? "+" : ""}£${abs}`;
}

export function pct(n: number, digits = 1) {
  return `${(n * 100).toFixed(digits)}%`;
}

/** "2026-09-04" -> "Fri 4 Sep" */
export function day(iso: string | null | undefined, year = false) {
  if (!iso) return "—";
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}), timeZone: "UTC" });
}
