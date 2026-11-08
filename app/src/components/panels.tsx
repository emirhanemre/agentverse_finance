"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  api,
  approve,
  payroll,
  pence,
  putLimits,
  reject,
  tool,
  type AppState,
  type Check,
  type Estimate,
  type Limits,
  type Outcomes,
  type PolicyPoint,
  type Proposal,
  type Receipt,
  type ToolResult,
  type Verdict,
} from "../lib/api";
import { day, gbp, pct } from "../lib/format";
import { Bullets, ModelChip } from "./AgentRun";
import { Num, ProvBadge, getReceipt } from "./Provenance";
import { Badge, Button, Icon, KeyValue, Panel, Spinner, cx, tooltipStyle } from "./ui";

type S = { s: AppState };
const money = (v: unknown) => gbp(Number(v));

/** Badge for a tool result, with the result itself as provenance. */
export function ToolBadge({ r }: { r?: ToolResult }) {
  if (!r) return null;
  return <ProvBadge badge={r.badge} meta={r} receiptId={r.receipt_id} />;
}

export function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="14" height="6" aria-hidden>
        <line x1="0" y1="3" x2="14" y2="3" stroke={color} strokeWidth="1.5" strokeDasharray={dashed ? "3 2" : undefined} />
      </svg>
      {label}
    </span>
  );
}

export function SyntheticNote({ s, className }: S & { className?: string }) {
  return (
    <p className={cx("flex items-center gap-2 text-[12px] text-warning", className)} data-testid="synthetic-label">
      <Icon name="alert" size={13} className="shrink-0" />
      {s.pub.financials_label.replace(/^SYNTHETIC:\s*/, "SYNTHETIC — ")}
    </p>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-[12.5px] text-fg-3">{children}</p>;
}

// ---------- What the agent sees ----------

export function VerifyPanel({ s }: S) {
  const ch = tool(s, "companies_house_profile");
  const off = tool(s, "companies_house_officer_match");
  const pc = tool(s, "locate_postcode");
  const row = (label: string, value: React.ReactNode, r?: ToolResult) => ({
    label,
    value: (
      <span className="flex items-center justify-between gap-3">
        <Num rid={r?.receipt_id}>{value}</Num>
        <ToolBadge r={r} />
      </span>
    ),
  });
  return (
    <div data-testid="panel-verify">
      <Panel
        title={String(ch?.company_name ?? s.pub.trading_name)}
        actions={
          <>
            <ProvBadge badge={s.pub.identity_badge} meta={{ source: "Companies House and postcodes.io, matched on company number and postcode" }} />
            {ch && (
              <Badge tone={ch.company_status === "active" ? "positive" : "warning"} dot>
                {ch.company_status === "active" ? "Verified" : String(ch.company_status)}
              </Badge>
            )}
          </>
        }
      >
        {!ch ? (
          <Empty>Run the agent to check the public registers.</Empty>
        ) : (
          <div className="grid grid-cols-2 gap-x-8">
            <KeyValue
              rows={[
                row("Trading as", s.pub.trading_name),
                row("Company number", s.pub.company_number, ch),
                row("Incorporated", day(String(ch.incorporated), true), ch),
                row("SIC code", (ch.sic_codes as string[] | undefined)?.join(", ") ?? "—", ch),
                row("Directors", off ? String(off.summary) : "—", off),
              ]}
            />
            <KeyValue
              rows={[
                row("Premises", s.pub.address),
                row("District", pc ? String(pc.district) : "—", pc),
                row("Location", pc ? `${Number(pc.lat).toFixed(4)}, ${Number(pc.lon).toFixed(4)}` : "—", pc),
                row("Owner", s.pub.owner),
              ]}
            />
          </div>
        )}
      </Panel>
    </div>
  );
}

const SOURCE_ROWS: { tool: string; name: string; kind: string; icon: Parameters<typeof Icon>[0]["name"] }[] = [
  { tool: "load_takings_history", name: "Till takings", kind: "Daily takings, generated for a pub of this profile", icon: "receipt" },
  { tool: "load_stripe_test_charges", name: "Card payments", kind: "Takings seeded as Stripe test-mode charges", icon: "receipt" },
  { tool: "load_bank_feed", name: "Bank feed", kind: "Open Banking format transactions", icon: "bank" },
  { tool: "load_weather_history", name: "Weather history", kind: "Open-Meteo archive for N4", icon: "rain" },
  { tool: "weekend_forecast", name: "Weekend forecast", kind: "What was forecast at the time", icon: "rain" },
  { tool: "load_match_and_duty_dates", name: "Match and duty dates", kind: "Fixtures and HMRC duty changes", icon: "calendar" },
  { tool: "check_real_weather_markets", name: "Polymarket", kind: "Read-only price check", icon: "layers" },
];

export function SourcesPanel({ s }: S) {
  return (
    <div data-testid="panel-sources">
      <Panel title="Data sources" actions={<span className="text-[12px] text-fg-3">Read-only access</span>} bodyClassName="p-0">
        <ul className="divide-y divide-line">
          {SOURCE_ROWS.map((row) => {
            const r = tool(s, row.tool);
            return (
              <li key={row.tool} className="flex min-h-14 items-center gap-4 px-4 py-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-line-strong bg-surface-2 text-fg-2">
                  <Icon name={row.icon} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium">{row.name}</div>
                  <div className="truncate text-[12px] text-fg-3">{r?.source ? `${row.kind} · ${r.source}` : row.kind}</div>
                </div>
                <div className="w-[300px] text-right font-mono text-[12px] text-fg-2">
                  {r ? <Num rid={r.receipt_id}>{r.summary || "no result"}</Num> : "Not read yet"}
                </div>
                <div className="flex w-[110px] justify-end">
                  <ToolBadge r={r} />
                </div>
              </li>
            );
          })}
          {["Smarkets", "Betfair Exchange"].map((v) => (
            <li key={v} className="flex h-14 items-center gap-4 px-4 opacity-70">
              <span className="flex h-8 w-8 items-center justify-center rounded border border-line bg-surface-2 text-fg-3">
                <Icon name="plug" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px]">{v}</div>
                <div className="text-[12px] text-fg-3">UK betting exchange</div>
              </div>
              <Badge>Not connected in demo</Badge>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

// ---------- Risks ----------

export function RisksPanel({ s }: S) {
  const fit = tool(s, "fit_takings_model");
  const exp = tool(s, "weekend_rain_exposure");
  if (!fit)
    return (
      <div data-testid="panel-risks">
        <Panel title="What moves your takings">
          <Empty>Run the agent to fit the takings model.</Empty>
        </Panel>
      </div>
    );
  const e = (k: string) => fit[k] as Estimate;
  const rows: { name: string; driver: string; est: Estimate; unit: string }[] = [
    { name: "Rain on a Friday–Sunday afternoon", driver: "Weather", est: e("rain_weekend_gbp_per_mm"), unit: "per mm" },
    { name: "Rain on a weekday afternoon", driver: "Weather", est: e("rain_weekday_gbp_per_mm"), unit: "per mm" },
    { name: "Warmer days", driver: "Weather", est: e("heat_gbp_per_c"), unit: "per °C" },
    { name: "Match days", driver: "Sport", est: e("match_day_gbp"), unit: "per day" },
    { name: "Beer duty rises", driver: "Policy", est: e("duty_rise_gbp_per_day"), unit: "per day" },
  ].filter((r) => r.est);
  return (
    <div data-testid="panel-risks">
      <Panel
        title="What moves your takings"
        actions={
          <>
            <span className="font-mono text-[11.5px] text-fg-3">
              <Num rid={fit.receipt_id}>R² {Number(fit.r2_holdout).toFixed(3)} held-out</Num> · n = {String(fit.n_holdout)}
            </span>
            <ToolBadge r={fit} />
          </>
        }
        bodyClassName="p-0"
      >
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-line bg-surface-2 text-[11px] uppercase tracking-[0.04em] text-fg-3">
              <th className="px-4 py-2 font-medium">Driver</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 text-right font-medium">Effect on takings</th>
              <th className="px-4 py-2 text-right font-medium">95% interval</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.name}>
                <td className="px-4 py-2.5 text-[13px]">{r.name}</td>
                <td className="px-4 py-2.5 text-[12.5px] text-fg-2">{r.driver}</td>
                <td className={cx("px-4 py-2.5 text-right font-mono text-[13px]", r.est.estimate < 0 ? "text-negative" : "text-positive")}>
                  <Num rid={fit.receipt_id}>
                    {gbp(r.est.estimate, { sign: true })} {r.unit}
                  </Num>
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-[12px] text-fg-2">
                  {gbp(r.est.ci95[0])} to {gbp(r.est.ci95[1])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center justify-between gap-4 border-t border-line px-4 py-3">
          <p className="text-[12.5px] text-fg-2">
            {exp ? (
              <>
                A {String(exp.wet_scenario_mm)}mm Friday–Sunday afternoon costs about{" "}
                <Num rid={exp.receipt_id} className="font-mono text-negative">
                  {gbp(-Number(exp.loss_wet_day_gbp))}
                </Num>{" "}
                in takings. That is the risk worth covering.
              </>
            ) : (
              "Rain exposure not computed yet."
            )}
          </p>
          <ToolBadge r={exp} />
        </div>
        <p className="border-t border-line px-4 py-2 text-[11.5px] text-fg-3">{String(fit.label)}</p>
      </Panel>
    </div>
  );
}

export function ForecastPanel({ s }: S) {
  const f = tool(s, "weekend_forecast");
  const prices = tool(s, "price_rain_contracts");
  const days = (f?.days ?? {}) as Record<string, { mm: number }>;
  const contracts = (prices?.contracts ?? []) as { date: string; model_prob: number; ask: number }[];
  return (
    <div data-testid="panel-forecast">
      <Panel
        title="The weekend"
        actions={
          <>
            <span className="font-mono text-[11.5px] text-fg-3">{s.scenario.name}</span>
            <ToolBadge r={f} />
          </>
        }
      >
        {!f || f.badge === "ERROR" ? (
          <Empty>No forecast available for this run.</Empty>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(days).map(([d, v]) => {
              const c = contracts.find((x) => x.date === d);
              return (
                <div key={d} className="rounded border border-line bg-surface-2 px-3 py-2.5">
                  <div className="flex items-baseline justify-between font-mono text-[11.5px]">
                    <span className="text-fg-2">{day(d)}</span>
                    <span className="text-fg-3">afternoon</span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 font-mono text-[18px]">
                    <Icon name="rain" size={15} className={v.mm >= 1 ? "text-accent" : "text-fg-3"} />
                    <Num rid={f.receipt_id}>{v.mm.toFixed(1)} mm</Num>
                  </div>
                  {c && (
                    <div className="mt-1 flex items-center justify-between font-mono text-[11.5px] text-fg-3">
                      <span>
                        P(≥3mm) <Num rid={prices?.receipt_id}>{pct(c.model_prob, 0)}</Num> · ask {c.ask.toFixed(2)}
                      </span>
                      <ToolBadge r={prices} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-2 text-[11.5px] text-fg-3">{String(f?.grid_note ?? f?.source ?? "")}</p>
      </Panel>
    </div>
  );
}

// ---------- Cashflow: the failure that hurts ----------

function mergeTimelines(s: AppState) {
  const wet = payroll(s, "wet");
  const dry = payroll(s, "dry");
  const close = (rows?: { date: string; balance_gbp: number }[]) => {
    const m = new Map<string, number>();
    rows?.forEach((r) => m.set(r.date, r.balance_gbp));
    return m;
  };
  const w = close(wet?.timeline);
  const d = close(dry?.timeline);
  const dates = Array.from(new Set([...Array.from(w.keys()), ...Array.from(d.keys())])).sort();
  return dates.map((date) => ({ date, wet: w.get(date), dry: d.get(date) }));
}

export function CashflowPanel({ s, compact }: S & { compact?: boolean }) {
  const wet = payroll(s, "wet");
  const dry = payroll(s, "dry");
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  const data = mergeTimelines(s);
  return (
    <div data-testid="panel-cashflow" className="flex min-h-0 flex-col">
      <Panel
        title="Payroll week after a wet weekend"
        actions={
          <>
            <Legend color="var(--negative)" label="Wet weekend" />
            <Legend color="var(--fg-3)" label="Dry weekend" dashed />
            <ToolBadge r={wet} />
          </>
        }
      >
        {!wet ? (
          <Empty>Run the agent to project payroll.</Empty>
        ) : (
          <>
            <div className="grid grid-cols-4 gap-px overflow-hidden rounded border border-line bg-line">
              {[
                { l: "First day overdrawn", v: day(wet.first_negative_date), rid: wet.receipt_id, c: "text-negative" },
                { l: "Payroll due", v: day(wet.payroll_date), rid: wet.receipt_id },
                { l: "Short on payroll day, wet", v: gbp(-wet.shortfall_gbp, { pence: true }), rid: wet.receipt_id, c: "text-negative" },
                { l: "Short on payroll day, dry", v: dry ? gbp(-dry.shortfall_gbp, { pence: true }) : "—", rid: dry?.receipt_id, c: "text-warning" },
              ].map((m) => (
                <div key={m.l} className="bg-surface-2 px-3 py-2">
                  <div className="text-[11.5px] text-fg-3">{m.l}</div>
                  <Num rid={m.rid} className={cx("font-mono text-[16px]", m.c)}>
                    {m.v}
                  </Num>
                </div>
              ))}
            </div>
            <p className="mt-2.5 text-[12.5px] leading-5 text-fg-2">
              {wet.payroll_clears
                ? "Payroll clears in both cases."
                : `The account goes overdrawn on ${day(wet.first_negative_date)} when rent, suppliers and the VAT sweep land, and payroll on ${day(
                    wet.payroll_date
                  )} doesn’t clear. A wet weekend makes it ${gbp(o?.wet_extra_shortfall_gbp ?? wet.shortfall_gbp - (dry?.shortfall_gbp ?? 0))} worse.`}
            </p>
            <div className={cx("mt-2", compact ? "h-[150px]" : "h-[190px]")}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 6, right: 56, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} strokeDasharray="2 4" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} tickFormatter={(d: string) => day(d)} />
                  <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={money} />
                  <ReferenceLine y={0} stroke="var(--negative)" strokeDasharray="4 4" strokeOpacity={0.6} label={{ value: "£0", position: "right", fill: "var(--fg-3)", fontSize: 11 }} />
                  <ReferenceLine x={wet.payroll_date} stroke="var(--fg-3)" strokeDasharray="3 3" label={{ value: "Payroll", position: "insideTopRight", fill: "var(--fg-3)", fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} labelFormatter={(d) => day(String(d))} formatter={(v, n) => [gbp(Number(v), { pence: true }), n === "wet" ? "Wet weekend" : "Dry weekend"]} />
                  <Line type="stepAfter" dataKey="dry" stroke="var(--fg-3)" strokeWidth={1.25} strokeDasharray="4 3" dot={false} connectNulls isAnimationActive={false} />
                  <Line type="stepAfter" dataKey="wet" stroke="var(--negative)" strokeWidth={1.75} dot={false} connectNulls isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
        {o && <OutcomesTable o={o} rid={sized?.receipt_id} r={sized} />}
        <SyntheticNote s={s} className="mt-3" />
      </Panel>
    </div>
  );
}

function OutcomesTable({ o, rid, r }: { o: Outcomes; rid?: string; r?: ToolResult }) {
  const cell = (v: number, tone?: string) => (
    <td className={cx("px-3 py-2 text-right font-mono text-[12.5px]", tone)}>
      <Num rid={rid}>{v > 0 ? gbp(-v, { pence: true }) : "Clears"}</Num>
    </td>
  );
  return (
    <div className="mt-3 rounded border border-line" data-testid="outcomes">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="text-[12.5px] font-medium">What the hedge does to payroll on {day(o.payroll_date)}</span>
        {r && <ToolBadge r={r} />}
      </div>
      <table className="w-full">
        <thead>
          <tr className="text-[11px] uppercase tracking-[0.04em] text-fg-3">
            <th className="px-3 py-1.5 text-left font-medium">Weekend</th>
            <th className="px-3 py-1.5 text-right font-medium">Without hedge</th>
            <th className="px-3 py-1.5 text-right font-medium">With hedge</th>
            <th className="px-3 py-1.5 text-left font-medium">Why</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line border-t border-line">
          <tr>
            <td className="px-3 py-2 text-[12.5px]">Wet</td>
            {cell(o.wet_no_hedge_shortfall_gbp, "text-negative")}
            {cell(o.wet_with_hedge_shortfall_gbp, "text-negative")}
            <td className="px-3 py-2 text-[12px] text-fg-2">Pays {gbp(o.hedge_payout_if_wet_gbp, { pence: true })}. Narrows the gap, doesn’t close it.</td>
          </tr>
          <tr>
            <td className="px-3 py-2 text-[12.5px]">Dry</td>
            {cell(o.dry_no_hedge_shortfall_gbp, "text-warning")}
            {cell(o.dry_with_hedge_shortfall_gbp, "text-warning")}
            <td className="px-3 py-2 text-[12px] text-fg-2">Expires worthless. The {gbp(o.hedge_cost_gbp, { pence: true })} is lost.</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ---------- Backtest ----------

const POLICY_LABEL: Record<string, string> = {
  none: "No cover",
  naive: "Naive: £20 every weekend day",
  ours: "Pub Hedge, at your caps",
  ours_caps_x5: "Pub Hedge, caps ×5",
};

const btMeta = (s: AppState) => ({
  source: `Backtest, ${s.backtest.setup.pubs} synthetic pubs, held-out ${s.backtest.setup.test[0]} to ${s.backtest.setup.test[1]}`,
  generator: s.synthetic_manifest.generator,
  seed: s.backtest.setup.seed,
  method: s.backtest.setup.bootstrap,
  label: s.synthetic_manifest.label,
});

export function WeeklyBacktestChart({ s }: S) {
  const none = s.backtest.demo_weeks.none ?? [];
  const ours = s.backtest.demo_weeks.ours ?? [];
  const data = none.map((w, i) => ({ i, start: w.start, none: w.net, ours: ours[i]?.net }));
  const shortNone = none.filter((w) => w.shortfall).length;
  const shortOurs = ours.filter((w) => w.shortfall).length;
  return (
    <div data-testid="panel-weekly">
      <Panel
        title="Weekly cash after costs · backtest on held-out months"
        actions={
          <>
            <Legend color="var(--accent)" label="With Pub Hedge" />
            <Legend color="var(--fg-3)" label="Without" dashed />
            <ProvBadge badge="SYNTHETIC" meta={btMeta(s)} />
          </>
        }
      >
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 6, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} strokeDasharray="2 4" />
              <XAxis dataKey="start" tickLine={false} axisLine={false} interval={12} tickFormatter={(d: string) => new Date(d).toLocaleDateString("en-GB", { month: "short", year: "2-digit" })} />
              <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={money} />
              <ReferenceLine y={0} stroke="var(--negative)" strokeDasharray="4 4" strokeOpacity={0.6} />
              <Tooltip {...tooltipStyle} labelFormatter={(d) => `Week of ${day(String(d), true)}`} formatter={(v, n) => [money(v), n === "ours" ? "With Pub Hedge" : "Without"]} />
              <Line type="monotone" dataKey="none" stroke="var(--fg-3)" strokeWidth={1.25} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="ours" stroke="var(--accent)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-[12px] text-fg-2">
          Weeks below zero over {none.length} held-out weeks: {shortNone} without cover, {shortOurs} with it. The two lines sit almost on top of each other.
        </p>
      </Panel>
    </div>
  );
}

export function BacktestPanel({ s }: S) {
  const p = s.backtest.policies;
  const cols: { k: keyof PolicyPoint; l: string; f: (v: number) => string }[] = [
    { k: "hedge_net_gbp_per_year", l: "Net hedge result / pub-year", f: (v) => gbp(v, { sign: true }) },
    { k: "shortfall_weeks_per_year", l: "Weeks short / year", f: (v) => v.toFixed(1) },
    { k: "worst_week_gbp", l: "Worst week", f: (v) => gbp(v) },
    { k: "cvar5_weekly_gbp", l: "CVaR 5%, weekly", f: (v) => gbp(v) },
  ];
  const ours = p.ours.point;
  const none = p.none.point;
  const naive = p.naive.point;
  return (
    <div data-testid="panel-backtest">
      <Panel
        title="Backtest"
        actions={
          <>
            <span className="font-mono text-[11.5px] text-fg-3">
              {s.backtest.setup.pubs} pubs · {s.backtest.setup.bootstrap}
            </span>
            <ProvBadge badge="SYNTHETIC" meta={btMeta(s)} />
          </>
        }
        bodyClassName="p-0"
      >
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-line bg-surface-2 text-[11px] uppercase tracking-[0.04em] text-fg-3">
              <th className="px-4 py-2 font-medium">Policy</th>
              {cols.map((c) => (
                <th key={c.k} className="px-4 py-2 text-right font-medium">
                  {c.l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(Object.keys(POLICY_LABEL) as (keyof typeof p)[]).map((k) =>
              p[k] ? (
                <tr key={k} className={k === "ours" ? "bg-accent-wash" : undefined}>
                  <td className="px-4 py-2.5 text-[13px]">{POLICY_LABEL[k]}</td>
                  {cols.map((c) => (
                    <td key={c.k} className="px-4 py-2.5 text-right">
                      <div className="font-mono text-[13px]">{c.f(p[k].point[c.k])}</div>
                      <div className="font-mono text-[11px] text-fg-3">
                        {c.f(p[k].ci95[c.k][0])} to {c.f(p[k].ci95[c.k][1])}
                      </div>
                    </td>
                  ))}
                </tr>
              ) : null
            )}
          </tbody>
        </table>
        <p className="border-t border-line px-4 py-3 text-[12.5px] leading-5 text-fg-2" data-testid="backtest-honest">
          {Math.abs(ours.shortfall_weeks_per_year - none.shortfall_weeks_per_year) < 0.05
            ? `At these caps, Pub Hedge does not reduce the number of weeks a pub can’t cover its costs: ${ours.shortfall_weeks_per_year.toFixed(1)} a year with or without it.`
            : `Weeks short: ${none.shortfall_weeks_per_year.toFixed(1)} a year without cover, ${ours.shortfall_weeks_per_year.toFixed(1)} with it.`}{" "}
          It costs about {gbp(-ours.hedge_net_gbp_per_year)} a pub-year net, against {gbp(-naive.hedge_net_gbp_per_year)} for naive daily cover. Raising the caps five-fold
          doesn’t help either. Intervals are 95% bootstrap. Held-out {s.backtest.setup.test[0]} to {s.backtest.setup.test[1]}.
        </p>
      </Panel>
    </div>
  );
}

// ---------- Recommendation ----------

export function ProposalPanel({ s, p }: S & { p?: Proposal }) {
  const rat = s.run?.summary?.narration?.rationale;
  const pricer = s.run?.summary?.narration?.pricer;
  const sized = tool(s, "size_hedges");
  const noValue = (sized?.no_value_at_price ?? []) as string[];
  if (!p)
    return (
      <div data-testid="panel-recommendation">
        <Panel title="Recommendation">
          <Empty>Nothing is worth buying at today’s prices, so nothing is proposed.</Empty>
          {rat && <div className="mt-3"><Bullets text={rat.text} /></div>}
        </Panel>
      </div>
    );
  const m = p.market;
  const cost = p.cost_pence / 100;
  return (
    <div data-testid="panel-recommendation">
      <Panel title={`Rain cover, ${day(m.date)}`} actions={<ProvBadge badge={m.price_badge} meta={{ source: "Synthetic rain contract", method: m.rule, label: "No London rain market exists on Polymarket, so this contract is priced from calibrated forecasts" }} receiptId={sized?.receipt_id} />}>
        <div className="text-[12px] text-fg-2">Pays out if</div>
        <p className="mt-1 text-[13px] leading-5">At least 3mm of rain falls on the afternoon of {day(m.date, true)} at the grid cell nearest {s.pub.postcode}.</p>

        <div className="mt-4 grid grid-cols-4 gap-px overflow-hidden rounded border border-line bg-line">
          {[
            { l: "Cost", v: gbp(cost, { pence: true }) },
            { l: "Pays if wet", v: gbp(m.payout_if_event_gbp, { pence: true }), c: "text-positive" },
            { l: "Max loss", v: gbp(cost, { pence: true }), c: "text-negative" },
            { l: "Shares", v: String(p.shares) },
          ].map((x) => (
            <div key={x.l} className="bg-surface-2 px-3 py-2">
              <div className="text-[11.5px] text-fg-3">{x.l}</div>
              <Num rid={sized?.receipt_id} className={cx("font-mono text-[14px]", x.c)}>
                {x.v}
              </Num>
            </div>
          ))}
        </div>

        {rat && (
          <>
            <h3 className="mt-5 flex items-center gap-2 text-[12px] font-medium text-fg-2">
              Why it was suggested
              {rat.model && <ModelChip model={rat.model} />}
              <ProvBadge badge={rat.badge} receiptId={rat.receipt_id} />
            </h3>
            <div className="mt-2" data-testid="rationale">
              <Bullets text={rat.text} />
            </div>
          </>
        )}

        <h3 className="mt-5 text-[12px] font-medium text-fg-2">How it was calculated</h3>
        <dl className="mt-2 rounded border border-line bg-surface-2 px-3 py-2 font-mono text-[12px] leading-6">
          <CalcRow k="Forecast" v={`${m.forecast_mm.toFixed(1)} mm`} />
          <CalcRow k="P(rain ≥ 3mm)" v={`${pct(m.model_prob)} (calibrated on archived forecasts)`} />
          <CalcRow k="Ask" v={`${m.ask.toFixed(4)} → ${m.cost_per_share.toFixed(4)} a share all in (1% slippage + taker fee ${m.fee_rate} × p × (1 − p))`} />
          <CalcRow k="Pricing rule" v={m.rule} />
          {noValue.length > 0 && <CalcRow k="Not proposed" v={`${noValue.join(", ")}: no value at the price`} />}
        </dl>
        {pricer && (
          <p className="mt-3 flex items-start gap-2 text-[12px] leading-5 text-fg-3">
            <span className="flex-1">{pricer.text}</span>
            <ProvBadge badge={pricer.badge} receiptId={pricer.receipt_id} />
          </p>
        )}
      </Panel>
    </div>
  );
}

function CalcRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="grid grid-cols-[130px_1fr]">
      <dt className="text-fg-3">{k}</dt>
      <dd className="text-fg">{v}</dd>
    </div>
  );
}

// ---------- Execute: approval + limits ----------

const CHECK_LABEL: Record<string, string> = {
  weekly_spend: "Weekly spend",
  monthly_max_loss: "Maximum loss this month",
  per_market_concentration: "One market",
};

export function PaperBanner() {
  return (
    <div className="flex items-center gap-2 rounded border border-accent-edge bg-accent-wash px-3 py-1.5 text-[12px] font-medium text-accent" data-testid="paper-banner">
      <Icon name="lock" size={13} />
      PAPER TRADING — no real orders
      <span className="ml-auto">
        <ProvBadge badge="PAPER" meta={{ source: "Paper execution against synthetic prices. Nothing is sent to any venue." }} />
      </span>
    </div>
  );
}

const STATUS_TONE = { pending: "warning", blocked: "negative", filled: "positive", rejected: "neutral" } as const;

export function ApprovalCard({ s, p, onChange }: S & { p?: Proposal; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [needsSecond, setNeedsSecond] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [fill, setFill] = useState<Record<string, unknown> | null>(null);
  const [blockReceipt, setBlockReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState("");

  // A block by the owner's limits writes a receipt with fresh checks. Show those over the stale proposal-time verdict.
  useEffect(() => {
    if (p?.status === "blocked" && p.receipt_id) getReceipt(p.receipt_id).then(setBlockReceipt, () => {});
    if (p?.status === "filled" && p.receipt_id)
      getReceipt(p.receipt_id).then((r) => setFill(((r.result as Record<string, unknown>)?.fill as Record<string, unknown>) ?? null), () => {});
  }, [p?.status, p?.receipt_id]);

  if (!p)
    return (
      <div data-testid="panel-approval">
        <Panel title="Needs approval">
          <PaperBanner />
          <Empty>
            <span className="mt-3 block">Nothing waiting. Run the agent to price cover for the weekend.</span>
          </Empty>
        </Panel>
      </div>
    );

  const blockChecks = (blockReceipt?.result as { checks?: Check[] } | undefined)?.checks;
  const checks = verdict?.checks ?? blockChecks ?? p.market.verdict.checks;
  const cost = p.cost_pence / 100;

  const go = async (confirmSecond: boolean) => {
    setBusy(true);
    setError("");
    try {
      const r = await approve(p.id, confirmSecond);
      setVerdict(r.verdict);
      setNeedsSecond(r.status === "needs_second_approval");
      if (r.fill) setFill(r.fill);
      onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="panel-approval">
      <Panel
        title="Needs approval"
        actions={
          <>
            <ProvBadge badge="PAPER" meta={{ source: "Paper trading. Limits are enforced in code by the API before any fill." }} receiptId={p.receipt_id} />
            <Badge tone={STATUS_TONE[p.status]} dot>
              <span data-testid={`status-${p.id}`}>{p.status}</span>
            </Badge>
          </>
        }
      >
        <PaperBanner />
        <div className="mt-3 flex items-start justify-between gap-4">
          <div>
            <div className="text-[13px] font-medium">Rain cover, {day(p.market.date)}</div>
            <div className="mt-0.5 font-mono text-[11.5px] text-fg-3">
              {p.market.market_id} · {p.shares} shares at {p.market.cost_per_share.toFixed(4)}
            </div>
          </div>
          <div className="text-right font-mono text-[12.5px]">
            <Num rid={tool(s, "size_hedges")?.receipt_id}>{gbp(cost, { pence: true })}</Num>
            <div className="text-[11.5px] text-fg-3">pays {gbp(p.market.payout_if_event_gbp, { pence: true })}</div>
          </div>
        </div>

        <ul className="mt-3 divide-y divide-line rounded border border-line text-[12.5px]" data-testid="limit-checks">
          {checks.map((c) => (
            <li key={c.name} className="flex h-9 items-center justify-between px-3" data-testid={`check-${c.name}`}>
              <span className="text-fg-2">{CHECK_LABEL[c.name] ?? c.name}</span>
              <span className="flex items-center gap-2 font-mono">
                {pence(c.value_pence)} <span className="text-fg-3">of {pence(c.cap_pence)}</span>
                <span className={c.pass ? "text-positive" : "text-negative"}>
                  <Icon name={c.pass ? "check" : "x"} size={14} />
                </span>
              </span>
            </li>
          ))}
          <li className="flex h-9 items-center justify-between px-3">
            <span className="text-fg-2">Second approval over {pence(s.limits.approval_threshold_pence)}</span>
            <span className="font-mono">{p.cost_pence > s.limits.approval_threshold_pence ? "Needed" : "Not needed"}</span>
          </li>
        </ul>

        {p.status === "blocked" && (
          <p className="mt-3 flex items-start gap-2 rounded border border-negative bg-negative-wash px-3 py-2 text-[12.5px] text-negative">
            <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
            <span>
              Blocked by your limits: <span data-testid="blocked-reason">{p.reason}</span>
            </span>
          </p>
        )}
        {p.status === "filled" && (
          <p className="mt-3 rounded border border-positive-edge bg-positive-wash px-3 py-2 text-[12.5px] text-positive" data-testid="filled-note">
            Paper fill: {String(fill?.shares ?? p.shares)} shares
            {fill?.fill_price ? ` at ${Number(fill.fill_price).toFixed(4)}` : ""}
            {fill?.cost_gbp ? `, ${gbp(Number(fill.cost_gbp), { pence: true })}` : ""}. {String(fill?.note ?? "No real order was placed.")}
          </p>
        )}
        {p.status === "rejected" && <p className="mt-3 text-[12.5px] text-fg-2">You declined this. It won’t be placed.</p>}
        {error && <p className="mt-3 text-[12.5px] text-negative">{error}</p>}

        {p.status === "pending" && (
          <div className="mt-3 flex items-center gap-2">
            {needsSecond ? (
              <>
                <Button variant="primary" onClick={() => go(true)} disabled={busy} data-testid={`confirm-second-${p.id}`}>
                  {busy && <Spinner size={12} />}
                  Yes, place {gbp(cost, { pence: true })} on paper
                </Button>
                <Button onClick={() => setNeedsSecond(false)} disabled={busy}>
                  Cancel
                </Button>
                <span className="text-[12px] text-warning">Over {pence(s.limits.approval_threshold_pence)}, so it needs a second confirm.</span>
              </>
            ) : (
              <>
                <Button variant="primary" onClick={() => go(false)} disabled={busy} data-testid={`approve-${p.id}`}>
                  {busy && <Spinner size={12} />}
                  Approve {gbp(cost, { pence: true })}
                </Button>
                <Button
                  onClick={async () => {
                    await reject(p.id).catch((e) => setError(String(e)));
                    onChange();
                  }}
                  disabled={busy}
                  data-testid={`reject-${p.id}`}
                >
                  Decline
                </Button>
                <span className="text-[12px] text-fg-3">If it stays dry you lose {gbp(cost, { pence: true })}.</span>
              </>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}

const LIMIT_FIELDS: { k: keyof Limits; l: string; id: string }[] = [
  { k: "weekly_spend_cap_pence", l: "Weekly spend cap", id: "limit-weekly" },
  { k: "monthly_max_loss_pence", l: "Monthly maximum loss", id: "limit-monthly" },
  { k: "per_market_cap_pence", l: "Cap on any one market", id: "limit-market" },
  { k: "approval_threshold_pence", l: "Second approval over", id: "limit-approval" },
];

export function LimitsPanel({ s, onChange }: S & { onChange: () => void }) {
  const toPounds = (l: Limits) => Object.fromEntries(LIMIT_FIELDS.map((f) => [f.k, String(l[f.k] / 100)])) as Record<keyof Limits, string>;
  const [form, setForm] = useState(() => toPounds(s.limits));
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ id: string; reason: string; receipt_id: string }[] | null>(null);
  const [error, setError] = useState("");
  const limitsKey = JSON.stringify(s.limits);
  useEffect(() => setForm(toPounds(JSON.parse(limitsKey))), [limitsKey]);

  const invalid = LIMIT_FIELDS.some((f) => !/^\d+(\.\d{1,2})?$/.test(form[f.k].trim()));
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const patch = Object.fromEntries(LIMIT_FIELDS.map((f) => [f.k, Math.round(Number(form[f.k]) * 100)]));
      const r = await putLimits(patch);
      setResult(r.blocked);
      onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="panel-limits">
      <Panel title="Limits" actions={<ProvBadge badge="PAPER" meta={{ source: "Enforced by the API on every approval. Lowering a cap re-checks pending cover at once." }} />}>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          {LIMIT_FIELDS.map((f) => (
            <label key={f.k} className="block">
              <span className="text-[12px] text-fg-2">{f.l}</span>
              <div className="mt-1 flex h-8 items-center rounded border border-line-strong bg-surface-2 px-2.5 focus-within:border-accent">
                <span className="font-mono text-[13px] text-fg-3">£</span>
                <input
                  data-testid={f.id}
                  inputMode="decimal"
                  value={form[f.k]}
                  onChange={(e) => setForm({ ...form, [f.k]: e.target.value })}
                  className="ml-1 w-full bg-transparent font-mono text-[13px] text-fg outline-none"
                />
              </div>
            </label>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button variant="primary" size="sm" onClick={save} disabled={saving || invalid} data-testid="limits-save">
            {saving && <Spinner size={12} />}
            Save limits
          </Button>
          <span className="font-mono text-[11.5px] text-fg-3">
            Spent this week {pence(s.ledger.spent_this_week_pence)} · at risk this month {pence(s.ledger.at_risk_this_month_pence)}
          </span>
        </div>
        {invalid && <p className="mt-2 text-[12px] text-negative">Enter amounts in pounds, like 30 or 30.50.</p>}
        {error && <p className="mt-2 text-[12px] text-negative">{error}</p>}
        {result && (
          <p className="mt-2 text-[12px] text-fg-2" data-testid="limits-result">
            {result.length === 0
              ? "Saved. Nothing pending breaks the new limits."
              : result.map((b) => (
                  <span key={b.id} className="block text-negative">
                    Blocked {b.id}: <Num rid={b.receipt_id}>{b.reason}</Num>
                  </span>
                ))}
          </p>
        )}
      </Panel>
    </div>
  );
}

// ---------- Activity (the audit log) ----------

type AuditRow = { seq: number; ts: number; step: string; call: string; badge: string; model: string; receipt_id: string };

export function ActivityFeed({ limit = 40, refreshKey }: { limit?: number; refreshKey?: unknown }) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  useEffect(() => {
    api<{ rows: AuditRow[] }>(`/api/audit?limit=${limit}`).then((r) => setRows(r.rows), () => setRows([]));
  }, [limit, refreshKey]);
  if (!rows) return <Spinner className="m-4 text-accent" />;
  if (rows.length === 0) return <Empty>No activity yet.</Empty>;
  return (
    <ul className="divide-y divide-line">
      {rows.map((r) => (
        <li key={r.seq} className="grid grid-cols-[60px_72px_1fr_auto] items-center gap-3 py-1.5">
          <span className="font-mono text-[11.5px] text-fg-3">
            {new Date(r.ts * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
          <span className="truncate font-mono text-[11px] text-fg-3">{r.step}</span>
          <Num rid={r.receipt_id} className="truncate text-left font-mono text-[12px] text-fg-2">
            {r.call}
          </Num>
          <ProvBadge badge={r.badge} receiptId={r.receipt_id} />
        </li>
      ))}
    </ul>
  );
}
