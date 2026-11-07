"""Validated schemas for model inputs, tool outputs, financial calculations, and paper execution.

Also provides deterministic secret/credential redaction for logs, errors, and tool outputs.
"""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


AgentFinalStatus = Literal[
    "recommend_paper_hedge",
    "no_suitable_hedge",
    "need_information",
    "data_unavailable",
]

DataOriginLabel = Literal[
    "live_polymarket_api",
    "cached_polymarket_snapshot",
    "historical_replay_snapshot",
    "synthetic_test_fixture",
]


_SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(sk-[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(ghp_[0-9A-Za-z]{20,})"),
    re.compile(r"(github_pat_[0-9A-Za-z_]{20,})"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s\"']+)"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password|private[_-]?key)\s*[=:]\s*)([^\s\"'&]+)"),
    re.compile(r"(?i)([?&](?:key|api_key|token|secret|access_token)=)([^&\s\"']+)"),
]


def redact_sensitive_text(text: str) -> str:
    """Redact API keys, Bearer tokens, and credential-bearing URL parameters."""
    if not text:
        return text
    cleaned = str(text)
    for idx, pat in enumerate(_SECRET_PATTERNS):
        if idx < 4:
            cleaned = pat.sub("[REDACTED_CREDENTIAL]", cleaned)
        else:
            cleaned = pat.sub(r"\1[REDACTED_CREDENTIAL]", cleaned)
    return cleaned


class BusinessProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: str = "uk_pub_london_se1_01"
    description: str = "Independent UK pub with outdoor beer garden seating (Southbank / London SE1)"
    location_name: str = "London, United Kingdom"
    latitude: float = 51.5074
    longitude: float = -0.1278
    currency: Literal["GBP"] = "GBP"
    indoor_capacity: int = Field(default=90, ge=10, le=500)
    outdoor_capacity: int = Field(default=70, ge=0, le=500)
    default_opening_hours: float = Field(default=11.0, ge=1.0, le=24.0)
    is_synthetic_business_data: bool = True
    synthetic_disclaimer: str = (
        "Synthetic business profile and daily sales history generated for controlled "
        "pipeline demonstration. Does not represent private financial records of a real pub."
    )


class DailyFeatureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(..., description="ISO date YYYY-MM-DD")
    temp_max_c: float = Field(..., ge=-30.0, le=55.0)
    temp_min_c: float = Field(..., ge=-35.0, le=45.0)
    temp_mean_c: float = Field(..., ge=-32.0, le=50.0)
    precipitation_mm: float = Field(..., ge=0.0, le=300.0)
    rain_mm: float = Field(..., ge=0.0, le=300.0)
    wind_max_kmh: float = Field(..., ge=0.0, le=200.0)
    sunshine_hours: float = Field(..., ge=0.0, le=24.0)
    opening_hours: float = Field(default=11.0, ge=0.0, le=24.0)
    indoor_capacity: int = Field(default=90, ge=10, le=500)
    outdoor_capacity: int = Field(default=70, ge=0, le=500)
    is_uk_bank_holiday: int = Field(default=0, ge=0, le=1)
    local_event_indicator: int = Field(default=0, ge=0, le=1)
    lag_7d_revenue_gbp: float | None = Field(default=None, ge=0.0)
    rolling_14d_mean_revenue_gbp: float | None = Field(default=None, ge=0.0)

    @field_validator("date")
    @classmethod
    def validate_iso_date(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("date must be formatted as YYYY-MM-DD")
        return v


class RevenuePredictionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    predictor_used: str
    model_version: str
    predicted_revenue_gbp: float
    predicted_revenue_pence: int
    baseline_weekday_revenue_gbp: float
    prediction_interval_80_low_gbp: float
    prediction_interval_80_high_gbp: float
    interval_method: str
    is_out_of_training_range: bool
    out_of_range_reasons: list[str]
    prediction_mode: Literal["conditional_on_weather_scenario", "retrospective_observed_weather"]
    synthetic_data_warning: str


class ScenarioComparisonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    scenario_label: str
    reference_label: str
    scenario_predicted_revenue_gbp: float
    reference_predicted_revenue_gbp: float
    estimated_difference_gbp: float
    estimated_downside_loss_gbp: float
    estimated_downside_loss_pence: int
    scenario_prediction: RevenuePredictionOutput
    reference_prediction: RevenuePredictionOutput
    framing_note: str = (
        "Model-based conditional scenario estimate comparing two explicitly defined weather "
        "inputs under the trained revenue model. Not a proven causal loss."
    )
    assumptions: list[str]


class OrderBookLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    size: Decimal = Field(..., ge=Decimal("0"))


class MarketCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_id: str
    condition_id: str = ""
    source_url: str
    retrieval_timestamp: str
    data_origin: DataOriginLabel
    question: str
    resolution_rules: str
    resolution_source: str
    location: str
    measurement: str
    start_date: str | None = None
    end_date: str | None = None
    status: Literal["active", "closed", "inactive"]
    outcomes: list[str]
    outcome_prices: list[str]
    clob_token_ids: list[str]
    asks_by_outcome: dict[str, list[OrderBookLevel]] = Field(default_factory=dict)
    bids_by_outcome: dict[str, list[OrderBookLevel]] = Field(default_factory=dict)
    untrusted_content_flags: list[str] = Field(default_factory=list)


class HedgeCalculationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_id: str
    outcome_selected: str
    target_date: str
    budget_gbp: float
    budget_pence: int
    fx_rate_usd_per_gbp: float
    fx_rate_source: str
    fee_bps: int
    executable_contracts: int
    average_ask_price_usd: float
    gross_entry_cost_usd: float
    estimated_fee_usd: float
    total_entry_cost_usd: float
    total_entry_cost_gbp: float
    total_entry_cost_pence: int
    unfilled_budget_gbp: float
    depth_exhausted: bool
    payout_if_win_usd: float
    payout_if_win_gbp: float
    net_profit_if_win_gbp: float
    net_loss_if_lose_gbp: float
    adverse_weather_pub_revenue_gbp: float
    reference_weather_pub_revenue_gbp: float
    estimated_unhedged_downside_gbp: float
    combined_outcome_if_adverse_and_contract_pays_gbp: float
    combined_outcome_if_adverse_and_contract_fails_gbp: float
    combined_outcome_if_benign_and_contract_fails_gbp: float
    remaining_downside_if_contract_pays_gbp: float
    basis_risk_summary: str


class RiskControlResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    blocking_reasons: list[str]
    warnings: list[str]
    checks_run: dict[str, bool]


class HedgeProposalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    proposal_hash: str
    created_at: str
    target_date: str
    budget_gbp: float
    status: AgentFinalStatus
    market_id: str | None = None
    market_question: str | None = None
    outcome_selected: str | None = None
    paper_quantity: int = 0
    max_total_cost_gbp: float = 0.0
    quote_timestamp: str | None = None
    data_origin: DataOriginLabel | None = None
    is_historical_replay: bool = False
    explanation: str
    rejection_reasons: dict[str, list[str]] = Field(default_factory=dict)
    calculation: HedgeCalculationResult | None = None
    risk_check: RiskControlResult | None = None
    approval_state: Literal["pending_human_approval", "approved", "rejected", "not_applicable"] = (
        "not_applicable"
    )
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
