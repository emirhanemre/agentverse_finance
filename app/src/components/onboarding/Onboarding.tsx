"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button, Icon, Logo, Spinner, ThemeToggle, cx } from "../ui";
import { API, useAppState } from "../../lib/api";
import { AuditSwitch } from "../Provenance";
import { BusinessStep, RunStep, VerifyStep } from "./IdentitySteps";
import { AnalysisStep, ImpactStep, RecommendationsStep, ReviewStep } from "./PlanSteps";

const STEPS = [
  { title: "Your business", description: "Tell us which pub to protect. We'll find the rest from public records." },
  { title: "Agent run", description: "Five agents check the registers, read the books, cost the weather and price cover. Every call leaves a receipt." },
  { title: "Verification", description: "What the agent checked, and where each figure came from." },
  { title: "Risk analysis", description: "Five years of takings matched against local weather, fixtures and duty changes." },
  { title: "Impact", description: "The payroll week that doesn't clear after a wet weekend, and what cover does about it." },
  { title: "Recommendation", description: "Cover sized to the exposure and your limits. Open any figure to see how it was worked out." },
  { title: "Review and approve", description: "Nothing is placed until you approve it. This demo trades on paper only." },
];

export type Form = { pubName: string; postcode: string; owner: string };

export default function Onboarding() {
  const { state, error, refresh } = useAppState();
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const [form, setForm] = useState<Form | null>(null);
  const [ran, setRan] = useState(false);
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    main.current?.scrollTo(0, 0); // newer Chromium returns a Promise here, which React would call as cleanup
  }, [step]);

  useEffect(() => {
    if (state && !form) setForm({ pubName: state.pub.trading_name, postcode: state.pub.postcode, owner: state.pub.owner });
  }, [state, form]);

  const go = (i: number) => {
    setStep(i);
    setReached((r) => Math.max(r, i));
  };
  const next = () => go(step + 1);
  const back = () => setStep((s) => Math.max(0, s - 1));
  const nav = { onNext: next, onBack: back };

  const body =
    !state || !form ? (
      <div className="flex items-center justify-center gap-2 text-sm text-fg-2">
        {error ? <span className="text-negative">Can’t reach the Pub Hedge API at {API}. Is it running?</span> : <Spinner className="text-accent" />}
      </div>
    ) : (
      [
        <BusinessStep key="0" form={form} setForm={setForm} s={state} {...nav} />,
        <RunStep key="1" ran={ran} onRan={() => { setRan(true); refresh(); }} {...nav} />,
        <VerifyStep key="2" s={state} onEdit={() => go(0)} {...nav} />,
        <AnalysisStep key="3" s={state} {...nav} />,
        <ImpactStep key="4" s={state} {...nav} />,
        <RecommendationsStep key="5" s={state} {...nav} />,
        <ReviewStep key="6" s={state} refresh={refresh} {...nav} />,
      ][step]
    );

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-6">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="hidden h-4 w-px bg-line-strong sm:block" />
          <span className="hidden text-sm text-fg-2 sm:block">Set up {form?.pubName.trim() || "your pub"}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-fg-3">
          <span className="hidden items-center gap-2 text-fg-2 md:flex">
            <Icon name="lock" size={13} />
            Read-only access · paper trading
          </span>
          <AuditSwitch />
          <ThemeToggle />
        </div>
      </header>

      <main ref={main} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1040px] px-4 pb-10 pt-10 sm:px-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-10 text-center">
                <h1 className="mx-auto font-display text-2xl font-medium">{STEPS[step].title}</h1>
                <p className="mx-auto mt-2 max-w-[640px] text-md text-fg-2">{STEPS[step].description}</p>
              </div>
              {body}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      <nav aria-label="Setup progress" className="shrink-0 border-t border-line bg-bg">
        <ol className="mx-auto flex h-16 max-w-[1120px] items-center gap-2 px-4 sm:px-10">
          {STEPS.map((s, i) => {
            const done = i < reached;
            const active = i === step;
            const reachable = i <= reached;
            return (
              <li key={s.title} className="min-w-0 flex-1">
                <button
                  onClick={() => reachable && setStep(i)}
                  disabled={!reachable}
                  aria-current={active ? "step" : undefined}
                  className={cx("hit group block w-full text-left", reachable ? "cursor-pointer" : "cursor-default")}
                >
                  <span className="block h-[3px] overflow-hidden rounded-full bg-surface-3">
                    <motion.span
                      className="block h-full origin-left rounded-full bg-accent"
                      initial={false}
                      animate={{ scaleX: done || active ? 1 : 0 }}
                      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </span>
                  <span
                    className={cx(
                      "mt-2 flex items-center gap-2 truncate text-xs transition-colors",
                      active ? "text-fg" : done ? "text-fg-2 group-hover:text-fg" : "text-fg-3"
                    )}
                  >
                    {done && !active ? (
                      <Icon name="check" size={12} className="shrink-0 text-positive" />
                    ) : (
                      <span className="text-xs">{i + 1}</span>
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
    <div className="mt-10 flex items-center justify-between border-t border-line pt-6">
      <div>
        {onBack && (
          <Button variant="ghost" onClick={onBack}>
            <Icon name="chevron-left" size={14} />
            Back
          </Button>
        )}
      </div>
      <div className="flex items-center gap-4">
        {hint && <span className="text-xs text-fg-3">{hint}</span>}
        <Button variant="primary" onClick={onNext} disabled={disabled}>
          {nextLabel}
          <Icon name="chevron-right" size={14} />
        </Button>
      </div>
    </div>
  );
}
