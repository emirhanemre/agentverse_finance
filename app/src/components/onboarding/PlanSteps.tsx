"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApprovalCard, CashflowPanel, ForecastPanel, LimitsPanel, OfferCard, PaydayPanel, PayrollBridge, ProposalPanel, RisksPanel, hasBridge } from "../panels";
import { Num } from "../Provenance";
import { rainProposals, tool, type AppState, type Outcomes } from "../../lib/api";
import { day, gbp } from "../../lib/format";
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

/** Counts up to target once (ease-out), or lands on it at once under reduced motion. */
function useCountUp(target: number, ms = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / ms);
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return value;
}

type Hero = Outcomes & { wet_no_hedge_headroom_gbp: number; wet_with_hedge_headroom_gbp: number };
const hasHero = (o?: Outcomes): o is Hero => typeof o?.wet_with_hedge_headroom_gbp === "number" && typeof o?.wet_no_hedge_headroom_gbp === "number" && !!o.payroll_date;

/** "You could have made payroll." Every figure is the size_hedges result; nothing here is computed but its sign. */
function PayrollHero({ o, rid, wet }: { o: Hero; rid?: string; wet: string }) {
  const saved = o.wet_with_hedge_headroom_gbp >= 0;
  const big = useCountUp(Math.abs(o.wet_with_hedge_headroom_gbp));
  const without = o.wet_no_hedge_headroom_gbp;
  return (
    <section className="mb-10 text-center" data-testid="impact-hero" aria-labelledby="impact-hero-head">
      <h2 id="impact-hero-head" className="mx-auto max-w-none font-display text-2xl font-medium text-fg">
        {saved ? "You could have made payroll." : "Payroll is at risk."}
      </h2>
      <p className={`mt-2 font-display text-4xl font-medium tracking-[var(--tracking-display)] ${saved ? "text-positive" : "text-warning"}`}>
        <Num rid={rid}>{gbp(big)}</Num> {saved ? "to spare" : "short"}
      </p>
      <p className="mx-auto mt-3 max-w-[60ch] text-md text-fg-2">
        {saved ? (
          <>
            With <Num rid={rid}>{gbp(o.hedge_cost_gbp)}</Num> of rain cover, payroll on <Num rid={rid}>{day(o.payroll_date)}</Num> clears after a {wet}.{" "}
            {without < 0 ? (
              <>
                Without it you’d have been <Num rid={rid}>{gbp(-without)}</Num> short.
              </>
            ) : (
              <>
                Without it, payroll still clears with <Num rid={rid}>{gbp(without)}</Num> to spare.
              </>
            )}
          </>
        ) : (
          <>
            Even with <Num rid={rid}>{gbp(o.hedge_cost_gbp)}</Num> of rain cover, payroll on <Num rid={rid}>{day(o.payroll_date)}</Num> falls short after a {wet}.{" "}
            {without < 0 && (
              <>
                Without it, <Num rid={rid}>{gbp(-without)}</Num> short.
              </>
            )}
          </>
        )}
      </p>
    </section>
  );
}

export function ImpactStep({ s, onNext, onBack }: P) {
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  const wet = /bank holiday/i.test(s.scenario.name) ? "wet bank holiday" : "wet weekend";
  return (
    <div className="space-y-4">
      {hasHero(o) && <PayrollHero o={o} rid={sized?.receipt_id} wet={wet} />}
      {hasBridge(o) ? (
        <>
          <PaydayPanel s={s} />
          <PayrollBridge s={s} />
        </>
      ) : (
        // Older API results carry no headroom figures: fall back to the cash path.
        <CashflowPanel s={s} />
      )}
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="See the recommendation" />
    </div>
  );
}

export function RecommendationsStep({ s, refresh, onNext, onBack }: P & { refresh: () => void }) {
  const p = rainProposals(s).find((x) => x.run_id === s.run?.run_id) ?? rainProposals(s)[0];
  return (
    <div>
      <div className="space-y-4">
        <ProposalPanel s={s} p={p} />
        <OfferCard s={s} onChange={refresh} />
      </div>
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="Review" />
    </div>
  );
}

export function ReviewStep({ s, refresh, onBack }: P & { refresh: () => void }) {
  const router = useRouter();
  const p = rainProposals(s)[0];
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
