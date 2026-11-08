"use client";
import { motion } from "framer-motion";
import { Icon, Spinner } from "./ui";
import { stamp, type Analysis } from "../lib/api";

export default function AgentRun({ analysis }: { analysis: Analysis }) {
  const running = analysis.state === "running";
  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex h-10 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2.5">
          {running ? (
            <Spinner className="text-accent" />
          ) : (
            <Icon
              name={analysis.state === "failed" ? "alert" : "check"}
              className={
                analysis.state === "failed" ? "text-warning" : "text-positive"
              }
            />
          )}
          <span className="text-[13px] font-medium">
            {running
              ? "Analysing weather exposure"
              : analysis.state === "failed"
                ? "Analysis failed"
                : "Assessment saved"}
          </span>
          <span className="rounded bg-surface-3 px-1.5 py-px font-mono text-[11px] text-fg-2">
            Deterministic Python
          </span>
        </div>
        <span className="font-mono text-[11.5px] text-fg-3">{analysis.id}</span>
      </div>
      <div className="h-px bg-line">
        <motion.div
          className="h-px bg-accent"
          initial={false}
          animate={{
            width: running
              ? `${Math.min(90, analysis.events.length * 12)}%`
              : "100%",
          }}
          transition={{ duration: 0.4 }}
        />
      </div>
      <ol className="px-4 py-2">
        {analysis.events.map((e) => (
          <motion.li
            key={e.id}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            className="py-2"
          >
            <div className="flex items-center gap-3">
              <Icon name="check" size={14} className="text-positive" />
              <span className="text-[13px] text-fg-2">{e.label}</span>
              <span className="ml-auto font-mono text-[11px] text-fg-3">
                {stamp(e.created_at)}
              </span>
            </div>
            <p className="ml-7 mt-1 text-[11.5px] leading-5 text-fg-3">
              {e.detail}
            </p>
          </motion.li>
        ))}
        {running && (
          <li className="flex items-center gap-3 py-2 text-[13px] text-fg-2">
            <Spinner />
            Waiting for the backend operation…
          </li>
        )}
      </ol>
    </div>
  );
}
