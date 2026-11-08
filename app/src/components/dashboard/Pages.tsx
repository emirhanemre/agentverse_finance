"use client";

import { useState } from "react";
import { Badge, Panel, cx } from "../ui";
import { Num, ProvPanel } from "../Provenance";
import { ActivityFeed, ApprovalCard, BacktestPanel, LimitsPanel, ProposalPanel, RisksPanel, SourcesPanel, VerifyPanel, WeeklyBacktestChart, ForecastPanel } from "../panels";
import { Td, Th } from "./Shell";
import { proposals, type AppState } from "../../lib/api";
import { day, gbp } from "../../lib/format";

const TONE = { pending: "warning", blocked: "negative", filled: "positive", rejected: "neutral" } as const;

export function ProtectionsPage({ s, refresh }: { s: AppState; refresh: () => void }) {
  const all = proposals(s);
  const [selected, setSelected] = useState(all[0]?.id);
  const p = all.find((x) => x.id === selected) ?? all[0];
  return (
    <div className="grid grid-cols-[1.3fr_1fr] items-start gap-4">
      <div className="flex min-w-0 flex-col gap-4">
        <ProvPanel title="Proposals" prov={{ badge: "PAPER", meta: { source: "Paper trading. No real orders." } }} bodyClassName="p-0">
          <table className="w-full">
            <thead className="border-b border-line">
              <tr>
                <Th>Cover</Th>
                <Th>Run</Th>
                <Th right>Cost</Th>
                <Th right>Pays</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {all.map((x) => (
                <tr key={x.id} onClick={() => setSelected(x.id)} className={cx("cursor-pointer transition-colors", x.id === p?.id ? "bg-surface-3" : "hover:bg-surface-2")}>
                  <Td className="whitespace-nowrap text-fg">Rain cover, {day(x.market.date)}</Td>
                  <Td mono className="text-fg-3">
                    {x.run_id}
                  </Td>
                  <Td right>{gbp(x.cost_pence / 100, { pence: true })}</Td>
                  <Td right>{gbp(x.market.payout_if_event_gbp)}</Td>
                  <Td>
                    <Badge tone={TONE[x.status]} dot>
                      {x.status}
                    </Badge>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
          {all.length === 0 && <p className="px-6 py-4 text-sm text-fg-2">No proposals. Run the agent before the next risky weekend.</p>}
        </ProvPanel>
        <ProposalPanel s={s} p={p} />
      </div>
      <ApprovalCard key={p?.id} s={s} p={p} onChange={refresh} />
    </div>
  );
}

export function RisksPage({ s }: { s: AppState }) {
  return (
    <div className="flex flex-col gap-4">
      <RisksPanel s={s} />
      <ForecastPanel s={s} />
    </div>
  );
}

export function BacktestPage({ s }: { s: AppState }) {
  return (
    <div className="flex flex-col gap-4">
      <BacktestPanel s={s} />
      <WeeklyBacktestChart s={s} />
    </div>
  );
}

export function ActivityPage({ tick }: { tick: number }) {
  return (
    <Panel title="Audit log" actions={<span>Hash-chained. Click any call for its receipt.</span>} bodyClassName="px-6 py-2">
      <ActivityFeed limit={200} refreshKey={tick} />
    </Panel>
  );
}

export function SourcesPage({ s }: { s: AppState }) {
  return (
    <div className="flex flex-col gap-4">
      <VerifyPanel s={s} />
      <SourcesPanel s={s} />
      <ProvPanel title="Synthetic data" prov={{ badge: "SYNTHETIC", meta: s.synthetic_manifest }}>
        <p className="text-sm text-fg-2">{s.synthetic_manifest.label}</p>
        <p className="mt-2 text-xs text-fg-3">
          <span className="font-mono">{s.synthetic_manifest.generator}</span> · seed <Num>{s.synthetic_manifest.seed}</Num>
        </p>
        <p className="mt-2 max-w-[75ch] text-xs leading-5 text-fg-3">{s.synthetic_manifest.method}</p>
      </ProvPanel>
    </div>
  );
}

export function SettingsPage({ s, refresh }: { s: AppState; refresh: () => void }) {
  return (
    <div className="grid grid-cols-2 items-start gap-4">
      <LimitsPanel s={s} onChange={refresh} />
    </div>
  );
}
