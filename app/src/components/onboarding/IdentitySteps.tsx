"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import AgentRun from "../AgentRun";
import { ProvPanel } from "../Provenance";
import { SourcesPanel, VerifyPanel } from "../panels";
import { Icon, cx } from "../ui";
import type { AppState } from "../../lib/api";
import { StepFooter, type Form } from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };

const POSTCODE = /^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i;

export function BusinessStep({ form, setForm, s, onNext }: Nav & { form: Form; setForm: (f: Form) => void; s: AppState }) {
  const [touched, setTouched] = useState(false);
  const errors = {
    pubName: form.pubName.trim().length < 2 ? "Enter the name on your sign or licence." : "",
    postcode: !POSTCODE.test(form.postcode.trim()) ? "Enter a full UK postcode, like N4 3HB." : "",
    owner: form.owner.trim().length < 2 ? "Enter your name." : "",
  };
  const valid = Object.values(errors).every((e) => !e);
  const submit = () => {
    setTouched(true);
    if (valid) onNext();
  };
  const set = (k: keyof Form) => (v: string) => setForm({ ...form, [k]: v });
  const differs = form.pubName.trim() !== s.pub.trading_name || form.postcode.trim().toUpperCase() !== s.pub.postcode;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <ProvPanel prov={{ badge: s.pub.identity_badge, meta: { source: "Companies House and postcodes.io" } }} title="Pub">
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Pub name" value={form.pubName} onChange={set("pubName")} error={touched ? errors.pubName : ""} autoFocus />
          <Field label="Postcode" value={form.postcode} onChange={(v) => set("postcode")(v.toUpperCase())} error={touched ? errors.postcode : ""} mono />
          <Field label="Your name" value={form.owner} onChange={set("owner")} error={touched ? errors.owner : ""} />
        </div>
      </ProvPanel>
      <div className="mt-4 flex items-start gap-3 text-sm text-fg-2">
        <Icon name="search" size={14} className="mt-1 shrink-0 text-fg-3" />
        We’ll look up your company on Companies House and your premises on postcodes.io. You won’t need to type them.
      </div>
      {differs && (
        <p className="mt-2 text-sm text-warning">
          This demo is set up for {s.pub.trading_name}, {s.pub.postcode}. The agent will check that pub.
        </p>
      )}
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
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  mono?: boolean;
  autoFocus?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-xs text-fg-2">{label}</span>
      <input
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        className={cx(
          "field mt-2 h-10 w-full px-3 text-sm placeholder:text-fg-3",
          mono && "font-mono"
        )}
      />
      {error && <span className="mt-1 block text-xs text-negative">{error}</span>}
    </label>
  );
}

export function RunStep({ ran, onRan, onNext, onBack }: Nav & { ran: boolean; onRan: () => void }) {
  return (
    <div>
      <AgentRun title="Pub Hedge agent" onDone={onRan} />
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="See what it found" disabled={!ran} hint={!ran ? "Run the agent to continue" : undefined} />
    </div>
  );
}

export function VerifyStep({ s, onEdit, onNext, onBack }: Nav & { s: AppState; onEdit: () => void }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="space-y-4">
      <VerifyPanel s={s} />
      <SourcesPanel s={s} />
      <div className="text-sm text-fg-2">
        Something wrong?{" "}
        <button type="button" onClick={onEdit} className="hit text-accent underline-offset-4 hover:underline">
          Edit your details
        </button>
      </div>
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="Confirm details" />
    </motion.div>
  );
}
