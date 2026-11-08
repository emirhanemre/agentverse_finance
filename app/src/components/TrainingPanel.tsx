"use client";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge, Button, KeyValue, Panel, Spinner, tooltipStyle } from "./ui";
import {
  api,
  message,
  money,
  stamp,
  type AppState,
  type TrainingJob,
} from "../lib/api";
import { ErrorNotice } from "./onboarding/Onboarding";

export default function TrainingPanel({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const [job, setJob] = useState<TrainingJob | null>(state.training_job),
    [id, setId] = useState<string | null>(
      state.training_job?.state === "running" ? state.training_job.id : null,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (!id && !busy) setJob(state.training_job);
  }, [state.training_job, id, busy]);
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api<TrainingJob>(`/models/training/${id}`);
        if (cancelled) return;
        setJob(result);
        if (result.state !== "running") {
          setId(null);
          setBusy(false);
          await refresh();
        } else timer = setTimeout(poll, 700);
      } catch (e) {
        if (!cancelled) {
          setError(message(e));
          timer = setTimeout(poll, 2000);
        }
      }
    };
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, refresh]);
  const train = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id: string }>("/models/train", "POST");
      setId(result.id);
      setJob({
        id: result.id,
        state: "running",
        created_at: new Date().toISOString(),
        payload: { stage: "retrieving historical weather" },
      });
    } catch (e) {
      setBusy(false);
      setError(message(e));
    }
  };
  const report =
    state.business_model ||
    job?.payload.model ||
    state.training_job?.payload.model;
  const running = busy || !!id || state.training_job?.state === "running";
  return (
    <Panel
      className="mt-4"
      title="Train and evaluate your weather model"
      actions={
        report ? (
          <Badge tone={report.accepted ? "positive" : "warning"}>
            {report.accepted
              ? "Chronological holdout passed"
              : "Holdout did not pass"}
          </Badge>
        ) : (
          <Badge>Separate training step</Badge>
        )
      }
    >
      {error && <ErrorNotice text={error} />}
      <p className="text-[12.5px] leading-5 text-fg-2">
        Join daily sales to historical weather at your configured coordinates.
        The server fits on the oldest 60%, selects a model on the next 20%, then
        evaluates once on the newest 20%. A model is activated only if holdout
        error beats the weekday baseline by at least 5%. This does not establish
        causality or verify the sales source.
      </p>
      <div className="mt-4 flex items-center justify-between gap-4">
        <span className="text-[12px] text-fg-3">
          At least 180 matched daily records · missing days are not filled with
          zero sales
        </span>
        <Button
          onClick={train}
          disabled={running || !state.dataset || state.dataset.row_count < 180}
          variant="primary"
        >
          {running ? (
            <>
              <Spinner />
              Training and evaluating…
            </>
          ) : (
            "Train and evaluate sales model"
          )}
        </Button>
      </div>
      {job?.state === "running" && (
        <p role="status" className="mt-3 font-mono text-[12px] text-fg-2">
          {job.id} · {job.payload.stage}
        </p>
      )}
      {(job?.payload.error || state.training_job?.payload.error) && (
        <div className="mt-3">
          <ErrorNotice
            text={
              job?.payload.error ||
              state.training_job?.payload.error ||
              "Training failed"
            }
          />
        </div>
      )}
      {report && (
        <>
          <KeyValue
            className="mt-4"
            rows={[
              {
                label: "Training data",
                value: `${report.matched_rows} matched days · ${report.origin} · ${report.unmatched_sales_rows} unmatched sales days`,
              },
              {
                label: "Fit / validation / holdout",
                value: `${report.training_rows} / ${report.validation_rows} / ${report.test_rows} records`,
              },
              { label: "Fitted through", value: report.training_end },
              {
                label: "Untouched holdout",
                value: `${report.test_start} to ${report.test_end}`,
              },
              {
                label: "Holdout MAE / weekday baseline",
                value: `${money(report.test_mae_gbp)} / ${money(report.baseline_test_mae_gbp)}`,
                mono: true,
              },
              {
                label: "MAE improvement",
                value: `${report.improvement_pct.toFixed(1)}%`,
                mono: true,
              },
              {
                label: "Weather source",
                value: `${report.weather_provenance.source} · retrieved ${stamp(report.weather_provenance.retrieved_at)}`,
              },
              { label: "Limits", value: report.note },
            ]}
          />
          <div className="mt-4 h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={report.test_predictions}
                margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
              >
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  minTickGap={40}
                />
                <YAxis
                  width={70}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `£${Math.round(Number(v) / 1000)}k`}
                />
                <Tooltip
                  {...tooltipStyle}
                  formatter={(v) => money(Number(v))}
                />
                <Line
                  name="Actual recorded sales"
                  type="monotone"
                  dataKey="actual_revenue_gbp"
                  stroke="var(--fg-3)"
                  dot={false}
                  strokeWidth={1.5}
                />
                <Line
                  name="Holdout prediction"
                  type="monotone"
                  dataKey="predicted_revenue_gbp"
                  stroke="var(--accent)"
                  dot={false}
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[11.5px] text-fg-3">
            Held-out recorded revenue (grey) and model prediction (blue). No
            fabricated hedge savings or cashflow.
          </p>
        </>
      )}
    </Panel>
  );
}
