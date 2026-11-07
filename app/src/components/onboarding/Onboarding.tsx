"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button, Icon, Logo, cx } from "../ui";
import { HEDGES, PUB } from "../../lib/data";
import { BusinessStep, SourcesStep, VerifyStep } from "./IdentitySteps";
import { AnalysisStep, ImpactStep, RecommendationsStep, ReviewStep } from "./PlanSteps";

const STEPS = [
  { title: "Your business", description: "Tell us which pub to protect. We'll find the rest from public records." },
  { title: "Verification", description: "The agent checks your company, licence and premises against official registers." },
  { title: "Data sources", description: "Connect your till, bank and accounts so the agent can measure what each risk costs you." },
  { title: "Risk analysis", description: "Five years of your sales, matched against local weather, fixtures and duty changes." },
  { title: "Impact", description: "What last year would have looked like with protection in place." },
  { title: "Recommendations", description: "Positions sized to your exposure and your limits. Open any one to see how it was worked out." },
  { title: "Review and approve", description: "Nothing is placed until you approve it." },
];

export type Form = { pubName: string; postcode: string; owner: string; email: string };
export type SourceStatus = Record<string, "idle" | "connected">;

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const [form, setForm] = useState<Form>({ pubName: PUB.name, postcode: PUB.postcode, owner: PUB.owner, email: PUB.email });
  const [verified, setVerified] = useState(false);
  const [sources, setSources] = useState<SourceStatus>({ toast: "idle", monzo: "idle", xero: "idle" });
  const [analysed, setAnalysed] = useState(false);
  const [selected, setSelected] = useState<string[]>(HEDGES.map((h) => h.id));
  const [placed, setPlaced] = useState(false);

  const go = (i: number) => {
    setStep(i);
    setReached((r) => Math.max(r, i));
  };
  const next = () => go(step + 1);
  const back = () => setStep((s) => Math.max(0, s - 1));
  const nav = { onNext: next, onBack: back };

  const body = [
    <BusinessStep key="0" form={form} setForm={setForm} {...nav} />,
    <VerifyStep key="1" verified={verified} onVerified={() => setVerified(true)} onEdit={() => go(0)} {...nav} />,
    <SourcesStep key="2" status={sources} setStatus={setSources} {...nav} />,
    <AnalysisStep key="3" analysed={analysed} onAnalysed={() => setAnalysed(true)} {...nav} />,
    <ImpactStep key="4" {...nav} />,
    <RecommendationsStep key="5" selected={selected} setSelected={setSelected} {...nav} />,
    <ReviewStep key="6" selected={selected} placed={placed} onPlaced={() => setPlaced(true)} form={form} {...nav} />,
  ][step];

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-line px-6">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="h-4 w-px bg-line-strong" />
          <span className="text-[13px] text-fg-2">Set up {form.pubName.trim() || "your pub"}</span>
        </div>
        <div className="flex items-center gap-4 text-[12px] text-fg-3">
          <span className="flex items-center gap-1.5 text-fg-2">
            <Icon name="lock" size={13} />
            Read-only access
          </span>
          <span>{form.email}</span>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[920px] px-10 pb-10 pt-12">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-7 text-center">
                <h1 className="text-[24px] font-medium tracking-[-0.01em]">{STEPS[step].title}</h1>
                <p className="mx-auto mt-1.5 max-w-[600px] text-fg-2">{STEPS[step].description}</p>
              </div>
              {body}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      <nav aria-label="Setup progress" className="shrink-0 border-t border-line bg-surface">
        <ol className="mx-auto flex h-16 max-w-[1120px] items-center gap-2 px-8">
          {STEPS.map((s, i) => {
            const done = i < reached || (i === 6 && placed);
            const active = i === step;
            const reachable = i <= reached && !placed;
            return (
              <li key={s.title} className="flex-1">
                <button
                  onClick={() => reachable && setStep(i)}
                  disabled={!reachable}
                  aria-current={active ? "step" : undefined}
                  className={cx("group block w-full text-left", reachable ? "cursor-pointer" : "cursor-default")}
                >
                  <span className="block h-[3px] overflow-hidden rounded-full bg-line-strong">
                    <motion.span
                      className={cx("block h-full rounded-full", active ? "bg-accent" : "bg-accent-strong")}
                      initial={false}
                      animate={{ width: done || active ? "100%" : "0%" }}
                      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </span>
                  <span
                    className={cx(
                      "mt-2 flex items-center gap-1.5 truncate text-[12px] transition-colors",
                      active ? "text-fg" : done ? "text-fg-2 group-hover:text-fg" : "text-fg-3"
                    )}
                  >
                    {done && !active ? (
                      <Icon name="check" size={12} className="shrink-0 text-positive" />
                    ) : (
                      <span className="font-mono text-[11px]">{i + 1}</span>
                    )}
                    {s.title}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
    </div>
  );
}

export function StepFooter({
  onBack,
  onNext,
  nextLabel = "Continue",
  disabled,
  hint,
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  disabled?: boolean;
  hint?: React.ReactNode;
}) {
  return (
    <div className="mt-8 flex items-center justify-between border-t border-line pt-5">
      <div>
        {onBack && (
          <Button variant="ghost" onClick={onBack}>
            <Icon name="chevron-left" size={14} />
            Back
          </Button>
        )}
      </div>
      <div className="flex items-center gap-4">
        {hint && <span className="text-[12px] text-fg-3">{hint}</span>}
        <Button variant="primary" onClick={onNext} disabled={disabled}>
          {nextLabel}
          <Icon name="chevron-right" size={14} />
        </Button>
      </div>
    </div>
  );
}

export function RunSummary({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="flex h-10 items-center gap-2.5 rounded-md border border-line bg-surface px-4">
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-positive text-bg">
        <Icon name="check" size={11} />
      </span>
      <span className="text-[13px]">{label}</span>
      <span className="ml-auto font-mono text-[11.5px] text-fg-3">{detail}</span>
    </div>
  );
}
