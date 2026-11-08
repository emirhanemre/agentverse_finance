"use client";

import { Metric, Panel } from "../ui";
import { Num, ProvBadge } from "../Provenance";
import { ActivityFeed, ApprovalCard, CashflowPanel, ForecastPanel, LimitsPanel, ToolBadge } from "../panels";
import { payroll, proposals, tool, type AppState } from "../../lib/api";
import { day, gbp } from "../../lib/format";

function Kpi({ badge, ...props }: React.ComponentProps<typeof Metric> & { badge?: React.ReactNode }) {
  return (
    <div className="relative px-4 py-3">
      <div className="absolute right-3 top-3">{badge}</div>
      <Metric {...props} />
    </div>
  );
}

export function TodayView({ s, refresh, tick }: { s: AppState; refresh: () => void; tick: number }) {
  const p = proposals(s)[0];
  const wet = payroll(s, "wet");
  const dry = payroll(s, "dry");
  const f = tool(s, "weekend_forecast");
  const days = Object.entries((f?.days ?? {}) as Record<string, { mm: number }>);
  const sized = tool(s, "size_hedges");

  return (
    <div className="flex flex-col gap-3">
      <section className="grid grid-cols-4 divide-x divide-line rounded-md border border-line bg-surface" data-testid="kpis">
        <Kpi
          label="Cover awaiting you"
          value={p ? <Num rid={sized?.receipt_id}>{gbp(p.cost_pence / 100, { pence: true })}</Num> : "—"}
          sub={p ? `${p.status} · pays ${gbp(p.market.payout_if_event_gbp)} if wet` : "Nothing proposed"}
          badge={<ProvBadge badge="PAPER" meta={{ source: "Paper trading. No real orders." }} />}
        />
        <Kpi
          label="Payroll short if wet"
          value={wet ? <Num rid={wet.receipt_id}>{gbp(-wet.shortfall_gbp)}</Num> : "—"}
          tone="negative"
          sub={wet ? `Payroll due ${day(wet.payroll_date)}` : undefined}
          badge={<ToolBadge r={wet} />}
        />
        <Kpi
          label="First day overdrawn"
          value={wet ? <Num rid={wet.receipt_id}>{day(wet.first_negative_date)}</Num> : "—"}
          tone="warning"
          sub={dry ? (dry.first_negative_date === wet?.first_negative_date ? "Same day if it stays dry" : `Dry weekend: ${day(dry.first_negative_date)}`) : undefined}
          badge={<ToolBadge r={wet} />}
        />
        <Kpi
          label="Weekend forecast"
          value={days.length ? <Num rid={f?.receipt_id}>{days.map(([, v]) => `${v.mm.toFixed(1)}`).join(" / ")} mm</Num> : "—"}
          sub={days.length ? days.map(([d]) => day(d)).join(" · ") : s.scenario.name}
          badge={<ToolBadge r={f} />}
        />
      </section>

      <div className="grid grid-cols-[1.45fr_1fr] items-start gap-3">
        <div className="flex min-w-0 flex-col gap-3">
          <CashflowPanel s={s} compact />
          <Panel title="Agent activity" actions={<span className="text-[12px] text-fg-3">From the audit log</span>} bodyClassName="max-h-[320px] overflow-y-auto py-1">
            <ActivityFeed limit={25} refreshKey={tick} />
          </Panel>
        </div>
        <div className="flex min-w-0 flex-col gap-3">
          <ApprovalCard key={p?.id} s={s} p={p} onChange={refresh} />
          <LimitsPanel s={s} onChange={refresh} />
          <ForecastPanel s={s} />
        </div>
      </div>
    </div>
  );
}
