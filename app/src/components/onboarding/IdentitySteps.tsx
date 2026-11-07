"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import AgentRun from "../AgentRun";
import { Badge, Button, Icon, KeyValue, Panel, Spinner, cx } from "../ui";
import { PUB, SOURCES, VERIFY_RUN, type Source } from "../../lib/data";
import { RunSummary, StepFooter, type Form, type SourceStatus } from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };

const POSTCODE = /^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function BusinessStep({ form, setForm, onNext }: Nav & { form: Form; setForm: (f: Form) => void }) {
  const [touched, setTouched] = useState(false);
  const errors = {
    pubName: form.pubName.trim().length < 2 ? "Enter the name on your sign or licence." : "",
    postcode: !POSTCODE.test(form.postcode.trim()) ? "Enter a full UK postcode, like SE22 8HD." : "",
    owner: form.owner.trim().length < 2 ? "Enter your name." : "",
    email: !EMAIL.test(form.email.trim()) ? "Enter an email address we can reach you on." : "",
  };
  const valid = Object.values(errors).every((e) => !e);
  const submit = () => {
    setTouched(true);
    if (valid) onNext();
  };
  const set = (k: keyof Form) => (v: string) => setForm({ ...form, [k]: v });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Panel>
        <div className="grid grid-cols-2 gap-x-5 gap-y-4">
          <Field label="Pub name" value={form.pubName} onChange={set("pubName")} error={touched ? errors.pubName : ""} autoFocus />
          <Field
            label="Postcode"
            value={form.postcode}
            onChange={(v) => set("postcode")(v.toUpperCase())}
            error={touched ? errors.postcode : ""}
            mono
          />
          <Field label="Your name" value={form.owner} onChange={set("owner")} error={touched ? errors.owner : ""} />
          <Field label="Work email" value={form.email} onChange={set("email")} error={touched ? errors.email : ""} type="email" />
        </div>
      </Panel>
      <div className="mt-4 flex items-start gap-2.5 text-[12.5px] text-fg-2">
        <Icon name="search" size={14} className="mt-0.5 shrink-0 text-fg-3" />
        We’ll look up your company, licence and premises from Companies House and Southwark Council. You won’t need to type them.
      </div>
      <StepFooter onNext={submit} nextLabel="Look up my pub" />
    </form>
  );
}

function Field({
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
          mono && "font-mono tracking-wide"
        )}
      />
      {error && <span className="mt-1 block text-[12px] text-negative">{error}</span>}
    </label>
  );
}

export function VerifyStep({
  verified,
  onVerified,
  onEdit,
  onNext,
  onBack,
}: Nav & { verified: boolean; onVerified: () => void; onEdit: () => void }) {
  const [showResult, setShowResult] = useState(verified);
  const [live] = useState(!verified);

  return (
    <div>
      {!live ? (
        <RunSummary label="Verification complete" detail="9 checks · 4 sources · 7.6s" />
      ) : (
        <AgentRun
          title="Verifying your business"
          runId="run_7f3a91"
          steps={VERIFY_RUN}
          onDone={() => {
            onVerified();
            setTimeout(() => setShowResult(true), 500);
          }}
        />
      )}

      {showResult && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
          <Panel
            className="mt-4"
            title={PUB.legalName}
            actions={
              <Badge tone="positive" dot>
                Verified
              </Badge>
            }
          >
            <div className="grid grid-cols-2 gap-x-8">
              <KeyValue
                rows={[
                  { label: "Company number", value: PUB.companyNo, mono: true },
                  { label: "Incorporated", value: PUB.incorporated },
                  { label: "Director", value: `${PUB.owner} · matches you` },
                  { label: "VAT", value: PUB.vat, mono: true },
                ]}
              />
              <KeyValue
                rows={[
                  { label: "Premises", value: <span className="whitespace-nowrap">48 Lordship Lane, SE22 8HD</span> },
                  { label: "Premises licence", value: PUB.licence },
                  { label: "Capacity", value: `${PUB.covers} covers · ${PUB.gardenCovers} outdoor` },
                  { label: "Weather station", value: `${PUB.station} · ${PUB.stationDistance}` },
                ]}
              />
            </div>
          </Panel>
          <div className="mt-3 text-[12.5px] text-fg-2">
            Something wrong?{" "}
            <button onClick={onEdit} className="text-accent hover:underline">
              Edit your details
            </button>
          </div>
        </motion.div>
      )}

      <StepFooter onBack={onBack} onNext={onNext} nextLabel="Confirm details" disabled={!showResult} />
    </div>
  );
}

type Phase = "idle" | "authorising" | "importing" | "connected";

export function SourcesStep({
  status,
  setStatus,
  onNext,
  onBack,
}: Nav & { status: SourceStatus; setStatus: React.Dispatch<React.SetStateAction<SourceStatus>> }) {
  const [phase, setPhase] = useState<Record<string, Phase>>(() =>
    Object.fromEntries(SOURCES.map((s) => [s.id, status[s.id] === "connected" ? "connected" : "idle"]))
  );
  const allConnected = SOURCES.every((s) => phase[s.id] === "connected");
  const anyBusy = SOURCES.some((s) => phase[s.id] === "authorising" || phase[s.id] === "importing");

  const connect = (id: string) => setPhase((p) => ({ ...p, [id]: "authorising" }));
  const onConnected = (id: string) => {
    setPhase((p) => ({ ...p, [id]: "connected" }));
    setStatus((s) => ({ ...s, [id]: "connected" }));
  };

  return (
    <div>
      <Panel
        title="Sources"
        actions={
          <Button
            size="sm"
            onClick={() =>
              SOURCES.forEach((s, i) => phase[s.id] === "idle" && setTimeout(() => connect(s.id), i * 350))
            }
            disabled={allConnected || anyBusy}
          >
            Connect all
          </Button>
        }
        bodyClassName="p-0"
      >
        <ul className="divide-y divide-line">
          {SOURCES.map((s) => (
            <SourceRow
              key={s.id}
              source={s}
              phase={phase[s.id]}
              onConnect={() => connect(s.id)}
              onAuthorised={() => setPhase((p) => ({ ...p, [s.id]: "importing" }))}
              onConnected={() => onConnected(s.id)}
            />
          ))}
        </ul>
      </Panel>
      <div className="mt-4 flex items-start gap-2.5 text-[12.5px] text-fg-2">
        <Icon name="lock" size={14} className="mt-0.5 shrink-0 text-fg-3" />
        Read-only. Pub Hedge can’t move money, change your prices or edit your books, and you can revoke access from each provider at any time.
      </div>
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        disabled={!allConnected}
        hint={!allConnected ? "Connect all three to continue" : undefined}
        nextLabel="Run analysis"
      />
    </div>
  );
}

function SourceRow({
  source,
  phase,
  onConnect,
  onAuthorised,
  onConnected,
}: {
  source: Source;
  phase: Phase;
  onConnect: () => void;
  onAuthorised: () => void;
  onConnected: () => void;
}) {
  const [count, setCount] = useState(0);
  const cb = useRef({ onAuthorised, onConnected });
  cb.current = { onAuthorised, onConnected };

  useEffect(() => {
    if (phase === "authorising") {
      const t = setTimeout(() => cb.current.onAuthorised(), 1000);
      return () => clearTimeout(t);
    }
    if (phase === "importing") {
      const start = performance.now();
      const dur = 1800;
      let raf = 0;
      const tick = (now: number) => {
        const p = Math.min(1, (now - start) / dur);
        setCount(Math.round(source.total * (1 - Math.pow(1 - p, 2))));
        if (p < 1) raf = requestAnimationFrame(tick);
        else cb.current.onConnected();
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    }
  }, [phase, source.total]);

  return (
    <li className="flex h-16 items-center gap-4 px-4">
      <span className="flex h-8 w-8 items-center justify-center rounded border border-line-strong bg-surface-2 text-fg-2">
        <Icon name={source.icon} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-medium">{source.name}</div>
        <div className="truncate text-[12px] text-fg-3">
          {phase === "connected" ? source.result : `${source.kind} · ${source.via}`}
        </div>
      </div>
      <div className="flex w-[300px] items-center justify-end gap-3">
        {phase === "idle" && (
          <Button size="sm" onClick={onConnect}>
            Connect
          </Button>
        )}
        {phase === "authorising" && (
          <span className="flex items-center gap-2 text-[12.5px] text-fg-2">
            <Spinner className="text-accent" />
            Waiting for {source.name} to authorise
          </span>
        )}
        {phase === "importing" && (
          <div className="w-full">
            <div className="flex justify-between font-mono text-[11.5px] text-fg-2">
              <span>Importing {source.importing}</span>
              <span>
                {count.toLocaleString("en-GB")} / {source.total.toLocaleString("en-GB")}
              </span>
            </div>
            <div className="mt-1.5 h-1 rounded-full bg-surface-3">
              <div className="h-1 rounded-full bg-accent" style={{ width: `${(count / source.total) * 100}%` }} />
            </div>
          </div>
        )}
        {phase === "connected" && (
          <Badge tone="positive" dot>
            Connected
          </Badge>
        )}
      </div>
    </li>
  );
}
