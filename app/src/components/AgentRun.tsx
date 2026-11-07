"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Icon, Spinner, cx } from "./ui";
import type { RunStep } from "../lib/data";

const LINE_MS = 620;
const STEP_GAP_MS = 380;

export default function AgentRun({
  title,
  runId,
  steps,
  onDone,
}: {
  title: string;
  runId: string;
  steps: RunStep[];
  onDone?: () => void;
}) {
  const [step, setStep] = useState(0);
  const [line, setLine] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const started = useRef(performance.now());
  const done = step >= steps.length;
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (done) {
      onDoneRef.current?.();
      return;
    }
    const current = steps[step];
    if (line < current.calls.length) {
      const t = setTimeout(() => setLine((l) => l + 1), LINE_MS);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => {
      setStep((s) => s + 1);
      setLine(0);
    }, STEP_GAP_MS);
    return () => clearTimeout(t);
  }, [step, line, done, steps]);

  useEffect(() => {
    if (done) return;
    const i = setInterval(() => setElapsed((performance.now() - started.current) / 1000), 100);
    return () => clearInterval(i);
  }, [done]);

  const totalCalls = steps.reduce((a, s) => a + s.calls.length, 0);
  const finishedCalls = steps.slice(0, step).reduce((a, s) => a + s.calls.length, 0) + (done ? 0 : line);
  const progress = finishedCalls / totalCalls;

  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex h-10 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2.5">
          {done ? (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-positive text-bg">
              <Icon name="check" size={11} />
            </span>
          ) : (
            <Spinner className="text-accent" />
          )}
          <span className="text-[13px] font-medium">{title}</span>
          <span className="rounded bg-surface-3 px-1.5 py-px font-mono text-[11px] text-fg-2">gemini-2.5-pro</span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11.5px] text-fg-3">
          <span>{runId}</span>
          <span className="text-fg-2">{elapsed.toFixed(1)}s</span>
        </div>
      </div>
      <div className="h-px bg-line">
        <motion.div
          className="h-px bg-accent"
          initial={false}
          animate={{ width: `${progress * 100}%` }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>

      <ol className="px-4 py-2">
        {steps.map((s, i) => {
          const state = i < step ? "done" : i === step ? "active" : "pending";
          const shown = state === "done" ? s.calls.length : state === "active" ? line : 0;
          return (
            <li key={s.label} className="py-2">
              <div className="flex items-center gap-3">
                <StepMarker state={state} />
                <span
                  className={cx(
                    "text-[13px]",
                    state === "pending" && "text-fg-3",
                    state === "active" && "text-fg",
                    state === "done" && "text-fg-2"
                  )}
                >
                  {s.label}
                  {state === "active" && <span className="text-fg-3">…</span>}
                </span>
                {state === "done" && (
                  <span className="ml-auto font-mono text-[11.5px] text-fg-3">
                    {s.summary} · {((s.calls.length * LINE_MS + STEP_GAP_MS) / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
              <AnimatePresence initial={false}>
                {state === "active" && shown > 0 && (
                  <motion.ul
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="ml-[7px] mt-1.5 space-y-1 overflow-hidden border-l border-line pl-[22px]"
                  >
                    {s.calls.slice(0, shown).map((c, j) => (
                      <motion.li
                        key={c.call}
                        initial={{ opacity: 0, y: 3 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.18 }}
                        className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 font-mono text-[11.5px] leading-5"
                      >
                        <span className="truncate text-fg-2">
                          <span className="text-accent">{c.call.split("(")[0]}</span>
                          {c.call.includes("(") && <span className="text-fg-3">({c.call.split("(").slice(1).join("(")}</span>}
                        </span>
                        <span className={cx("text-right", j === shown - 1 && line < s.calls.length ? "text-fg-2" : "text-fg-3")}>
                          {c.result}
                        </span>
                      </motion.li>
                    ))}
                  </motion.ul>
                )}
              </AnimatePresence>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StepMarker({ state }: { state: "done" | "active" | "pending" }) {
  if (state === "done")
    return (
      <span className="flex h-4 w-4 items-center justify-center text-positive">
        <Icon name="check" size={14} />
      </span>
    );
  if (state === "active") return <Spinner className="text-accent" size={16} />;
  return <span className="mx-[3px] h-2.5 w-2.5 rounded-full border border-line-strong" />;
}
