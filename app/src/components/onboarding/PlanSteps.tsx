"use client";

import { useRouter } from "next/navigation";
import { ApprovalCard, BacktestPanel, CashflowPanel, ForecastPanel, LimitsPanel, ProposalPanel, RisksPanel, WeeklyBacktestChart } from "../panels";
import { proposals, type AppState } from "../../lib/api";
import { StepFooter } from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };
type P = Nav & { s: AppState };

export function AnalysisStep({ s, onNext, onBack }: P) {
  return (
    <div className="space-y-4">
      <RisksPanel s={s} />
      <ForecastPanel s={s} />
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="See the impact" />
    </div>
  );
}

export function ImpactStep({ s, onNext, onBack }: P) {
  return (
    <div className="space-y-4">
      <CashflowPanel s={s} />
      <WeeklyBacktestChart s={s} />
      <BacktestPanel s={s} />
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="See the recommendation" />
    </div>
  );
}

export function RecommendationsStep({ s, onNext, onBack }: P) {
  const p = proposals(s).find((x) => x.run_id === s.run?.run_id) ?? proposals(s)[0];
  return (
    <div>
      <ProposalPanel s={s} p={p} />
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="Review" />
    </div>
  );
}

export function ReviewStep({ s, refresh, onBack }: P & { refresh: () => void }) {
  const router = useRouter();
  const p = proposals(s)[0];
  return (
    <div>
      <div className="grid grid-cols-2 items-start gap-4">
        <ApprovalCard s={s} p={p} onChange={refresh} />
        <LimitsPanel s={s} onChange={refresh} />
      </div>
      <StepFooter onBack={onBack} onNext={() => router.push("/dashboard")} nextLabel="Open dashboard" />
    </div>
  );
}
