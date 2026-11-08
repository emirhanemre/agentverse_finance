"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import AgentRun from "../AgentRun";
import { Num, ProvPanel, ProvScope } from "../Provenance";
import { SourcesPanel, VerifyPanel } from "../panels";
import { Button, Icon, cx } from "../ui";
import { payroll, tool, type AppState, type OfferQuote, type Outcomes } from "../../lib/api";
import { day, gbp } from "../../lib/format";
import { StepFooter, type Form } from "./Onboarding";

type Nav = { onNext: () => void; onBack: () => void };

const POSTCODE = /^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i;
const COMPANY_NO = /^(\d{1,8}|[A-Z]{2}\d{6})$/i;

export function BusinessStep({ form, setForm, s, onNext }: Nav & { form: Form; setForm: (f: Form) => void; s: AppState }) {
  const [touched, setTouched] = useState(false);
  const errors = {
    pubName: form.pubName.trim().length < 2 ? "Enter the name on your sign or licence." : "",
    postcode: !POSTCODE.test(form.postcode.trim()) ? "Enter a full UK postcode, like N4 3HB." : "",
    owner: form.owner.trim().length < 2 ? "Enter your name." : "",
    companyNumber: form.companyNumber.trim() && !COMPANY_NO.test(form.companyNumber.trim()) ? "8 characters, like 05770953." : "",
  };
  const valid = Object.values(errors).every((e) => !e);
  const submit = () => {
    setTouched(true);
    if (valid) onNext();
  };
  const set = (k: keyof Form) => (v: string) => setForm({ ...form, [k]: v });
  const demo = s.demo_pub;
  const useDemo = () => {
    if (!demo) return;
    setTouched(false);
    setForm({ pubName: demo.trading_name, postcode: demo.postcode, owner: "Owner (demo)", companyNumber: demo.company_number });
  };

  return (
    <div className="grid items-center gap-10 lg:min-h-[calc(100vh-15rem)] lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <form
        className="on-hour max-w-[26rem]"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <h1 className="max-w-[12ch] font-display text-4xl font-medium leading-[1.04]" style={{ overflowWrap: "break-word" }}>
          Make payroll, whatever the weather.
        </h1>
        <p className="muted mt-4 max-w-[30ch] text-lg">An AI risk officer for independent pubs. You approve every move.</p>

        {demo && (
          <button
            type="button"
            onClick={useDemo}
            data-testid="use-demo-pub"
            className="hit press mt-6 inline-flex h-8 items-center gap-2 rounded-pill bg-[color-mix(in_oklab,var(--color-fog)_62%,transparent)] px-3 text-sm text-[var(--color-day-ink)] shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--color-day-ink)_14%,transparent)] backdrop-blur hover:bg-[color-mix(in_oklab,var(--color-fog)_82%,transparent)]"
          >
            <Icon name="spark" size={13} />
            Use the demo pub: {demo.trading_name}
          </button>
        )}
        <ProvScope value={s.pub.identity_badge}>
          <div className="mt-3 grid gap-3">
            <Field fog label="Pub name" value={form.pubName} onChange={set("pubName")} error={touched ? errors.pubName : ""} autoFocus />
            <div className="grid grid-cols-2 gap-3">
              <Field fog label="Postcode" value={form.postcode} onChange={(v) => set("postcode")(v.toUpperCase())} error={touched ? errors.postcode : ""} />
              <Field fog label="Your name" value={form.owner} onChange={set("owner")} error={touched ? errors.owner : ""} />
            </div>
            <Field
              fog
              label="Company number (optional, for pubs run by a pub company)"
              value={form.companyNumber}
              onChange={(v) => set("companyNumber")(v.toUpperCase())}
              error={touched ? errors.companyNumber : ""}
            />
          </div>
        </ProvScope>
        <p className="mt-3 text-sm text-[var(--color-day-ink)]">
          Any UK pub. The agent checks it on the public registers; the books it then works from are our demo books.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Button variant="primary" type="submit">
            Look up my pub
            <Icon name="chevron-right" size={14} />
          </Button>
          <span className="muted text-sm">The food hygiene register and Companies House fill in the rest.</span>
        </div>
      </form>

      <WeekendPreview s={s} />
    </div>
  );
}

/** The product in glass: a real weekend from the recorded run, every figure a receipt. */
function WeekendPreview({ s: live }: { s: AppState }) {
  // The recorded demo weekend, not whatever ran last. Its receipts belong to the recording,
  // so figures here carry their provenance on hover without opening a receipt.
  const s = { ...live, tools: live.demo_tools ?? live.tools };
  const days = Object.entries((tool(s, "weekend_forecast")?.days ?? {}) as Record<string, { mm: number }>);
  const wet = payroll(s, "wet");
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  const offer = tool<OfferQuote>(s, "price_match_offer");
  const rows = [
    days[0] && { i: "rain", t: "Weekend forecast", d: `${day(days[0][0])} afternoon`, st: "Read", tone: "", v: `${days[0][1].mm.toFixed(1)} mm` },
    wet && { i: "alert", t: "Payroll if it rains", d: `Due ${day(wet.payroll_date)}`, st: "At risk", tone: "text-warning", v: `${gbp(wet.shortfall_gbp)} short` },
    o && { i: "shield", t: "Rain cover", d: `Pays ${gbp(o.hedge_payout_if_wet_gbp)} if wet`, st: "Proposed", tone: "", v: gbp(o.hedge_cost_gbp, { pence: true }) },
    o?.wet_with_hedge_headroom_gbp !== undefined && o.wet_with_hedge_headroom_gbp >= 0 && { i: "check", t: "Payroll with cover", d: "Wet weekend", st: "Covered", tone: "text-positive", v: `${gbp(o.wet_with_hedge_headroom_gbp)} to spare` },
  ].filter(Boolean) as { i: "rain" | "alert" | "shield" | "check"; t: string; d: string; st: string; tone: string; v: string }[];

  return (
    <ProvPanel
      title="A weekend it would have caught"
      prov={{ badge: "SYNTHETIC", meta: { source: "The recorded demo run", label: "Illustrative scenario: modelled for a pub of this profile, not The Faltering Fullback's actual figures." } }}
      className="hidden lg:block"
    >
      <p className="-mt-1 text-xs text-fg-3">{s.scenario.name}</p>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-fg-2">Run the agent and a weekend like this appears here.</p>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {rows.map((r) => (
            <li key={r.t} className="flex items-center gap-3 py-3">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-fg-2">
                <Icon name={r.i} size={14} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-fg">{r.t}</span>
                <span className="block text-xs text-fg-3">{r.d}</span>
              </span>
              <span className={cx("hidden text-xs sm:block", r.tone || "text-fg-3")}>{r.st}</span>
              <Num badge="SYNTHETIC" className={cx("w-[9.5rem] text-right font-display text-md font-medium", r.tone)}>
                {r.v}
              </Num>
            </li>
          ))}
        </ul>
      )}
      {offer && !offer.error && (
        <div className="mt-3 flex items-center justify-between gap-4 rounded-inner bg-[color-mix(in_oklab,var(--color-accent-2)_12%,transparent)] px-4 py-3 text-sm">
          <span className="text-fg-2">
            Next: {offer.fixture}, a match-day offer at a fixed <Num badge={offer.badge} className="text-warning">{gbp(offer.fixed_cost_gbp, { pence: true })}</Num>
          </span>
          <span className="shrink-0 text-xs text-fg-3">{day(String(offer.kickoff).slice(0, 10))}</span>
        </div>
      )}
      <p className="mt-4 text-xs text-fg-3">Photo: an illustrative image made for this demo, not The Faltering Fullback.</p>
    </ProvPanel>
  );
}

function Field({
  label,
  value,
  onChange,
  error,
  mono,
  fog,
  autoFocus,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  mono?: boolean;
  fog?: boolean;
  autoFocus?: boolean;
}) {
  return (
    <label className="block">
      <span className={cx("text-xs", fog ? "muted" : "text-fg-2")}>{label}</span>
      <input
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        className={cx(
          "field mt-2 h-10 w-full px-3 text-sm placeholder:text-fg-3",
          mono && "font-mono",
          fog && "field--fog"
        )}
      />
      {error && <span className="mt-1 block text-xs text-negative">{error}</span>}
    </label>
  );
}

export function RunStep({ form, ran, onRan, onNext, onBack }: Nav & { form: Form; ran: boolean; onRan: () => void }) {
  return (
    <div>
      <AgentRun title="Pub Hedge agent" onDone={onRan} pub={form} />
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
