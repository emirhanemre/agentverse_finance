"use client";

import { useState } from "react";
import { Badge, Button, Icon, KeyValue, Panel, Spinner, cx } from "../ui";
import { motion } from "framer-motion";
import TrainingPanel from "../TrainingPanel";
import {
  api,
  message,
  money,
  stamp,
  type AppState,
  type Profile,
} from "../../lib/api";
import {
  ErrorNotice,
  StepFooter,
  sampleProfile,
  type Form,
} from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };
export function BusinessStep({
  form,
  setForm,
  onNext,
  busy,
}: Nav & { form: Form; setForm: (f: Form) => void; busy: boolean }) {
  const [touched, setTouched] = useState(false);
  const [coordinatesConfirmed, setCoordinatesConfirmed] = useState(false);
  const errors = {
    pubName: form.pubName.trim().length < 2 ? "Enter your business name." : "",
    postcode: !/^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i.test(form.postcode)
      ? "Enter a full UK postcode."
      : "",
    owner: form.owner.trim().length < 2 ? "Enter your name." : "",
    email: !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)
      ? "Enter a valid email."
      : "",
  };
  const set = (k: keyof Form) => (v: string) => {
    setForm({ ...form, [k]: v });
    if (k === "postcode" || k === "location_name")
      setCoordinatesConfirmed(false);
  };
  const submit = () => {
    setTouched(true);
    if (
      !Object.values(errors).some(Boolean) &&
      form.location_name.length > 1 &&
      coordinatesConfirmed
    )
      onNext();
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Panel>
        <div className="grid grid-cols-2 gap-x-5 gap-y-4">
          <Field
            label="Pub name"
            value={form.pubName}
            onChange={set("pubName")}
            error={touched ? errors.pubName : ""}
            autoFocus
          />
          <Field
            label="Postcode"
            value={form.postcode}
            onChange={(v) => set("postcode")(v.toUpperCase())}
            error={touched ? errors.postcode : ""}
            mono
          />
          <Field
            label="Your name"
            value={form.owner}
            onChange={set("owner")}
            error={touched ? errors.owner : ""}
          />
          <Field
            label="Work email"
            value={form.email}
            onChange={set("email")}
            error={touched ? errors.email : ""}
            type="email"
          />
        </div>
      </Panel>
      <Panel
        className="mt-4"
        title="Weather location and premises"
        actions={
          <Button
            size="sm"
            onClick={() => {
              setForm(sampleProfile);
              setCoordinatesConfirmed(true);
            }}
          >
            Use sample business
          </Button>
        }
      >
        <div className="grid grid-cols-3 gap-x-5 gap-y-4">
          <Field
            label="City / location"
            value={form.location_name}
            onChange={set("location_name")}
            error={
              touched && form.location_name.length < 2
                ? "Enter a location."
                : ""
            }
          />
          <NumberField
            label="Latitude"
            value={form.latitude}
            min={-90}
            max={90}
            step="any"
            onChange={(v) => {
              setForm({ ...form, latitude: v });
              setCoordinatesConfirmed(false);
            }}
          />
          <NumberField
            label="Longitude"
            value={form.longitude}
            min={-180}
            max={180}
            step="any"
            onChange={(v) => {
              setForm({ ...form, longitude: v });
              setCoordinatesConfirmed(false);
            }}
          />
          <NumberField
            label="Indoor seats"
            value={form.indoor_capacity}
            min={10}
            max={500}
            onChange={(v) => setForm({ ...form, indoor_capacity: v })}
          />
          <NumberField
            label="Outdoor seats"
            value={form.outdoor_capacity}
            min={0}
            max={500}
            onChange={(v) => setForm({ ...form, outdoor_capacity: v })}
          />
          <NumberField
            label="Opening hours / day"
            value={form.opening_hours}
            min={1}
            max={24}
            step="0.5"
            onChange={(v) => setForm({ ...form, opening_hours: v })}
          />
        </div>
        <label className="mt-4 flex items-start gap-2 text-[12px] text-fg-2">
          <input
            type="checkbox"
            checked={coordinatesConfirmed}
            onChange={(e) => setCoordinatesConfirmed(e.target.checked)}
          />
          I confirm these coordinates describe my weather location. The initial
          coordinates are an editable London example, not a postcode lookup.
        </label>
        {touched && !coordinatesConfirmed && (
          <p className="mt-2 text-[12px] text-negative">
            Confirm your weather coordinates, or explicitly choose the sample
            business.
          </p>
        )}
      </Panel>
      <div className="mt-4 flex items-start gap-2.5 text-[12.5px] text-fg-2">
        <Icon name="search" size={14} className="mt-0.5 shrink-0 text-fg-3" />
        Company and licence checks are unavailable. Details are self-reported;
        sample business details are fictional.
      </div>
      <StepFooter
        onNext={submit}
        nextLabel={busy ? "Saving…" : "Save business details"}
        disabled={busy}
      />
    </form>
  );
}
export function Field({
  label,
  value,
  onChange,
  error,
  mono,
  autoFocus,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  mono?: boolean;
  autoFocus?: boolean;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-[12px] text-fg-2">{label}</span>
      <input
        type={type}
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        className={cx(
          "mt-1.5 h-9 w-full rounded border bg-surface-2 px-3 text-[13px] text-fg outline-none transition-colors placeholder:text-fg-3",
          error ? "border-negative" : "border-line-strong focus:border-accent",
          mono && "font-mono tracking-wide",
        )}
      />
      {error && (
        <span className="mt-1 block text-[12px] text-negative">{error}</span>
      )}
    </label>
  );
}
export function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = "1",
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="text-[12px] text-fg-2">{label}</span>
      <input
        type="number"
        value={Number.isFinite(value) ? value : ""}
        min={min}
        max={max}
        step={step}
        onChange={(e) =>
          onChange(e.target.value === "" ? NaN : Number(e.target.value))
        }
        className="mt-1.5 h-9 w-full rounded border border-line-strong bg-surface-2 px-3 font-mono text-[13px] outline-none focus:border-accent"
      />
    </label>
  );
}
export function VerifyStep({
  profile,
  companyDemo,
  refresh,
  onEdit,
  onNext,
  onBack,
}: Nav & {
  profile: Profile | null;
  companyDemo: boolean;
  refresh: () => Promise<unknown>;
  onEdit: () => void;
}) {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const connect = async () => {
    setConnecting(true);
    setError("");
    try {
      await Promise.all([
        api("/sources/companies_house/demo-connect", "POST"),
        new Promise((resolve) => setTimeout(resolve, 1400)),
      ]);
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setConnecting(false);
    }
  };
  return (
    <div>
      <Panel
        title={profile?.pubName || "Business details"}
        actions={
          <Badge tone="warning" dot>
            Self-reported
          </Badge>
        }
      >
        <div className="grid grid-cols-2 gap-x-8">
          <KeyValue
            rows={[
              { label: "Business", value: profile?.pubName },
              { label: "Operator", value: profile?.owner },
              { label: "Email", value: profile?.email },
              { label: "Currency", value: "GBP" },
            ]}
          />
          <KeyValue
            rows={[
              { label: "Postcode", value: profile?.postcode },
              { label: "Weather location", value: profile?.location_name },
              {
                label: "Coordinates",
                value: `${profile?.latitude}, ${profile?.longitude}`,
                mono: true,
              },
              {
                label: "Seats",
                value: `${profile?.indoor_capacity} indoor · ${profile?.outdoor_capacity} outdoor`,
              },
            ]}
          />
        </div>
      </Panel>
      <Panel className="mt-4" title="External checks">
        {error && <ErrorNotice text={error} />}
        <KeyValue
          rows={[
            {
              label: "Companies House",
              value: (
                <span className="flex items-center gap-3">
                  {connecting ? (
                    <span className="flex items-center gap-2 text-fg-2">
                      <Spinner /> Connecting · visual demo
                    </span>
                  ) : (
                    <>
                      <Badge tone={companyDemo ? "accent" : "neutral"}>
                        {companyDemo
                          ? "Demo connected"
                          : "Visual demo available"}
                      </Badge>
                      <Button size="sm" onClick={connect}>
                        {companyDemo
                          ? "Replay Companies House demo"
                          : "Connect Companies House demo"}
                      </Button>
                    </>
                  )}
                </span>
              ),
            },
            { label: "Premises licence", value: <Badge>Unavailable</Badge> },
            {
              label: "Identity verification",
              value: <Badge>Not implemented</Badge>,
            },
          ]}
        />
        <p className="mt-3 text-[12.5px] text-fg-2">
          The Companies House connection is a visual placeholder. No official
          register has been checked. You can continue with self-reported
          details.
        </p>
      </Panel>
      <div className="mt-3 text-[12.5px] text-fg-2">
        <button onClick={onEdit} className="text-accent hover:underline">
          Edit your details
        </button>
      </div>
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextLabel="Continue with these details"
        disabled={!profile}
      />
    </div>
  );
}
export function DataSources({
  state,
  refresh,
}: {
  state: AppState;
  refresh: () => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [connecting, setConnecting] = useState<Record<string, boolean>>({});
  const connect = async (id: string) => {
    setConnecting((c) => ({ ...c, [id]: true }));
    setError("");
    try {
      await Promise.all([
        api(`/sources/${id}/demo-connect`, "POST"),
        new Promise((resolve) => setTimeout(resolve, 1400)),
      ]);
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setConnecting((c) => ({ ...c, [id]: false }));
    }
  };
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Panel
        title="Sources"
        bodyClassName="p-0"
        actions={
          <Button
            size="sm"
            disabled={Object.values(connecting).some(Boolean)}
            onClick={() =>
              state.sources
                .filter((s) => ["toast", "monzo", "xero"].includes(s.id))
                .forEach((s) => connect(s.id))
            }
          >
            Connect all demos
          </Button>
        }
      >
        <ul className="divide-y divide-line">
          {state.sources
            .filter((s) => ["toast", "monzo", "xero"].includes(s.id))
            .map((s) => (
              <li key={s.id} className="flex h-16 items-center gap-4 px-4">
                <span className="flex h-8 w-8 items-center justify-center rounded border border-line-strong bg-surface-2 text-fg-2">
                  <Icon
                    name={
                      s.id === "monzo"
                        ? "bank"
                        : s.id === "toast"
                          ? "receipt"
                          : "layers"
                    }
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium">{s.name}</div>
                  <div className="truncate text-[12px] text-fg-3">{s.note}</div>
                </div>
                <div className="flex w-[210px] shrink-0 items-center justify-end gap-3">
                  {connecting[s.id] ? (
                    <div className="w-full">
                      <div className="flex items-center justify-end gap-2 text-[12px] text-fg-2">
                        <Spinner className="text-accent" />
                        Connecting · visual demo
                      </div>
                      <div className="mt-1.5 h-1 rounded-full bg-surface-3">
                        <motion.div
                          className="h-1 rounded-full bg-accent"
                          initial={{ width: 0 }}
                          animate={{ width: "100%" }}
                          transition={{ duration: 1.3 }}
                        />
                      </div>
                    </div>
                  ) : s.status === "demo_connected" ? (
                    <>
                      <Badge tone="accent" dot>
                        Demo connected
                      </Badge>
                      <Button size="sm" onClick={() => connect(s.id)}>
                        Replay
                      </Button>
                    </>
                  ) : (
                    <Button size="sm" onClick={() => connect(s.id)}>
                      Connect demo
                    </Button>
                  )}
                </div>
              </li>
            ))}
        </ul>
        <p className="border-t border-line px-4 py-3 text-[11.5px] text-fg-3">
          Provider connections are visual placeholders. They do not authorise
          accounts or import records; select sample sales or import a CSV below.
        </p>
      </Panel>
      <Panel
        className="mt-4"
        title="Sales data"
        actions={
          state.dataset && (
            <Badge tone="accent">
              {state.dataset.origin === "synthetic_sample"
                ? "Synthetic sample"
                : "User import · unverified"}
            </Badge>
          )
        }
      >
        {error && <ErrorNotice text={error} />}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            onClick={() => act(() => api("/sources/sample", "POST"))}
            disabled={busy}
          >
            Use synthetic sample sales
          </Button>
          <label className="cursor-pointer rounded border border-line-strong bg-surface-2 px-3 py-1.5 text-[13px] font-medium">
            {busy ? "Processing…" : "Import sales CSV"}
            <input
              aria-label="Import sales CSV"
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file)
                  act(async () => {
                    if (file.size > 2_000_000)
                      throw new Error("CSV must be under 2 MB.");
                    await api("/sources/import", "POST", {
                      filename: file.name,
                      csv: await file.text(),
                    });
                  });
                e.target.value = "";
              }}
            />
          </label>
          <a
            href="/sample-sales.csv"
            download
            className="text-[12px] text-accent underline"
          >
            CSV template
          </a>
          <a
            href="/synthetic-sales-training.csv"
            download
            className="text-[12px] text-accent underline"
          >
            Full synthetic training CSV
          </a>
        </div>
        <p className="mt-3 text-[12.5px] leading-5 text-fg-2">
          CSV columns:{" "}
          <span className="font-mono">date,revenue_gbp,currency</span>. ISO
          dates, one daily total per date, nonnegative GBP amounts with at most
          two decimals. Importing validates the file; use the separate training
          and evaluation step below for business-specific estimates.
        </p>
        {state.dataset && (
          <KeyValue
            className="mt-4"
            rows={[
              { label: "Selected file", value: state.dataset.filename },
              {
                label: "Records",
                value: `${state.dataset.row_count} days · ${state.dataset.start_date} to ${state.dataset.end_date}`,
              },
              {
                label: "Recorded revenue",
                value: money(state.dataset.total_revenue_gbp),
                mono: true,
              },
              { label: "Selected", value: stamp(state.dataset.selected_at) },
              { label: "Provenance", value: state.dataset.note },
            ]}
          />
        )}
      </Panel>
      <TrainingPanel state={state} refresh={refresh} />
    </>
  );
}
export function SourcesStep({
  state,
  refresh,
  onNext,
  onBack,
}: Nav & { state: AppState; refresh: () => Promise<unknown> }) {
  return (
    <div>
      <DataSources state={state} refresh={refresh} />
      <div className="mt-4 flex items-start gap-2.5 text-[12.5px] text-fg-2">
        <Icon name="lock" size={14} className="mt-0.5 shrink-0 text-fg-3" />
        Records are stored in the local server database. No provider account is
        connected.
      </div>
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextLabel="Configure analysis"
        hint={
          !state.dataset
            ? "You can continue; analysis will explain missing data."
            : undefined
        }
      />
    </div>
  );
}
