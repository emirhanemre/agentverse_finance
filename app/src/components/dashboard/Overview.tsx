"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar as RBar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge, Button, Icon, Metric, Panel, Spinner, cx, tooltipStyle } from "../ui";
import { Bar, Feed, Td, Th } from "./Shell";
import { gbp } from "../../lib/format";
import { BACKTEST, LIMITS, WEEKS_BELOW_PAYROLL, type Hedge } from "../../lib/data";
import {
  ACTIVITY_TODAY,
  BANK_FEED,
  CASH_FORECAST,
  FORECAST,
  HISTORY,
  MONTHLY_NET,
  RAIN_EVENTS,
  RAIN_PAYOUT,
  RAIN_THRESHOLD_MM,
  RAIN_TICKS,
  SETTLES,
  YEAR_CASHFLOW,
  rainSoFar,
} from "../../lib/dashboard-data";

export type Approval = "pending" | "approved" | "declined";

const money = (v: unknown) => gbp(Number(v));

function KpiStrip({ children }: { children: React.ReactNode }) {
  return (
    <section className="grid grid-cols-4 divide-x divide-line rounded-md border border-line bg-surface">
      {children}
    </section>
  );
}

function Kpi(props: React.ComponentProps<typeof Metric>) {
  return (
    <div className="px-4 py-3">
      <Metric {...props} />
    </div>
  );
}

type PositionStatus = "Open" | "Triggered" | "Settled";

function PositionsTable({ hedges, statusFor }: { hedges: Hedge[]; statusFor: (h: Hedge) => PositionStatus }) {
  return (
    <table className="w-full">
      <thead className="border-b border-line bg-surface-2">
        <tr>
          <Th>Position</Th>
          <Th>Venue</Th>
          <Th right>Stake</Th>
          <Th right>Pays</Th>
          <Th>Status</Th>
          <Th>Settles</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {hedges.map((h) => {
          const s = statusFor(h);
          return (
            <tr key={h.id}>
              <Td className="text-fg">{h.name}</Td>
              <Td className="text-fg-2">{h.venue}</Td>
              <Td right mono>
                {gbp(h.stake)}
              </Td>
              <Td right mono>
                {gbp(h.payout)}
              </Td>
              <Td>
                <Badge tone={s === "Open" ? "accent" : s === "Triggered" ? "warning" : "positive"} dot>
                  {s}
                </Badge>
              </Td>
              <Td className="text-fg-2" mono>
                {SETTLES[h.id]}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function TodayView({
  hedges,
  approval,
  onApproval,
}: {
  hedges: Hedge[];
  approval: Approval;
  onApproval: (a: Approval) => void;
}) {
  const stake = hedges.reduce((a, h) => a + h.stake, 0);
  const payout = hedges.reduce((a, h) => a + h.payout, 0);
  const activity =
    approval === "pending"
      ? ACTIVITY_TODAY
      : [
          {
            time: "09:14",
            text:
              approval === "approved"
                ? "Placed rain cover for Sat 19 Jul after your approval. £20 at 0.11."
                : "You declined rain cover for Sat 19 Jul. Won't propose it again.",
            tone: approval === "approved" ? ("positive" as const) : undefined,
          },
          ...ACTIVITY_TODAY,
        ];

  return (
    <div className="flex h-full flex-col gap-3">
      <KpiStrip>
        <Kpi label="Open positions" value={hedges.length + (approval === "approved" ? 1 : 0)} sub={`${gbp(stake + (approval === "approved" ? 20 : 0))} staked`} />
        <Kpi label="Maximum loss this month" value={gbp(stake + (approval === "approved" ? 20 : 0))} sub={`of ${gbp(LIMITS.monthlyLoss)} limit`} />
        <Kpi label="Potential payout" value={gbp(payout + (approval === "approved" ? 180 : 0))} tone="positive" sub="If every covered event happens" />
        <Kpi label="Next risk event" value="Sat 12 Jul" sub="Afternoon rain 71% · Met Office" tone="warning" />
      </KpiStrip>

      <Panel title="Next 14 days" actions={<span className="font-mono text-[11.5px] text-fg-3">Met Office · Greenwich</span>} bodyClassName="p-3">
        <div className="grid grid-cols-14 gap-1.5" style={{ gridTemplateColumns: "repeat(14, minmax(0, 1fr))" }}>
          {FORECAST.map((d) => (
            <div
              key={d.date}
              className={cx(
                "rounded border px-2 py-2",
                d.covered ? "border-accent-edge bg-accent-wash" : d.proposed && approval !== "declined" ? "border-warning-edge bg-warning-wash" : "border-line bg-surface-2"
              )}
            >
              <div className="flex items-baseline justify-between font-mono text-[11px]">
                <span className="text-fg-3">{d.dow}</span>
                <span className="text-fg">{d.date}</span>
              </div>
              <div className={cx("mt-1.5 flex items-center gap-1 font-mono text-[12px]", d.rain >= 60 ? "text-fg" : "text-fg-2")}>
                <Icon name="rain" size={13} className={d.rain >= 60 ? "text-accent" : "text-fg-3"} />
                {d.rain}%
              </div>
              <div className="mt-1 h-4 truncate text-[10.5px] text-fg-3">
                {d.covered && <span className="text-accent">Covered</span>}
                {d.proposed && (approval === "approved" ? <span className="text-accent">Covered</span> : approval === "pending" ? <span className="text-warning">Proposed</span> : null)}
                {!d.covered && !d.proposed && d.marker}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid min-h-0 flex-1 grid-cols-[1.45fr_1fr] gap-3">
        <div className="flex min-h-0 flex-col gap-3">
          <Panel
            title="Cashflow forecast, 8 weeks"
            actions={
              <div className="flex items-center gap-3 text-[11.5px] text-fg-2">
                <Legend color="var(--accent)" label="Expected" />
                <Legend color="var(--warning)" label="Bad case" dashed />
              </div>
            }
            className="flex min-h-0 flex-1 flex-col"
            bodyClassName="min-h-0 flex-1"
          >
            <div className="h-full min-h-[150px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={CASH_FORECAST} margin={{ top: 6, right: 56, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} strokeDasharray="2 4" />
                  <XAxis dataKey="wk" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={money} ticks={[0, 500, 1000, 1500]} domain={[-100, 1500]} />
                  <ReferenceLine y={0} stroke="var(--fg-3)" strokeDasharray="3 3" label={{ value: "Payroll", position: "right", fill: "var(--fg-3)", fontSize: 11 }} />
                  <Tooltip {...tooltipStyle} formatter={(v, n) => [money(v), n === "expected" ? "Expected" : "Bad case"]} />
                  <Area type="monotone" dataKey="expected" stroke="var(--accent)" strokeWidth={1.5} fill="var(--accent-wash)" />
                  <Area type="monotone" dataKey="bad" stroke="var(--warning)" strokeWidth={1.25} strokeDasharray="4 3" fill="transparent" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Open positions" bodyClassName="p-0">
            <PositionsTable hedges={hedges} statusFor={() => "Open"} />
          </Panel>
        </div>

        <div className="flex min-h-0 flex-col gap-3">
          <Panel title="Needs approval" actions={approval === "pending" ? <Badge tone="warning" dot>1 pending</Badge> : undefined}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[13px] font-medium">Rain cover, Sat 19 Jul</div>
                <div className="mt-0.5 font-mono text-[11.5px] text-fg-3">Polymarket · London City above 4mm, 12:00–18:00</div>
              </div>
              <div className="text-right font-mono text-[12.5px]">
                <div>{gbp(20)}</div>
                <div className="text-[11.5px] text-fg-3">pays {gbp(180)}</div>
              </div>
            </div>
            <p className="mt-2.5 text-[12.5px] leading-5 text-fg-2">
              The forecast shows a 64% chance of afternoon rain. The market prices it at 0.11. If it stays dry you lose the £20 stake.
            </p>
            <div className="mt-3 flex items-center gap-2">
              {approval === "pending" ? (
                <>
                  <Button variant="primary" onClick={() => onApproval("approved")}>
                    Approve £20
                  </Button>
                  <Button onClick={() => onApproval("declined")}>Decline</Button>
                </>
              ) : approval === "approved" ? (
                <Badge tone="positive" dot>
                  Approved · order placed 09:14
                </Badge>
              ) : (
                <Badge>Declined · not proposed again for 19 Jul</Badge>
              )}
            </div>
          </Panel>
          <Panel title="Agent activity" className="flex min-h-0 flex-1 flex-col" bodyClassName="min-h-0 flex-1 overflow-y-auto py-1">
            <Feed rows={activity} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="14" height="6" aria-hidden>
        <line x1="0" y1="3" x2="14" y2="3" stroke={color} strokeWidth="1.5" strokeDasharray={dashed ? "3 2" : undefined} />
      </svg>
      {label}
    </span>
  );
}

export function RainView({ hedges }: { hedges: Hedge[] }) {
  const [tick, setTick] = useState(0);
  const last = RAIN_TICKS.length - 1;

  useEffect(() => {
    if (tick >= last) return;
    const t = setTimeout(() => setTick((x) => x + 1), 700);
    return () => clearTimeout(t);
  }, [tick, last]);

  const now = RAIN_TICKS[tick];
  const mm = rainSoFar(tick);
  const triggered = mm > RAIN_THRESHOLD_MM;
  const settled = tick >= last;
  const gap = now.actual - now.typical;
  const events = RAIN_EVENTS.filter((e) => e.at <= tick).reverse();
  const data = RAIN_TICKS.map((t, i) => ({ ...t, actual: i <= tick ? t.actual : null }));

  const banner = settled
    ? { tone: "positive" as const, text: "Rain position settled · £180 paid to Monzo ••1847 at 18:00" }
    : tick >= 4
      ? { tone: "warning" as const, text: "Heavy rain from 13:00 · garden closed at 14:10" }
      : { tone: "warning" as const, text: "Met Office heavy rain warning for south-east London, 13:00–17:00" };

  return (
    <div className="flex h-full flex-col gap-3">
      <div
        className={cx(
          "flex h-10 shrink-0 items-center gap-2.5 rounded-md border px-4 text-[13px]",
          banner.tone === "positive" ? "border-positive-edge bg-positive-wash text-positive" : "border-warning-edge bg-warning-wash text-warning"
        )}
      >
        <Icon name={banner.tone === "positive" ? "check" : "rain"} />
        <span>{banner.text}</span>
        <span className="ml-auto flex items-center gap-2 font-mono text-[12px] text-fg-2">
          {!settled && <Spinner size={12} className="text-accent" />}
          {now.time}
        </span>
      </div>

      <KpiStrip>
        <Kpi label="Takings so far" value={gbp(now.actual)} sub={`${gbp(gap)} vs a typical July Saturday`} />
        <Kpi label="Rain since 12:00" value={`${mm.toFixed(1)} mm`} sub={`Position pays above ${RAIN_THRESHOLD_MM.toFixed(1)} mm`} tone={triggered ? "warning" : undefined} />
        <Kpi
          label="Hedge payout"
          value={settled ? gbp(RAIN_PAYOUT, { sign: true }) : triggered ? gbp(RAIN_PAYOUT) : gbp(0)}
          sub={settled ? "Paid 18:00" : triggered ? "Due when the window closes at 18:00" : `${gbp(RAIN_PAYOUT)} if rain passes 4 mm`}
          tone={settled ? "positive" : triggered ? "warning" : undefined}
        />
        <Kpi label="Net impact after hedge" value={gbp(gap + (settled ? RAIN_PAYOUT : 0))} tone="negative" sub={settled ? `${gbp(gap)} takings, ${gbp(RAIN_PAYOUT, { sign: true })} payout` : "Updates at settlement"} />
      </KpiStrip>

      <div className="grid min-h-0 flex-1 grid-cols-[1.45fr_1fr] gap-3">
        <div className="flex min-h-0 flex-col gap-3">
          <Panel
            title="Today's takings"
            className="flex min-h-0 flex-1 flex-col"
            bodyClassName="min-h-0 flex-1"
            actions={
              <div className="flex items-center gap-3 text-[11.5px] text-fg-2">
                <Legend color="var(--negative)" label="Today" />
                <Legend color="var(--fg-3)" label="Typical July Saturday" dashed />
              </div>
            }
          >
            <div className="h-full min-h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 6, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} strokeDasharray="2 4" />
                  <XAxis dataKey="time" tickLine={false} axisLine={false} interval={1} />
                  <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={money} ticks={[0, 1000, 2000, 3000, 4000]} domain={[0, 4000]} />
                  <Tooltip {...tooltipStyle} formatter={(v, n) => [money(v), n === "actual" ? "Today" : "Typical"]} />
                  <Line type="monotone" dataKey="typical" stroke="var(--fg-3)" strokeWidth={1.25} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="actual" stroke="var(--negative)" strokeWidth={1.75} dot={false} isAnimationActive={false} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Positions" bodyClassName="p-0">
            <PositionsTable hedges={hedges} statusFor={(h) => (h.id !== "rain" ? "Open" : settled ? "Settled" : triggered ? "Triggered" : "Open")} />
          </Panel>
        </div>

        <div className="flex min-h-0 flex-col gap-3">
          <Panel title="Bank feed" actions={<span className="font-mono text-[11.5px] text-fg-3">Monzo ••1847</span>} bodyClassName="py-1">
            <ul className="divide-y divide-line">
              <AnimatePresence initial={false}>
                {settled && (
                  <motion.li
                    key="payout"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    transition={{ duration: 0.25 }}
                    className="overflow-hidden"
                  >
                    <BankItem time="Sat 18:00" text="Polymarket settlement · rain, Sat 12 Jul" amount={RAIN_PAYOUT} highlight />
                  </motion.li>
                )}
              </AnimatePresence>
              {BANK_FEED.map((b) => (
                <li key={b.text}>
                  <BankItem {...b} />
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Agent activity" className="flex min-h-0 flex-1 flex-col" bodyClassName="min-h-0 flex-1 overflow-y-auto py-1">
            <Feed
              rows={events}
              live={
                !settled && (
                  <li className="grid grid-cols-[44px_1fr] gap-3 py-2">
                    <span className="flex h-5 items-center">
                      <Spinner size={12} className="text-accent" />
                    </span>
                    <span className="text-[12.5px] leading-5 text-fg">Monitoring takings and rainfall</span>
                  </li>
                )
              }
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}

function BankItem({ time, text, amount, highlight }: { time: string; text: string; amount: number; highlight?: boolean }) {
  return (
    <div className={cx("grid grid-cols-[72px_1fr_auto] items-center gap-3 py-2", highlight && "-mx-4 bg-positive-wash px-4")}>
      <span className="font-mono text-[11.5px] text-fg-3">{time}</span>
      <span className={cx("text-[12.5px]", highlight ? "text-fg" : "text-fg-2")}>{text}</span>
      <span className={cx("font-mono text-[12.5px]", amount > 0 ? "text-positive" : "text-fg-2")}>{gbp(amount, { sign: true })}</span>
    </div>
  );
}

export function YearView() {
  const worst = Math.min(...MONTHLY_NET.map((m) => m.net));
  return (
    <div className="flex h-full flex-col gap-3">
      <KpiStrip>
        <Kpi label="Net benefit, 12 months" value={gbp(BACKTEST.netBenefit, { sign: true })} tone="positive" sub={`Payouts ${gbp(BACKTEST.payouts)} less spend ${gbp(BACKTEST.spend)}`} />
        <Kpi label="Weeks below payroll" value={`${WEEKS_BELOW_PAYROLL.actual} → ${WEEKS_BELOW_PAYROLL.hedged}`} sub="Without vs with Pub Hedge" />
        <Kpi label="Spend / payouts" value={`${gbp(BACKTEST.spend)} / ${gbp(BACKTEST.payouts)}`} sub="48 positions" />
        <Kpi label="Losing months" value={`${BACKTEST.losingMonths} of ${BACKTEST.months}`} sub={`Worst ${gbp(worst)} in March`} tone="negative" />
      </KpiStrip>

      <div className="grid grid-cols-[1.45fr_1fr] gap-3">
        <Panel
          title="Weekly margin after fixed costs"
          actions={
            <div className="flex items-center gap-3 text-[11.5px] text-fg-2">
              <Legend color="var(--accent)" label="With Pub Hedge" />
              <Legend color="var(--fg-3)" label="Without" dashed />
            </div>
          }
        >
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={YEAR_CASHFLOW} margin={{ top: 6, right: 56, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} strokeDasharray="2 4" />
                <XAxis dataKey="i" tickLine={false} axisLine={false} ticks={[0, 8, 16, 24, 32, 40]} tickFormatter={(i: number) => YEAR_CASHFLOW[i]?.month ?? ""} />
                <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={money} ticks={[-1000, -500, 0, 500, 1000, 1500]} domain={[-1200, 1700]} />
                <ReferenceLine y={0} stroke="var(--fg-3)" strokeDasharray="3 3" label={{ value: "Payroll", position: "right", fill: "var(--fg-3)", fontSize: 11 }} />
                <Tooltip
                  {...tooltipStyle}
                  labelFormatter={(i) => `Week of ${YEAR_CASHFLOW[Number(i)]?.month ?? ""}`}
                  formatter={(v, n) => [money(v), n === "hedged" ? "With Pub Hedge" : "Without"]}
                />
                <Line type="monotone" dataKey="actual" stroke="var(--fg-3)" strokeWidth={1.25} strokeDasharray="4 3" dot={false} />
                <Line type="monotone" dataKey="hedged" stroke="var(--accent)" strokeWidth={1.75} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Net result by month" actions={<span className="font-mono text-[11.5px] text-fg-3">Payouts less spend</span>}>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={MONTHLY_NET} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} strokeDasharray="2 4" />
                <XAxis dataKey="m" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={money} ticks={[-400, -200, 0, 200, 400, 600]} domain={[-400, 650]} />
                <ReferenceLine y={0} stroke="var(--line-strong)" />
                <Tooltip {...tooltipStyle} cursor={{ fill: "var(--surface-2)" }} formatter={(v) => [gbp(Number(v), { sign: true }), "Net"]} />
                <RBar dataKey="net" radius={[2, 2, 0, 0]} maxBarSize={22}>
                  {MONTHLY_NET.map((m) => (
                    <Cell key={m.m} fill={m.net < 0 ? "var(--negative)" : "var(--positive)"} />
                  ))}
                </RBar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[1.45fr_1fr] gap-3">
        <Panel title="Settled positions" actions={<span className="font-mono text-[11.5px] text-fg-3">8 of 48</span>} className="flex min-h-0 flex-col" bodyClassName="min-h-0 flex-1 overflow-y-auto p-0">
          <table className="w-full">
            <thead className="sticky top-0 border-b border-line bg-surface-2">
              <tr>
                <Th>Position</Th>
                <Th>Settled</Th>
                <Th right>Stake</Th>
                <Th right>Paid</Th>
                <Th right>Result</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {HISTORY.map((h) => {
                const net = h.payout - h.stake;
                return (
                  <tr key={h.name}>
                    <Td className="text-fg">
                      {h.name}
                      <span className="ml-2 text-fg-3">{h.venue}</span>
                    </Td>
                    <Td mono className="text-fg-2">
                      {h.settled}
                    </Td>
                    <Td right mono>
                      {gbp(h.stake)}
                    </Td>
                    <Td right mono className={h.payout ? "text-positive" : "text-fg-3"}>
                      {gbp(h.payout)}
                    </Td>
                    <Td right mono className={net < 0 ? "text-negative" : "text-positive"}>
                      {gbp(net, { sign: true })}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
        <Panel title="Limits used">
          <div className="space-y-4">
            <LimitRow label="Average weekly spend" value={BACKTEST.spend / 52} limit={LIMITS.weeklySpend} />
            <LimitRow label="Worst monthly loss" value={Math.abs(worst)} limit={LIMITS.monthlyLoss} tone="warning" />
            <LimitRow label="Largest single stake" value={20} limit={LIMITS.approvalOver} note="Approval needed over £50" />
            <div className="flex justify-between border-t border-line pt-3 text-[12.5px]">
              <span className="text-fg-2">Approvals</span>
              <span className="font-mono">41 approved · 7 declined</span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function LimitRow({ label, value, limit, tone, note }: { label: string; value: number; limit: number; tone?: "warning"; note?: string }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-[12.5px]">
        <span className="text-fg-2">{label}</span>
        <span className="font-mono">
          {gbp(value)} <span className="text-fg-3">of {gbp(limit)}</span>
        </span>
      </div>
      <Bar value={value} max={limit} tone={tone} />
      {note && <div className="mt-1 text-[11.5px] text-fg-3">{note}</div>}
    </div>
  );
}
