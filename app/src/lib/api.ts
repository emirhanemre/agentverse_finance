"use client";

import { useCallback, useEffect, useState } from "react";

export type Profile = {
  pubName: string;
  postcode: string;
  owner: string;
  email: string;
  location_name: string;
  latitude: number;
  longitude: number;
  indoor_capacity: number;
  outdoor_capacity: number;
  opening_hours: number;
  currency: "GBP";
};
export type Settings = {
  weekly_spend_gbp: number;
  monthly_loss_gbp: number;
  per_contract_gbp: number;
  fx_usd_per_gbp: number;
  fee_bps: number;
  max_station_distance_km: number;
  monitor_enabled: boolean;
  monitor_interval_minutes: number;
  monitor_horizon_days: number;
  monitor_budget_gbp: number;
};
export type OperatingCosts = {
  fixed_daily_cost_gbp: number;
  variable_cost_pct: number;
};
export type OperatingProfitScenario = {
  revenue_gbp: number;
  variable_cost_gbp: number;
  fixed_cost_gbp: number;
  total_cost_gbp: number;
  operating_profit_gbp: number;
  operating_margin_pct: number | null;
  prediction_interval_80_low_gbp: number | null;
  prediction_interval_80_high_gbp: number | null;
};
export type OperatingProfit = {
  target_date: string;
  origin: "demo_cost_assumptions";
  assumptions: OperatingCosts;
  selected: OperatingProfitScenario;
  reference: OperatingProfitScenario;
  profit_difference_gbp: number;
  note: string;
};
export type BusinessModel = {
  id: string;
  accepted: boolean;
  status: string;
  origin: string;
  algorithm: string;
  matched_rows: number;
  unmatched_sales_rows: number;
  training_rows: number;
  validation_rows: number;
  test_rows: number;
  training_start: string;
  training_end: string;
  validation_start: string;
  validation_end: string;
  test_start: string;
  test_end: string;
  test_mae_gbp: number;
  baseline_test_mae_gbp: number;
  improvement_pct: number;
  test_r2: number | null;
  note: string;
  weather_provenance: {
    source: string;
    retrieved_at: string;
    start_date: string;
    end_date: string;
  };
  test_predictions: {
    date: string;
    actual_revenue_gbp: number;
    predicted_revenue_gbp: number;
    baseline_revenue_gbp: number;
  }[];
};
export type TrainingJob = {
  id: string;
  state: "running" | "complete" | "failed";
  created_at: string;
  payload: { stage: string; error?: string; model?: BusinessModel };
};
export type ContractSpec = {
  date: string;
  station: string;
  station_name: string;
  station_distance_km: number;
  timezone: string;
  metric: string;
  unit: string;
  lower: number | null;
  upper: number | null;
  rounding: string;
  source: string;
  basis_note: string;
  rules_hash: string;
};
export type Dataset = {
  origin: string;
  filename: string;
  row_count: number;
  start_date: string;
  end_date: string;
  total_revenue_gbp: number;
  monthly: { month: string; revenue_gbp: number }[];
  note: string;
  selected_at: string;
};
export type WeatherDay = {
  date: string;
  temp_max_c: number;
  temp_min_c: number;
  rain_mm: number;
  precipitation_probability_max?: number | null;
};
export type Forecast = {
  origin: string;
  source: string;
  source_url?: string;
  retrieved_at: string | null;
  horizon_start?: string;
  horizon_end?: string;
  days: WeatherDay[];
  note: string;
};
export type Calculation = {
  total_entry_cost_gbp: number;
  payout_if_win_gbp: number;
  net_profit_if_win_gbp: number;
  net_loss_if_lose_gbp: number;
  average_ask_price_usd: number;
  executable_contracts: number;
  fee_bps: number;
  fx_rate_usd_per_gbp: number;
  fx_rate_source: string;
  basis_risk_summary: string;
  combined_outcome_if_adverse_and_contract_pays_gbp: number;
  combined_outcome_if_adverse_and_contract_fails_gbp: number;
  combined_outcome_if_benign_and_contract_fails_gbp: number;
  estimated_unhedged_downside_gbp: number;
};
export type Proposal = {
  outcome_selected: string | null;
  contract_spec?: ContractSpec | null;
  model_note?: string;
  source_url?: string;
  proposal_id: string;
  proposal_hash: string;
  status:
    | "recommend_paper_hedge"
    | "no_suitable_hedge"
    | "need_information"
    | "data_unavailable";
  approval_state:
    | "pending_human_approval"
    | "approved"
    | "rejected"
    | "not_applicable";
  expired: boolean;
  expires_at: string;
  created_at: string;
  target_date: string;
  market_question: string | null;
  quote_timestamp: string;
  paper_quantity: number;
  max_total_cost_gbp: number;
  explanation: string;
  data_origin: string | null;
  rejection_reasons: Record<string, string[]>;
  calculation: Calculation | null;
};
export type Position = {
  outcome_selected: string;
  resolution?: {
    resolved_at: string;
    checked_at: string;
    payout_gbp: number;
    net_pnl_gbp: number;
    evidence: {
      source_url: string;
      transaction_hash: string;
      payouts: string[];
    };
  } | null;
  business_name?: string;
  position_id: string;
  market_question: string;
  target_date: string;
  approved_at: string;
  paper_quantity: number;
  average_fill_price_usd: number;
  total_entry_cost_gbp: number;
  hypothetical_payout_if_win_gbp: number;
  hypothetical_net_loss_if_lose_gbp: number;
  actual_resolved_outcome: string;
  settlement_note: string;
  data_origin: string;
};
export type Comparison = {
  scenario_predicted_revenue_gbp: number;
  reference_predicted_revenue_gbp: number;
  estimated_downside_loss_gbp: number;
  framing_note: string;
  assumptions: string[];
  scenario_prediction: {
    model_version: string;
    predictor_used: string;
    synthetic_data_warning: string;
    is_out_of_training_range: boolean;
    out_of_range_reasons: string[];
    prediction_interval_80_low_gbp: number;
    prediction_interval_80_high_gbp: number;
  };
};
export type Analysis = {
  id: string;
  created_at: string;
  state: "running" | "complete" | "failed";
  events: { id: number; created_at: string; label: string; detail: string }[];
  payload: {
    status?: Proposal["status"];
    error?: string;
    proposal_id?: string;
    execution_mode: string;
    model_note: string;
    comparison?: Comparison;
    weather_provenance?: Forecast;
    discovery?: { origin: string; note: string; retrieved_at?: string };
    inputs: AnalysisInputs;
    candidates?: {
      market: {
        market_id: string;
        question: string;
        source_url: string;
        resolution_rules: string;
      };
      risk: { blocking_reasons: string[] };
    }[];
  };
};
export type AnalysisInputs = {
  model_mode?: "auto" | "synthetic_demo";
  target_date: string;
  weather_mode: "manual" | "forecast";
  market_mode: "live" | "cached" | "test_suitable" | "test_no_match";
  budget_gbp: number;
  temp_max_c: number;
  rain_mm: number;
  wind_max_kmh: number;
  sunshine_hours: number;
};
export type AppState = {
  business_model: BusinessModel | null;
  training_job: TrainingJob | null;
  monitoring: {
    status: string;
    running?: boolean;
    note?: string;
    last_run_at?: string;
    next_run_at?: string;
    analysis_id?: string;
  } | null;
  notifications: {
    id: number;
    created_at: string;
    category: string;
    message: string;
    read_at: string | null;
  }[];
  profile: Profile | null;
  dataset: Dataset | null;
  settings: Settings;
  operating_costs: OperatingCosts;
  operating_profit: OperatingProfit | null;
  revision: number;
  setup_complete: boolean;
  forecast: Forecast | null;
  analysis: Analysis | null;
  active_analysis: string | null;
  proposals: Proposal[];
  positions: Position[];
  activity: {
    id: number;
    logged_at: string;
    event_type: string;
    details: Record<string, unknown>;
  }[];
  sources: { id: string; name: string; status: string; note: string }[];
  summary: {
    open_positions: number;
    total_entry_cost_gbp: number;
    hypothetical_payout_gbp: number;
    pending_approvals: number;
    weekly_reserved_gbp: number;
    monthly_reserved_loss_gbp: number;
    settled_payout_gbp: number | null;
    realized_paper_pnl_gbp: number | null;
  };
  execution_mode: string;
  model_note: string;
};

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail
            .map(
              (e: { loc: string[]; msg: string }) =>
                `${e.loc.slice(1).join(".")}: ${e.msg}`,
            )
            .join(" · ")
        : typeof detail === "string"
          ? detail
          : `Backend unavailable (${response.status}). Start both services and retry.`,
    );
  }
  return data as T;
}

export function useApplication() {
  const [state, setState] = useState<AppState | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const value = await api<AppState>("/state");
      setState(value);
      setError("");
      return value;
    } catch (e) {
      setError(message(e));
      return null;
    }
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);
  return { state, error, refresh };
}

export const message = (e: unknown) =>
  e instanceof Error ? e.message : "Request failed. Please retry.";
export const money = (n: number) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
export const stamp = (s?: string | null) =>
  s
    ? new Date(s).toLocaleString("en-GB", {
        timeZone: "Europe/London",
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Unavailable";
export const statusLabel = (s?: string) =>
  ({
    recommend_paper_hedge: "Paper scenario recommended",
    no_suitable_hedge: "No suitable hedge",
    need_information: "More information required",
    data_unavailable: "Required data unavailable",
  })[s || ""] || "No assessment yet";
export const pending = (s: AppState) =>
  s.proposals.filter(
    (p) => p.approval_state === "pending_human_approval" && !p.expired,
  );
export const latestProposal = (s: AppState) =>
  s.proposals.find((p) => p.proposal_id === s.analysis?.payload.proposal_id);
export const defaultInputs = (): AnalysisInputs => ({
  target_date: new Date(Date.now() + 86400000).toLocaleDateString("en-CA", {
    timeZone: "Europe/London",
  }),
  weather_mode: "manual",
  market_mode: "live",
  budget_gbp: 100,
  temp_max_c: 15,
  rain_mm: 14,
  wind_max_kmh: 26,
  sunshine_hours: 0.5,
});
export async function decide(p: Proposal, approve: boolean) {
  return api(
    `/proposals/${p.proposal_id}/${approve ? "approve" : "reject"}`,
    "POST",
    approve
      ? {
          confirmed_proposal_hash: p.proposal_hash,
          confirmed_quantity: p.paper_quantity,
          confirmed_max_cost_gbp: p.max_total_cost_gbp,
          confirmed_quote_timestamp: p.quote_timestamp,
          acknowledge_paper_risk: true,
        }
      : { note: "Rejected by local operator" },
  );
}
