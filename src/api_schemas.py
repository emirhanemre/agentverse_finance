"""HTTP contracts. Browser-supplied data is never trusted as a financial record."""
from __future__ import annotations

import datetime as dt
import re
from typing import Literal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class ProfileInput(StrictModel):
    pubName: str = Field(min_length=2, max_length=120)
    postcode: str = Field(max_length=12)
    owner: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    location_name: str = Field(min_length=2, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    indoor_capacity: int = Field(default=90, ge=10, le=500)
    outdoor_capacity: int = Field(default=70, ge=0, le=500)
    opening_hours: float = Field(default=11, ge=1, le=24)
    currency: Literal["GBP"] = "GBP"

    @field_validator("postcode")
    @classmethod
    def postcode_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}", value, re.I):
            raise ValueError("Enter a full UK postcode, for example SE22 8HD.")
        return value.upper()

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class SettingsInput(StrictModel):
    weekly_spend_gbp: float = Field(default=300, gt=0, le=10000, multiple_of=.01)
    monthly_loss_gbp: float = Field(default=500, gt=0, le=10000, multiple_of=.01)
    per_contract_gbp: float = Field(default=200, gt=0, le=1000, multiple_of=.01)
    fx_usd_per_gbp: float = Field(default=1.28, gt=.5, lt=3, multiple_of=.0001)
    fee_bps: int = Field(default=50, ge=0, le=1000)
    max_station_distance_km: float = Field(default=30, ge=1, le=100)
    monitor_enabled: bool = False
    monitor_interval_minutes: int = Field(default=30, ge=5, le=1440)
    monitor_horizon_days: int = Field(default=3, ge=1, le=7)
    monitor_budget_gbp: float = Field(default=100, gt=0, le=1000, multiple_of=.01)


class SalesImport(StrictModel):
    filename: str = Field(min_length=1, max_length=200)
    csv: str = Field(min_length=1, max_length=2_000_000)


class OperatingCostsInput(StrictModel):
    fixed_daily_cost_gbp: float = Field(default=1000, ge=0, le=100000, multiple_of=.01)
    variable_cost_pct: float = Field(default=30, ge=0, le=100, multiple_of=.01)


class OperatingProfitScenario(StrictModel):
    revenue_gbp: float
    variable_cost_gbp: float
    fixed_cost_gbp: float
    total_cost_gbp: float
    operating_profit_gbp: float
    operating_margin_pct: float | None
    prediction_interval_80_low_gbp: float | None
    prediction_interval_80_high_gbp: float | None


class OperatingProfitResponse(StrictModel):
    target_date: str
    origin: Literal['demo_cost_assumptions']
    assumptions: OperatingCostsInput
    selected: OperatingProfitScenario
    reference: OperatingProfitScenario
    profit_difference_gbp: float
    note: str


class AnalysisInput(StrictModel):
    target_date: dt.date
    weather_mode: Literal["manual", "forecast"] = "manual"
    market_mode: Literal["live", "cached", "test_suitable", "test_no_match"] = "live"
    budget_gbp: float = Field(default=100, gt=0, le=1000, multiple_of=.01)
    temp_max_c: float = Field(default=15, ge=-30, le=55)
    rain_mm: float = Field(default=14, ge=0, le=300)
    wind_max_kmh: float = Field(default=26, ge=0, le=200)
    sunshine_hours: float = Field(default=.5, ge=0, le=24)
    model_mode: Literal['auto', 'synthetic_demo'] = 'auto'


class ApprovalInput(StrictModel):
    confirmed_proposal_hash: str
    confirmed_quantity: int = Field(gt=0)
    confirmed_max_cost_gbp: float = Field(gt=0, multiple_of=.01)
    confirmed_quote_timestamp: str
    acknowledge_paper_risk: Literal[True]


class RejectInput(StrictModel):
    note: str = Field(default="Rejected by human operator", max_length=500)


class ProfileResponse(StrictModel):
    profile: ProfileInput | None
    verification: Literal['self_reported']


class TaskEventResponse(StrictModel):
    id: int
    analysis_id: str
    created_at: str
    label: str
    detail: str


class AnalysisResponse(StrictModel):
    id: str
    revision: int
    created_at: str
    state: Literal['running', 'complete', 'failed']
    payload: dict[str, Any] = Field(description='Saved inputs, source provenance, comparison, candidates, decision and errors. Financial values are computed on the server.')
    events: list[TaskEventResponse]


class AnalysisStartedResponse(StrictModel):
    id: str
    state: Literal['running']


class SummaryResponse(StrictModel):
    weekly_reserved_gbp: float
    monthly_reserved_loss_gbp: float
    open_positions: int
    total_entry_cost_gbp: float
    hypothetical_payout_gbp: float
    pending_approvals: int
    settled_payout_gbp: float | None = None
    realized_paper_pnl_gbp: float | None = None


class StateResponse(StrictModel):
    profile: ProfileInput | None
    settings: SettingsInput
    revision: int
    setup_complete: bool
    dataset: dict[str, Any] | None = Field(description='Validated daily sales summary and provenance; raw rows stay server-side.')
    forecast: dict[str, Any] | None
    latest_analysis: str | None
    active_analysis: str | None
    analysis: AnalysisResponse | None
    proposals: list[dict[str, Any]]
    positions: list[dict[str, Any]]
    activity: list[dict[str, Any]]
    sources: list[dict[str, str]]
    summary: SummaryResponse
    execution_mode: str
    model_note: str
    business_model: dict[str, Any] | None = None
    training_job: dict[str, Any] | None = None
    monitoring: dict[str, Any] | None = None
    notifications: list[dict[str, Any]] = []
    company: dict[str, Any] | None = None
    operating_costs: OperatingCostsInput = Field(default_factory=OperatingCostsInput)
    operating_profit: OperatingProfitResponse | None = None
