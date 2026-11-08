"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AgentRun from "../AgentRun";
import {
  Badge,
  Button,
  Checkbox,
  Icon,
  KeyValue,
  Metric,
  Panel,
  cx,
  tooltipStyle,
} from "../ui";
import {
  api,
  decide,
  defaultInputs,
  latestProposal,
  message,
  money,
  stamp,
  statusLabel,
  type Analysis,
  type AnalysisInputs,
  type AppState,
  type Dataset,
  type Proposal,
} from "../../lib/api";
import { NumberField } from "./IdentitySteps";
import { ErrorNotice, StepFooter } from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };
export function AnalysisControls({
  state,
  refresh,
  onResult,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
  onResult?: (a: Analysis) => void;
}) {
  const [inputs, setInputs] = useState<AnalysisInputs>(
    state.analysis?.payload.inputs || defaultInputs(),
  );
  const [current, setCurrent] = useState<Analysis | null>(state.analysis),
    [runId, setRunId] = useState<string | null>(
      state.analysis?.state === "running" ? state.analysis.id : null,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (!runId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const a = await api<Analysis>(`/analyses/${runId}`);
        if (stopped) return;
        setCurrent(a);
        if (a.state !== "running") {
          setRunId(null);
          setBusy(false);
          await refresh();
          onResult?.(a);
        } else timer = setTimeout(poll, 600);
      } catch (e) {
        if (!stopped) {
          setError(message(e));
          timer = setTimeout(poll, 2000);
        }
      }
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [runId, refresh, onResult]);
  const run = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api<{ id: string }>("/analyses", "POST", inputs);
      setRunId(r.id);
      setCurrent({
        id: r.id,
        state: "running",
        created_at: new Date().toISOString(),
        events: [],
        payload: {
          inputs,
          execution_mode: state.execution_mode,
          model_note: state.model_note,
        },
      });
    } catch (e) {
      setBusy(false);
      setError(message(e));
    }
  };
  const numeric = (key: keyof AnalysisInputs) => (value: number) =>
    setInputs({ ...inputs, [key]: value });
  const disabled = busy || !!runId || state.analysis?.state === "running";
  return (
    <>
      {error && <ErrorNotice text={error} />}
      <Panel
        title="Weather scenario"
        actions={
          <>
            <Button
              size="sm"
              onClick={() =>
                setInputs({
                  ...inputs,
                  weather_mode: "manual",
                  temp_max_c: 15,
                  rain_mm: 14,
                })
              }
            >
              Rain scenario
            </Button>
            <Button
              size="sm"
              onClick={() =>
                setInputs({
                  ...inputs,
                  weather_mode: "manual",
                  temp_max_c: 4,
                  rain_mm: 0,
                })
              }
            >
              Cold scenario
            </Button>
            <Badge>Revenue estimate · paper only</Badge>
          </>
        }
      >
        <div className="grid grid-cols-3 gap-x-5 gap-y-4">
          <label className="block">
            <span className="text-[12px] text-fg-2">Exposure date</span>
            <input
              aria-label="Exposure date"
              type="date"
              value={inputs.target_date}
              onChange={(e) =>
                setInputs({ ...inputs, target_date: e.target.value })
              }
              className="mt-1.5 h-9 w-full rounded border border-line-strong bg-surface-2 px-3 font-mono text-[13px]"
            />
          </label>
          <Select
            label="Weather input"
            value={inputs.weather_mode}
            onChange={(v) =>
              setInputs({
                ...inputs,
                weather_mode: v as AnalysisInputs["weather_mode"],
              })
            }
            options={[
              ["manual", "Manual scenario"],
              ["forecast", "Current forecast"],
            ]}
          />
          <Select
            label="Market evidence"
            value={inputs.market_mode}
            onChange={(v) =>
              setInputs({
                ...inputs,
                market_mode: v as AnalysisInputs["market_mode"],
              })
            }
            options={[
              ["live", "Live discovery (bounded)"],
              ["cached", "Cached catalogue · inspect only"],
              ["test_suitable", "Synthetic test · suitable contract"],
              ["test_no_match", "Synthetic test · no suitable hedge"],
            ]}
          />
          <NumberField
            label="Budget (GBP)"
            value={inputs.budget_gbp}
            min={0.01}
            max={1000}
            step="0.01"
            onChange={numeric("budget_gbp")}
          />
          <Select
            label="Revenue model"
            value={inputs.model_mode || "auto"}
            onChange={(v) =>
              setInputs({
                ...inputs,
                model_mode: v as AnalysisInputs["model_mode"],
              })
            }
            options={[
              [
                "auto",
                state.dataset?.origin === "synthetic_sample"
                  ? "Sample model / evaluated sample"
                  : "Evaluated business model",
              ],
              ["synthetic_demo", "Synthetic demonstration · London only"],
            ]}
          />
          {inputs.weather_mode === "manual" && (
            <>
              <NumberField
                label="Maximum temperature (°C)"
                value={inputs.temp_max_c}
                min={-30}
                max={55}
                step="0.1"
                onChange={numeric("temp_max_c")}
              />
              <NumberField
                label="Daily rain (mm)"
                value={inputs.rain_mm}
                min={0}
                max={300}
                step="0.1"
                onChange={numeric("rain_mm")}
              />
              <NumberField
                label="Maximum wind (km/h)"
                value={inputs.wind_max_kmh}
                min={0}
                max={200}
                step="0.1"
                onChange={numeric("wind_max_kmh")}
              />
              <NumberField
                label="Sunshine (hours)"
                value={inputs.sunshine_hours}
                min={0}
                max={24}
                step="0.1"
                onChange={numeric("sunshine_hours")}
              />
            </>
          )}
        </div>
        <p className="mt-4 text-[12px] leading-5 text-fg-2">
          {state.model_note}
        </p>
        {inputs.market_mode.startsWith("test_") && (
          <p className="mt-2 text-[12px] text-warning">
            Synthetic test market and order book. No exchange listing or actual
            settlement. Test paper records stay labelled in your local history.
          </p>
        )}
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[12px] text-fg-3">
            {state.profile?.location_name} ·{" "}
            {state.dataset?.origin || "No sales selected"}
          </span>
          <Button variant="primary" onClick={run} disabled={disabled}>
            {disabled ? "Analysing…" : "Run weather analysis"}
          </Button>
        </div>
      </Panel>
      {current && (
        <div className="mt-4">
          <AgentRun analysis={current} />
          {current.payload.error && (
            <ErrorNotice text={current.payload.error} />
          )}
        </div>
      )}
    </>
  );
}
export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[][];
}) {
  return (
    <label className="block">
      <span className="text-[12px] text-fg-2">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 h-9 w-full rounded border border-line-strong bg-surface-2 px-2 text-[12.5px]"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
export function AnalysisStep({
  state,
  refresh,
  onNext,
  onBack,
}: Nav & { state: AppState; refresh: () => Promise<unknown> }) {
  return (
    <div>
      <AnalysisControls state={state} refresh={refresh} />
      {state.analysis && (
        <Panel className="mt-4" title="Risk assessment" bodyClassName="p-0">
          <RiskTable state={state} />
        </Panel>
      )}
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        disabled={!state.analysis || state.analysis.state === "running"}
        nextLabel="See the impact"
      />
    </div>
  );
}
export function RiskTable({ state }: { state: AppState }) {
  const c = state.analysis?.payload.comparison;
  const businessModelUsed =
    c?.scenario_prediction.model_version.startsWith("business_model_");
  return (
    <table className="w-full text-left">
      <thead>
        <tr className="border-b border-line text-[11px] uppercase tracking-[.04em] text-fg-3">
          <th className="px-4 py-2 font-medium">Risk</th>
          <th className="px-4 py-2 font-medium">Conditional downside</th>
          <th className="px-4 py-2 font-medium">Evidence</th>
          <th className="px-4 py-2 font-medium">Model fit</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {[
          {
            name: "Weather",
            driver: "Selected daily scenario",
            value: c ? money(c.estimated_downside_loss_gbp) : "Unavailable",
            evidence: state.model_note,
            fit: c ? c.scenario_prediction.model_version : "Not assessed",
          },
          {
            name: "Sports",
            driver: "Not supported",
            value: "Unavailable",
            evidence: "No sports exposure data or model is implemented.",
            fit: "Unavailable",
          },
          {
            name: "Beer duty",
            driver: "Not supported",
            value: "Unavailable",
            evidence: "No duty exposure data or model is implemented.",
            fit: "Unavailable",
          },
        ].map((r) => (
          <tr key={r.name} className="align-top">
            <td className="w-[180px] px-4 py-3">
              <div className="text-[13px] font-medium">{r.name}</div>
              <div className="mt-0.5 text-[12px] text-fg-3">{r.driver}</div>
            </td>
            <td className="w-[140px] px-4 py-3 font-mono text-[13px] text-negative">
              {r.value}
            </td>
            <td className="px-4 py-3 text-[12.5px] leading-5 text-fg-2">
              {r.evidence}
            </td>
            <td className="w-[160px] px-4 py-3 text-[12px] text-fg-2">
              {r.fit}
              {r.name === "Weather" && (
                <div className="mt-1">
                  <Badge tone={businessModelUsed ? "positive" : "warning"}>
                    {businessModelUsed
                      ? state.business_model?.origin === "synthetic_sample"
                        ? "Evaluated synthetic sample"
                        : "Evaluated on selected records"
                      : c
                        ? "Synthetic model"
                        : "Not assessed"}
                  </Badge>
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
export function RevenueChart({ dataset }: { dataset: Dataset | null }) {
  if (!dataset)
    return (
      <Empty text="Select sales data to see recorded monthly revenue. No cashflow or margin history is available." />
    );
  return (
    <div className="h-[232px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={dataset.monthly}
          margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
        >
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="month"
            tickLine={false}
            axisLine={false}
            minTickGap={30}
          />
          <YAxis
            width={76}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `£${Math.round(Number(v) / 1000)}k`}
          />
          <Tooltip
            {...tooltipStyle}
            formatter={(v) => [money(Number(v)), "Recorded revenue"]}
          />
          <Line
            type="monotone"
            dataKey="revenue_gbp"
            stroke="var(--fg-3)"
            strokeWidth={1.5}
            dot={false}
            animationDuration={900}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function ImpactStep({
  state,
  onNext,
  onBack,
}: Nav & { state: AppState }) {
  const c = state.analysis?.payload.comparison;
  return (
    <div>
      <div className="mb-6 text-center">
        <p className="text-[36px] font-medium leading-[1.15] tracking-[-.02em] text-fg">
          {c ? (
            <>
              Conditional downside{" "}
              <span className="font-mono text-negative">
                {money(c.estimated_downside_loss_gbp)}
              </span>
            </>
          ) : (
            "No supported exposure estimate"
          )}
        </p>
        <p className="mt-2 text-[13px] text-fg-2">
          {c
            ? "Selected weather versus the training-derived seasonal dry reference. No historical savings claim."
            : statusLabel(state.analysis?.payload.status)}
        </p>
      </div>
      <div className="grid grid-cols-[1fr_240px] gap-4">
        <Panel
          title="Recorded monthly revenue"
          actions={
            <Badge>
              {state.dataset?.origin === "synthetic_sample"
                ? "Synthetic sales"
                : "Imported records"}
            </Badge>
          }
        >
          <RevenueChart dataset={state.dataset} />
          <p className="mt-3 text-[12px] text-fg-3">{state.dataset?.note}</p>
        </Panel>
        <div className="flex flex-col gap-4">
          <Panel className="flex-1">
            <Metric
              label="Selected weather revenue"
              value={
                c ? money(c.scenario_predicted_revenue_gbp) : "Unavailable"
              }
              sub={state.analysis?.payload.model_note || state.model_note}
            />
          </Panel>
          <Panel className="flex-1">
            <Metric
              label="Reference weather revenue"
              value={
                c ? money(c.reference_predicted_revenue_gbp) : "Unavailable"
              }
              sub="Same business inputs and calendar date"
            />
          </Panel>
          <Panel>
            <Metric
              label="Profit / cashflow"
              value="Unavailable"
              sub="Costs, margins and payment timing are not modelled"
            />
          </Panel>
        </div>
      </div>
      <Panel className="mt-4" title="Assumptions and limits">
        <p className="text-[12.5px] leading-5 text-fg-2">{state.model_note}</p>
        {c && (
          <ul className="mt-3 space-y-2 text-[12px] text-fg-2">
            {c.assumptions.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}
      </Panel>
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextLabel="See recommendations"
      />
    </div>
  );
}
export function Empty({ text }: { text: string }) {
  return (
    <div className="flex min-h-[130px] items-center justify-center p-5 text-center text-[12.5px] leading-6 text-fg-3">
      {text}
    </div>
  );
}
export function ProposalDetail({ proposal: p }: { proposal: Proposal }) {
  const c = p.calculation;
  return (
    <motion.div
      key={p.proposal_id}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
    >
      <Panel
        title={p.market_question || statusLabel(p.status)}
        actions={
          <Badge tone={p.expired ? "warning" : "accent"}>
            {p.expired ? "Expired" : p.data_origin || "Assessment"}
          </Badge>
        }
      >
        <p className="text-[13px] leading-5">{p.explanation}</p>
        {p.model_note && (
          <p className="mt-3 text-[12px] leading-5 text-fg-2">{p.model_note}</p>
        )}
        {p.contract_spec && (
          <KeyValue
            className="mt-4"
            rows={[
              {
                label: "Resolution station",
                value: `${p.contract_spec.station_name} (${p.contract_spec.station}) · ${p.contract_spec.station_distance_km.toFixed(1)}km from business`,
              },
              {
                label: "Observation day / timezone",
                value: `${p.contract_spec.date} · ${p.contract_spec.timezone}`,
              },
              {
                label: "Contract measurement",
                value: `${p.contract_spec.metric} · ${p.contract_spec.unit} · lower ${p.contract_spec.lower ?? "unbounded"} / upper ${p.contract_spec.upper ?? "unbounded"}`,
              },
              { label: "Rounding rule", value: p.contract_spec.rounding },
              {
                label: "Resolution source",
                value: (
                  <a
                    className="break-all text-accent underline"
                    href={p.contract_spec.source}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Official observation source
                  </a>
                ),
              },
              {
                label: "Original contract",
                value: p.source_url ? (
                  <a
                    className="text-accent underline"
                    href={p.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Read market rules
                  </a>
                ) : (
                  "Synthetic fixture"
                ),
              },
            ]}
          />
        )}
        {c && (
          <>
            <div className="mt-4 grid grid-cols-4 gap-px overflow-hidden rounded border border-line bg-line">
              {[
                { l: "Paper cost", v: money(c.total_entry_cost_gbp) },
                {
                  l: "If contract pays",
                  v: money(c.payout_if_win_gbp),
                  c: "text-positive",
                },
                {
                  l: "Max loss",
                  v: money(c.total_entry_cost_gbp),
                  c: "text-negative",
                },
                { l: "Expected value", v: "Unavailable" },
              ].map((m) => (
                <div key={m.l} className="bg-surface-2 px-3 py-2">
                  <div className="text-[11.5px] text-fg-3">{m.l}</div>
                  <div className={cx("font-mono text-[14px]", m.c)}>{m.v}</div>
                </div>
              ))}
            </div>
            <h3 className="mt-5 text-[12px] font-medium text-fg-2">
              How it was calculated
            </h3>
            <KeyValue
              className="mt-2"
              rows={[
                {
                  label: "Selected outcome",
                  value: p.outcome_selected || "Not applicable",
                },
                {
                  label: "Metric-specific conditional downside",
                  value: money(c.estimated_unhedged_downside_gbp),
                },
                {
                  label: "Quantity / average ask",
                  value: `${c.executable_contracts} shares / $${c.average_ask_price_usd.toFixed(4)}`,
                  mono: true,
                },
                {
                  label: "Fixed simulation FX",
                  value: `£1 = $${c.fx_rate_usd_per_gbp} · ${c.fx_rate_source}`,
                },
                {
                  label: "Fee assumption",
                  value: `${c.fee_bps} bps (${(c.fee_bps / 100).toFixed(2)}%)`,
                },
                { label: "Quote retrieved", value: stamp(p.quote_timestamp) },
                { label: "Approval expires", value: stamp(p.expires_at) },
                {
                  label: "Contract probability / EV",
                  value: "Unavailable; no validated exact-event probability",
                },
                { label: "Basis risk", value: c.basis_risk_summary },
              ]}
            />
          </>
        )}
        {Object.entries(p.rejection_reasons).length > 0 && (
          <div className="mt-4 space-y-3">
            {Object.entries(p.rejection_reasons).map(([id, reasons]) => (
              <div key={id}>
                <h3 className="break-all font-mono text-[11.5px] text-fg-2">
                  {id}
                </h3>
                <ul className="mt-1 space-y-1 text-[12px] leading-5 text-fg-3">
                  {reasons.map((r, i) => (
                    <li key={i}>• {r}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </motion.div>
  );
}
export function RecommendationsStep({
  state,
  selected,
  setSelected,
  onNext,
  onBack,
}: Nav & {
  state: AppState;
  selected: boolean;
  setSelected: (v: boolean) => void;
}) {
  const p = latestProposal(state);
  const eligible =
    p?.status === "recommend_paper_hedge" &&
    !p.expired &&
    p.approval_state === "pending_human_approval";
  return (
    <div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] items-start gap-4">
        <Panel title="Recommended" bodyClassName="p-0">
          {p && eligible ? (
            <div className="flex items-start gap-3 bg-surface-3 px-4 py-3">
              <div className="pt-0.5">
                <Checkbox
                  checked={selected}
                  onChange={setSelected}
                  ariaLabel="Select rainfall paper scenario"
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-medium">
                  {p.contract_spec?.metric === "daily_max_temperature"
                    ? "Temperature paper proposal"
                    : "Rainfall paper scenario"}
                </div>
                <div className="mt-0.5 text-[12px] leading-4 text-fg-3">
                  {p.market_question}
                </div>
              </div>
              <div className="text-right font-mono text-[12.5px]">
                <div>{money(p.max_total_cost_gbp)}</div>
                <div className="text-[11.5px] text-positive">
                  if pays {money(p.calculation?.payout_if_win_gbp || 0)}
                </div>
              </div>
            </div>
          ) : (
            <Empty
              text={
                p
                  ? `${statusLabel(p.status)}${p.expired ? " · proposal expired; run analysis again" : ""}. You can finish without selecting a hedge.`
                  : "No completed proposal. You can finish setup without a hedge."
              }
            />
          )}
          <div className="flex items-center justify-between border-t border-line px-4 py-3 font-mono text-[12px] text-fg-2">
            <span>{eligible && selected ? 1 : 0} selected</span>
            <span>
              max loss {money(eligible && selected ? p.max_total_cost_gbp : 0)}
            </span>
          </div>
        </Panel>
        {p ? (
          <ProposalDetail proposal={p} />
        ) : (
          <Panel title="Assessment unavailable">
            <Empty text="Run weather analysis to get a recommendation or an explained rejection." />
          </Panel>
        )}
      </div>
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextLabel={eligible && selected ? "Review" : "Continue without a hedge"}
      />
    </div>
  );
}
export function ReviewStep({
  state,
  selected,
  refresh,
  onFinish,
  busy,
  onBack,
}: Nav & {
  state: AppState;
  selected: boolean;
  refresh: () => Promise<unknown>;
  onFinish: () => void;
  busy: boolean;
}) {
  const p = latestProposal(state),
    eligible =
      !!p &&
      selected &&
      p.status === "recommend_paper_hedge" &&
      p.approval_state === "pending_human_approval" &&
      !p.expired;
  const [ack, setAck] = useState(false),
    [sending, setSending] = useState(false),
    [error, setError] = useState("");
  const act = async (approve: boolean) => {
    if (!p) return;
    setSending(true);
    setError("");
    try {
      await decide(p, approve);
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setSending(false);
    }
  };
  return (
    <div>
      {error && <ErrorNotice text={error} />}
      <Panel
        title="Paper approval"
        actions={
          <Badge
            tone={p?.approval_state === "approved" ? "positive" : "neutral"}
          >
            {p?.approval_state === "approved"
              ? "Approved · recorded as paper"
              : p?.approval_state === "rejected"
                ? "Rejected"
                : eligible
                  ? "Proposed"
                  : "No selected proposal"}
          </Badge>
        }
      >
        {eligible && p ? (
          <>
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-[13px]">{p.market_question}</p>
                <p className="mt-1 text-[12px] text-fg-3">
                  {p.paper_quantity} {p.outcome_selected || "Yes"} shares ·{" "}
                  {p.data_origin} · {p.target_date}
                </p>
              </div>
              <div className="font-mono">{money(p.max_total_cost_gbp)}</div>
            </div>
            <KeyValue
              className="mt-4"
              rows={[
                {
                  label: "Weekly cost including reservations",
                  value: `${money(state.summary.weekly_reserved_gbp)} of ${money(state.settings.weekly_spend_gbp)}`,
                },
                {
                  label: "Worst-case loss including reservations",
                  value: `${money(state.summary.monthly_reserved_loss_gbp)} of ${money(state.settings.monthly_loss_gbp)}`,
                },
                {
                  label: "Quote / expiry",
                  value: `${stamp(p.quote_timestamp)} / ${stamp(p.expires_at)}`,
                },
              ]}
            />
            <div className="mt-5">
              <Checkbox
                checked={ack}
                onChange={setAck}
                label={
                  <span className="text-fg-2">
                    I approve this simulated paper position and understand the
                    maximum loss of {money(p.max_total_cost_gbp)}. Payout is
                    hypothetical; no money moves.
                  </span>
                }
              />
            </div>
            <div className="mt-5 flex gap-2">
              <Button
                variant="primary"
                onClick={() => act(true)}
                disabled={!ack || sending}
              >
                {sending ? "Recording…" : "Approve and record paper position"}
              </Button>
              <Button onClick={() => act(false)} disabled={sending}>
                Reject proposal
              </Button>
            </div>
          </>
        ) : (
          <Empty
            text={
              p?.approval_state === "approved"
                ? `${state.profile?.pubName}: paper position saved in the local database. No exchange order was submitted.`
                : p?.approval_state === "rejected"
                  ? "Your rejection was saved. You can open the dashboard without a position."
                  : "No paper position will be recorded. You can complete setup and open the dashboard."
            }
          />
        )}
      </Panel>
      <Panel className="mt-4" title="What happens next">
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded border border-line bg-line">
          {[
            {
              i: "activity" as const,
              t: "Persistent history",
              d: "Profiles, runs and human decisions are saved",
            },
            {
              i: "shield" as const,
              t: "Human approval for every position",
              d: "No automatic execution or real funds",
            },
            {
              i: "calendar" as const,
              t: "Manual refresh",
              d: "No background monitoring or scheduled alerts",
            },
          ].map((x) => (
            <div key={x.t} className="flex gap-3 bg-surface-2 px-4 py-3">
              <Icon name={x.i} className="mt-0.5 shrink-0 text-fg-3" />
              <div>
                <div className="text-[13px]">{x.t}</div>
                <div className="text-[12px] text-fg-3">{x.d}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <StepFooter
        onBack={onBack}
        onNext={onFinish}
        disabled={busy || sending}
        nextLabel={busy ? "Saving setup…" : "Open dashboard"}
        hint={
          eligible
            ? "Unapproved proposals remain pending until expiry."
            : undefined
        }
      />
    </div>
  );
}
