"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import AgentRun from "../AgentRun";
import { Badge, Checkbox, Icon, Metric, Panel, cx, tooltipStyle } from "../ui";
import {
  ANALYSIS_RUN,
  AVG_MONTHLY_MARGIN,
  BACKTEST,
  CASHFLOW,
  HEDGES,
  LIMITS,
  PLACE_RUN,
  RISKS,
  WEEKS_BELOW_PAYROLL,
  ev,
  saveSetup,
  type Hedge,
} from "../../lib/data";
import { gbp, pct } from "../../lib/format";
import { RunSummary, StepFooter, type Form } from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };

const totals = (ids: string[]) => {
  const hs = HEDGES.filter((h) => ids.includes(h.id));
  return {
    hedges: hs,
    stake: hs.reduce((a, h) => a + h.stake, 0),
    payout: hs.reduce((a, h) => a + h.payout, 0),
  };
};

export function AnalysisStep({ analysed, onAnalysed, onNext, onBack }: Nav & { analysed: boolean; onAnalysed: () => void }) {
  const [showResult, setShowResult] = useState(analysed);
  const [live] = useState(!analysed);
  const totalCost = RISKS.reduce((a, r) => a + r.annualCost, 0);

  return (
    <div>
      {!live ? (
        <RunSummary label="Analysis complete" detail="13 tool calls · 1,827 days · 9.8s" />
      ) : (
        <AgentRun
          title="Analysing The Oak Tree"
          runId="run_b21c04"
          steps={ANALYSIS_RUN}
          onDone={() => {
            onAnalysed();
            setTimeout(() => setShowResult(true), 500);
          }}
        />
      )}

      {showResult && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
          <Panel
            className="mt-4"
            title="Risks found"
            actions={<span className="font-mono text-[12px] text-fg-2">Total exposure {gbp(-totalCost)} a year</span>}
            bodyClassName="p-0"
          >
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-[0.04em] text-fg-3">
                  <th className="px-4 py-2 font-medium">Risk</th>
                  <th className="px-4 py-2 font-medium">Cost a year</th>
                  <th className="px-4 py-2 font-medium">Evidence</th>
                  <th className="px-4 py-2 font-medium">Model fit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {RISKS.map((r) => (
                  <tr key={r.id} className="align-top">
                    <td className="w-[230px] px-4 py-3">
                      <div className="text-[13px] font-medium">{r.name}</div>
                      <div className="mt-0.5 text-[12px] text-fg-3">{r.driver}</div>
                    </td>
                    <td className="w-[120px] px-4 py-3 font-mono text-[13px] text-negative">{gbp(-r.annualCost)}</td>
                    <td className="px-4 py-3 text-[12.5px] leading-5 text-fg-2">{r.evidence}</td>
                    <td className="w-[190px] px-4 py-3">
                      <div className="whitespace-nowrap font-mono text-[12px] text-fg-2">{r.fit}</div>
                      <div className="mt-1">
                        <Badge tone={r.confidence === "High" ? "positive" : "neutral"}>{r.confidence} confidence</Badge>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </motion.div>
      )}

      <StepFooter onBack={onBack} onNext={onNext} disabled={!showResult} nextLabel="See the impact" />
    </div>
  );
}

export function ImpactStep({ onNext, onBack }: Nav) {
  const maxLoss = HEDGES.reduce((a, h) => a + h.stake, 0);
  const share = maxLoss / AVG_MONTHLY_MARGIN;
  const worstActual = Math.min(...CASHFLOW.map((w) => w.actual));
  const worstHedged = Math.min(...CASHFLOW.map((w) => w.hedged));

  return (
    <div>
      <div className="grid grid-cols-[1fr_240px] gap-4">
        <Panel
          title="Last year, week by week"
          actions={
            <div className="flex items-center gap-4 text-[12px] text-fg-2">
              <Legend color="var(--fg-3)" label="Without protection" />
              <Legend color="var(--accent)" label="With Pub Hedge" />
            </div>
          }
        >
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={CASHFLOW} margin={{ top: 8, right: 56, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="week" tickLine={false} axisLine={false} interval={3} tickFormatter={(w) => CASHFLOW[w - 1]?.month ?? ""} />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={64}
                  domain={[-1500, 2000]}
                  ticks={[-1500, -1000, -500, 0, 500, 1000, 1500, 2000]}
                  tickFormatter={(v) => gbp(v)}
                />
                <ReferenceLine
                  y={0}
                  stroke="var(--negative)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.6}
                  label={{ value: "Payroll", position: "right", fill: "var(--fg-3)", fontSize: 11 }}
                />
                <Tooltip
                  {...tooltipStyle}
                  labelFormatter={(w) => `Week ${w}`}
                  formatter={((v: number, name: string) => [gbp(v), name === "actual" ? "Without" : "With Pub Hedge"]) as never}
                />
                <Line type="monotone" dataKey="actual" stroke="var(--fg-3)" strokeWidth={1.5} dot={false} animationDuration={900} />
                <Line type="monotone" dataKey="hedged" stroke="var(--accent)" strokeWidth={2} dot={false} animationDuration={900} animationBegin={500} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel className="flex-1">
            <Metric label="Net benefit, after costs" value={gbp(BACKTEST.netBenefit, { sign: true })} sub="a year" tone="positive" size="lg" />
          </Panel>
          <Panel className="flex-1">
            <Metric
              label="Weeks you couldn't cover payroll"
              value={
                <span>
                  {WEEKS_BELOW_PAYROLL.actual} <span className="text-fg-3">→</span> {WEEKS_BELOW_PAYROLL.hedged}
                </span>
              }
            />
          </Panel>
          <Panel className="flex-1">
            <Metric
              label="Worst week"
              value={
                <span className="text-[18px]">
                  <span className="text-negative">{gbp(worstActual)}</span> <span className="text-fg-3">→</span>{" "}
                  <span className="text-positive">{gbp(worstHedged, { sign: true })}</span>
                </span>
              }
            />
          </Panel>
        </div>
      </div>

      <Panel className="mt-4" title="If none of these events happen">
        <div className="grid grid-cols-[1fr_280px] items-center gap-8">
          <p className="text-[13px] leading-6 text-fg-2">
            You lose what you paid and nothing more: at most <span className="font-mono text-fg">{gbp(maxLoss)}</span> a month, which is{" "}
            <span className="font-mono text-fg">{pct(share)}</span> of your average monthly margin of{" "}
            <span className="font-mono text-fg">{gbp(AVG_MONTHLY_MARGIN)}</span>. Across a 50-pub backtest, {BACKTEST.losingMonths} months in{" "}
            {BACKTEST.months} lost money. The worst was <span className="font-mono text-negative">{gbp(BACKTEST.worstMonth)}</span>.
          </p>
          <div>
            <div className="flex justify-between font-mono text-[11.5px] text-fg-3">
              <span>Max monthly loss</span>
              <span>Monthly margin</span>
            </div>
            <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-surface-3">
              <div className="h-2 bg-negative" style={{ width: `${Math.max(share * 100, 1.5)}%` }} />
            </div>
            <div className="mt-1.5 flex justify-between font-mono text-[12px]">
              <span className="text-negative">{gbp(maxLoss)}</span>
              <span className="text-fg-2">{gbp(AVG_MONTHLY_MARGIN)}</span>
            </div>
          </div>
        </div>
      </Panel>

      <StepFooter onBack={onBack} onNext={onNext} nextLabel="See recommendations" />
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-0.5 w-3 rounded" style={{ background: color }} />
      {label}
    </span>
  );
}

export function RecommendationsStep({
  selected,
  setSelected,
  onNext,
  onBack,
}: Nav & { selected: string[]; setSelected: (ids: string[]) => void }) {
  const [focus, setFocus] = useState(HEDGES[0].id);
  const t = totals(selected);
  const hedge = HEDGES.find((h) => h.id === focus)!;
  const toggle = (id: string, on: boolean) => setSelected(on ? [...selected, id] : selected.filter((s) => s !== id));

  return (
    <div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] items-start gap-4">
        <Panel title="Recommended" bodyClassName="p-0">
          <ul className="divide-y divide-line">
            {HEDGES.map((h) => (
              <li
                key={h.id}
                onClick={() => setFocus(h.id)}
                className={cx(
                  "flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors",
                  focus === h.id ? "bg-surface-3" : "hover:bg-surface-2"
                )}
              >
                <div className="pt-0.5" onClick={(e) => e.stopPropagation()}>
                  <Checkbox checked={selected.includes(h.id)} onChange={(v) => toggle(h.id, v)} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium">{h.name}</div>
                  <div className="mt-0.5 text-[12px] leading-4 text-fg-3">{h.market}</div>
                </div>
                <div className="text-right font-mono text-[12.5px]">
                  <div>{gbp(h.stake)}</div>
                  <div className="text-[11.5px] text-positive">pays {gbp(h.payout)}</div>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 font-mono text-[12px] text-fg-2">
            <span>{t.hedges.length} selected</span>
            <span>
              stake {gbp(t.stake)} · max loss {gbp(t.stake)}
            </span>
          </div>
        </Panel>

        <HedgeDetail hedge={hedge} />
      </div>

      <StepFooter
        onBack={onBack}
        onNext={onNext}
        disabled={t.hedges.length === 0}
        hint={t.hedges.length === 0 ? "Select at least one" : undefined}
        nextLabel="Review"
      />
    </div>
  );
}

function HedgeDetail({ hedge: h }: { hedge: Hedge }) {
  const value = ev(h);
  return (
    <motion.div key={h.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
      <Panel title={h.name} actions={<Badge>{h.venue}</Badge>}>
        <div className="text-[12px] text-fg-2">Pays out if</div>
        <p className="mt-1 text-[13px] leading-5">{h.pays}</p>

        <div className="mt-4 grid grid-cols-4 gap-px overflow-hidden rounded border border-line bg-line">
          {[
            { l: "Stake", v: gbp(h.stake) },
            { l: "Pays", v: gbp(h.payout), c: "text-positive" },
            { l: "Max loss", v: gbp(h.stake), c: "text-negative" },
            { l: "Expected value", v: gbp(Math.round(value * 10) / 10, { sign: true }) },
          ].map((m) => (
            <div key={m.l} className="bg-surface-2 px-3 py-2">
              <div className="text-[11.5px] text-fg-3">{m.l}</div>
              <div className={cx("font-mono text-[14px]", m.c)}>{m.v}</div>
            </div>
          ))}
        </div>

        <h3 className="mt-5 text-[12px] font-medium text-fg-2">Why it was suggested</h3>
        <ul className="mt-2 space-y-1.5">
          {h.rationale.map((r) => (
            <li key={r} className="flex gap-2.5 text-[12.5px] leading-5 text-fg">
              <Icon name="chevron-right" size={12} className="mt-1 shrink-0 text-fg-3" />
              {r}
            </li>
          ))}
        </ul>

        <h3 className="mt-5 text-[12px] font-medium text-fg-2">How it was calculated</h3>
        <dl className="mt-2 rounded border border-line bg-surface-2 px-3 py-2 font-mono text-[12px] leading-6">
          <CalcRow k="Market price" v={`${h.price} (${pct(h.marketProb, 0)} implied)`} />
          <CalcRow k="Our estimate" v={pct(h.modelProb, 0)} />
          <CalcRow k="Expected value" v={`${h.modelProb.toFixed(2)} × ${gbp(h.payout)} − ${gbp(h.stake)} = ${gbp(Math.round(value * 10) / 10, { sign: true })}`} />
          <CalcRow k="Basis risk" v={`${h.basisRisk.toFixed(2)} (lower tracks your loss better)`} />
          <CalcRow k="Liquidity" v={h.liquidity} />
          <CalcRow k="Share of margin" v={`${pct(h.stake / AVG_MONTHLY_MARGIN)} of a month, worst case`} />
        </dl>
      </Panel>
    </motion.div>
  );
}

function CalcRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="grid grid-cols-[130px_1fr]">
      <dt className="text-fg-3">{k}</dt>
      <dd className="text-fg">{v}</dd>
    </div>
  );
}

export function ReviewStep({
  selected,
  placed,
  onPlaced,
  form,
  onBack,
}: Nav & { selected: string[]; placed: boolean; onPlaced: () => void; form: Form }) {
  const router = useRouter();
  const [ack, setAck] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [showDone, setShowDone] = useState(placed);
  const [live] = useState(!placed);
  const t = totals(selected);
  const needsApproval = t.stake > LIMITS.approvalOver;
  const [runSteps] = useState(() => [
    {
      ...PLACE_RUN[0],
      calls: [
        { call: `guard.spend(${gbp(t.stake)} ≤ ${gbp(LIMITS.weeklySpend)}/wk)`, result: "Pass" },
        { call: `guard.max_loss(${gbp(t.stake)} ≤ ${gbp(LIMITS.monthlyLoss)}/mo)`, result: "Pass" },
        { call: `guard.approval(${form.owner.trim().toLowerCase().replace(/\s+/g, ".")})`, result: "Signed" },
      ],
    },
    {
      ...PLACE_RUN[1],
      summary: `${t.hedges.length} filled`,
      calls: PLACE_RUN[1].calls.filter((_, i) => selected.includes(HEDGES[i].id)),
    },
    PLACE_RUN[2],
  ]);

  if (placing || placed) {
    return (
      <div>
        {!live ? (
          <RunSummary label="Orders placed" detail={`${t.hedges.length} filled · limits checked · 5.9s`} />
        ) : (
          <AgentRun
            title="Placing your orders"
            runId="run_e90d55"
            steps={runSteps}
            onDone={() => {
              onPlaced();
              setTimeout(() => setShowDone(true), 500);
            }}
          />
        )}
        {showDone && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            <Panel className="mt-4">
              <div className="flex items-start gap-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-positive-wash text-positive">
                  <Icon name="check" />
                </span>
                <div>
                  <h2 className="text-[16px] font-medium">{form.pubName} is set up</h2>
                  <p className="mt-1 max-w-[600px] text-[13px] leading-6 text-fg-2">
                    {t.hedges.length} positions are open. The agent now watches your till, the forecast and these markets, and asks you
                    before it places anything over {gbp(LIMITS.approvalOver)}.
                  </p>
                </div>
              </div>
              <ul className="mt-5 grid grid-cols-3 gap-px overflow-hidden rounded border border-line bg-line">
                {[
                  { i: "bell" as const, t: "Alerts before an event", d: "Usually two to three days ahead" },
                  { i: "shield" as const, t: "Your approval over £50", d: "Smaller renewals follow your limits" },
                  { i: "calendar" as const, t: "Weekly summary", d: "Every Monday at 08:00" },
                ].map((x) => (
                  <li key={x.t} className="flex gap-3 bg-surface-2 px-4 py-3">
                    <Icon name={x.i} className="mt-0.5 text-fg-3" />
                    <div>
                      <div className="text-[13px]">{x.t}</div>
                      <div className="text-[12px] text-fg-3">{x.d}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </Panel>
          </motion.div>
        )}
        <StepFooter
          onNext={() => {
            saveSetup({ pubName: form.pubName, owner: form.owner, hedges: selected });
            router.push("/dashboard");
          }}
          disabled={!showDone}
          nextLabel="Open dashboard"
        />
      </div>
    );
  }

  return (
    <div>
      <Panel title="Order" bodyClassName="p-0">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-[0.04em] text-fg-3">
              <th className="px-4 py-2 font-medium">Position</th>
              <th className="px-4 py-2 font-medium">Venue</th>
              <th className="px-4 py-2 text-right font-medium">Stake</th>
              <th className="px-4 py-2 text-right font-medium">Pays if it happens</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {t.hedges.map((h) => (
              <tr key={h.id}>
                <td className="px-4 py-2.5">
                  <div className="text-[13px]">{h.name}</div>
                  <div className="text-[12px] text-fg-3">{h.market}</div>
                </td>
                <td className="px-4 py-2.5 text-[12.5px] text-fg-2">{h.venue}</td>
                <td className="px-4 py-2.5 text-right font-mono text-[13px]">{gbp(h.stake)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-[13px] text-positive">{gbp(h.payout)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line-strong font-mono text-[13px]">
              <td className="px-4 py-2.5 font-sans text-fg-2" colSpan={2}>
                Total
              </td>
              <td className="px-4 py-2.5 text-right">{gbp(t.stake)}</td>
              <td className="px-4 py-2.5 text-right text-positive">up to {gbp(t.payout)}</td>
            </tr>
          </tfoot>
        </table>
      </Panel>

      <Panel className="mt-4" title="Limits" bodyClassName="p-0">
        <ul className="divide-y divide-line text-[13px]">
          <LimitRow label="Weekly spend" value={`${gbp(t.stake)} of ${gbp(LIMITS.weeklySpend)}`} ok />
          <LimitRow label="Maximum loss this month" value={`${gbp(t.stake)} of ${gbp(LIMITS.monthlyLoss)}`} ok />
          <LimitRow
            label={`Orders over ${gbp(LIMITS.approvalOver)} need your approval`}
            value={needsApproval ? "This order needs it" : "Not needed"}
            ok={!needsApproval}
          />
        </ul>
      </Panel>

      <div className="mt-5">
        <Checkbox
          checked={ack}
          onChange={setAck}
          label={
            <span className="text-fg-2">
              I understand I lose up to <span className="font-mono text-fg">{gbp(t.stake)}</span> if none of these events happen.
            </span>
          }
        />
      </div>

      <StepFooter onBack={onBack} onNext={() => setPlacing(true)} disabled={!ack || t.hedges.length === 0} nextLabel="Approve and place orders" />
    </div>
  );
}

function LimitRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <li className="flex h-10 items-center justify-between px-4">
      <span className="text-fg-2">{label}</span>
      <span className="flex items-center gap-2 font-mono text-[12.5px]">
        {value}
        <span className={ok ? "text-positive" : "text-warning"}>
          <Icon name={ok ? "check" : "alert"} size={14} />
        </span>
      </span>
    </li>
  );
}
