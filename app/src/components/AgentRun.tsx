"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { API } from "../lib/api";
import { Num, ProvBadge } from "./Provenance";
import { Button, Icon, Spinner, cx } from "./ui";

export type RunMode = "scenario" | "live" | "replay";

const MODES: { id: RunMode; label: string; hint: string }[] = [
  { id: "scenario", label: "Historical scenario", hint: "August bank holiday 2026, as forecast at the time" },
  { id: "live", label: "Live", hint: "This coming weekend’s Met Office forecast" },
  { id: "replay", label: "Replay", hint: "A recorded run, for when the wifi fails" },
];

// The chain the API runs, in order. Labels are replaced by the API's own on step_start.
const CHAIN = [
  { step: "verifier", label: "Verifying the business" },
  { step: "ingest", label: "Reading takings, bank feed and history" },
  { step: "risk", label: "Finding what weather costs" },
  { step: "pricer", label: "Pricing protection for the weekend" },
  { step: "monitor", label: "Checking limits and queueing for approval" },
];

type ToolLine = { call: string; result_summary: string; source_badge: string; receipt_id: string; model: string; ms: number };
type Step = {
  step: string;
  label: string;
  model?: string;
  state: "pending" | "active" | "done";
  tools: ToolLine[];
  narration?: string;
  narration_badge?: string;
  grounding_ok?: boolean;
  receipt_id?: string;
  ms?: number;
};
type Rationale = { model: string; text: string; badge: string; grounding_ok: boolean; receipt_id: string };
type Phase = "idle" | "running" | "done" | "error";

export default function AgentRun({ title, onDone }: { title: string; onDone?: (runId: string) => void }) {
  const [mode, setMode] = useState<RunMode>("scenario");
  const [phase, setPhase] = useState<Phase>("idle");
  const [runId, setRunId] = useState("");
  const [replay, setReplay] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [rationale, setRationale] = useState<Rationale | null>(null);
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const es = useRef<EventSource | null>(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => () => es.current?.close(), []);

  useEffect(() => {
    if (phase !== "running") return;
    const start = performance.now();
    const i = setInterval(() => setElapsed((performance.now() - start) / 1000), 100);
    return () => clearInterval(i);
  }, [phase]);

  const start = () => {
    es.current?.close();
    setPhase("running");
    setSteps(CHAIN.map((c) => ({ ...c, state: "pending", tools: [] })));
    setRationale(null);
    setError("");
    setRunId("");
    setElapsed(0);
    const src = new EventSource(`${API}/api/runs/stream?mode=${mode}&speed=4`);
    es.current = src;
    let finished = false;
    const patch = (step: string, f: (s: Step) => Step) =>
      setSteps((all) => {
        const has = all.some((s) => s.step === step);
        const list = has ? all : [...all, { step, label: step, state: "pending" as const, tools: [] }];
        return list.map((s) => (s.step === step ? f(s) : s));
      });

    src.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (e.type === "run") {
        setRunId(e.run_id);
        setReplay(e.mode === "replay");
      } else if (e.type === "step_start") patch(e.step, (s) => ({ ...s, label: e.label, model: e.model, state: "active" }));
      else if (e.type === "tool") patch(e.step, (s) => ({ ...s, model: s.model ?? e.model, tools: [...s.tools, e] }));
      else if (e.type === "step_end")
        patch(e.step, (s) => ({
          ...s,
          label: e.label,
          model: e.model,
          state: "done",
          narration: e.narration,
          narration_badge: e.narration_badge,
          grounding_ok: e.grounding_ok,
          receipt_id: e.receipt_id,
          ms: e.ms,
        }));
      else if (e.type === "rationale") setRationale(e);
      else if (e.type === "done") {
        finished = true;
        src.close();
        setPhase("done");
        onDoneRef.current?.(e.run_id);
      } else if (e.type === "error") {
        finished = true;
        src.close();
        setError(e.message);
        setPhase("error");
      }
    };
    // EventSource reconnects by default, which would start a second run. Close instead.
    src.onerror = () => {
      src.close();
      if (!finished) {
        setError(`Lost the connection to the agent at ${API}.`);
        setPhase("error");
      }
    };
  };

  const done = phase === "done";
  const finishedSteps = steps.filter((s) => s.state === "done").length;
  const progress = steps.length ? finishedSteps / steps.length : 0;
  const models = Array.from(new Set(steps.map((s) => s.model).filter(Boolean).concat(rationale ? [rationale.model] : [])));

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface" data-testid="agent-run">
      <div className="flex h-10 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2.5">
          {done ? (
            <span data-testid="run-done" className="flex h-4 w-4 items-center justify-center rounded-full bg-positive text-bg">
              <Icon name="check" size={11} />
            </span>
          ) : phase === "running" ? (
            <Spinner className="text-accent" />
          ) : (
            <Icon name="spark" size={15} className="text-fg-3" />
          )}
          <span className="text-[13px] font-medium">{title}</span>
          {models.map((m) => (
            <ModelChip key={m} model={m!} />
          ))}
          {replay && <ProvBadge badge="REPLAY" meta={{ source: "Recorded run, played back from fixtures/runs/demo-run.json" }} />}
        </div>
        <div className="flex items-center gap-4 font-mono text-[11.5px] text-fg-3">
          {runId && <span>{runId}</span>}
          {phase !== "idle" && <span className="text-fg-2">{elapsed.toFixed(1)}s</span>}
        </div>
      </div>
      <div className="h-px bg-line">
        <motion.div className="h-px bg-accent" initial={false} animate={{ width: `${progress * 100}%` }} transition={{ duration: 0.4 }} />
      </div>

      <div className="flex items-center gap-3 border-b border-line px-4 py-2.5">
        <div role="tablist" aria-label="Run mode" className="flex rounded border border-line-strong bg-surface-2 p-0.5">
          {MODES.map((m) => (
            <button
              key={m.id}
              role="tab"
              aria-selected={mode === m.id}
              data-testid={`mode-${m.id}`}
              disabled={phase === "running"}
              onClick={() => setMode(m.id)}
              className={cx(
                "h-6 rounded-[3px] px-2.5 text-[12px] transition-colors disabled:cursor-not-allowed",
                mode === m.id ? "bg-surface text-fg shadow-sm" : "text-fg-2 hover:text-fg"
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
        <span className="flex-1 truncate text-[12px] text-fg-3">{MODES.find((m) => m.id === mode)?.hint}</span>
        <Button size="sm" variant={phase === "idle" ? "primary" : "secondary"} onClick={start} disabled={phase === "running"} data-testid="run-start">
          {phase === "idle" ? "Run the agent" : "Run again"}
        </Button>
      </div>

      {phase === "idle" && (
        <p className="px-4 py-4 text-[12.5px] text-fg-2">
          Five agents check the register, read the books, cost the weather, price cover and queue it for you. Every call is logged with a receipt.
        </p>
      )}

      {steps.length > 0 && (
        <ol className="px-4 py-2">
          {steps.map((s) => (
            <li key={s.step} className="py-2" data-testid={`step-${s.step}`}>
              <div className="flex items-center gap-3">
                <StepMarker state={s.state} />
                <span className={cx("text-[13px]", s.state === "pending" ? "text-fg-3" : s.state === "active" ? "text-fg" : "text-fg-2")}>
                  {s.label}
                  {s.state === "active" && <span className="text-fg-3">…</span>}
                </span>
                {s.model && <ModelChip model={s.model} />}
                {s.state === "done" && (
                  <span className="ml-auto flex items-center gap-2 font-mono text-[11.5px] text-fg-3">
                    {s.tools.length} calls · {((s.ms ?? 0) / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
              {s.tools.length > 0 && (
                <ul className="ml-[7px] mt-1.5 space-y-1 border-l border-line pl-[22px]">
                  {s.tools.map((c, j) => (
                    <motion.li
                      key={c.receipt_id + j}
                      initial={{ opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.18 }}
                      className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 font-mono text-[11.5px] leading-5"
                    >
                      <span className="truncate text-fg-2">
                        <span className="text-accent">{c.call.split("(")[0]}</span>
                        {c.call.includes("(") && <span className="text-fg-3">({c.call.split("(").slice(1).join("(")}</span>}
                      </span>
                      <Num rid={c.receipt_id} className="text-right text-fg-2">
                        {c.result_summary || "no result"}
                      </Num>
                      <ProvBadge badge={c.source_badge} receiptId={c.receipt_id} />
                    </motion.li>
                  ))}
                </ul>
              )}
              {s.narration && (
                <div className="ml-[29px] mt-1.5 flex items-start gap-2 text-[12.5px] leading-5 text-fg">
                  <p className="flex-1">{s.narration}</p>
                  <ProvBadge badge={s.narration_badge ?? "TEMPLATE"} receiptId={s.receipt_id} />
                  {s.grounding_ok === false && <span className="font-mono text-[11px] text-negative">ungrounded</span>}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {rationale && (
        <div className="border-t border-line px-4 py-3" data-testid="run-rationale">
          <div className="mb-1.5 flex items-center gap-2 text-[12px] text-fg-2">
            Why the agent recommends this
            <ModelChip model={rationale.model} />
            <ProvBadge badge={rationale.badge} receiptId={rationale.receipt_id} />
          </div>
          <Bullets text={rationale.text} />
        </div>
      )}

      {phase === "error" && <p className="border-t border-line px-4 py-3 text-[12.5px] text-negative">{error}</p>}
    </div>
  );
}

export function ModelChip({ model }: { model: string }) {
  return (
    <span data-testid="model-chip" className="rounded bg-surface-3 px-1.5 py-px font-mono text-[11px] text-fg-2">
      {model}
    </span>
  );
}

export function Bullets({ text }: { text: string }) {
  return (
    <ul className="space-y-1.5">
      {text
        .split("\n")
        .map((l) => l.replace(/^\s*-\s*/, "").trim())
        .filter(Boolean)
        .map((l) => (
          <li key={l} className="flex gap-2.5 text-[12.5px] leading-5 text-fg">
            <Icon name="chevron-right" size={12} className="mt-1 shrink-0 text-fg-3" />
            {l}
          </li>
        ))}
    </ul>
  );
}

function StepMarker({ state }: { state: Step["state"] }) {
  if (state === "done")
    return (
      <span className="flex h-4 w-4 items-center justify-center text-positive">
        <Icon name="check" size={14} />
      </span>
    );
  if (state === "active") return <Spinner className="text-accent" size={16} />;
  return <span className="mx-[3px] h-2.5 w-2.5 rounded-full border border-line-strong" />;
}
