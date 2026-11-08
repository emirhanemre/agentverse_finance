"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type Grounding, type Receipt } from "../lib/api";
import { Icon, Spinner, cx } from "./ui";

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

export function ProvenanceProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Ctx.Provider value={setOpen}>
      {children}
      <AnimatePresence>{open && <ReceiptDrawer key={open} id={open} onClose={() => setOpen(null)} />}</AnimatePresence>
    </Ctx.Provider>
  );
}

const TONE: Record<string, string> = {
  REAL: "border-positive-edge bg-positive-wash text-positive",
  "REAL · CACHED": "border-positive-edge bg-positive-wash text-positive",
  SYNTHETIC: "border-warning-edge bg-warning-wash text-warning",
  "TEST MODE": "border-warning-edge bg-warning-wash text-warning",
  PAPER: "border-accent-edge bg-accent-wash text-accent",
  MODEL: "border-accent-edge bg-accent-wash text-accent",
  ERROR: "border-negative bg-negative-wash text-negative",
};

type Meta = Record<string, unknown>;
const META_KEYS = ["source", "licence", "fetched_at", "url", "generator", "seed", "label", "method", "model"] as const;

/** The one provenance badge. Hover shows where the figure came from; click opens its receipt. */
export function ProvBadge({ badge, meta, receiptId, className }: { badge: string; meta?: Meta; receiptId?: string | null; className?: string }) {
  const openReceipt = useReceipt();
  const [fetched, setFetched] = useState<Meta | null>(null);
  const info = meta ?? fetched;
  const load = () => {
    if (!meta && !fetched && receiptId)
      getReceipt(receiptId)
        .then((r) => setFetched({ ...(typeof r.result === "object" && r.result ? (r.result as Meta) : {}), model: r.model }))
        .catch(() => setFetched({}));
  };
  const rows = info ? META_KEYS.filter((k) => info[k] !== undefined && info[k] !== null && info[k] !== "").map((k) => [k, String(info[k])]) : [];

  return (
    <span className={cx("group relative inline-flex", className)} onMouseEnter={load} onFocus={load}>
      <button
        type="button"
        data-testid="badge"
        data-badge={badge}
        onClick={(e) => {
          e.stopPropagation();
          if (receiptId) openReceipt(receiptId);
        }}
        className={cx(
          "inline-flex h-[18px] items-center whitespace-nowrap rounded-[3px] border px-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.04em]",
          TONE[badge] ?? "border-line-strong bg-surface-3 text-fg-2",
          receiptId ? "cursor-pointer" : "cursor-default"
        )}
      >
        {badge}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute right-0 top-full z-40 mt-1 w-[320px] rounded border border-line-strong bg-surface-2 p-2.5 text-left opacity-0 shadow-overlay transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
      >
        <span className="block font-mono text-[10.5px] uppercase tracking-[0.04em] text-fg-3">{badge}</span>
        {rows.length === 0 && <span className="mt-1 block text-[12px] text-fg-2">{receiptId ? "Loading source…" : "No source recorded."}</span>}
        {rows.map(([k, v]) => (
          <span key={k} className="mt-1 grid grid-cols-[72px_1fr] gap-2 text-[11.5px] leading-4">
            <span className="text-fg-3">{k.replace("_", " ")}</span>
            <span className="break-words text-fg">{v}</span>
          </span>
        ))}
        {receiptId && <span className="mt-1.5 block text-[11px] text-fg-3">Click for the receipt</span>}
      </span>
    </span>
  );
}

/** A number that opens its receipt. */
export function Num({ rid, children, className }: { rid?: string | null; children: React.ReactNode; className?: string }) {
  const openReceipt = useReceipt();
  if (!rid) return <span className={className}>{children}</span>;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        openReceipt(rid);
      }}
      title="Open receipt"
      className={cx("cursor-pointer underline decoration-line-strong decoration-dotted underline-offset-4 hover:decoration-accent", className)}
    >
      {children}
    </button>
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
      <motion.div className="fixed inset-0 z-40 bg-black/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.aside
        data-testid="receipt-drawer"
        role="dialog"
        aria-label="Receipt"
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 40, opacity: 0 }}
        transition={{ duration: 0.18 }}
        className="fixed right-0 top-0 z-50 flex h-screen w-[560px] flex-col border-l border-line-strong bg-surface"
      >
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-line px-4">
          <div className="flex items-center gap-2.5">
            <span className="text-[13px] font-medium">Receipt</span>
            <span className="font-mono text-[11.5px] text-fg-3">{id}</span>
          </div>
          <button onClick={onClose} aria-label="Close receipt" className="flex h-8 w-8 items-center justify-center rounded text-fg-2 hover:bg-surface-2">
            <Icon name="x" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {err && <p className="text-[13px] text-negative">Couldn’t load this receipt ({err}).</p>}
          {!r && !err && <Spinner className="text-accent" />}
          {r && (
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[13px] text-accent">{r.call}</span>
                  <ProvBadge badge={r.badge} meta={result ?? undefined} />
                </div>
                <dl className="mt-2 grid grid-cols-[110px_1fr] gap-y-1 font-mono text-[11.5px]">
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
                      <dd className="text-fg">{String(v ?? "")}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              {grounding && (
                <Section title={`Grounding check · ${grounding.ok ? "passed" : "failed"}`}>
                  <p className="text-[12px] text-fg-2">Every number in the narration must appear in a tool result from this run.</p>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {grounding.numbers.map((n, i) => (
                      <li
                        key={i}
                        className={cx(
                          "rounded border px-1.5 font-mono text-[11.5px]",
                          n.grounded ? "border-positive-edge text-positive" : "border-negative text-negative"
                        )}
                      >
                        {n.grounded ? "✓" : "✗"} {n.text}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 font-mono text-[11.5px] text-fg-2">
                    ungrounded: {grounding.ungrounded.length ? grounding.ungrounded.join(", ") : "none"}
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
                <dl className="grid grid-cols-[80px_1fr] gap-y-1 font-mono text-[11px]">
                  <dt className="text-fg-3">prev_hash</dt>
                  <dd className="break-all text-fg-2">{r.prev_hash}</dd>
                  <dt className="text-fg-3">hash</dt>
                  <dd className="break-all text-fg">{r.hash}</dd>
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
      <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.04em] text-fg-3">{title}</h3>
      {children}
    </section>
  );
}

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[320px] overflow-auto rounded border border-line bg-surface-2 p-2.5 font-mono text-[11px] leading-[16px] text-fg-2">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
