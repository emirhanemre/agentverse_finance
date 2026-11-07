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
    <div className="flex h-screen">
      <aside className="flex w-[264px] shrink-0 flex-col border-r border-line bg-surface">
        <div className="flex h-12 items-center border-b border-line px-5">
          <Logo />
        </div>
        <div className="px-5 pb-2 pt-6 text-[12px] text-fg-2">Set up {form.pubName.trim() || "your pub"}</div>
        <ol className="px-2">
          {STEPS.map((s, i) => {
            const done = i < reached || (i === 6 && placed);
            const active = i === step;
            const reachable = i <= reached && !placed;
            return (
              <li key={s.title}>
                <button
                  onClick={() => reachable && setStep(i)}
                  disabled={!reachable}
                  className={cx(
                    "flex h-9 w-full items-center gap-3 rounded px-3 text-left text-[13px] transition-colors",
                    active ? "bg-surface-3 text-fg" : "text-fg-2",
                    reachable && !active && "hover:bg-surface-2 hover:text-fg",
                    !reachable && !active && "cursor-default text-fg-3"
                  )}
                >
                  <StepDot index={i} done={done && !active} active={active} />
                  {s.title}
                </button>
              </li>
            );
          })}
        </ol>
        <div className="mt-auto border-t border-line px-5 py-4 text-[12px] leading-5 text-fg-3">
          <div className="flex items-center gap-2 text-fg-2">
            <Icon name="lock" size={14} />
            Read-only access to your data
          </div>
          <div className="mt-1">Signed in as {form.email}</div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[920px] px-10 py-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            >
              <header className="mb-6">
                <h1 className="text-[22px] font-medium tracking-[-0.01em]">{STEPS[step].title}</h1>
                <p className="mt-1 max-w-[640px] text-fg-2">{STEPS[step].description}</p>
              </header>
              {body}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function StepDot({ index, done, active }: { index: number; done: boolean; active: boolean }) {
  if (done)
    return (
      <span className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-positive-wash text-positive">
        <Icon name="check" size={12} />
      </span>
    );
  return (
    <span
      className={cx(
        "flex h-[18px] w-[18px] items-center justify-center rounded-full border font-mono text-[10.5px]",
        active ? "border-accent text-accent" : "border-line-strong text-fg-3"
      )}
    >
      {index + 1}
    </span>
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
