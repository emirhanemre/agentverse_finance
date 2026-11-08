"use client";
import { useState } from "react";
import { Badge, Button, KeyValue, Panel } from "./ui";
import { api, message, stamp, type AppState, type Settings } from "../lib/api";
import { NumberField } from "./onboarding/IdentitySteps";
import { ErrorNotice } from "./onboarding/Onboarding";
export default function MonitoringPanel({
  state,
  settings,
  onChange,
  onSave,
  saving,
  refresh,
}: {
  state: AppState;
  settings: Settings;
  onChange: (s: Settings) => void;
  onSave: () => void;
  saving: boolean;
  refresh: () => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const check = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/monitor/check", "POST");
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel
      title="Forecast monitoring"
      actions={
        <Badge tone={state.settings.monitor_enabled ? "accent" : "neutral"}>
          {state.settings.monitor_enabled
            ? "Enabled while API runs"
            : "Disabled"}
        </Badge>
      }
    >
      {error && <ErrorNotice text={error} />}
      <label className="flex items-start gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={settings.monitor_enabled}
          onChange={(e) =>
            onChange({ ...settings, monitor_enabled: e.target.checked })
          }
        />
        Enable forecast monitoring and in-app alerts
      </label>
      <p className="mt-2 text-[12px] leading-5 text-fg-2">
        While the Python service is running, monitoring refreshes weather and
        official outcomes, assesses the next few days and creates proposals when
        suitable. Every position still requires your approval. Rejected or
        unchanged active proposals are not duplicated. No email, push service or
        exchange execution is enabled.
      </p>
      <div className="mt-4 grid grid-cols-3 gap-4">
        <NumberField
          label="Check every (minutes)"
          value={settings.monitor_interval_minutes}
          min={5}
          max={1440}
          onChange={(v) =>
            onChange({ ...settings, monitor_interval_minutes: v })
          }
        />
        <NumberField
          label="Forecast horizon (days)"
          value={settings.monitor_horizon_days}
          min={1}
          max={7}
          onChange={(v) => onChange({ ...settings, monitor_horizon_days: v })}
        />
        <NumberField
          label="Paper budget per check (GBP)"
          value={settings.monitor_budget_gbp}
          min={0.01}
          max={1000}
          step=".01"
          onChange={(v) => onChange({ ...settings, monitor_budget_gbp: v })}
        />
      </div>
      {state.monitoring && (
        <KeyValue
          className="mt-4"
          rows={[
            { label: "Last monitor state", value: state.monitoring.status },
            { label: "Last check", value: stamp(state.monitoring.last_run_at) },
            {
              label: "Next scheduled check",
              value: state.settings.monitor_enabled
                ? stamp(state.monitoring.next_run_at)
                : "Disabled",
            },
            {
              label: "Result",
              value:
                state.monitoring.note ||
                "Retrieving data and assessing exposure…",
            },
          ]}
        />
      )}
      <div className="mt-4 flex justify-end gap-2">
        <Button onClick={check} disabled={busy || state.monitoring?.running}>
          {busy || state.monitoring?.running
            ? "Checking forecast…"
            : "Check monitoring now"}
        </Button>
        <Button variant="primary" onClick={onSave} disabled={saving}>
          Save monitoring settings
        </Button>
      </div>
    </Panel>
  );
}
