"use client";

import { useState } from "react";
import { Badge, Icon, KeyValue, Panel, cx } from "../ui";
import { Td, Th } from "./Shell";
import { gbp, pct } from "../../lib/format";
import { BACKTEST, LIMITS, PUB, RISKS, SOURCES, ev, type Hedge } from "../../lib/data";
import { ACTIVITY_LOG, HISTORY, RAIN_EVENTS, SETTLES, SYNC, type FeedRow, type Timeline } from "../../lib/dashboard-data";

export function ProtectionsPage({ hedges, timeline }: { hedges: Hedge[]; timeline: Timeline }) {
  const [selected, setSelected] = useState(hedges[0]?.id);
  const h = hedges.find((x) => x.id === selected) ?? hedges[0];
  if (timeline === "year") return <SettledPositions />;
  const settled = (x: Hedge) => timeline === "rain" && x.id === "rain";
  return (
    <div className="grid h-full grid-cols-[1.3fr_1fr] gap-3">
      <Panel title="Positions" bodyClassName="p-0">
        <table className="w-full">
          <thead className="border-b border-line bg-surface-2">
            <tr>
              <Th>Position</Th>
              <Th>Venue</Th>
              <Th right>Stake</Th>
              <Th right>Pays</Th>
              <Th right>Price</Th>
              <Th>Settles</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {hedges.map((x) => (
              <tr
                key={x.id}
                onClick={() => setSelected(x.id)}
                className={cx("cursor-pointer transition-colors", x.id === h?.id ? "bg-surface-3" : "hover:bg-surface-2")}
              >
                <Td className="whitespace-nowrap text-fg">{x.name}</Td>
                <Td className="text-fg-2">{x.venue}</Td>
                <Td right mono>
                  {gbp(x.stake)}
                </Td>
                <Td right mono>
                  {gbp(x.payout)}
                </Td>
                <Td right mono className="text-fg-2">
                  {x.price}
                </Td>
                <Td mono className="whitespace-nowrap text-fg-2">
                  {SETTLES[x.id]}
                </Td>
                <Td>
                  {settled(x) ? (
                    <Badge tone="positive" dot>
                      Paid {gbp(x.payout)}
                    </Badge>
                  ) : (
                    <Badge tone="accent" dot>
                      Open
                    </Badge>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
        {hedges.length === 0 && <p className="p-4 text-[13px] text-fg-2">No open positions. The agent will propose cover before your next risk event.</p>}
      </Panel>
      {h && (
        <Panel
          title={h.name}
          actions={
            settled(h) ? (
              <Badge tone="positive" dot>
                Settled
              </Badge>
            ) : (
              <Badge tone="accent" dot>
                Open
              </Badge>
            )
          }
          className="overflow-y-auto"
        >
          <p className="text-[13px] leading-5 text-fg-2">Pays out if {h.pays.charAt(0).toLowerCase() + h.pays.slice(1)}</p>
          <KeyValue
            className="mt-3"
            rows={[
              { label: "Market", value: h.market },
              { label: "Venue", value: h.venue },
              { label: "Stake / payout", value: `${gbp(h.stake)} / ${gbp(h.payout)}`, mono: true },
              { label: "Market vs our estimate", value: `${pct(h.marketProb, 0)} vs ${pct(h.modelProb, 0)}`, mono: true },
              { label: "Expected value", value: gbp(ev(h), { sign: true }), mono: true },
              { label: "Basis risk", value: h.basisRisk.toFixed(2), mono: true },
              { label: "Liquidity", value: h.liquidity, mono: true },
              { label: "Covers", value: h.covers },
            ]}
          />
          <h3 className="mt-4 text-[12.5px] font-medium text-fg">Why it was chosen</h3>
          <ul className="mt-2 space-y-1.5">
            {h.rationale.map((r) => (
              <li key={r} className="flex gap-2 text-[12.5px] leading-5 text-fg-2">
                <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-fg-3" />
                {r}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function SettledPositions() {
  const paid = HISTORY.filter((r) => r.result === "Paid").length;
  return (
    <div className="grid h-full grid-cols-[1.6fr_1fr] gap-3">
      <Panel title="Settled positions" actions={<span className="font-mono text-[11.5px] text-fg-3">Latest 8 of 48</span>} bodyClassName="p-0">
        <table className="w-full">
          <thead className="border-b border-line bg-surface-2">
            <tr>
              <Th>Position</Th>
              <Th>Venue</Th>
              <Th>Settled</Th>
              <Th right>Stake</Th>
              <Th right>Payout</Th>
              <Th right>Net</Th>
              <Th>Result</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {HISTORY.map((r) => (
              <tr key={r.name + r.settled}>
                <Td className="text-fg">{r.name}</Td>
                <Td className="text-fg-2">{r.venue}</Td>
                <Td mono className="text-fg-2">
                  {r.settled}
                </Td>
                <Td right mono>
                  {gbp(r.stake)}
                </Td>
                <Td right mono>
                  {gbp(r.payout)}
                </Td>
                <Td right mono className={r.payout > r.stake ? "text-positive" : "text-negative"}>
                  {gbp(r.payout - r.stake, { sign: true })}
                </Td>
                <Td>
                  <Badge tone={r.result === "Paid" ? "positive" : "neutral"}>{r.result}</Badge>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <Panel title="Year one">
        <KeyValue
          rows={[
            { label: "Positions settled", value: "48", mono: true },
            { label: "Paid out", value: `${paid} of the latest 8`, mono: true },
            { label: "Total spend", value: gbp(BACKTEST.spend), mono: true },
            { label: "Total payouts", value: gbp(BACKTEST.payouts), mono: true },
            { label: "Net", value: <span className="text-positive">{gbp(BACKTEST.netBenefit, { sign: true })}</span>, mono: true },
          ]}
        />
        <p className="mt-3 text-[12.5px] leading-5 text-fg-2">
          Most positions expire worthless. That is the cost of cover. The ones that pay land on the days the till is down.
        </p>
      </Panel>
    </div>
  );
}

const YEAR_LOG: (FeedRow & { day: string })[] = [
  { day: "Wed 8 Jul 2026", time: "09:10", text: "Year-one review sent: net +£1,840 across 48 positions.", tone: "positive" },
  { day: "Wed 8 Jul 2026", time: "09:04", text: "Proposed July weekend rain cover, 4 × £20. Waiting for your approval.", tone: "warning" },
  { day: "Wed 8 Jul 2026", time: "09:02", text: "Refit revenue model on 12 new months of till data. Rain elasticity now −£352 per mm." },
  { day: "Sat 7 Mar 2026", time: "17:40", text: "England out before Round 5 expired. −£20, within your monthly limit." },
  { day: "Wed 26 Nov 2025", time: "13:15", text: "Budget left beer duty unchanged. Duty position expired, −£15." },
];

export function RisksPage() {
  return (
    <Panel title="Risks to your margin" actions={<span className="font-mono text-[11.5px] text-fg-3">Model refreshed 09:00</span>} bodyClassName="p-0">
      <table className="w-full">
        <thead className="border-b border-line bg-surface-2">
          <tr>
            <Th>Risk</Th>
            <Th>Driver</Th>
            <Th right>Cost per year</Th>
            <Th>Evidence</Th>
            <Th>Fit</Th>
            <Th>Confidence</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {RISKS.map((r) => (
            <tr key={r.id} className="align-top">
              <Td className="py-3 text-fg">{r.name}</Td>
              <Td className="py-3 text-fg-2">{r.driver}</Td>
              <Td right mono className="py-3 text-negative">
                {gbp(-r.annualCost)}
              </Td>
              <Td className="max-w-[420px] py-3 leading-5 text-fg-2">{r.evidence}</Td>
              <Td mono className="py-3 text-fg-2">
                {r.fit}
              </Td>
              <Td className="py-3">
                <Badge tone={r.confidence === "High" ? "positive" : "neutral"}>{r.confidence}</Badge>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

export function ActivityPage({ timeline }: { timeline: Timeline }) {
  const rain = [...RAIN_EVENTS].reverse().map(({ time, text, tone }) => ({ day: "Sat 12 Jul 2025", time, text, tone }));
  const log = [...(timeline === "year" ? YEAR_LOG : []), ...(timeline !== "today" ? rain : []), ...ACTIVITY_LOG];
  const days = Array.from(new Set(log.map((a) => a.day)));
  return (
    <Panel title="Agent activity" bodyClassName="p-0">
      {days.map((d) => (
        <div key={d}>
          <div className="border-b border-line bg-surface-2 px-4 py-1.5 font-mono text-[11.5px] text-fg-3">{d}</div>
          <ul className="divide-y divide-line px-4">
            {log.filter((a) => a.day === d).map((a, i) => (
              <li key={i} className="grid grid-cols-[52px_1fr] gap-3 py-2">
                <span className="font-mono text-[11.5px] leading-5 text-fg-3">{a.time}</span>
                <span
                  className={cx(
                    "text-[12.5px] leading-5",
                    a.tone === "positive" ? "text-positive" : a.tone === "warning" ? "text-warning" : a.tone === "accent" ? "text-fg" : "text-fg-2"
                  )}
                >
                  {a.text}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Panel>
  );
}

export function SourcesPage() {
  return (
    <Panel title="Data sources" actions={<span className="text-[12px] text-fg-3">Read-only access</span>} bodyClassName="p-0">
      <ul className="divide-y divide-line">
        {SOURCES.map((s) => (
          <li key={s.id} className="flex items-center gap-4 px-4 py-3">
            <span className="flex h-8 w-8 items-center justify-center rounded border border-line-strong bg-surface-2 text-fg-2">
              <Icon name={s.icon} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] text-fg">{s.name}</div>
              <div className="text-[12px] text-fg-3">
                {s.kind} · {s.via}
              </div>
            </div>
            <div className="w-[300px] font-mono text-[12px] text-fg-2">{s.result}</div>
            <div className="w-[150px] whitespace-nowrap font-mono text-[12px] text-fg-3">Synced {SYNC[s.id]}</div>
            <Badge tone="positive" dot>
              Connected
            </Badge>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function SettingsPage() {
  const [prefs, setPrefs] = useState({ approvals: true, summary: true, payouts: false });
  const toggle = (k: keyof typeof prefs) => setPrefs((p) => ({ ...p, [k]: !p[k] }));
  return (
    <div className="grid grid-cols-2 gap-3">
      <Panel title="Limits">
        <p className="mb-3 text-[12.5px] text-fg-2">Enforced in code before any proposal reaches you. Contact support to change them.</p>
        <div className="space-y-3">
          <ReadOnly label="Weekly spend limit" value={gbp(LIMITS.weeklySpend)} />
          <ReadOnly label="Monthly loss limit" value={gbp(LIMITS.monthlyLoss)} />
          <ReadOnly label="Needs your approval over" value={gbp(LIMITS.approvalOver)} />
        </div>
      </Panel>
      <Panel title="Notifications">
        <div className="divide-y divide-line">
          <ToggleRow label="Email me when something needs approval" sub={PUB.email} on={prefs.approvals} onToggle={() => toggle("approvals")} />
          <ToggleRow label="Daily summary at 07:00" sub="Takings, forecast and positions" on={prefs.summary} onToggle={() => toggle("summary")} />
          <ToggleRow label="Text me when a payout lands" sub="+44 7700 900 418" on={prefs.payouts} onToggle={() => toggle("payouts")} />
        </div>
      </Panel>
    </div>
  );
}

function ReadOnly({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="text-[12px] text-fg-2">{label}</span>
      <div className="mt-1 flex h-8 items-center justify-between rounded border border-line-strong bg-surface-2 px-2.5 font-mono text-[13px]">
        {value}
        <Icon name="lock" size={13} className="text-fg-3" />
      </div>
    </label>
  );
}

function ToggleRow({ label, sub, on, onToggle }: { label: string; sub: string; on: boolean; onToggle: () => void }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div>
        <div className="text-[13px] text-fg">{label}</div>
        <div className="text-[12px] text-fg-3">{sub}</div>
      </div>
      <button
        role="switch"
        aria-checked={on}
        aria-label={label}
        onClick={onToggle}
        className={cx("relative h-[18px] w-8 shrink-0 rounded-full transition-colors", on ? "bg-accent-strong" : "bg-surface-3")}
      >
        <span className={cx("absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white transition-[left]", on ? "left-[16px]" : "left-[2px]")} />
      </button>
    </div>
  );
}
