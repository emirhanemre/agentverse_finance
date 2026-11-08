"use client";
import { useState } from "react";
import { Badge, Button, KeyValue, Panel } from "../ui";
import { Td, Th } from "./Shell";
import {
  api,
  message,
  money,
  stamp,
  type AppState,
  type Settings,
} from "../../lib/api";
import { DataSources, NumberField } from "../onboarding/IdentitySteps";
import { Empty, RiskTable } from "../onboarding/PlanSteps";
import { ErrorNotice } from "../onboarding/Onboarding";
import { PositionsTable, activityText } from "./Overview";
import Notifications from "../Notifications";
import MonitoringPanel from "../MonitoringPanel";

export function ProtectionsPage({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const [selected, setSelected] = useState(state.positions[0]?.position_id),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false);
  const p =
    state.positions.find((x) => x.position_id === selected) ||
    state.positions[0];
  const check = async () => {
    setBusy(true);
    try {
      const result = await api<{ note: string }>("/positions/refresh", "POST");
      setNote(result.note);
      await refresh();
    } catch (e) {
      setNote(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid h-full grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-3">
      <Panel
        title="Positions"
        bodyClassName="p-0"
        actions={
          <Button size="sm" disabled={busy} onClick={check}>
            {busy ? "Checking…" : "Check settlement"}
          </Button>
        }
      >
        <PositionsTable positions={state.positions} />
        {state.positions.length > 1 && (
          <div className="flex flex-wrap gap-2 p-4">
            {state.positions.map((x) => (
              <Button
                key={x.position_id}
                size="sm"
                onClick={() => setSelected(x.position_id)}
              >
                {x.target_date} · {money(x.total_entry_cost_gbp)}
              </Button>
            ))}
          </div>
        )}
        {note && <p className="p-4 text-[12px] text-fg-2">{note}</p>}
      </Panel>
      <Panel
        title={p ? "Paper position details" : "No position selected"}
        actions={
          p ? (
            <Badge tone="accent" dot>
              {p.resolution ? "Resolved · paper" : "Unresolved · paper"}
            </Badge>
          ) : undefined
        }
      >
        {p ? (
          <>
            <p className="text-[13px] leading-5 text-fg-2">
              {p.market_question}
            </p>
            <KeyValue
              className="mt-3"
              rows={[
                { label: "Paper position", value: p.position_id },
                { label: "Origin", value: p.data_origin },
                { label: "Approved", value: stamp(p.approved_at) },
                {
                  label: "Paper cost / hypothetical payout",
                  value: `${money(p.total_entry_cost_gbp)} / ${money(p.hypothetical_payout_if_win_gbp)}`,
                },
                {
                  label: "Quantity / average ask",
                  value: `${p.paper_quantity} / $${p.average_fill_price_usd.toFixed(4)}`,
                },
                {
                  label: "Actual settlement",
                  value: p.actual_resolved_outcome,
                },
                { label: "Settlement evidence", value: p.settlement_note },
                ...(p.resolution
                  ? [
                      {
                        label: "Recorded paper payout / net P&L",
                        value: `${money(p.resolution.payout_gbp)} / ${money(p.resolution.net_pnl_gbp)}`,
                      },
                      {
                        label: "Official resolution time",
                        value: stamp(p.resolution.resolved_at),
                      },
                      {
                        label: "Official resolution record",
                        value: (
                          <a
                            className="break-all text-accent underline"
                            href={p.resolution.evidence.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            View payout evidence
                          </a>
                        ),
                      },
                    ]
                  : []),
              ]}
            />
          </>
        ) : (
          <Empty text="Approved paper positions appear here. No orders have been submitted to an exchange." />
        )}
      </Panel>
    </div>
  );
}
export function RisksPage({ state }: { state: AppState }) {
  return (
    <div className="space-y-3">
      <Panel title="Risk assessments" bodyClassName="p-0">
        <RiskTable state={state} />
      </Panel>
      <Panel title="Model and evidence">
        <p className="text-[13px] leading-6 text-fg-2">{state.model_note}</p>
        <p className="mt-3 text-[12px] text-fg-3">
          Exact contract probabilities, expected values and numerical basis-risk
          scores are unavailable. Forecast precipitation probabilities do not
          establish the probability of a contract’s threshold, station and time
          window.
        </p>
      </Panel>
    </div>
  );
}
export function ActivityPage({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  return (
    <div className="space-y-3">
      <Notifications state={state} refresh={refresh} />
      <Panel
        title="Activity"
        actions={
          <span className="font-mono text-[11.5px] text-fg-3">
            Latest {state.activity.length} persisted events
          </span>
        }
        bodyClassName="p-0"
      >
        <table className="w-full">
          <thead className="border-b border-line bg-surface-2">
            <tr>
              <Th>Time (London)</Th>
              <Th>Event</Th>
              <Th>Record</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {state.activity.map((e) => (
              <tr key={e.id}>
                <Td mono className="whitespace-nowrap text-fg-3">
                  {stamp(e.logged_at)}
                </Td>
                <Td className="text-fg-2">{activityText(e)}</Td>
                <Td mono className="text-fg-3">
                  #{e.id}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
        {!state.activity.length && <Empty text="No activity recorded." />}
      </Panel>
    </div>
  );
}
export function SourcesPage({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  return (
    <div className="mx-auto max-w-[1000px]">
      <DataSources state={state} refresh={refresh} />
      <Panel className="mt-4" title="Weather and market evidence">
        <KeyValue
          rows={[
            {
              label: "Weather",
              value: state.forecast
                ? `${state.forecast.source} · ${state.forecast.origin} · ${stamp(state.forecast.retrieved_at)}`
                : "Not retrieved",
            },
            {
              label: "Market catalogue",
              value:
                state.analysis?.payload.discovery?.note ||
                "No catalogue inspected yet",
            },
            { label: "Revenue model", value: state.model_note },
          ]}
        />
      </Panel>
    </div>
  );
}
export function SettingsPage({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const [settings, setSettings] = useState<Settings>(state.settings),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false),
    [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/settings", "PUT", settings);
      await refresh();
      setSaved(true);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mx-auto max-w-[920px] space-y-4">
      {error && <ErrorNotice text={error} />}
      <Panel
        title="Business"
        actions={
          <a href="/" className="text-[12px] text-accent hover:underline">
            Edit business details
          </a>
        }
      >
        <KeyValue
          rows={[
            {
              label: "Business",
              value: state.profile?.pubName || "No profile",
            },
            { label: "Operator", value: state.profile?.owner },
            {
              label: "Location",
              value: `${state.profile?.postcode || ""} · ${state.profile?.location_name || ""}`,
            },
            {
              label: "Verification",
              value: "Self-reported; external checks unavailable",
            },
          ]}
        />
      </Panel>
      <Panel
        title="Risk limits and paper assumptions"
        actions={saved ? <Badge tone="positive">Saved</Badge> : undefined}
      >
        <div className="grid grid-cols-2 gap-4">
          {(
            [
              {
                k: "weekly_spend_gbp",
                l: "Weekly spending limit (GBP)",
                max: 10000,
                step: "0.01",
              },
              {
                k: "monthly_loss_gbp",
                l: "Monthly worst-case loss limit (GBP)",
                max: 10000,
                step: "0.01",
              },
              {
                k: "per_contract_gbp",
                l: "Per-contract concentration limit (GBP)",
                max: 1000,
                step: "0.01",
              },
              {
                k: "fx_usd_per_gbp",
                l: "Fixed simulation USD per GBP",
                max: 2.9999,
                step: "0.0001",
              },
              {
                k: "fee_bps",
                l: "Simulation fee (basis points)",
                max: 1000,
                step: "1",
              },
              {
                k: "max_station_distance_km",
                l: "Maximum station distance (km)",
                max: 100,
                step: "1",
              },
            ] as const
          ).map((f) => (
            <NumberField
              key={f.k}
              label={f.l}
              value={settings[f.k]}
              min={f.k === "fee_bps" ? 0 : 0.01}
              max={f.max}
              step={f.step}
              onChange={(v) => {
                setSettings({ ...settings, [f.k]: v });
                setSaved(false);
              }}
            />
          ))}
        </div>
        <p className="mt-4 text-[12px] leading-5 text-fg-2">
          Weekly spend is entry cost approved since Monday 00:00 London plus
          pending reservations. The monthly loss allowance includes
          current-month entry costs, earlier unresolved entry costs, and pending
          reservations. Hypothetical payouts never credit these limits. Pending
          proposals expire after 15 minutes. Per-contract concentration includes
          existing unresolved positions and pending proposals. Changing settings
          invalidates pending proposals and analysis.
        </p>
        <div className="mt-4 flex justify-end">
          <Button variant="primary" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save settings"}
          </Button>
        </div>
      </Panel>
      <MonitoringPanel
        state={state}
        settings={settings}
        onChange={setSettings}
        onSave={save}
        saving={busy}
        refresh={refresh}
      />
      <Panel title="Execution">
        <KeyValue
          rows={[
            {
              label: "Trading",
              value: "Paper simulation only; human approval for every position",
            },
            { label: "Analysis mode", value: state.execution_mode },
            { label: "LLM", value: "Not used by the primary application" },
            {
              label: "Monitoring / alerts",
              value: state.settings.monitor_enabled
                ? `Enabled while API runs · every ${state.settings.monitor_interval_minutes} min · in-app alerts`
                : "Monitoring disabled; manual checks available",
            },
            {
              label: "Persistence",
              value:
                "Local SQLite server database; browser theme preference only",
            },
            {
              label: "Settlement",
              value:
                "Official Polymarket resolution feed; proposed, disputed and unavailable outcomes stay unresolved",
            },
          ]}
        />
      </Panel>
    </div>
  );
}
