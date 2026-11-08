"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { api, type Grounding, type Receipt } from "../lib/api";
import { Icon, Panel, Spinner, cx } from "./ui";

const Ctx = createContext<(receiptId: string) => void>(() => {});
export const useReceipt = () => useContext(Ctx);

const parse = (v: unknown) => {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
};

// Receipts are immutable (hash-chained), so caching by id is safe.
const cache = new Map<string, Promise<Receipt>>();
export function getReceipt(id: string) {
  if (!cache.has(id)) {
    const p = api<Receipt>(`/api/receipts/${id}`).then((r) => ({ ...r, args: parse(r.args), result: parse(r.result) }));
    p.catch(() => cache.delete(id));
    cache.set(id, p);
  }
  return cache.get(id)!;
}

const AUDIT_KEY = "pubhedge.audit";
type AuditState = { audit: boolean; setAudit: (v: boolean | ((a: boolean) => boolean)) => void };
const AuditCtx = createContext<AuditState>({ audit: false, setAudit: () => {} });
/** Quiet view (false) or the audit view, where every figure and panel shows its full badge. */
export const useAudit = () => useContext(AuditCtx);

// The badge of the panel a figure sits in. undefined: not inside a labelled panel.
const ScopeCtx = createContext<string | undefined>(undefined);
export const ProvScope = ScopeCtx.Provider;

export function ProvenanceProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState<string | null>(null);
  const [audit, setAuditState] = useState(false);
  const setAudit = useCallback<AuditState["setAudit"]>(
    (v) =>
      setAuditState((prev) => {
        const next = typeof v === "function" ? v(prev) : v;
        try {
          localStorage.setItem(AUDIT_KEY, next ? "1" : "0");
        } catch {}
        return next;
      }),
    []
  );
  useEffect(() => {
    try {
      setAuditState(localStorage.getItem(AUDIT_KEY) === "1");
    } catch {}
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "s" || e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      setAudit((a) => !a);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setAudit]);
  return (
    <AuditCtx.Provider value={{ audit, setAudit }}>
      <MotionConfig reducedMotion="user">
      <Ctx.Provider value={setOpen}>
        {children}
        {audit && <AuditLegend />}
        <AnimatePresence>{open && <ReceiptDrawer key={open} id={open} onClose={() => setOpen(null)} />}</AnimatePresence>
      </Ctx.Provider>
      </MotionConfig>
    </AuditCtx.Provider>
  );
}

/** The top-bar switch between the quiet view and the audit view (keyboard: S). */
export function AuditSwitch() {
  const { audit, setAudit } = useAudit();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={audit}
      aria-keyshortcuts="S"
      onClick={() => setAudit(!audit)}
      data-testid="audit-switch"
      className="hit press flex h-8 items-center gap-2 whitespace-nowrap rounded-pill px-3 text-xs text-fg-2 hover:bg-surface-3 hover:text-fg"
    >
      <span
        aria-hidden
        className={cx(
          "relative h-4 w-6 shrink-0 rounded-pill transition-colors",
          audit ? "bg-accent-fill" : "bg-surface-3 shadow-[inset_0_0_0_1px_var(--field-edge)]"
        )}
      >
        <span
          className={cx(
            "absolute top-0.5 h-3 w-3 rounded-full transition-transform",
            audit ? "translate-x-[10px] bg-accent-ink" : "translate-x-0.5 bg-fg-3"
          )}
        />
      </span>
      Show sources
    </button>
  );
}

// ---------- The quiet label: a short word and a monochrome shape ----------

type GlyphName = "solid" | "hollow" | "dashed" | "square" | "square-dashed" | "triangle" | "diamond" | "half" | "cross";
const CACHED = "REAL · CACHED";
// Circles are data (live, cached, modelled); squares are the sandboxes (test mode, paper); the rest are runs.
const KIND: Record<string, { label: string; glyph: GlyphName }> = {
  REAL: { label: "Live", glyph: "solid" },
  [CACHED]: { label: "Cached", glyph: "hollow" },
  SYNTHETIC: { label: "Modelled", glyph: "dashed" },
  "TEST MODE": { label: "Test mode", glyph: "square" },
  PAPER: { label: "Paper", glyph: "square-dashed" },
  REPLAY: { label: "Replay", glyph: "triangle" },
  TEMPLATE: { label: "Template", glyph: "diamond" },
  MODEL: { label: "Model", glyph: "half" },
  ERROR: { label: "Unavailable", glyph: "cross" },
};
// A badge the API left out says so rather than passing for a known one.
const kind = (badge: string | null | undefined) =>
  badge ? (KIND[badge] ?? { label: badge.charAt(0) + badge.slice(1).toLowerCase(), glyph: "hollow" as GlyphName }) : { label: "No badge", glyph: "cross" as GlyphName };

/** The key to the shapes, shown while the audit view is on. */
function AuditLegend() {
  const items = ["REAL", CACHED, "SYNTHETIC", "TEST MODE", "PAPER", "REPLAY", "TEMPLATE", "MODEL"];
  return (
    <div
      role="note"
      aria-label="What the source shapes mean"
      data-testid="audit-legend"
      className="prov-reveal fixed bottom-6 left-1/2 z-[var(--z-toast)] flex max-w-[calc(100vw-2rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-x-4 gap-y-1 rounded-pill bg-[var(--popover)] px-4 py-2 text-xs text-fg-2 shadow-[var(--panel-hi),var(--panel-shadow)]"
    >
      <span className="text-fg">Sources</span>
      {items.map((b) => (
        <span key={b} className="inline-flex items-center gap-1 whitespace-nowrap">
          <Glyph badge={b} />
          {b}
        </span>
      ))}
      <span className="text-fg-3">Click any figure for its receipt</span>
    </div>
  );
}

const LONDON = "Europe/London";
function londonTime(iso: unknown, full = false) {
  if (typeof iso !== "string") return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: LONDON });
  const date = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(full ? { year: "numeric" } : {}), timeZone: LONDON });
  if (full) return `${date}, ${time}`;
  return date === new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: LONDON }) ? time : date;
}

/** "Live", "Cached 14:02", "Modelled"... */
export function quietLabel(badge: string, fetchedAt?: unknown) {
  const k = kind(badge);
  const at = badge === CACHED ? londonTime(fetchedAt) : "";
  return at ? `${k.label} ${at}` : k.label;
}

export function Glyph({ badge }: { badge: string }) {
  const g = kind(badge).glyph;
  const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.25 };
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden className="shrink-0">
      {g === "solid" && <circle cx="5" cy="5" r="3.5" fill="currentColor" />}
      {g === "hollow" && <circle cx="5" cy="5" r="3.4" {...stroke} />}
      {g === "dashed" && <circle cx="5" cy="5" r="3.4" {...stroke} strokeDasharray="1.8 1.6" />}
      {g === "square" && <rect x="1.6" y="1.6" width="6.8" height="6.8" rx="1" {...stroke} />}
      {g === "square-dashed" && <rect x="1.6" y="1.6" width="6.8" height="6.8" rx="1" {...stroke} strokeDasharray="1.8 1.4" />}
      {g === "triangle" && <path d="M2.5 1.8v6.4L8.2 5z" {...stroke} strokeLinejoin="round" />}
      {g === "diamond" && <path d="M5 1.3L8.7 5 5 8.7 1.3 5z" {...stroke} strokeLinejoin="round" />}
      {g === "half" && (
        <>
          <circle cx="5" cy="5" r="3.4" {...stroke} />
          <path d="M5 1.6a3.4 3.4 0 010 6.8z" fill="currentColor" />
        </>
      )}
      {g === "cross" && <path d="M2.2 2.2l5.6 5.6M7.8 2.2L2.2 7.8" {...stroke} strokeLinecap="round" />}
    </svg>
  );
}

type Meta = Record<string, unknown>;
const META_KEYS = ["source", "licence", "fetched_at", "generator", "seed", "method", "model"] as const;
const metaRows = (info: Meta | null | undefined) =>
  info
    ? META_KEYS.filter((k) => info[k] !== undefined && info[k] !== null && info[k] !== "").map((k) => [
        k === "fetched_at" ? "fetched" : k,
        k === "fetched_at" ? londonTime(info[k], true) || String(info[k]) : String(info[k]),
      ])
    : [];

const receiptMeta = (r: Receipt): Meta => ({ ...(typeof r.result === "object" && r.result ? (r.result as Meta) : {}), badge: r.badge, model: r.model });

/** The glass card a label or a figure shows on hover (after a beat) and on focus (at once). */
// The card stays empty until first hover or focus, so its text is never hidden content at rest.
function ProvCard({ armed, badge, info, receiptId, align = "left" }: { armed: boolean; badge?: string; info: Meta | null | undefined; receiptId?: string | null; align?: "left" | "right" }) {
  const rows = metaRows(info);
  if (!armed) return <span aria-hidden className={cx("prov-card block", align === "right" ? "right-0" : "left-0")} />;
  return (
    <span role="tooltip" className={cx("prov-card block", align === "right" ? "right-0" : "left-0")}>
      <span className="flex items-center gap-2 text-xs font-medium text-fg">
        {badge && <Glyph badge={badge} />}
        {badge ?? "Source"}
      </span>
      {rows.length === 0 && <span className="mt-1 block text-xs text-fg-3">{receiptId ? "Loading source…" : "No source recorded."}</span>}
      {rows.map(([k, v]) => (
        <span key={k} className="mt-1 grid grid-cols-[4.5rem_minmax(0,1fr)] gap-2 text-xs">
          <span className="text-fg-3">{k}</span>
          <span className="break-words text-fg-2">{v}</span>
        </span>
      ))}
      {receiptId && <span className="mt-2 block text-xs text-fg-3">Click for the receipt</span>}
    </span>
  );
}

/** The clickable mark itself: a quiet label, a lone shape, or (audit view) the full badge as a chip. */
function Mark({ badge, mode, fetchedAt, receiptId }: { badge: string; mode: "label" | "inline" | "chip"; fetchedAt?: unknown; receiptId?: string | null }) {
  const openReceipt = useReceipt();
  const short = quietLabel(badge, fetchedAt);
  return (
    <button
      type="button"
      data-testid="badge"
      data-badge={badge}
      aria-label={`${mode === "chip" ? badge : `${short}, ${badge}`}${receiptId ? ", open receipt" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        if (receiptId) openReceipt(receiptId);
      }}
      className={cx(
        "hit inline-flex shrink-0 items-center gap-1 whitespace-nowrap align-middle text-xs font-normal text-fg-3 transition-colors hover:text-fg-2",
        mode === "chip" && "prov-reveal h-6 rounded-pill px-2 shadow-[inset_0_0_0_1px_var(--line-strong)]",
        mode === "label" && "h-6",
        mode === "inline" && "ml-1 h-4 w-4 justify-center",
        receiptId ? "cursor-pointer" : "cursor-default"
      )}
    >
      <Glyph badge={badge} />
      {mode === "chip" ? badge : mode === "label" ? short : null}
    </button>
  );
}

/**
 * The one provenance mark. Quiet by default: a muted word and shape in a panel header ("label"),
 * a lone shape after a figure whose source differs from its panel ("inline"), nothing where it matches.
 * The audit view shows the exact badge everywhere. Hover shows the source; click opens the receipt.
 */
export function ProvBadge({
  badge,
  meta,
  receiptId,
  className,
  variant,
}: {
  badge: string;
  meta?: Meta;
  receiptId?: string | null;
  className?: string;
  variant?: "label" | "inline" | "chip";
}) {
  const { audit } = useAudit();
  const scope = useContext(ScopeCtx);
  const [fetched, setFetched] = useState<Meta | null>(null);
  const [armed, setArmed] = useState(false);
  const info = meta ?? fetched;
  const load = useCallback(() => {
    if (!meta && !fetched && receiptId) getReceipt(receiptId).then((r) => setFetched(receiptMeta(r)), () => setFetched({}));
  }, [meta, fetched, receiptId]);
  const arm = () => {
    setArmed(true);
    load();
  };
  const mode = variant ?? (scope !== undefined ? "inline" : "label");
  if (mode === "inline" && !audit && badge === scope) return null;
  return (
    <span className={cx("prov inline-flex", className)} onMouseEnter={arm} onFocus={arm}>
      <Mark badge={badge} mode={audit && mode !== "inline" ? "chip" : mode} fetchedAt={info?.fetched_at} receiptId={receiptId} />
      <ProvCard armed={armed} badge={badge} info={info} receiptId={receiptId} align={mode === "label" ? "right" : "left"} />
    </span>
  );
}

/**
 * A figure. It inherits its panel's provenance; a source that differs shows its shape after it.
 * Hover: a faint dotted underline and the source card. Click: the receipt.
 */
export function Num({
  rid,
  r,
  badge,
  mark = true,
  children,
  className,
}: {
  rid?: string | null;
  /** A tool result: its receipt, badge and source in one. */
  r?: { receipt_id: string; badge: string } & Meta;
  badge?: string;
  /** false where the row already carries its own label (a source list, the audit log, an agent-run line). */
  mark?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  const openReceipt = useReceipt();
  const { audit } = useAudit();
  const scope = useContext(ScopeCtx);
  const id = rid ?? r?.receipt_id;
  const known = badge ?? r?.badge;
  const [rec, setRec] = useState<Meta | null>(null);
  const [armed, setArmed] = useState(false);
  const load = useCallback(() => {
    if (id && !rec) getReceipt(id).then((x) => setRec(receiptMeta(x)), () => setRec({}));
  }, [id, rec]);
  const arm = () => {
    setArmed(true);
    if (!r) load();
  };
  // In the audit view a figure outside any labelled panel finds its badge on its receipt.
  useEffect(() => {
    if (mark && audit && known === undefined && scope === undefined) load();
  }, [mark, audit, known, scope, load]);
  if (!id) return <span className={className}>{children}</span>;
  const own = known ?? scope ?? (rec?.badge as string | undefined);
  const info = (r as Meta | undefined) ?? rec;
  return (
    <span className="prov inline" onMouseEnter={arm} onFocus={arm}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          openReceipt(id);
        }}
        className={cx("num-link cursor-pointer whitespace-nowrap", audit && "num-link--audit", className)}
      >
        {children}
      </button>
      {mark && own && (audit || own !== scope) && <Mark badge={own} mode="inline" fetchedAt={info?.fetched_at} receiptId={id} />}
      <ProvCard armed={armed} badge={own} info={info} receiptId={id} />
    </span>
  );
}

/** A glass panel whose header carries one quiet provenance label; figures inside inherit it. */
export function ProvPanel({
  prov,
  actions,
  ...rest
}: React.ComponentProps<typeof Panel> & { prov?: { badge: string; meta?: Meta; receiptId?: string | null } }) {
  return (
    <ScopeCtx.Provider value={prov?.badge}>
      <Panel
        {...rest}
        actions={
          (actions || prov) && (
            <>
              {actions}
              {prov && <ProvBadge {...prov} variant="label" />}
            </>
          )
        }
      />
    </ScopeCtx.Provider>
  );
}

function ReceiptDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [r, setR] = useState<Receipt | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    getReceipt(id).then(setR, (e) => setErr(String(e)));
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [id, onClose]);
  const result = (r?.result ?? null) as Record<string, unknown> | null;
  const grounding = (result && typeof result === "object" ? result.grounding : undefined) as Grounding | undefined;

  return (
    <>
      <motion.div className="fixed inset-0 z-modal bg-[var(--scrim)]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.aside
        data-testid="receipt-drawer"
        role="dialog"
        aria-label="Receipt"
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 40, opacity: 0 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="glass fixed bottom-2 right-2 top-2 z-modal flex w-[min(560px,calc(100%-16px))] flex-col bg-[var(--surface-solid)]"
      >
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-line px-6">
          <div className="flex items-center gap-3">
            <h2 className="max-w-none font-display text-lg font-medium">Receipt</h2>
            <span className="font-mono text-xs text-fg-3">{id}</span>
          </div>
          <button type="button" onClick={onClose} aria-label="Close receipt" className="hit press flex h-8 w-8 items-center justify-center rounded-pill text-fg-2 hover:bg-surface-3 hover:text-fg">
            <Icon name="x" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          {err && <p className="text-sm text-negative">Couldn’t load this receipt ({err}).</p>}
          {!r && !err && <Spinner className="text-accent" />}
          {r && (
            <div className="space-y-6">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-accent">{r.call}</span>
                  <ProvBadge badge={r.badge} meta={result ?? undefined} variant="chip" />
                </div>
                <dl className="mt-3 grid grid-cols-[7rem_minmax(0,1fr)] gap-y-1 text-xs">
                  {[
                    ["step", r.step],
                    ["model", r.model],
                    ["ms", r.ms],
                    ["run", r.run_id],
                    ["seq", r.seq],
                    ["at", new Date(r.ts * 1000).toISOString()],
                  ].map(([k, v]) => (
                    <div key={String(k)} className="contents">
                      <dt className="text-fg-3">{k}</dt>
                      <dd className="font-mono text-fg">{String(v ?? "")}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              {grounding && (
                <Section title={`Grounding check · ${grounding.ok ? "passed" : "failed"}`}>
                  <p className="text-sm text-fg-2">Every number in the narration must appear in a tool result from this run.</p>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {grounding.numbers.map((n, i) => (
                      <li
                        key={i}
                        className={cx(
                          "rounded-pill px-2 text-xs",
                          n.grounded ? "text-positive shadow-[inset_0_0_0_1px_var(--accent-edge)]" : "text-negative shadow-[inset_0_0_0_1px_var(--negative)]"
                        )}
                      >
                        {n.grounded ? "✓" : "✗"} {n.text}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-fg-2">
                    Ungrounded: {grounding.ungrounded.length ? grounding.ungrounded.join(", ") : "none"}
                  </p>
                </Section>
              )}

              <Section title="Inputs">
                <Json value={r.args} />
              </Section>
              <Section title="Result and source">
                <Json value={r.result} />
              </Section>
              <Section title="Hash chain">
                <dl className="grid grid-cols-[5rem_minmax(0,1fr)] gap-y-1 text-xs">
                  <dt className="text-fg-3">prev_hash</dt>
                  <dd className="break-all font-mono text-fg-2">{r.prev_hash}</dd>
                  <dt className="text-fg-3">hash</dt>
                  <dd className="break-all font-mono text-fg">{r.hash}</dd>
                </dl>
              </Section>
            </div>
          )}
        </div>
      </motion.aside>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 font-sans text-xs font-medium tracking-normal text-fg-3">{title}</h3>
      {children}
    </section>
  );
}

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[320px] overflow-auto rounded bg-surface-2 p-3 font-mono text-xs text-fg-2 shadow-[inset_0_0_0_1px_var(--line)]">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
