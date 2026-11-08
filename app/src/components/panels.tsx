"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  api,
  approve,
  payroll,
  pence,
  proposalTitle,
  putLimits,
  queueOffer,
  reject,
  settle,
  tool,
  type OfferQuote,
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
import { Glyph, Num, ProvBadge, ProvPanel, getReceipt, useAudit } from "./Provenance";
import { Badge, Button, Icon, KeyValue, Panel, Spinner, cx, tooltipStyle } from "./ui";

type S = { s: AppState };
const money = (v: unknown) => gbp(Number(v));

/** A tool result as a panel's provenance: `<ProvPanel prov={provOf(r)}>`. */
export const provOf = (r?: ToolResult) => (r ? { badge: r.badge, meta: r, receiptId: r.receipt_id } : undefined);

/** Badge for a tool result, with the result itself as provenance. */
export function ToolBadge({ r }: { r?: ToolResult }) {
  if (!r) return null;
  return <ProvBadge badge={r.badge} meta={r} receiptId={r.receipt_id} />;
}

export function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-2 whitespace-nowrap">
      <svg width="14" height="6" aria-hidden>
        <line x1="0" y1="3" x2="14" y2="3" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeDasharray={dashed ? "3 3" : undefined} />
      </svg>
      {label}
    </span>
  );
}

/** The one quiet line at the foot of a money screen. The exact SYNTHETIC label stays for screen readers and the audit view. */
export function SyntheticNote({ s, className }: S & { className?: string }) {
  const { audit } = useAudit();
  const exact = s.pub.financials_label.replace(/^SYNTHETIC:\s*/, "SYNTHETIC — ");
  const plain = s.pub.financials_label.replace(/^SYNTHETIC:\s*/, "");
  return (
    <p className={cx("flex items-start gap-2 text-xs text-fg-3", className)} data-testid="synthetic-label">
      <span className="mt-1">
        <Glyph badge="SYNTHETIC" />
      </span>
      <span aria-hidden>{audit ? exact : `Illustrative scenario: ${plain}.`}</span>
      <span className="sr-only">{exact}</span>
    </p>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-fg-3">{children}</p>;
}

// ---------- What the agent sees ----------

type RegisterCheck = { check: string; ok: boolean; detail?: string };
type Considered = { company_number: string; name: string; status?: string; kept: boolean; why: string };

export function VerifyPanel({ s }: S) {
  const prem = tool(s, "find_premises");
  const op = tool(s, "find_operator");
  const ch = tool(s, "companies_house_profile", (r) => r.company_number === op?.company_number) ?? tool(s, "companies_house_profile");
  const off = tool(s, "companies_house_officer_match");
  const reg = tool(s, "register_checks");
  const pc = tool(s, "locate_postcode");
  const found = !!prem?.found;
  const matched = !!op?.matched && !!ch && !ch.error;
  const status = !prem && !ch ? null : found && matched && ch?.company_status === "active" ? "Verified" : found ? "Premises verified" : "Not found";
  const row = (label: string, value: React.ReactNode, r?: ToolResult) => ({ label, value: r ? <Num r={r}>{value}</Num> : value });
  const rating = String(prem?.rating ?? "");
  return (
    <div data-testid="panel-verify">
      <ProvPanel
        title={String(prem?.business_name ?? ch?.company_name ?? s.pub.trading_name)}
        prov={{ badge: s.pub.identity_badge, meta: { source: "Food Standards Agency hygiene register, Companies House and postcodes.io" } }}
        actions={
          status && (
            <Badge tone={status === "Verified" ? "positive" : "warning"} dot>
              {status}
            </Badge>
          )
        }
      >
        {!prem && !ch ? (
          <Empty>Run the agent to check the public registers.</Empty>
        ) : (
          <div className="space-y-6">
            <div className="grid gap-x-10 md:grid-cols-2">
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wide text-fg-3">Premises · food hygiene register</h3>
                {found ? (
                  <KeyValue
                    rows={[
                      row(
                        "Hygiene rating",
                        <span className="font-display text-lg font-medium" data-testid="hygiene-rating">
                          {/^\d$/.test(rating) ? `${rating} / 5` : rating}
                          {prem?.rating_date ? <span className="ml-2 font-sans text-xs font-normal text-fg-3">inspected {day(String(prem.rating_date), true)}</span> : null}
                        </span>,
                        prem
                      ),
                      row("Premises", String(prem?.address)),
                      row("Type", String(prem?.business_type)),
                      row("Council", String(prem?.local_authority)),
                      row("Location", pc ? `${Number(pc.lat).toFixed(4)}, ${Number(pc.lon).toFixed(4)}` : "—", pc),
                    ]}
                  />
                ) : (
                  <p className="py-3 text-sm text-fg-2">{prem ? String(prem.summary) : "Not checked"}</p>
                )}
              </div>
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wide text-fg-3">Operator · Companies House</h3>
                {matched ? (
                  <KeyValue
                    rows={[
                      row("Company", `${String(ch?.company_name)} · ${String(ch?.company_status)}`),
                      row("Company number", String(op?.company_number), op),
                      row("Incorporated", day(String(ch?.incorporated), true), ch),
                      row("SIC code", (ch?.sic_codes as string[] | undefined)?.join(", ") ?? "—", ch),
                      row("Directors", off ? String(off.summary) : "—"),
                      row(
                        "Control",
                        !reg
                          ? "—"
                          : reg.parent_company
                            ? `Controlled by ${String(reg.parent_company)}`
                            : Number(reg.individual_controllers)
                              ? `${Number(reg.individual_controllers)} ${Number(reg.individual_controllers) === 1 ? "person" : "people"} with significant control`
                              : "None listed on the register"
                      ),
                    ]}
                  />
                ) : (
                  <div className="py-3 text-sm text-fg-2" data-testid="operator-unmatched">
                    <p className="first-letter:uppercase">{op ? String(op.summary) : "Not checked"}</p>
                    {((op?.considered as Considered[] | undefined) ?? []).length > 0 && (
                      <ul className="mt-3 space-y-1 text-xs text-fg-3">
                        {(op?.considered as Considered[]).map((c) => (
                          <li key={c.company_number} className="flex justify-between gap-3">
                            <span className="truncate">{c.name}</span>
                            <span className="shrink-0">{c.why}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-3 text-xs">Know the operator? Add its company number on the first step.</p>
                  </div>
                )}
              </div>
            </div>
            {reg && (
              <div data-testid="register-checks">
                <h3 className="text-xs font-medium uppercase tracking-wide text-fg-3">Register checks</h3>
                <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                  {(reg.checks as RegisterCheck[]).map((c) => (
                    <li key={c.check} className="flex items-start gap-2 text-sm">
                      <Icon name={c.ok ? "check" : "alert"} size={14} className={cx("mt-1 shrink-0", c.ok ? "text-positive" : "text-warning")} />
                      <span>
                        <Num r={reg}>{c.check}</Num>
                        {c.detail && <span className="block text-xs text-fg-3">{c.detail}</span>}
                      </span>
                    </li>
                  ))}
                  <li className="flex items-start gap-2 text-sm">
                    <Icon name="lock" size={14} className="mt-1 shrink-0 text-fg-3" />
                    <Num r={reg}>
                      {Number(reg.charges_outstanding)} outstanding charge{Number(reg.charges_outstanding) === 1 ? "" : "s"} (secured debt)
                    </Num>
                  </li>
                </ul>
              </div>
            )}
            <p className="text-xs text-fg-3">Owner: {s.pub.owner}. Identity is from public registers; the figures on the next screens are our demo books, not this pub’s.</p>
          </div>
        )}
      </ProvPanel>
    </div>
  );
}

const SOURCE_ROWS: { tool: string; name: string; kind: string; icon: Parameters<typeof Icon>[0]["name"] }[] = [
  { tool: "load_takings_history", name: "Till takings", kind: "Demo books · daily takings generated for a pub of this profile", icon: "receipt" },
  { tool: "load_stripe_test_charges", name: "Card payments", kind: "Demo books · takings seeded as Stripe test-mode charges", icon: "receipt" },
  { tool: "load_bank_feed", name: "Bank feed", kind: "Demo books · Open Banking-format transactions", icon: "bank" },
  { tool: "load_weather_history", name: "Weather history", kind: "Open-Meteo archive at the demo books\u2019 site (N4)", icon: "rain" },
  { tool: "weekend_forecast", name: "Weekend forecast", kind: "What was forecast at the time", icon: "rain" },
  { tool: "load_match_and_duty_dates", name: "Match and duty dates", kind: "Fixtures and HMRC duty changes", icon: "calendar" },
  { tool: "check_real_weather_markets", name: "Polymarket", kind: "Read-only price check", icon: "layers" },
];

export function SourcesPanel({ s }: S) {
  return (
    <div data-testid="panel-sources">
      <Panel title="Data sources" actions={<span>Read-only access · books are demo data from test integrations</span>} bodyClassName="p-0">
        <ul className="divide-y divide-line">
          {SOURCE_ROWS.map((row) => {
            const r = tool(s, row.tool);
            return (
              <li key={row.tool} className="flex min-h-16 items-center gap-4 px-6 py-3">
                <Icon name={row.icon} className="shrink-0 text-fg-3" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{row.name}</div>
                  <div className="truncate text-xs text-fg-3">{r?.source ? `${row.kind} · ${r.source}` : row.kind}</div>
                </div>
                <div className="w-[300px] min-w-0 text-right text-sm text-fg-2">
                  {r ? (
                    <Num rid={r.receipt_id} mark={false} className="!whitespace-normal text-right">
                      {r.summary || "no result"}
                    </Num>
                  ) : (
                    "Not read yet"
                  )}
                </div>
                <div className="flex w-[124px] justify-end">
                  <ToolBadge r={r} />
                </div>
              </li>
            );
          })}
          {["Smarkets", "Betfair Exchange"].map((v) => (
            <li key={v} className="flex min-h-16 items-center gap-4 px-6 py-3">
              <Icon name="plug" className="shrink-0 text-fg-3" />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-fg-2">{v}</div>
                <div className="text-xs text-fg-3">UK betting exchange</div>
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

const TH = "py-2 font-medium";

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
    { name: "Rain on a Friday to Sunday afternoon", driver: "Weather", est: e("rain_weekend_gbp_per_mm"), unit: "per mm" },
    { name: "Rain on a weekday afternoon", driver: "Weather", est: e("rain_weekday_gbp_per_mm"), unit: "per mm" },
    { name: "Warmer days", driver: "Weather", est: e("heat_gbp_per_c"), unit: "per °C" },
    { name: "Match days", driver: "Sport", est: e("match_day_gbp"), unit: "per day" },
    { name: "Beer duty rises", driver: "Policy", est: e("duty_rise_gbp_per_day"), unit: "per day" },
  ].filter((r) => r.est);
  return (
    <div data-testid="panel-risks">
      <ProvPanel
        title="What moves your takings"
        prov={provOf(fit)}
        actions={
          <span>
            <Num rid={fit.receipt_id}>R² {Number(fit.r2_holdout).toFixed(3)} held-out</Num> · n = {String(fit.n_holdout)}
          </span>
        }
        bodyClassName="p-0"
      >
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-line text-xs text-fg-3">
              <th className={cx(TH, "px-6")}>Driver</th>
              <th className={cx(TH, "px-4")}>Type</th>
              <th className={cx(TH, "px-4 text-right")}>Effect on takings</th>
              <th className={cx(TH, "px-6 text-right")}>95% interval</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.name}>
                <td className="px-6 py-3 text-sm">{r.name}</td>
                <td className="px-4 py-3 text-sm text-fg-3">{r.driver}</td>
                <td className={cx("px-4 py-3 text-right text-sm", r.est.estimate < 0 ? "text-warning" : "text-positive")}>
                  <Num rid={fit.receipt_id}>
                    {gbp(r.est.estimate, { sign: true })} {r.unit}
                  </Num>
                </td>
                <td className="px-6 py-3 text-right text-sm text-fg-3">
                  {gbp(r.est.ci95[0])} to {gbp(r.est.ci95[1])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-line px-6 py-4 text-sm text-fg-2">
          {exp ? (
            <>
              A {String(exp.wet_scenario_mm)}mm Friday to Sunday afternoon costs about{" "}
              <Num r={exp} className="text-warning">
                {gbp(-Number(exp.loss_wet_day_gbp))}
              </Num>{" "}
              in takings. That is the risk worth covering.
            </>
          ) : (
            "Rain exposure not computed yet."
          )}
        </p>
        <p className="border-t border-line px-6 py-3 text-xs text-fg-3">{String(fit.label)}</p>
      </ProvPanel>
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
      <ProvPanel title="The weekend" prov={provOf(f)} actions={<span>{s.scenario.name}</span>}>
        {!f || f.badge === "ERROR" ? (
          <Empty>No forecast available for this run.</Empty>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(days).map(([d, v]) => {
              const c = contracts.find((x) => x.date === d);
              return (
                <div key={d} className="rounded bg-surface-2 px-4 py-3">
                  <div className="flex items-baseline justify-between text-xs text-fg-3">
                    <span className="text-fg-2">{day(d)}</span>
                    <span>afternoon</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 font-display text-xl font-medium">
                    <Icon name="rain" size={16} className={v.mm >= 1 ? "text-fg-2" : "text-fg-3"} />
                    <Num rid={f.receipt_id}>{v.mm.toFixed(1)} mm</Num>
                  </div>
                  {c && (
                    <div className="mt-1 text-xs text-fg-3">
                      P(≥3mm) <Num r={prices}>{pct(c.model_prob, 0)}</Num> · ask {c.ask.toFixed(2)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-3 text-xs text-fg-3">{String(f?.grid_note ?? f?.source ?? "")}</p>
      </ProvPanel>
    </div>
  );
}

// ---------- Cashflow: the failure that hurts ----------

type CashRow = { key: string; date: string; t?: number; wet?: number; covered?: number; dry?: number };

/** The cash path, one point per cash event: wet and wet-with-cover from size_hedges, dry from the dry payroll projection. */
function cashRows(s: AppState): CashRow[] {
  const wet = payroll(s, "wet");
  const dry = payroll(s, "dry");
  const dryById = new Map((dry?.timeline ?? []).map((r) => [r.id, r.balance_gbp]));
  const sized = (tool(s, "size_hedges")?.timeline ?? []) as { date: string; id: string; wet_gbp: number; wet_with_hedge_gbp: number }[];
  if (sized.length) return sized.map((r) => ({ key: r.id, date: r.date, wet: r.wet_gbp, covered: r.wet_with_hedge_gbp, dry: dryById.get(r.id) }));
  return (wet?.timeline ?? []).map((r) => ({ key: r.id, date: r.date, wet: r.balance_gbp, dry: dryById.get(r.id) }));
}

/** The payroll week that matters: the last four days, ending on the payday low; the y-range fits the last three days so the gap shows. */
function payrollWindow(rows: CashRow[]) {
  const dates = Array.from(new Set(rows.map((r) => r.date))).sort();
  if (dates.length === 0) return { rows, domain: undefined as [number, number] | undefined, ticks: undefined as number[] | undefined, days: [] as string[] };
  const lastDay = dates[dates.length - 1];
  const payday = rows.filter((r) => r.date === lastDay).reduce((lo, r) => ((r.wet ?? Infinity) < (lo.wet ?? Infinity) ? r : lo));
  const end = rows.indexOf(payday);
  const win = rows.slice(0, end + 1).filter((r) => r.date >= dates[Math.max(0, dates.length - 4)]);
  const fit = win.filter((r) => r.date >= dates[Math.max(0, dates.length - 3)]);
  const vals = fit.flatMap((r) => [r.wet, r.covered, r.dry]).filter((v): v is number => typeof v === "number");
  const hi = Math.max(0, ...vals);
  const lo = Math.min(0, ...vals);
  const step = niceStep((hi - lo) / 4);
  // x is time: day number plus the event's place within its day, so a busy Tuesday does not take half the axis.
  const days = Array.from(new Set(win.map((r) => r.date)));
  const timed = win.map((r) => {
    const same = rows.filter((x) => x.date === r.date);
    return { ...r, t: days.indexOf(r.date) + same.indexOf(r) / same.length };
  });
  const domain: [number, number] = [lo - (hi - lo) * 0.15, Math.ceil(hi / step) * step];
  const ticks: number[] = [];
  for (let v = Math.ceil(domain[0] / step) * step; v <= domain[1]; v += step) ticks.push(v);
  return { rows: timed, domain, ticks, days };
}

function niceStep(raw: number) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= raw) ?? 10 * p;
}

const LINE_NAME: Record<string, string> = { wet: "Wet, no cover", dry: "Dry weekend", covered: "Wet, with cover" };
const endNote = (v: number) => (v >= 0 ? `${gbp(v)} to spare` : `${gbp(-v)} short`);

export function CashflowPanel({ s, compact }: S & { compact?: boolean }) {
  const wet = payroll(s, "wet");
  const dry = payroll(s, "dry");
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  const { rows: data, domain, ticks: yTicks, days } = payrollWindow(cashRows(s));
  const last = data[data.length - 1];
  const hasCover = data.some((r) => typeof r.covered === "number");
  const dayAt = (t: unknown) => day(days[Math.floor(Number(t))]);
  return (
    <div data-testid="panel-cashflow" className="flex min-h-0 flex-col">
      <ProvPanel
        title="Payroll week after a wet weekend"
        prov={provOf(wet)}
        actions={
          <>
            <Legend color="var(--warning)" label="Wet, no cover" />
            {hasCover && <Legend color="var(--accent)" label="Wet, with cover" />}
            <Legend color="var(--fg-3)" label="Dry weekend" dashed />
          </>
        }
      >
        {!wet ? (
          <Empty>Run the agent to project payroll.</Empty>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-y-3 divide-line sm:grid-cols-4 sm:gap-y-0 sm:divide-x">
              {[
                { l: "First day overdrawn", v: day(wet.first_negative_date), rid: wet.receipt_id, c: wet.first_negative_date ? "text-warning" : undefined },
                { l: "Payroll due", v: day(wet.payroll_date), rid: wet.receipt_id },
                { l: "Short on payroll day, wet", v: gbp(-wet.shortfall_gbp, { pence: true }), rid: wet.receipt_id, c: wet.shortfall_gbp > 0 ? "text-warning" : undefined },
                { l: "Short on payroll day, dry", v: dry ? gbp(-dry.shortfall_gbp, { pence: true }) : "—", rid: dry?.receipt_id, c: dry && dry.shortfall_gbp > 0 ? "text-warning" : undefined },
              ].map((m) => (
                <div key={m.l} className="pr-4 sm:px-4 sm:first:pl-0 sm:last:pr-0">
                  <div className="text-xs text-fg-3">{m.l}</div>
                  <Num rid={m.rid} className={cx("font-display text-lg font-medium", m.c)}>
                    {m.v}
                  </Num>
                </div>
              ))}
            </div>
            <p className="mt-4 text-sm text-fg-2">
              {wet.payroll_clears
                ? "Payroll clears in both cases."
                : `The account goes overdrawn on ${day(wet.first_negative_date)} when rent, suppliers and the VAT sweep land, and payroll on ${day(
                    wet.payroll_date
                  )} doesn’t clear. A wet weekend makes it ${gbp(o?.wet_extra_shortfall_gbp ?? wet.shortfall_gbp - (dry?.shortfall_gbp ?? 0))} worse.`}
            </p>
            <div className={cx("mt-3", compact ? "h-[200px]" : "h-[260px]")} role="img" aria-label="Cash balance from the rent and supplier run to payday: dry weekend, wet weekend, wet weekend with cover">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 16, right: 120, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} strokeDasharray="2 4" />
                  <XAxis dataKey="t" type="number" domain={[0, "dataMax"]} ticks={days.map((_, i) => i)} padding={{ left: 24 }} tickLine={false} axisLine={false} tickFormatter={dayAt} />
                  <YAxis tickLine={false} axisLine={false} width={80} tickFormatter={money} domain={domain ?? ["auto", "auto"]} ticks={yTicks} allowDataOverflow />
                  {domain && <ReferenceArea y1={domain[0]} y2={0} fill="var(--warning)" fillOpacity={0.07} stroke="none" ifOverflow="hidden" />}
                  <ReferenceLine y={0} stroke="var(--fg-2)" strokeWidth={1.5} label={{ value: "Payroll line", position: "insideBottomLeft", fill: "var(--fg-2)", fontSize: 12 }} />
                  {last && <ReferenceLine x={last.t} stroke="var(--fg-3)" strokeDasharray="3 3" label={{ value: "Payday", position: "insideTopRight", fill: "var(--fg-3)", fontSize: 12 }} />}
                  <Tooltip {...tooltipStyle} labelFormatter={dayAt} formatter={(v, n) => [gbp(Number(v), { pence: true }), LINE_NAME[String(n)] ?? String(n)]} />
                  <Line type="stepAfter" dataKey="dry" stroke="var(--fg-3)" strokeWidth={1.25} strokeDasharray="4 3" dot={false} connectNulls isAnimationActive={false} />
                  <Line type="stepAfter" dataKey="wet" stroke="var(--warning)" strokeWidth={1.75} dot={false} connectNulls isAnimationActive={false} />
                  {hasCover && <Line type="stepAfter" dataKey="covered" stroke="var(--accent)" strokeWidth={2.75} dot={false} connectNulls isAnimationActive={false} />}
                  {typeof last?.wet === "number" && (
                    <ReferenceDot x={last.t} y={last.wet} r={3.5} fill="var(--warning)" stroke="none" label={{ value: endNote(last.wet), position: "right", dy: 10, fill: "var(--warning)", fontSize: 12 }} />
                  )}
                  {typeof last?.covered === "number" && (
                    <ReferenceDot x={last.t} y={last.covered} r={4} fill="var(--accent)" stroke="none" label={{ value: endNote(last.covered), position: "right", dy: -10, fill: "var(--accent)", fontSize: 12 }} />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
        {o && <OutcomesTable o={o} rid={sized?.receipt_id} />}
        <SyntheticNote s={s} className="mt-6 border-t border-line pt-3" />
      </ProvPanel>
    </div>
  );
}

// ---------- Payday: three bars either side of the payroll line ----------

/** The lead picture: lowest balance before payroll on payday, dry, wet and wet with cover, from one £0 line. */
export function PaydayPanel({ s }: S) {
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  if (!hasBridge(o)) return null;
  const rid = sized?.receipt_id;
  const rows = [
    { l: "Dry weekend", v: o.dry_no_hedge_headroom_gbp, bar: "bg-surface-3 shadow-[inset_0_0_0_1px_var(--line-strong)]", ink: "text-fg" },
    { l: "Wet weekend, no cover", v: o.wet_no_hedge_headroom_gbp, bar: o.wet_no_hedge_headroom_gbp < 0 ? "bg-warning" : "bg-surface-3", ink: o.wet_no_hedge_headroom_gbp < 0 ? "text-warning" : "text-fg" },
    { l: "Wet weekend, with cover", v: o.wet_with_hedge_headroom_gbp, bar: o.wet_with_hedge_headroom_gbp >= 0 ? "bg-accent" : "bg-warning", ink: o.wet_with_hedge_headroom_gbp >= 0 ? "text-positive" : "text-warning" },
  ];
  const max = 1.15 * Math.max(...rows.map((r) => Math.abs(r.v)), 1);
  const w = (v: number) => (Math.abs(v) / max) * 50;
  return (
    <div data-testid="panel-payday">
      <ProvPanel title={`Payday, ${day(o.payroll_date)}`} prov={provOf(sized)} actions={<span>Lowest balance before payroll</span>}>
        <div className="grid gap-x-4 sm:grid-cols-[12rem_minmax(0,1fr)]" role="img" aria-label="Payday balance after payroll: dry weekend, wet weekend without cover, wet weekend with cover">
          <div className="hidden flex-col gap-3 sm:flex">
            {rows.map((r, i) => (
              <span key={r.l} className={cx("flex h-14 items-center text-sm", i === 2 ? "font-medium text-fg" : "text-fg-2")}>
                {r.l}
              </span>
            ))}
          </div>
          <div className="relative flex flex-col gap-3 pb-6">
            {rows.map((r, i) => (
              <div key={r.l}>
                <div className="mb-1 flex items-baseline justify-between gap-3 sm:hidden">
                  <span className={cx("text-sm", i === 2 ? "font-medium text-fg" : "text-fg-2")}>{r.l}</span>
                  <Num rid={rid} className={cx("font-display text-md font-medium", r.ink)}>
                    {endNote(r.v)}
                  </Num>
                </div>
              <div className="relative h-8 sm:h-14">
                <div aria-hidden className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-fg-2 sm:hidden" />
                <div
                  className={cx("pd-bar absolute inset-y-0 rounded", r.bar)}
                  style={{
                    ...(r.v >= 0 ? { left: "50%", transformOrigin: "left center" } : { right: "50%", transformOrigin: "right center" }),
                    width: `${w(r.v)}%`,
                    ["--i" as string]: i,
                  }}
                />
                {/* A long bar carries its figure inside its end; a short one beside it. */}
                <div
                  className={cx(
                    "absolute inset-y-0 hidden items-center whitespace-nowrap px-4 font-display text-xl font-medium sm:flex",
                    w(r.v) > 25 ? (r.bar.startsWith("bg-surface") ? "text-fg" : "text-accent-ink") : r.ink
                  )}
                  style={
                    w(r.v) > 25
                      ? r.v >= 0
                        ? { right: `${50 - w(r.v)}%` }
                        : { left: `${50 - w(r.v)}%` }
                      : r.v >= 0
                        ? { left: `${50 + w(r.v)}%` }
                        : { right: `${50 + w(r.v)}%` }
                  }
                >
                  <Num rid={rid}>{endNote(r.v)}</Num>
                </div>
              </div>
              </div>
            ))}
            <div aria-hidden className="absolute bottom-6 left-1/2 top-0 hidden w-0.5 -translate-x-1/2 bg-fg-2 sm:block" />
            <span className="absolute bottom-0 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs text-fg-2">Payroll line</span>
          </div>
        </div>
      </ProvPanel>
    </div>
  );
}

// ---------- The payroll bridge: dry, what rain takes, what cover does ----------

type Bridge = Outcomes & Required<Pick<Outcomes, "dry_no_hedge_headroom_gbp" | "wet_no_hedge_headroom_gbp" | "wet_with_hedge_headroom_gbp" | "wet_extra_shortfall_gbp">>;
export const hasBridge = (o?: Outcomes): o is Bridge =>
  !!o && [o.dry_no_hedge_headroom_gbp, o.wet_no_hedge_headroom_gbp, o.wet_with_hedge_headroom_gbp, o.wet_extra_shortfall_gbp, o.hedge_payout_if_wet_gbp, o.hedge_cost_gbp].every((v) => typeof v === "number");

/** A waterfall from the size_hedges outcomes: each bar starts where the last ended; totals stand on the payroll line. */
export function PayrollBridge({ s }: S) {
  const sized = tool(s, "size_hedges");
  const o = sized?.outcomes as Outcomes | undefined;
  if (!hasBridge(o)) return null;
  const rid = sized?.receipt_id;
  const steps: { l: string; v: number; total?: boolean; tone: "muted" | "warning" | "accent" }[] = [
    { l: o.dry_no_hedge_headroom_gbp >= 0 ? "Dry weekend: payroll clears" : "Dry weekend: payroll short", v: o.dry_no_hedge_headroom_gbp, total: true, tone: "muted" },
    { l: "Rain takes", v: -o.wet_extra_shortfall_gbp, tone: "warning" },
    { l: "Wet, no cover", v: o.wet_no_hedge_headroom_gbp, total: true, tone: o.wet_no_hedge_headroom_gbp < 0 ? "warning" : "muted" },
    { l: "Cover pays", v: o.hedge_payout_if_wet_gbp, tone: "accent" },
    { l: "Cover costs", v: -o.hedge_cost_gbp, tone: "muted" },
    { l: "Wet, with cover", v: o.wet_with_hedge_headroom_gbp, total: true, tone: o.wet_with_hedge_headroom_gbp >= 0 ? "accent" : "warning" },
  ];
  // Totals are the API's own; a step starts at the total before it.
  let level = 0;
  const bars = steps.map((st) => {
    const from = st.total ? 0 : level;
    const to = st.total ? st.v : level + st.v;
    level = to;
    return { ...st, from, to, end: to };
  });
  const all = bars.flatMap((b) => [b.from, b.to, 0]);
  const pad = (Math.max(...all) - Math.min(...all)) * 0.16;
  const top = Math.max(...all) + pad;
  const bottom = Math.min(...all) - pad;
  const y = (v: number) => ((top - v) / (top - bottom)) * 100;
  const fill = {
    muted: "bg-surface-3 shadow-[inset_0_0_0_1px_var(--line-strong)]",
    warning: "bg-warning-wash shadow-[inset_0_0_0_1px_var(--warning-edge)]",
    accent: "bg-accent-wash shadow-[inset_0_0_0_1px_var(--accent-edge)]",
  };
  const solid = { muted: fill.muted, warning: "bg-warning", accent: "bg-accent" };
  const ink = { muted: "text-fg", warning: "text-warning", accent: "text-positive" };
  return (
    <div data-testid="panel-bridge">
      <ProvPanel title="How the cover gets you there" prov={provOf(sized)}>
        <div className="relative h-[260px]" role="img" aria-label="Waterfall: dry weekend headroom, what rain takes, wet without cover, what cover pays and costs, wet with cover">
          <div className="absolute inset-x-0 bottom-0 bg-warning-wash" style={{ top: `${y(0)}%` }} aria-hidden />
          <div className="absolute inset-x-0 grid h-full grid-cols-6">
            {bars.map((b, i) => {
              const hi = Math.max(b.from, b.to);
              const lo = Math.min(b.from, b.to);
              const h = y(lo) - y(hi);
              const origin = h > 0 ? ((y(b.total ? 0 : b.from) - y(hi)) / h) * 100 : 50;
              return (
                <div key={b.l} className="relative h-full">
                  <div
                    className={cx("wf-bar absolute inset-x-[22%] rounded", b.total ? solid[b.tone] : fill[b.tone])}
                    style={{ top: `${y(hi)}%`, height: `${h}%`, transformOrigin: `50% ${origin}%`, ["--i" as string]: i }}
                  />
                  {i < bars.length - 1 && <div aria-hidden className="absolute left-[78%] right-[-22%] border-t border-dashed border-line-strong" style={{ top: `${y(b.end)}%` }} />}
                  <div
                    className={cx("absolute inset-x-0 text-center text-sm font-medium", ink[b.tone], b.v >= 0 ? "-translate-y-full pb-1" : "pt-1")}
                    style={{ top: `${b.v >= 0 ? y(hi) : y(lo)}%` }}
                  >
                    <Num rid={rid}>{b.total ? gbp(b.v) : gbp(b.v, { sign: true })}</Num>
                  </div>
                </div>
              );
            })}
          </div>
          <div aria-hidden className="absolute inset-x-0 h-0.5 bg-fg-2" style={{ top: `${y(0)}%` }} />
          <span className="absolute left-0 pt-1 text-xs text-fg-2" style={{ top: `${y(0)}%` }}>
            Payroll line
          </span>
        </div>
        <div className="mt-3 grid grid-cols-6 border-t border-line pt-2">
          {bars.map((b) => (
            <span key={b.l} className="px-2 text-center text-xs text-fg-3">
              {b.l}
            </span>
          ))}
        </div>
        <OutcomesTable o={o} rid={rid} />
        <SyntheticNote s={s} className="mt-6 border-t border-line pt-3" />
      </ProvPanel>
    </div>
  );
}

/** Payroll headroom both ways: positive clears with that much to spare, negative is short. Older API results carry the shortfall only. */
function headroom(v: number | undefined, shortfall: number) {
  if (typeof v !== "number") return shortfall > 0 ? { text: `${gbp(shortfall, { pence: true })} short`, tone: "text-warning" } : { text: "Clears", tone: "text-positive" };
  return v >= 0 ? { text: `Clears, ${gbp(v, { pence: true })} to spare`, tone: "text-positive" } : { text: `${gbp(-v, { pence: true })} short`, tone: "text-warning" };
}

export function OutcomesTable({ o, rid }: { o: Outcomes; rid?: string }) {
  const cell = (v: number | undefined, shortfall: number) => {
    const h = headroom(v, shortfall);
    return (
      <td className={cx("whitespace-nowrap px-4 py-3 text-right text-sm", h.tone)}>
        <Num rid={rid}>{h.text}</Num>
      </td>
    );
  };
  const closes = typeof o.wet_with_hedge_headroom_gbp === "number" ? o.wet_with_hedge_headroom_gbp >= 0 : o.wet_with_hedge_shortfall_gbp <= 0;
  return (
    <div className="mt-6" data-testid="outcomes">
      <h3 className="font-sans text-sm font-medium tracking-normal text-fg">What the hedge does to payroll on {day(o.payroll_date)}</h3>
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <table className="mt-2 w-full min-w-[34rem]">
        <thead>
          <tr className="border-b border-line text-xs text-fg-3">
            <th className={cx(TH, "pr-4 text-left")}>Weekend</th>
            <th className={cx(TH, "px-4 text-right")}>Without hedge</th>
            <th className={cx(TH, "px-4 text-right")}>With hedge</th>
            <th className={cx(TH, "pl-4 text-left")}>Why</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          <tr>
            <td className="py-3 pr-4 text-sm">Wet</td>
            {cell(o.wet_no_hedge_headroom_gbp, o.wet_no_hedge_shortfall_gbp)}
            {cell(o.wet_with_hedge_headroom_gbp, o.wet_with_hedge_shortfall_gbp)}
            <td className="py-3 pl-4 text-sm text-fg-2">
              Pays <Num rid={rid}>{gbp(o.hedge_payout_if_wet_gbp, { pence: true })}</Num>. {closes ? "Closes the gap." : "Narrows the gap, doesn’t close it."}
            </td>
          </tr>
          <tr>
            <td className="py-3 pr-4 text-sm">Dry</td>
            {cell(o.dry_no_hedge_headroom_gbp, o.dry_no_hedge_shortfall_gbp)}
            {cell(o.dry_with_hedge_headroom_gbp, o.dry_with_hedge_shortfall_gbp)}
            <td className="py-3 pl-4 text-sm text-fg-2">
              Expires worthless. The <Num rid={rid}>{gbp(o.hedge_cost_gbp, { pence: true })}</Num> is lost.
            </td>
          </tr>
        </tbody>
      </table>
      </div>
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
      <ProvPanel
        title="Weekly cash after costs · backtest on held-out months"
        prov={{ badge: "SYNTHETIC", meta: btMeta(s) }}
        actions={
          <>
            <Legend color="var(--accent)" label="With Pub Hedge" />
            <Legend color="var(--fg-3)" label="Without" dashed />
          </>
        }
      >
        <div className="h-[200px]" role="img" aria-label="Weekly cash after costs, with and without Pub Hedge">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} strokeDasharray="2 4" />
              <XAxis dataKey="start" tickLine={false} axisLine={false} interval={12} tickFormatter={(d: string) => new Date(d).toLocaleDateString("en-GB", { month: "short", year: "2-digit" })} />
              <YAxis tickLine={false} axisLine={false} width={80} tickFormatter={money} />
              <ReferenceLine y={0} stroke="var(--fg-3)" strokeDasharray="4 4" strokeOpacity={0.5} />
              <Tooltip {...tooltipStyle} labelFormatter={(d) => `Week of ${day(String(d), true)}`} formatter={(v, n) => [money(v), n === "ours" ? "With Pub Hedge" : "Without"]} />
              <Line type="monotone" dataKey="none" stroke="var(--fg-3)" strokeWidth={1.25} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="ours" stroke="var(--accent)" strokeWidth={1.75} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-3 text-sm text-fg-2">
          Weeks below zero over {none.length} held-out weeks: {shortNone} without cover, {shortOurs} with it. The two lines sit almost on top of each other.
        </p>
      </ProvPanel>
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
      <ProvPanel
        title="Backtest"
        prov={{ badge: "SYNTHETIC", meta: btMeta(s) }}
        actions={
          <span>
            {s.backtest.setup.pubs} pubs · {s.backtest.setup.bootstrap}
          </span>
        }
        bodyClassName="p-0"
      >
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-line text-xs text-fg-3">
              <th className={cx(TH, "px-6")}>Policy</th>
              {cols.map((c, i) => (
                <th key={c.k} className={cx(TH, "text-right", i === cols.length - 1 ? "px-6" : "px-4")}>
                  {c.l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(Object.keys(POLICY_LABEL) as (keyof typeof p)[]).map((k) =>
              p[k] ? (
                <tr key={k}>
                  <td className={cx("px-6 py-3 text-sm", k === "ours" ? "font-medium text-accent" : "text-fg")}>{POLICY_LABEL[k]}</td>
                  {cols.map((c, i) => (
                    <td key={c.k} className={cx("py-3 text-right", i === cols.length - 1 ? "px-6" : "px-4")}>
                      <div className="text-sm">{c.f(p[k].point[c.k])}</div>
                      <div className="text-xs text-fg-3">
                        {c.f(p[k].ci95[c.k][0])} to {c.f(p[k].ci95[c.k][1])}
                      </div>
                    </td>
                  ))}
                </tr>
              ) : null
            )}
          </tbody>
        </table>
        <p className="border-t border-line px-6 py-4 text-sm text-fg-2" data-testid="backtest-honest">
          {Math.abs(ours.shortfall_weeks_per_year - none.shortfall_weeks_per_year) < 0.05
            ? `At these caps, Pub Hedge does not reduce the number of weeks a pub can’t cover its costs: ${ours.shortfall_weeks_per_year.toFixed(1)} a year with or without it.`
            : `Weeks short: ${none.shortfall_weeks_per_year.toFixed(1)} a year without cover, ${ours.shortfall_weeks_per_year.toFixed(1)} with it.`}{" "}
          It costs about {gbp(-ours.hedge_net_gbp_per_year)} a pub-year net, against {gbp(-naive.hedge_net_gbp_per_year)} for naive daily cover. Raising the caps five-fold
          doesn’t help either. Intervals are 95% bootstrap. Held-out {s.backtest.setup.test[0]} to {s.backtest.setup.test[1]}.
        </p>
      </ProvPanel>
    </div>
  );
}

// ---------- Recommendation ----------

/** A ruled tally of figures: label over figure, hairlines between. */
export function Tally({ items, rid, r }: { items: { l: string; v: string; c?: string }[]; rid?: string; r?: ToolResult }) {
  return (
    <div className="grid grid-flow-col divide-x divide-line" style={{ gridAutoColumns: "minmax(0, 1fr)" }}>
      {items.map((x) => (
        <div key={x.l} className="px-4 first:pl-0 last:pr-0">
          <div className="text-xs text-fg-3">{x.l}</div>
          <Num rid={rid} r={r} className={cx("font-display text-lg font-medium", x.c)}>
            {x.v}
          </Num>
        </div>
      ))}
    </div>
  );
}

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
          {rat && (
            <div className="mt-3">
              <Bullets text={rat.text} />
            </div>
          )}
        </Panel>
      </div>
    );
  const m = p.market;
  const cost = p.cost_pence / 100;
  return (
    <div data-testid="panel-recommendation">
      <ProvPanel
        title={`Rain cover, ${day(m.date)}`}
        prov={{
          badge: m.price_badge,
          meta: { source: "Synthetic rain contract", method: m.rule, label: "No London rain market exists on Polymarket, so this contract is priced from calibrated forecasts" },
          receiptId: sized?.receipt_id,
        }}
      >
        <div className="text-xs text-fg-3">Pays out if</div>
        <p className="mt-1 text-md">At least 3mm of rain falls on the afternoon of {day(m.date, true)} at the grid cell nearest {s.pub.postcode}.</p>

        <div className="mt-6">
          <Tally
            rid={sized?.receipt_id}
            items={[
              { l: "Cost", v: gbp(cost, { pence: true }) },
              { l: "Pays if wet", v: gbp(m.payout_if_event_gbp, { pence: true }), c: "text-positive" },
              { l: "Max loss", v: gbp(cost, { pence: true }), c: "text-warning" },
              { l: "Shares", v: String(p.shares) },
            ]}
          />
        </div>

        {rat && (
          <>
            <h3 className="mt-6 flex items-center gap-2 font-sans text-sm font-medium tracking-normal text-fg-2">
              Why it was suggested
              {rat.model && <ModelChip model={rat.model} />}
              <ProvBadge badge={rat.badge} receiptId={rat.receipt_id} variant="label" />
            </h3>
            <div className="mt-2" data-testid="rationale">
              <Bullets text={rat.text} />
            </div>
          </>
        )}

        <h3 className="mt-6 font-sans text-sm font-medium tracking-normal text-fg-2">How it was calculated</h3>
        <dl className="mt-2 rounded bg-surface-2 px-4 py-3 text-sm leading-6">
          <CalcRow k="Forecast" v={`${m.forecast_mm.toFixed(1)} mm`} />
          <CalcRow k="P(rain ≥ 3mm)" v={`${pct(m.model_prob)} (calibrated on archived forecasts)`} />
          <CalcRow k="Ask" v={`${m.ask.toFixed(4)} → ${m.cost_per_share.toFixed(4)} a share all in (1% slippage + taker fee ${m.fee_rate} × p × (1 − p))`} />
          <CalcRow k="Pricing rule" v={m.rule} />
          {noValue.length > 0 && <CalcRow k="Not proposed" v={`${noValue.join(", ")}: no value at the price`} />}
        </dl>
        {pricer && (
          <p className="mt-3 flex items-start gap-2 text-xs text-fg-3">
            <span className="flex-1">{pricer.text}</span>
            <ProvBadge badge={pricer.badge} receiptId={pricer.receipt_id} variant="label" />
          </p>
        )}
      </ProvPanel>
    </div>
  );
}

function CalcRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-3">
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
    <div
      className="flex items-center gap-2 rounded px-3 py-2 text-xs font-medium text-accent shadow-[inset_0_0_0_1px_var(--accent-edge)]"
      data-testid="paper-banner"
    >
      <Icon name="lock" size={14} />
      PAPER TRADING — no real orders
      <span className="ml-auto">
        <ProvBadge badge="PAPER" meta={{ source: "Paper execution against synthetic prices. Nothing is sent to any venue." }} />
      </span>
    </div>
  );
}

const STATUS_TONE = { pending: "warning", blocked: "negative", filled: "positive", rejected: "neutral", expired: "neutral", settled: "positive" } as const;
const until = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });

export function ApprovalCard({ s, p, onChange }: S & { p?: Proposal; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [needsSecond, setNeedsSecond] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [fill, setFill] = useState<Record<string, unknown> | null>(null);
  const [blockReceipt, setBlockReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState("");
  const [awaiting, setAwaiting] = useState("");

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
      <ProvPanel
        title="Needs approval"
        prov={{ badge: "PAPER", meta: { source: "Paper trading. Limits are enforced in code by the API before any fill." }, receiptId: p.receipt_id }}
        actions={
          <Badge tone={STATUS_TONE[p.status]} dot>
            <span data-testid={`status-${p.id}`}>{p.status}</span>
          </Badge>
        }
      >
        <PaperBanner />
        <div className="mt-4 flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-medium">{proposalTitle(p)}</div>
            <div className="mt-0.5 text-xs text-fg-3">
              <span className="break-all font-mono">{p.market.market_id}</span> · {p.shares} shares at {p.market.cost_per_share.toFixed(4)}
            </div>
          </div>
          <div className="text-right">
            <Num r={tool(s, "size_hedges")} className="font-display text-lg font-medium">
              {gbp(cost, { pence: true })}
            </Num>
            <div className="text-xs text-fg-3">pays {gbp(p.market.payout_if_event_gbp, { pence: true })}</div>
          </div>
        </div>

        <ul className="mt-4 divide-y divide-line border-y border-line text-sm" data-testid="limit-checks">
          {checks.map((c) => (
            <li key={c.name} className="flex h-10 items-center justify-between" data-testid={`check-${c.name}`}>
              <span className="text-fg-2">{CHECK_LABEL[c.name] ?? c.name}</span>
              <span className="flex items-center gap-2">
                {pence(c.value_pence)} <span className="text-fg-3">of {pence(c.cap_pence)}</span>
                <span className={c.pass ? "text-positive" : "text-warning"}>
                  <Icon name={c.pass ? "check" : "x"} size={14} />
                </span>
              </span>
            </li>
          ))}
          <li className="flex h-10 items-center justify-between">
            <span className="text-fg-2">Second approval over {pence(s.limits.approval_threshold_pence)}</span>
            <span>{p.cost_pence > s.limits.approval_threshold_pence ? "Needed" : "Not needed"}</span>
          </li>
        </ul>

        {p.status === "blocked" && (
          <p className="mt-4 flex items-start gap-2 rounded px-3 py-2 text-sm text-warning shadow-[inset_0_0_0_1px_var(--warning-edge)]">
            <Icon name="alert" size={14} className="mt-1 shrink-0" />
            <span>
              Blocked by your limits: <span data-testid="blocked-reason">{p.reason}</span>
            </span>
          </p>
        )}
        {p.status === "filled" && (
          <p className="mt-4 rounded px-3 py-2 text-sm text-positive shadow-[inset_0_0_0_1px_var(--accent-edge)]" data-testid="filled-note">
            Paper fill: {String(fill?.shares ?? p.shares)} shares
            {fill?.fill_price ? ` at ${Number(fill.fill_price).toFixed(4)}` : ""}
            {fill?.cost_gbp ? `, ${gbp(Number(fill.cost_gbp), { pence: true })}` : ""}. {String(fill?.note ?? "No real order was placed.")}
          </p>
        )}
        {p.status === "filled" && (
          <div className="mt-3 flex items-center gap-3">
            <Button
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  const r = await settle(p.id);
                  setAwaiting(r.status === "awaiting" ? `No result yet: ${r.reason}.` : "");
                  onChange();
                } catch (e) {
                  setError(String(e));
                } finally {
                  setBusy(false);
                }
              }}
              disabled={busy}
              data-testid={`settle-${p.id}`}
            >
              {busy && <Spinner size={12} />}
              Check result
            </Button>
            {awaiting && <span className="text-xs text-fg-3">{awaiting}</span>}
          </div>
        )}
        {p.status === "settled" && p.market.settlement && (
          <p className="mt-4 rounded px-3 py-2 text-sm shadow-[inset_0_0_0_1px_var(--accent-edge)]" data-testid="settled-note">
            <span className={p.market.settlement.event_happened ? "text-positive" : "text-fg"}>
              {p.market.settlement.event_happened
                ? `Paid ${gbp(p.market.settlement.payout_gbp, { pence: true })}, ${gbp(p.market.settlement.net_gbp, { pence: true, sign: true })} after its cost.`
                : `Didn’t pay. The ${gbp(p.market.settlement.cost_gbp, { pence: true })} it cost is the loss.`}
            </span>{" "}
            <span className="text-fg-2">{p.market.settlement.evidence}.</span>
          </p>
        )}
        {p.status === "rejected" && <p className="mt-4 text-sm text-fg-2">You declined this. It won’t be placed.</p>}
        {p.status === "expired" && (
          <p className="mt-4 text-sm text-fg-2" data-testid="expired-note">
            Expired: {p.reason}.{p.market.kind !== "offer" && " Run the agent again for a fresh price."}
          </p>
        )}
        {error && <p className="mt-4 text-sm text-negative">{error}</p>}

        {p.status === "pending" && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {needsSecond ? (
              <>
                <Button variant="primary" onClick={() => go(true)} disabled={busy} data-testid={`confirm-second-${p.id}`}>
                  {busy && <Spinner size={12} />}
                  Yes, place {gbp(cost, { pence: true })} on paper
                </Button>
                <Button onClick={() => setNeedsSecond(false)} disabled={busy}>
                  Cancel
                </Button>
                <span className="text-xs text-warning">Over {pence(s.limits.approval_threshold_pence)}, so it needs a second confirm.</span>
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
                <span className="text-xs text-fg-3">
                  {p.market.kind === "offer" ? `If ${p.market.team ?? "England"} don’t lose` : "If it stays dry"} you lose {gbp(cost, { pence: true })}.
                  {p.market.expires_at && <span data-testid="valid-until"> Valid until {until(p.market.expires_at)}.</span>}
                </span>
              </>
            )}
          </div>
        )}
      </ProvPanel>
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
      <ProvPanel title="Limits" prov={{ badge: "PAPER", meta: { source: "Enforced by the API on every approval. Lowering a cap re-checks pending cover at once." } }}>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          {LIMIT_FIELDS.map((f) => (
            <label key={f.k} className="block">
              <span className="text-xs text-fg-2">{f.l}</span>
              <div className="field mt-1 flex h-10 items-center px-3">
                <span className="text-sm text-fg-3">£</span>
                <input
                  data-testid={f.id}
                  inputMode="decimal"
                  value={form[f.k]}
                  onChange={(e) => setForm({ ...form, [f.k]: e.target.value })}
                  className="ml-1 w-full bg-transparent text-sm text-fg"
                />
              </div>
            </label>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="primary" size="sm" onClick={save} disabled={saving || invalid} data-testid="limits-save">
            {saving && <Spinner size={12} />}
            Save limits
          </Button>
          <span className="text-xs text-fg-3">
            Spent this week {pence(s.ledger.spent_this_week_pence)} · at risk this month {pence(s.ledger.at_risk_this_month_pence)}
          </span>
        </div>
        {invalid && <p className="mt-2 text-xs text-negative">Enter amounts in pounds, like 30 or 30.50.</p>}
        {error && <p className="mt-2 text-xs text-negative">{error}</p>}
        {result && (
          <p className="mt-2 text-xs text-fg-2" data-testid="limits-result">
            {result.length === 0
              ? "Saved. Nothing pending breaks the new limits."
              : result.map((b) => (
                  <span key={b.id} className="block text-warning">
                    Blocked {b.id}: <Num rid={b.receipt_id} className="text-left !whitespace-normal">{b.reason}</Num>
                  </span>
                ))}
          </p>
        )}
      </ProvPanel>
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
        <li key={r.seq} className="grid grid-cols-[4.5rem_5rem_minmax(0,1fr)_auto] items-center gap-3 py-2">
          <span className="text-xs text-fg-3">
            {new Date(r.ts * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
          <span className="truncate text-xs text-fg-3">{r.step}</span>
          <span className="min-w-0 truncate">
            <Num rid={r.receipt_id} mark={false} className="text-left font-mono text-xs text-fg-2">
              {r.call}
            </Num>
          </span>
          <ProvBadge badge={r.badge} receiptId={r.receipt_id} />
        </li>
      ))}
    </ul>
  );
}

const kickoff = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });

/** Next on the calendar: a match-day offer whose cost is fixed by a hedge on the real match market. */
export function OfferCard({ s, onChange, compact }: S & { onChange?: () => void; compact?: boolean }) {
  const q = tool<OfferQuote>(s, "price_match_offer");
  const queued = s.proposals.find((p) => p.market.kind === "offer" && p.market.market_id === q?.market_id && p.status !== "rejected" && p.status !== "expired");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!q || q.error) return null;
  const menu = { source: "Demo menu assumptions", label: `Average main £${q.avg_main_gbp}, first ${q.covers_cap} covers` };
  // Once queued, the proposal (re-priced off the order book at queue time) is the truth; the run's quote may be older.
  const shares = queued ? queued.shares : q.shares;
  const pays = queued ? queued.market.payout_if_event_gbp : q.payout_if_event_gbp;
  const fixed = queued ? (queued.market as { fixed_cost_gbp?: number }).fixed_cost_gbp ?? queued.cost_pence / 100 : q.fixed_cost_gbp;
  const fig = queued ? { rid: queued.receipt_id, badge: queued.market.price_badge } : { r: q };
  async function onQueue() {
    setBusy(true);
    setErr(null);
    try {
      await queueOffer();
      onChange?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div data-testid="panel-offer">
      <ProvPanel title="Next on the calendar" prov={provOf(q)}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <div className="font-display text-lg font-medium">{q.fixture}</div>
          <div className="text-sm text-fg-2">
            <span>{kickoff(q.kickoff)}</span>
            <span className="ml-3 text-fg-3">{q.venue}</span>
          </div>
        </div>
        <p className="mt-2 text-md">
          {q.trigger}: {q.offer}, first {q.covers_cap} covers.
        </p>
        <div className="mt-6">
          <div className="grid grid-flow-col divide-x divide-line" style={{ gridAutoColumns: "minmax(0, 1fr)" }}>
            <div className="pr-4">
              <div className="text-xs text-fg-3">Worst case</div>
              <Num rid={q.receipt_id} badge="SYNTHETIC" className="font-display text-lg font-medium text-warning">
                {gbp(q.worst_case_gbp)}
              </Num>
            </div>
            <div className="px-4">
              <div className="text-xs text-fg-3">Chance {q.team ?? "England"} lose</div>
              <Num r={q} className="font-display text-lg font-medium">
                {pct(q.market_prob)}
              </Num>
            </div>
            {!compact && (
              <div className="px-4">
                <div className="text-xs text-fg-3">Cover</div>
                <Num {...fig} className="font-display text-lg font-medium">
                  {`${shares} shares`}
                </Num>
              </div>
            )}
            <div className="pl-4">
              <div className="text-xs text-fg-3">Fixed cost</div>
              <Num {...fig} className="font-display text-lg font-medium text-positive">
                {gbp(fixed, { pence: true })}
              </Num>
            </div>
          </div>
        </div>
        <p className="mt-4 text-sm text-fg-2">
          The cover pays <Num {...fig}>{gbp(pays)}</Num> if {q.team ?? "England"} lose, so the offer costs you{" "}
          <Num {...fig}>{gbp(fixed, { pence: true })}</Num> whatever happens. Real match price; menu figures are modelled.
        </p>
        <div className="mt-4 flex items-center justify-between gap-4">
          <span className="text-xs text-fg-3" title={menu.label}>
            {queued ? `Queued for approval: ${queued.status}` : q.verdict.allowed ? "Inside your limits" : q.verdict.reason}
          </span>
          {!queued && (
            <Button onClick={onQueue} disabled={busy || !q.verdict.allowed} data-testid="queue-offer">
              {busy ? <Spinner /> : null}
              Queue this offer
            </Button>
          )}
        </div>
        {err && <p className="mt-2 text-xs text-negative">{err}</p>}
      </ProvPanel>
    </div>
  );
}
