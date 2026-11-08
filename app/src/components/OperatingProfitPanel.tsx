"use client";
import { useState } from "react";
import { Badge, Button, Metric, Panel } from "./ui";
import {
  api,
  message,
  money,
  type AppState,
  type OperatingCosts,
} from "../lib/api";

export default function OperatingProfitPanel({
  state,
  refresh,
  expanded = false,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
  expanded?: boolean;
}) {
  const [editing, setEditing] = useState(expanded);
  const [draft, setDraft] = useState<OperatingCosts>(state.operating_costs);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const result = state.operating_profit;
  const selected = result?.selected;
  const costs = state.operating_costs;
  const edit = () => {
    setDraft(costs);
    setEditing(!editing);
    setError("");
    setSaved(false);
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/operating-costs", "PUT", draft);
      await refresh();
      setSaved(true);
      if (!expanded) setEditing(false);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between gap-2">
        <Badge tone="warning">Demo costs</Badge>
        {saved && (
          <span role="status" className="text-[11px] text-positive">
            Costs saved
          </span>
        )}
      </div>
      <Metric
        label="Estimated operating profit"
        value={
          selected ? (
            <span
              className={
                selected.operating_profit_gbp < 0 ? "text-negative" : "text-fg"
              }
            >
              {money(selected.operating_profit_gbp)}
            </span>
          ) : (
            "Run an analysis"
          )
        }
        sub={
          result
            ? `Per day · ${result.target_date}`
            : "Choose weather and run an assessment to estimate daily profit."
        }
      />
      {result && (
        <div className="mt-3 space-y-1 text-[12px] text-fg-2">
          <p>
            Reference profit:{" "}
            <span className="font-mono text-fg">
              {money(result.reference.operating_profit_gbp)}
            </span>
          </p>
          <p>
            Operating margin:{" "}
            <span className="font-mono text-fg">
              {selected?.operating_margin_pct === null
                ? "No revenue"
                : `${selected?.operating_margin_pct.toFixed(1)}%`}
            </span>
          </p>
          {selected?.prediction_interval_80_low_gbp != null &&
            selected.prediction_interval_80_high_gbp != null && (
              <p>
                Model 80% range:{" "}
                <span className="font-mono">
                  {money(selected.prediction_interval_80_low_gbp)} to{" "}
                  {money(selected.prediction_interval_80_high_gbp)}
                </span>
              </p>
            )}
        </div>
      )}
      <p className="mt-3 text-[11.5px] leading-5 text-fg-3">
        Assumed costs: {money(costs.fixed_daily_cost_gbp)} fixed per day +{" "}
        {costs.variable_cost_pct}% of revenue.
        {selected && (
          <> Selected-weather costs: {money(selected.total_cost_gbp)}.</>
        )}
      </p>
      <p className="mt-2 text-[11.5px] leading-5 text-fg-3">
        Illustrative costs, not imported expenses. Before tax/financing;
        excludes paper hedges. Cashflow requires payment dates. The range holds
        costs fixed.
      </p>
      <Button className="mt-3" size="sm" onClick={edit} disabled={busy}>
        {editing ? "Close cost editor" : "Edit demo cost assumptions"}
      </Button>
      {editing && (
        <form
          onSubmit={save}
          className="mt-4 space-y-3 border-t border-line pt-4"
        >
          {error && (
            <p role="alert" className="text-[12px] text-negative">
              {error}
            </p>
          )}
          {(
            [
              {
                key: "fixed_daily_cost_gbp",
                label: "Fixed daily costs (GBP)",
                max: 100000,
              },
              {
                key: "variable_cost_pct",
                label: "Variable costs (% of revenue)",
                max: 100,
              },
            ] as const
          ).map((field) => (
            <label key={field.key} className="block text-[12px] text-fg-2">
              {field.label}
              <input
                type="number"
                min={0}
                max={field.max}
                step="0.01"
                required
                value={
                  Number.isFinite(draft[field.key]) ? draft[field.key] : ""
                }
                onChange={(e) => {
                  setDraft({
                    ...draft,
                    [field.key]:
                      e.target.value === "" ? NaN : Number(e.target.value),
                  });
                  setSaved(false);
                }}
                className="mt-1.5 h-9 w-full rounded border border-line-strong bg-surface-2 px-3 font-mono text-[13px] text-fg outline-none focus:border-accent"
              />
            </label>
          ))}
          <p className="text-[11.5px] leading-5 text-fg-3">
            Profit = predicted revenue − variable costs − fixed daily costs.
            Include costs only once. Saving recalculates this scenario; it does
            not retrain the revenue model or change paper approvals.
          </p>
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? "Saving costs…" : "Save demo costs"}
          </Button>
        </form>
      )}
    </Panel>
  );
}
