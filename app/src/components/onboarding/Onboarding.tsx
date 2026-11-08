"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { Button, Icon, Logo, Spinner, ThemeToggle, cx } from "../ui";
import {
  api,
  latestProposal,
  message,
  useApplication,
  type Profile,
} from "../../lib/api";
import { BusinessStep, SourcesStep, VerifyStep } from "./IdentitySteps";
import {
  AnalysisStep,
  ImpactStep,
  RecommendationsStep,
  ReviewStep,
} from "./PlanSteps";

const STEPS = [
  {
    title: "Your business",
    description:
      "Tell us which business to analyse. Your details stay in this local application.",
  },
  {
    title: "Verification",
    description:
      "Review your self-reported details and the availability of external checks.",
  },
  {
    title: "Data sources",
    description: "Choose labelled sample sales or import your daily records.",
  },
  {
    title: "Risk analysis",
    description:
      "Compare explicit weather scenarios and inspect suitable paper markets.",
  },
  {
    title: "Impact",
    description:
      "Conditional revenue estimates under the synthetic model’s assumptions.",
  },
  {
    title: "Recommendations",
    description:
      "Review the evidence, or continue with an explained rejection.",
  },
  {
    title: "Review and approve",
    description:
      "Every paper position requires your approval. No real orders or payments.",
  },
];
export type Form = Profile;
export const emptyProfile: Profile = {
  pubName: "",
  postcode: "",
  owner: "",
  email: "",
  location_name: "",
  latitude: 51.45,
  longitude: -0.07,
  indoor_capacity: 90,
  outdoor_capacity: 70,
  opening_hours: 11,
  currency: "GBP",
};
export const sampleProfile: Profile = {
  ...emptyProfile,
  pubName: "Sample Oak Tree Pub",
  postcode: "SE22 8HD",
  owner: "Sample Operator",
  email: "sample@example.com",
  location_name: "London, UK",
};

export default function Onboarding() {
  const { state, error, refresh } = useApplication();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const [form, setForm] = useState<Form>(emptyProfile);
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [selected, setSelected] = useState(false);
  useEffect(() => {
    if (!state || hydrated) return;
    if (state.profile) setForm(state.profile);
    const savedStep = state.analysis
      ? state.analysis.state === "running"
        ? 3
        : 4
      : state.dataset
        ? 3
        : state.profile
          ? 1
          : 0;
    setStep(savedStep);
    setReached(savedStep);
    setHydrated(true);
  }, [state, hydrated]);
  const go = (i: number) => {
    setStep(i);
    setReached((r) => Math.max(r, i));
  };
  const next = () => go(step + 1);
  const back = () => setStep((s) => Math.max(0, s - 1));
  const save = async () => {
    setBusy(true);
    setActionError("");
    try {
      await api("/profile", "PUT", form);
      await refresh();
      setSelected(false);
      setReached(1);
      go(1);
    } catch (e) {
      setActionError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const finish = async () => {
    setBusy(true);
    try {
      await api("/setup/complete", "POST");
      router.push("/dashboard");
    } catch (e) {
      setActionError(message(e));
      setBusy(false);
    }
  };
  const nav = { onNext: next, onBack: back };
  const p = state ? latestProposal(state) : undefined;
  const body = state
    ? [
        <BusinessStep
          key="0"
          form={form}
          setForm={setForm}
          onNext={save}
          onBack={back}
          busy={busy}
        />,
        <VerifyStep
          key="1"
          profile={state.profile}
          companyDemo={
            state.sources.find((s) => s.id === "companies_house")?.status ===
            "demo_connected"
          }
          refresh={refresh}
          onEdit={() => go(0)}
          {...nav}
        />,
        <SourcesStep key="2" state={state} refresh={refresh} {...nav} />,
        <AnalysisStep key="3" state={state} refresh={refresh} {...nav} />,
        <ImpactStep key="4" state={state} refresh={refresh} {...nav} />,
        <RecommendationsStep
          key="5"
          state={state}
          selected={selected}
          setSelected={setSelected}
          {...nav}
        />,
        <ReviewStep
          key="6"
          state={state}
          selected={selected}
          refresh={refresh}
          onFinish={finish}
          busy={busy}
          {...nav}
        />,
      ][step]
    : null;
  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-line px-6">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="h-4 w-px bg-line-strong" />
          <span className="text-[13px] text-fg-2">
            Set up {form.pubName.trim() || "your business"}
          </span>
        </div>
        <div className="flex items-center gap-4 text-[12px] text-fg-3">
          <span className="flex items-center gap-1.5 text-fg-2">
            <Icon name="lock" size={13} />
            Local · paper only
          </span>
          <a href="/dashboard" className="hover:text-fg">
            Dashboard
          </a>
          <span>{form.email}</span>
          <ThemeToggle />
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[920px] px-10 pb-10 pt-12">
          {(error || actionError) && (
            <ErrorNotice
              text={actionError || error}
              onRetry={() => {
                setActionError("");
                refresh();
              }}
            />
          )}
          {!state && !error && (
            <RunSummary
              label="Loading saved application"
              detail="Connecting to local API"
            />
          )}
          {state?.setup_complete && (
            <div className="mb-5 text-center text-[12px] text-fg-2">
              Setup is saved.{" "}
              <a href="/dashboard" className="text-accent underline">
                Open your dashboard
              </a>{" "}
              or edit your details below.
            </div>
          )}
          {state && (
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="mb-7 text-center">
                  <h1 className="text-[24px] font-medium tracking-[-0.01em]">
                    {STEPS[step].title}
                  </h1>
                  <p className="mx-auto mt-1.5 max-w-[600px] text-fg-2">
                    {STEPS[step].description}
                  </p>
                </div>
                {body}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </main>
      <nav
        aria-label="Setup progress"
        className="shrink-0 border-t border-line bg-surface"
      >
        <ol className="mx-auto flex h-16 max-w-[1120px] items-center gap-2 px-8">
          {STEPS.map((s, i) => {
            const done =
                i < reached || (i === 6 && p?.approval_state === "approved"),
              active = i === step,
              reachable = hydrated && !!state && i <= reached;
            return (
              <li key={s.title} className="flex-1">
                <button
                  onClick={() => reachable && setStep(i)}
                  disabled={!reachable}
                  aria-current={active ? "step" : undefined}
                  className={cx(
                    "group block w-full text-left",
                    reachable ? "cursor-pointer" : "cursor-default",
                  )}
                >
                  <span className="block h-[3px] overflow-hidden rounded-full bg-line-strong">
                    <motion.span
                      className={cx(
                        "block h-full rounded-full",
                        active ? "bg-accent" : "bg-accent-strong",
                      )}
                      initial={false}
                      animate={{ width: done || active ? "100%" : "0%" }}
                      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </span>
                  <span
                    className={cx(
                      "mt-2 flex items-center gap-1.5 truncate text-[12px] transition-colors",
                      active
                        ? "text-fg"
                        : done
                          ? "text-fg-2 group-hover:text-fg"
                          : "text-fg-3",
                    )}
                  >
                    {done && !active ? (
                      <Icon
                        name="check"
                        size={12}
                        className="shrink-0 text-positive"
                      />
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
export function RunSummary({
  label,
  detail,
}: {
  label: string;
  detail: string;
}) {
  return (
    <div className="flex h-10 items-center gap-2.5 rounded-md border border-line bg-surface px-4">
      <Spinner className="text-accent" />
      <span className="text-[13px]">{label}</span>
      <span className="ml-auto font-mono text-[11.5px] text-fg-3">
        {detail}
      </span>
    </div>
  );
}
export function ErrorNotice({
  text,
  onRetry,
}: {
  text: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="mb-4 flex items-center justify-between gap-4 rounded border border-warning-edge bg-warning-wash p-4 text-[13px] text-warning"
    >
      <span>{text}</span>
      {onRetry && (
        <Button onClick={onRetry} size="sm">
          Retry
        </Button>
      )}
    </div>
  );
}
