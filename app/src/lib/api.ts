"use client";

import { useCallback, useEffect, useState } from "react";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Provenance strings come from the API verbatim: REAL, REAL · CACHED, SYNTHETIC, TEST MODE, PAPER, REPLAY, TEMPLATE, MODEL, ERROR.
export type BadgeText = string;

/** Any tool result: always has badge/summary/receipt_id, plus tool-specific fields. */
export type ToolResult = {
  badge: BadgeText;
  summary: string;
  receipt_id: string;
  source?: string;
  licence?: string;
  fetched_at?: string;
  url?: string;
  generator?: string;
  seed?: number;
  label?: string;
  [k: string]: unknown;
};

export type Estimate = { estimate: number; ci95: [number, number] };
export type TimelineRow = { date: string; amount_gbp: number; balance_gbp: number; id: string };
export type Payroll = ToolResult & {
  scenario: "dry" | "wet";
  first_negative_date: string | null;
  payroll_date: string;
  payroll_clears: boolean;
  shortfall_gbp: number;
  minimum_balance_gbp: number;
  opening_balance_gbp: number;
  opening_date: string;
  timeline: TimelineRow[];
};
export type Outcomes = {
  wet_no_hedge_shortfall_gbp: number;
  wet_with_hedge_shortfall_gbp: number;
  dry_no_hedge_shortfall_gbp: number;
  dry_with_hedge_shortfall_gbp: number;
  hedge_cost_gbp: number;
  hedge_payout_if_wet_gbp: number;
  /** wet minus dry shortfall; newer API only */
  wet_extra_shortfall_gbp?: number;
  payroll_date: string;
};

export type Check = { name: string; value_pence: number; cap_pence: number; pass: boolean };
export type Verdict = { market_id: string; allowed: boolean; checks: Check[]; reason: string | null; needs_second_approval: boolean };
export type Market = {
  market_id: string;
  date: string;
  forecast_mm: number;
  model_prob: number;
  mid: number;
  ask: number;
  cost_per_share: number;
  fee_rate: number;
  price_badge: BadgeText;
  rule: string;
  payout_if_event_gbp: number;
  verdict: Verdict;
};
export type Proposal = {
  id: string;
  run_id: string;
  created: number;
  market: Market;
  shares: number;
  cost_pence: number;
  status: "pending" | "blocked" | "filled" | "rejected";
  decided: number | null;
  reason: string | null;
  receipt_id: string | null;
};

export type Limits = {
  weekly_spend_cap_pence: number;
  monthly_max_loss_pence: number;
  per_market_cap_pence: number;
  approval_threshold_pence: number;
};

export type Grounding = { numbers: { text: string; grounded: boolean }[]; ungrounded: string[]; dropped_sentences?: string[]; ok: boolean };
export type Narration = { text: string; badge: BadgeText; grounding?: Grounding; receipt_id: string; model?: string };

export type PolicyPoint = {
  hedge_net_gbp_per_year: number;
  premium_gbp_per_year: number;
  payouts_gbp_per_year: number;
  shortfall_weeks_per_year: number;
  shortfall_depth_gbp_per_year: number;
  worst_week_gbp: number;
  worst_month_gbp: number;
  losing_months_per_year: number;
  weekly_cash_sd_gbp: number;
  cvar5_weekly_gbp: number;
};
export type Policy = {
  point: PolicyPoint;
  ci95: Record<keyof PolicyPoint, [number, number]>;
  demo_weeks_hedged: number;
  weeks_hedged_all: number;
  pub_weeks: number;
};
export type DemoWeek = { start: string; net: number; shortfall: boolean; premium: number; payout: number; depth: number };
export type Backtest = {
  policies: Record<"none" | "naive" | "ours" | "ours_caps_x5", Policy>;
  demo_weeks: Record<string, DemoWeek[]>;
  setup: { train: [string, string]; test: [string, string]; pubs: number; contract_mm: number; bootstrap: string; seed: number; limits_gbp: Record<string, number> };
};

export type AppState = {
  pub: {
    trading_name: string;
    company_number: string;
    postcode: string;
    address: string;
    lat: number;
    lon: number;
    identity_badge: BadgeText;
    financials_label: string;
    owner: string;
  };
  scenario: { name: string; decision_date: string; weekend: string[] };
  run: null | {
    run_id: string;
    mode: string;
    wall_ms: number;
    status: string;
    summary?: { narration: Record<string, Narration>; live_models: boolean };
  };
  tools: Record<string, ToolResult[]>;
  proposals: Proposal[];
  limits: Limits;
  ledger: { spent_this_week_pence: number; at_risk_this_month_pence: number; by_market_pence: Record<string, number> };
  backtest: Backtest;
  synthetic_manifest: { label: string; generator: string; seed: number; method: string };
};

export type Receipt = {
  seq: number;
  ts: number;
  run_id: string;
  step: string;
  call: string;
  args: unknown;
  result: unknown;
  badge: BadgeText;
  model: string;
  ms: number;
  receipt_id: string;
  prev_hash: string;
  hash: string;
};

export type ApproveResult = {
  status: "filled" | "blocked" | "needs_second_approval";
  reason?: string;
  fill?: Record<string, unknown>;
  verdict: Verdict;
  receipt_id?: string;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: init?.body ? { "content-type": "application/json" } : undefined,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

export const putLimits = (patch: Partial<Limits>) =>
  api<{ limits: Limits; blocked: { id: string; reason: string; receipt_id: string }[] }>("/api/limits", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
export const approve = (id: string, confirmSecond: boolean) =>
  api<ApproveResult>(`/api/proposals/${id}/approve`, { method: "POST", body: JSON.stringify({ confirm_second: confirmSecond }) });
export const reject = (id: string) => api<unknown>(`/api/proposals/${id}/reject`, { method: "POST" });

export function useAppState() {
  const [state, setState] = useState<AppState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(
    () =>
      api<AppState>("/api/state")
        .then((s) => {
          setState(s);
          setError(null);
        })
        .catch((e) => setError(String(e))),
    []
  );
  useEffect(() => {
    refresh();
  }, [refresh]);
  return { state, error, refresh };
}

/** Latest result of a tool, or the one matching a predicate. */
export function tool<T extends ToolResult = ToolResult>(s: AppState | null, name: string, pick?: (r: T) => boolean): T | undefined {
  const rows = (s?.tools?.[name] ?? []) as T[];
  return pick ? rows.find(pick) : rows[rows.length - 1];
}

export const payroll = (s: AppState | null, scenario: "wet" | "dry") => tool<Payroll>(s, "project_payroll", (r) => r.scenario === scenario);

/** Proposals from the latest run first, then older ones. */
export const proposals = (s: AppState | null) => [...(s?.proposals ?? [])].sort((a, b) => b.created - a.created);

export const pence = (p: number) => `£${(p / 100).toFixed(2)}`;
