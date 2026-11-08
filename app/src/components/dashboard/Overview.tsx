"use client";
import { useState } from "react";
import { Badge, Button, Icon, KeyValue, Metric, Panel } from "../ui";
import { Feed, Td, Th } from "./Shell";
import {
  decide,
  latestProposal,
  message,
  money,
  pending,
  stamp,
  statusLabel,
  type AppState,
  type Position,
  type Proposal,
} from "../../lib/api";
import {
  AnalysisControls,
  Empty,
  ProposalDetail,
  RevenueChart,
} from "../onboarding/PlanSteps";
import { ErrorNotice } from "../onboarding/Onboarding";
import OperatingProfitPanel from "../OperatingProfitPanel";

function KpiStrip({ children }: { children: React.ReactNode }) {
  return (
    <section className="grid grid-cols-4 divide-x divide-line rounded-md border border-line bg-surface">
      {children}
    </section>
  );
}
function Kpi(props: React.ComponentProps<typeof Metric>) {
  return (
    <div className="px-4 py-3">
      <Metric {...props} />
    </div>
  );
}
export function PositionsTable({ positions }: { positions: Position[] }) {
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-line bg-surface-2">
            <tr>
              <Th>Position</Th>
              <Th>Origin</Th>
              <Th right>Paper cost</Th>
              <Th right>Paper payout</Th>
              <Th>Status</Th>
              <Th>Exposure date</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {positions.map((p) => (
              <tr key={p.position_id}>
                <Td className="max-w-[300px] text-fg">
                  {p.market_question}
                  <span className="mt-0.5 block text-[11px] text-fg-3">
                    {p.business_name}
                  </span>
                </Td>
                <Td className="text-fg-2">
                  {p.data_origin === "synthetic_test_fixture"
                    ? "Synthetic test"
                    : "Live quote · paper"}
                </Td>
                <Td right mono>
                  {money(p.total_entry_cost_gbp)}
                </Td>
                <Td right mono>
                  {money(
                    p.resolution?.payout_gbp ??
                      p.hypothetical_payout_if_win_gbp,
                  )}
                  <span className="block text-[10px] text-fg-3">
                    {p.resolution ? "Recorded outcome" : "If contract pays"}
                  </span>
                </Td>
                <Td>
                  <Badge tone="accent" dot>
                    {["Yes", "No", "INVALID"].includes(
                      p.actual_resolved_outcome,
                    )
                      ? "Resolved · paper"
                      : "Unresolved · paper"}
                  </Badge>
                </Td>
                <Td mono className="text-fg-2">
                  {p.target_date}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!positions.length && (
        <Empty text="No paper positions recorded. Approve a suitable proposal to add one. Finishing setup does not require a hedge." />
      )}
    </>
  );
}
export function ApprovalCard({
  proposal: p,
  refresh,
}: {
  proposal: Proposal;
  refresh: () => Promise<unknown>;
}) {
  const [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const act = async (approve: boolean) => {
    setBusy(true);
    setError("");
    try {
      await decide(p, approve);
      await refresh();
    } catch (e) {
      setError(message(e));
      await refresh();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div>
      {error && <ErrorNotice text={error} />}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[13px] font-medium">{p.market_question}</div>
          <div className="mt-0.5 font-mono text-[11.5px] text-fg-3">
            {p.data_origin} · {p.target_date}
          </div>
        </div>
        <div className="text-right font-mono text-[12.5px]">
          <div>{money(p.max_total_cost_gbp)}</div>
          <div className="text-[11.5px] text-fg-3">
            if pays {money(p.calculation?.payout_if_win_gbp || 0)}
          </div>
        </div>
      </div>
      <p className="mt-2.5 text-[12.5px] leading-5 text-fg-2">
        {p.explanation}
      </p>
      <p className="mt-2 font-mono text-[11px] text-fg-3">
        {p.paper_quantity} {p.outcome_selected || "Yes"} shares · quote{" "}
        {stamp(p.quote_timestamp)} · expires {stamp(p.expires_at)}
      </p>
      <p className="mt-2 text-[12px] text-fg-3">
        Simulated fill at the quote shown above. Live price changes do not
        change this paper approval.
      </p>
      <label className="mt-3 flex items-start gap-2 text-[12px] leading-5 text-fg-2">
        <input
          type="checkbox"
          checked={ack}
          onChange={(e) => setAck(e.target.checked)}
        />
        I approve the paper cost and maximum loss of{" "}
        {money(p.max_total_cost_gbp)}. The payout is hypothetical; no real money
        moves.
      </label>
      <div className="mt-3 flex items-center gap-2">
        <Button
          variant="primary"
          onClick={() => act(true)}
          disabled={!ack || busy}
        >
          {busy ? "Recording…" : `Approve ${money(p.max_total_cost_gbp)} paper`}
        </Button>
        <Button onClick={() => act(false)} disabled={busy}>
          Reject
        </Button>
      </div>
    </div>
  );
}
export function TodayView({
  state,
  refresh,
  onAnalyse,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
  onAnalyse: () => void;
}) {
  const [weatherBusy, setWeatherBusy] = useState(false),
    [error, setError] = useState("");
  const proposals = pending(state),
    forecast = state.forecast;
  const refreshWeather = async () => {
    setWeatherBusy(true);
    setError("");
    try {
      const { api } = await import("../../lib/api");
      await api("/weather/refresh", "POST");
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setWeatherBusy(false);
    }
  };
  const rows = state.activity.slice(0, 6).map((e) => ({
    time: new Date(e.logged_at).toLocaleTimeString("en-GB", {
      timeZone: "Europe/London",
      hour: "2-digit",
      minute: "2-digit",
    }),
    text: activityText(e),
    tone: e.event_type === "paper_position_recorded" ? "positive" : undefined,
  }));
  return (
    <div className="flex min-h-full flex-col gap-3">
      {error && <ErrorNotice text={error} />}
      <KpiStrip>
        <Kpi
          label="Open paper positions"
          value={state.summary.open_positions}
          sub={`${money(state.summary.total_entry_cost_gbp)} recorded cost`}
        />
        <Kpi
          label="Worst-case loss + pending"
          value={money(state.summary.monthly_reserved_loss_gbp)}
          sub={`of ${money(state.settings.monthly_loss_gbp)} monthly limit`}
        />
        <Kpi
          label="Hypothetical payout"
          value={money(state.summary.hypothetical_payout_gbp)}
          tone="positive"
          sub="If every open contract pays; not settled"
        />
        <Kpi
          label="Latest assessment"
          value={statusLabel(state.analysis?.payload.status)}
          sub={
            state.analysis
              ? stamp(state.analysis.created_at)
              : "Run a weather scenario"
          }
          tone="warning"
        />
      </KpiStrip>
      <Panel
        title="Next 14 days"
        actions={
          <>
            <span className="font-mono text-[11.5px] text-fg-3">
              {forecast?.source || "Open-Meteo"} ·{" "}
              {forecast?.origin || "Not retrieved"}
            </span>
            <Button
              size="sm"
              onClick={refreshWeather}
              disabled={weatherBusy || !state.profile}
            >
              {weatherBusy ? "Retrieving…" : "Refresh forecast"}
            </Button>
          </>
        }
        bodyClassName="p-3"
      >
        {forecast?.days.length ? (
          <>
            <div
              className="grid gap-1.5"
              style={{
                gridTemplateColumns: `repeat(${forecast.days.length},minmax(0,1fr))`,
              }}
            >
              {forecast.days.map((d) => (
                <div
                  key={d.date}
                  className="rounded border border-line bg-surface-2 px-2 py-2"
                >
                  <div className="flex items-baseline justify-between font-mono text-[11px]">
                    <span className="text-fg-3">
                      {new Date(d.date + "T12:00:00").toLocaleDateString(
                        "en-GB",
                        { weekday: "short" },
                      )}
                    </span>
                    <span className="text-fg">{d.date.slice(8)}</span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-1 font-mono text-[12px] text-fg-2">
                    <Icon name="rain" size={13} className="text-fg-3" />
                    {d.rain_mm}mm
                  </div>
                  <div className="mt-1 h-4 truncate text-[10.5px] text-fg-3">
                    {d.temp_max_c}°C max
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-fg-3">
              Retrieved {stamp(forecast.retrieved_at)} · horizon{" "}
              {forecast.horizon_start}–{forecast.horizon_end} · {forecast.note}
            </p>
          </>
        ) : (
          <Empty
            text={
              forecast?.note ||
              "No forecast retrieved. Refresh for the configured coordinates, or analyse an explicit manual scenario."
            }
          />
        )}
      </Panel>
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] gap-3">
        <div className="flex min-h-0 min-w-0 flex-col gap-3">
          <Panel
            title="Recorded monthly revenue"
            actions={
              <Badge>
                {state.dataset?.origin === "synthetic_sample"
                  ? "Synthetic sample"
                  : state.dataset
                    ? "User import"
                    : "No sales selected"}
              </Badge>
            }
            className="flex min-h-0 flex-1 flex-col"
            bodyClassName="min-h-0 flex-1"
          >
            <RevenueChart dataset={state.dataset} />
            <p className="mt-2 text-[11.5px] text-fg-3">
              Recorded sales revenue. The operating-profit card applies editable
              demo costs to the selected weather scenario.
            </p>
          </Panel>
          <Panel title="Paper positions" bodyClassName="p-0">
            <PositionsTable positions={state.positions} />
          </Panel>
        </div>
        <div className="flex min-h-0 min-w-0 flex-col gap-3">
          <Panel
            title="Needs approval"
            actions={
              proposals.length ? (
                <Badge tone="warning" dot>
                  {proposals.length} pending
                </Badge>
              ) : undefined
            }
          >
            {proposals[0] ? (
              <ApprovalCard
                key={proposals[0].proposal_id}
                proposal={proposals[0]}
                refresh={refresh}
              />
            ) : (
              <>
                <Empty
                  text={
                    (latestProposal(state)?.approval_state === "approved"
                      ? "No pending approvals. The latest proposal was approved and recorded as a paper position."
                      : latestProposal(state)?.approval_state === "rejected"
                        ? "No pending approvals. The latest proposal was rejected by the operator."
                        : latestProposal(state)?.expired
                          ? "The latest proposal expired or its inputs changed. Run a new assessment before approval."
                          : latestProposal(state)?.explanation) ||
                    "No pending proposal. A suitable paper recommendation or an explained rejection will appear after analysis."
                  }
                />
                <Button onClick={onAnalyse}>Run another assessment</Button>
              </>
            )}
          </Panel>
          <OperatingProfitPanel state={state} refresh={refresh} />
          <Panel
            title="Recent activity"
            actions={
              <span className="font-mono text-[11.5px] text-fg-3">
                Local audit log
              </span>
            }
          >
            <Feed rows={rows} />
            {!rows.length && (
              <Empty text="No application events recorded yet." />
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
export function ScenarioView({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const p = latestProposal(state);
  return (
    <div className="mx-auto max-w-[1100px] space-y-4">
      <AnalysisControls state={state} refresh={refresh} />
      <OperatingProfitPanel state={state} refresh={refresh} />
      {p && <ProposalDetail proposal={p} />}
    </div>
  );
}
export function HistoryView({ state }: { state: AppState }) {
  return (
    <div className="grid grid-cols-[1.45fr_1fr] gap-3">
      <Panel title="Recorded revenue history">
        <RevenueChart dataset={state.dataset} />
        <p className="mt-3 text-[12px] text-fg-2">
          {state.dataset?.note || "No sales history selected."}
        </p>
      </Panel>
      <Panel title="Recorded paper performance">
        {state.summary.settled_payout_gbp === null ? (
          <Empty text="No finalized paper outcomes yet. Official resolution checks leave pending/disputed markets unresolved. No historical savings or cashflow are fabricated." />
        ) : (
          <KeyValue
            rows={[
              {
                label: "Resolved paper payout",
                value: money(state.summary.settled_payout_gbp),
              },
              {
                label: "Realized paper P&L",
                value: money(state.summary.realized_paper_pnl_gbp || 0),
              },
              {
                label: "Basis",
                value:
                  "Official payout vectors, recorded entry costs and fixed entry-time simulation FX. No real money paid.",
              },
            ]}
          />
        )}
      </Panel>
      <Panel
        title="All recorded paper positions"
        className="col-span-2"
        bodyClassName="p-0"
      >
        <PositionsTable positions={state.positions} />
      </Panel>
    </div>
  );
}
export function activityText(event: AppState["activity"][number]) {
  const d = event.details;
  const labels: Record<string, string> = {
    profile_saved: `Business details saved: ${d.name || ""} (self-reported).`,
    dependent_results_invalidated: String(
      d.reason || "Dependent results invalidated.",
    ),
    sales_data_selected: `Sales selected: ${d.filename || ""} · ${d.origin || ""} · ${d.row_count || 0} daily records.`,
    analysis_started: `Analysis started: ${d.analysis_id || ""}.`,
    analysis_completed: `Assessment saved: ${statusLabel(String(d.status))}.`,
    analysis_failed: `Analysis failed: ${d.error || "required data unavailable"}.`,
    paper_position_recorded: `Human approval recorded a paper position (${money(Number(d.cost_gbp || 0))}). No exchange order or payment.`,
    proposal_rejected_by_human: "Proposal rejected by human operator.",
    forecast_retrieved: `Forecast retrieval: ${d.origin || "unavailable"} · ${d.source || ""}.`,
    settings_saved: "Risk limits and simulation assumptions saved.",
    operating_cost_assumptions_saved: `Demo operating costs saved: ${money(Number(d.fixed_daily_cost_gbp || 0))} fixed per day + ${d.variable_cost_pct || 0}% of revenue.`,
    setup_completed: "Setup completed. A hedge is optional.",
    settlement_refresh_checked: String(d.result || "Settlement checked."),
    provider_demo_connected: `${d.provider || "Provider"} connection animation completed (visual placeholder; no records imported).`,
    model_training_started:
      "Training selected sales against historical weather with chronological splits.",
    model_training_completed: `Model evaluation completed: ${d.holdout_pass ? "holdout passed" : "model not activated"} · MAE ${money(Number(d.test_mae_gbp || 0))}.`,
    model_training_failed: String(d.error || "Business model training failed."),
    paper_position_resolved: `Official paper outcome recorded: payout ${money(Number(d.paper_payout_gbp || 0))}, net ${money(Number(d.paper_net_pnl_gbp || 0))}. No money moved.`,
    monitor_check_completed: String(
      d.note || "Forecast monitor completed a check.",
    ),
  };
  return labels[event.event_type] || event.event_type.replaceAll("_", " ");
}
