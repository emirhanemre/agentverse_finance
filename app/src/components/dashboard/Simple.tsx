"use client";

import { useState } from "react";
import { Num, ProvPanel } from "../Provenance";
import { OfferCard, PaperBanner, PaydayPanel, SyntheticNote } from "../panels";
import { Button, Icon, Spinner, cx } from "../ui";
import { approve, payroll, rainProposals, reject, tool, type AppState, type Outcomes, type Proposal } from "../../lib/api";
import { day, gbp } from "../../lib/format";

/** The owner's view: one sentence on the week, the payday picture, one decision, plain words. */
export function SimpleView({ s, refresh }: { s: AppState; refresh: () => void }) {
  const p = rainProposals(s)[0];
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  const wet = payroll(s, "wet");

  return (
    <div className="mx-auto flex max-w-[880px] flex-col gap-6">
      <Headline s={s} p={p} o={o} wetShort={wet?.payroll_clears === false ? wet.shortfall_gbp : 0} rid={sized?.receipt_id ?? wet?.receipt_id} />
      <PaydayPanel s={s} />
      <Decision key={p?.id} s={s} p={p} onChange={refresh} />
      <OfferCard s={s} onChange={refresh} compact />
      <Watch s={s} />
      <SyntheticNote s={s} />
    </div>
  );
}

function Headline({ s, p, o, wetShort, rid }: { s: AppState; p?: Proposal; o?: Outcomes; wetShort: number; rid?: string }) {
  const due = day(o?.payroll_date ?? payroll(s, "wet")?.payroll_date);
  const spare = o?.wet_with_hedge_headroom_gbp;
  let title = "Nothing needs you this week.";
  let line: React.ReactNode = "Payroll clears whatever the weather. I’ll keep watching the forecast.";
  if (p?.status === "filled" && spare !== undefined && spare >= 0) {
    title = "You’re covered for the weekend.";
    line = (
      <>
        If it rains, payroll on {due} still clears with <Num rid={rid}>{gbp(spare)}</Num> to spare.
      </>
    );
  } else if (wetShort > 0) {
    title = "Payroll is at risk this weekend.";
    line = (
      <>
        If it rains, payroll on {due} is <Num rid={rid} className="text-warning">{gbp(wetShort)}</Num> short.
        {p && p.status === "pending" && " Rain cover would fix that. It needs your yes."}
      </>
    );
  }
  return (
    <section className="pt-4 text-center" data-testid="simple-headline">
      <h2 className="font-display text-3xl font-medium">{title}</h2>
      <p className="mx-auto mt-3 max-w-[46ch] text-lg text-fg-2">{line}</p>
    </section>
  );
}

function Decision({ s, p, onChange }: { s: AppState; p?: Proposal; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [error, setError] = useState("");
  const sized = tool(s, "size_hedges");
  if (!p) return null;
  const cost = p.cost_pence / 100;
  const pays = p.market.payout_if_event_gbp;
  const limit = s.limits.approval_threshold_pence / 100;
  const reason = blocked ?? (p.status === "blocked" ? p.reason ?? p.market.verdict.reason : null) ?? (!p.market.verdict.allowed ? p.market.verdict.reason : null);

  const go = async (second: boolean) => {
    setBusy(true);
    setError("");
    try {
      const r = await approve(p.id, second);
      setConfirm(r.status === "needs_second_approval");
      setBlocked(r.status === "blocked" ? r.verdict?.reason ?? "Your limits stopped this." : null);
      onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const no = async () => {
    setBusy(true);
    try {
      await reject(p.id);
      onChange();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="simple-decision">
      <ProvPanel title="Your decision" prov={{ badge: "PAPER", meta: { source: "Paper trading. Your limits are checked in code before anything is placed." } }}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <div className="font-display text-lg font-medium">Rain cover for {day(p.market.date)}</div>
          <div className="text-md text-fg-2">
            Costs{" "}
            <Num rid={sized?.receipt_id} className="text-fg">
              {gbp(cost, { pence: true })}
            </Num>
            . Pays{" "}
            <Num rid={sized?.receipt_id} className="text-positive">
              {gbp(pays)}
            </Num>{" "}
            if it rains.
          </div>
        </div>
        <p className="mt-2 text-sm text-fg-3">If it stays dry, you lose the {gbp(cost, { pence: true })} and payroll still clears.</p>

        {p.status === "filled" ? (
          <p className="mt-6 flex items-center gap-2 text-md text-positive">
            <Icon name="check" size={16} />
            Done. Cover is in place on paper: no real money moved.
          </p>
        ) : p.status === "rejected" ? (
          <p className="mt-6 text-md text-fg-2">You said not now. Nothing was placed.</p>
        ) : (
          <>
            {reason && (
              <p className="mt-6 flex items-start gap-2 text-md text-warning">
                <Icon name="alert" size={16} className="mt-1 shrink-0" />
                Your limits stopped this: {reason}.
              </p>
            )}
            {confirm && !reason && (
              <p className="mt-6 text-md text-fg">
                That’s over your {gbp(limit)} approval line. Confirm you want {gbp(cost, { pence: true })} of cover?
              </p>
            )}
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button variant="primary" disabled={busy || !!reason} onClick={() => go(confirm)} data-testid="simple-approve">
                {busy ? <Spinner /> : <Icon name="check" size={14} />}
                {confirm ? `Yes, place ${gbp(cost, { pence: true })}` : "Approve cover"}
              </Button>
              <Button onClick={no} disabled={busy}>
                Not now
              </Button>
            </div>
          </>
        )}
        {error && <p className="mt-3 text-xs text-negative">{error}</p>}
        <div className="mt-6">
          <PaperBanner />
        </div>
      </ProvPanel>
    </div>
  );
}

function Watch({ s }: { s: AppState }) {
  const sched = tool(s, "schedule_monitor");
  const checks = ((sched?.checks ?? []) as string[]).map((c) => {
    const [d, t] = c.split(" ");
    return `${day(d)} at ${t}`;
  });
  const L = s.limits;
  const items = [
    checks.length > 0 && { i: "calendar" as const, t: `I’ll re-check the forecast ${checks.join(" and ")}.` },
    { i: "shield" as const, t: `I never spend more than ${gbp(L.weekly_spend_cap_pence / 100)} a week, or ${gbp(L.per_market_cap_pence / 100)} on any one cover.` },
    { i: "lock" as const, t: `Anything over ${gbp(L.approval_threshold_pence / 100)} waits for your yes, twice. Paper trading only.` },
  ].filter(Boolean) as { i: "calendar" | "shield" | "lock"; t: string }[];
  return (
    <ProvPanel title="Keeping watch" prov={sched ? { badge: sched.badge, meta: sched, receiptId: sched.receipt_id } : undefined}>
      <ul className="divide-y divide-line">
        {items.map((x) => (
          <li key={x.t} className={cx("flex items-center gap-3 py-3 text-md text-fg-2", "first:pt-0 last:pb-0")}>
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-fg-2">
              <Icon name={x.i} size={14} />
            </span>
            {x.t}
          </li>
        ))}
      </ul>
    </ProvPanel>
  );
}
