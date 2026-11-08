export function gbp(n: number, opts: { sign?: boolean } = {}) {
  const abs = Math.abs(n).toLocaleString("en-GB", { maximumFractionDigits: 0 });
  if (n < 0) return `−£${abs}`;
  return `${opts.sign ? "+" : ""}£${abs}`;
}

export function pct(n: number, digits = 1) {
  return `${(n * 100).toFixed(digits)}%`;
}
