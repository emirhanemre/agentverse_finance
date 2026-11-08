"use client";

import { Metric, Panel } from "../ui";
import { Num, ProvBadge, ProvScope } from "../Provenance";
import { ActivityFeed, ApprovalCard, CashflowPanel, ForecastPanel, LimitsPanel, OfferCard, provOf } from "../panels";
import { payroll, rainProposals, tool, type AppState } from "../../lib/api";
import { day, gbp } from "../../lib/format";

/** One figure of the ruled tally, carrying its own quiet provenance label. */
function Kpi({ prov, ...props }: React.ComponentProps<typeof Metric> & { prov?: React.ComponentProps<typeof ProvBadge> }) {
  return (
    <ProvScope value={prov?.badge}>
      <div className="relative px-6 py-4">
        {prov && <ProvBadge {...prov} variant="label" className="absolute right-4 top-3" />}
        <Metric {...props} />
      </div>
    </ProvScope>
  );
}

export function TodayView({ s, refresh, tick }: { s: AppState; refresh: () => void; tick: number }) {
  const p = rainProposals(s)[0];
  const wet = payroll(s, "wet");
  const dry = payroll(s, "dry");
  const f = tool(s, "weekend_forecast");
  const days = Object.entries((f?.days ?? {}) as Record<string, { mm: number }>);
  const sized = tool(s, "size_hedges");

  return (
    <div className="flex flex-col gap-4">
      <section className="glass grid grid-cols-4 divide-x divide-line" data-testid="kpis">
        <Kpi
          label="Cover awaiting you"
          value={p ? <Num r={sized}>{gbp(p.cost_pence / 100, { pence: true })}</Num> : "—"}
          sub={p ? `${p.status} · pays ${gbp(p.market.payout_if_event_gbp)} if wet` : "Nothing proposed"}
          prov={{ badge: "PAPER", meta: { source: "Paper trading. No real orders." } }}
        />
        <Kpi
          label="Payroll short if wet"
          value={wet ? <Num rid={wet.receipt_id}>{gbp(-wet.shortfall_gbp)}</Num> : "—"}
          tone="negative"
          sub={wet ? `Payroll due ${day(wet.payroll_date)}` : undefined}
          prov={provOf(wet)}
        />
        <Kpi
          label="First day overdrawn"
          value={wet ? <Num rid={wet.receipt_id}>{day(wet.first_negative_date)}</Num> : "—"}
          tone="warning"
          sub={dry ? (dry.first_negative_date === wet?.first_negative_date ? "Same day if it stays dry" : `Dry weekend: ${day(dry.first_negative_date)}`) : undefined}
          prov={provOf(wet)}
        />
        <Kpi
          label="Weekend forecast"
          value={days.length ? <Num rid={f?.receipt_id}>{days.map(([, v]) => `${v.mm.toFixed(1)}`).join(" / ")} mm</Num> : "—"}
          sub={days.length ? days.map(([d]) => day(d)).join(" · ") : s.scenario.name}
          prov={provOf(f)}
        />
      </section>

      <div className="grid grid-cols-[1.45fr_1fr] items-start gap-4">
        <div className="flex min-w-0 flex-col gap-4">
          <CashflowPanel s={s} compact />
          <Panel title="Agent activity" actions={<span>From the audit log</span>} bodyClassName="max-h-[320px] overflow-y-auto px-6 py-2">
            <ActivityFeed limit={25} refreshKey={tick} />
          </Panel>
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <ApprovalCard key={p?.id} s={s} p={p} onChange={refresh} />
          <OfferCard s={s} onChange={refresh} compact />
          <LimitsPanel s={s} onChange={refresh} />
          <ForecastPanel s={s} />
        </div>
      </div>
    </div>
  );
}
