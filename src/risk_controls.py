"""Deterministic risk controls and compliance checks enforced in Python code.

Checks enforced:
1. Market status (`active` vs `closed`) and historical replay eligibility.
2. Geographic alignment (`London, UK` required for London SE1 pub).
3. Date alignment (contract event/resolution date must match the exposure date).
4. Weather metric alignment (daily max temperature is NOT interchangeable with rainfall exposure).
5. Quote freshness (blocks stale quotes unless explicitly running a labelled snapshot/replay).
6. Order-book depth and minimum downside offset sufficiency.
7. Price attractiveness (blocks contracts priced so high that payout-to-cost ratio cannot meaningfully offset loss).
8. Budget and per-contract concentration limits.
9. Currency consistency and FX validity.
10. Untrusted external text / prompt-injection guard.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from src.polymarket_client import detect_untrusted_content_flags
from src.schemas import HedgeCalculationResult, MarketCandidate, RiskControlResult

MONTH_NAME_TO_NUM = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def extract_contract_event_date(market: MarketCandidate) -> str | None:
    """Extract the specific YYYY-MM-DD event date referenced by a weather contract if present."""
    combined = f"{market.question} {market.resolution_rules}"
    iso_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", combined)
    if iso_match:
        return iso_match.group(1)

    # Match patterns like "on January 22, 2025" or "on January 22" with end_date year fallback
    m = re.search(
        r"\bon\s+(January|Jan|February|Feb|March|Mar|April|Apr|May|June|Jun|July|Jul|August|Aug|September|Sep|Sept|October|Oct|November|Nov|December|Dec)\s+(\d{1,2})(?:,\s*(202\d))?",
        combined,
         flags=re.IGNORECASE,
    )
    if m:
        month_num = MONTH_NAME_TO_NUM[m.group(1).lower()]
        day_num = int(m.group(2))
        year_num = int(m.group(3)) if m.group(3) else None
        if year_num is None and market.end_date and len(market.end_date) >= 4:
            try:
                year_num = int(market.end_date[:4])
            except ValueError:
                year_num = None
        if year_num is not None:
            return f"{year_num:04d}-{month_num:02d}-{day_num:02d}"

    if market.end_date and len(market.end_date) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", market.end_date[:10]):
        # Only treat end_date as a daily contract date if start_date is within 10 days of end_date
        if market.start_date and len(market.start_date) >= 10:
            try:
                d_start = dt.date.fromisoformat(market.start_date[:10])
                d_end = dt.date.fromisoformat(market.end_date[:10])
                if 0 <= (d_end - d_start).days <= 10:
                    return market.end_date[:10]
            except ValueError:
                pass
    return None


def check_contract_and_hedge_risk(
    market: MarketCandidate,
    calc: HedgeCalculationResult,
    target_date: str,
    exposure_driver: str,  # e.g. "rainfall", "cold_temperature", "combined_rain_and_cold"
    budget_gbp: float,
    max_per_contract_gbp: float = 500.0,
    max_acceptable_ask_price_usd: float = 0.72,
    min_executable_contracts: int = 20,
    min_net_offset_gbp: float = 25.0,
    max_quote_age_minutes: int = 120,
    decision_time_utc: str | None = None,
    allow_cached_or_replay_snapshot: bool = True,
    business_location: str = "London, UK",
    contract_event_date: str | None = None,
    geography_verified: bool | None = None,
    payoff_verified: bool = False,
) -> RiskControlResult:
    """Run all deterministic risk and suitability checks on a candidate contract and hedge sizing."""
    blocking: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    # 1. Untrusted external text / prompt injection check
    detected_flags = sorted(
        set(list(market.untrusted_content_flags) + detect_untrusted_content_flags(f"{market.question}\n{market.resolution_rules}"))
    )
    if detected_flags:
        checks["untrusted_content_clean"] = False
        blocking.append(
            f"Contract text contains untrusted prompt-injection or control-override patterns: {detected_flags}."
        )
    else:
        checks["untrusted_content_clean"] = True

    # 2. Market status check
    is_replay_origin = market.data_origin == "historical_replay_snapshot"
    if market.status != "active" and not (allow_cached_or_replay_snapshot and is_replay_origin):
        checks["market_status_valid"] = False
        blocking.append(f"Market {market.market_id} status is '{market.status}' (not active for live trading).")
    elif market.status != "active" and is_replay_origin:
        # Even in historical replay, a closed market with no order book cannot be executed without explicit replay book data
        checks["market_status_valid"] = True
        warnings.append("Historical closed market inspected in labelled replay mode.")
    else:
        checks["market_status_valid"] = True

    # 3. Geographic alignment against the configured business, not a default pub.
    loc_lower = market.location.lower()
    city = business_location.split(',')[0].strip().lower()
    if geography_verified is False or (geography_verified is None and (not city or city not in loc_lower)):
        checks["geography_matches_pub"] = False
        blocking.append(
            f"Geographic mismatch: contract covers '{market.location}', business is '{business_location}'."
        )
    else:
        checks["geography_matches_pub"] = True

    # 4. Date alignment check
    contract_date = contract_event_date or extract_contract_event_date(market)
    if contract_date != target_date:
        checks["date_matches_exposure"] = False
        blocking.append(
            f"Date mismatch: contract event date is '{contract_date or market.end_date or 'annual/unspecified'}', "
            f"which does not match target exposure date '{target_date}'."
        )
    else:
        checks["date_matches_exposure"] = True

    # 5. Weather measurement alignment check
    # A daily maximum-temperature market is NOT interchangeable with a rainfall market!
    meas = market.measurement
    driver = exposure_driver.lower()
    if meas == "non_weather_event" or meas == "storm_or_hurricane":
        checks["measurement_matches_exposure"] = False
        blocking.append(
            f"Weather metric mismatch: contract measures '{meas}', which does not hedge UK pub weather exposure."
        )
    elif "rain" in driver and "cold" not in driver and meas == "daily_max_temperature":
        checks["measurement_matches_exposure"] = False
        blocking.append(
            "Weather metric mismatch (basis risk): exposure is driven by rainfall, whereas this contract "
            "settles on daily maximum temperature (`daily_max_temperature`). A daily max-temperature market "
            "is not interchangeable with a rainfall market."
        )
    elif "cold" in driver and "rain" not in driver and meas == "precipitation_or_rainfall":
        checks["measurement_matches_exposure"] = False
        blocking.append(
            "Weather metric mismatch (basis risk): exposure is driven by cold temperature, whereas this contract "
            "settles on rainfall (`precipitation_or_rainfall`)."
        )
    else:
        # Also check that for a cold-temperature exposure, the contract bracket actually pays when it is cold!
        q_lower = market.question.lower()
        if "cold" in driver and meas == "daily_max_temperature" and not payoff_verified:
            # Look for "or higher" or warm brackets (> 45°F / 7.2°C) when hedging a cold snap
            if "or higher" in q_lower or "between 5" in q_lower or "between 46" in q_lower or "between 47" in q_lower or "between 48" in q_lower or "between 49" in q_lower:
                if calc.outcome_selected == "Yes":
                    checks["measurement_matches_exposure"] = False
                    blocking.append(
                        f"Payoff direction mismatch: buying 'Yes' on '{market.question}' pays in warmer weather, not during a cold snap."
                    )
                else:
                    checks["measurement_matches_exposure"] = True
            else:
                checks["measurement_matches_exposure"] = True
        else:
            checks["measurement_matches_exposure"] = True

    # 6. Quote freshness check
    checks["quote_freshness_valid"] = True
    if decision_time_utc and market.retrieval_timestamp:
        try:
            dec_dt = dt.datetime.fromisoformat(decision_time_utc.replace("Z", "+00:00"))
            ret_dt = dt.datetime.fromisoformat(market.retrieval_timestamp.replace("Z", "+00:00"))
            age_minutes = (dec_dt - ret_dt).total_seconds() / 60.0
            if age_minutes > max_quote_age_minutes and not allow_cached_or_replay_snapshot:
                checks["quote_freshness_valid"] = False
                blocking.append(
                    f"Stale quote: order book snapshot is {age_minutes:.1f} minutes old (limit {max_quote_age_minutes} min)."
                )
            elif age_minutes > max_quote_age_minutes:
                warnings.append(
                    f"Using saved snapshot retrieved {age_minutes:.1f} minutes before decision time (labelled cached/replay mode)."
                )
        except ValueError:
            checks["quote_freshness_valid"] = False
            blocking.append("Invalid retrieval_timestamp or decision_time_utc format.")

    # 7. Order-book depth check
    if calc.executable_contracts < min_executable_contracts:
        checks["sufficient_order_book_depth"] = False
        blocking.append(
            f"Insufficient order-book depth: only {calc.executable_contracts} contracts executable on the ask book "
            f"(minimum required: {min_executable_contracts})."
        )
    else:
        checks["sufficient_order_book_depth"] = True
        if calc.depth_exhausted and calc.unfilled_budget_gbp > 5.0:
            warnings.append(
                f"Ask book depth exhausted before full budget was deployed (£{calc.unfilled_budget_gbp:.2f} unfilled)."
            )

    # 8. Price attractiveness & minimum net downside offset check
    if calc.executable_contracts > 0 and calc.average_ask_price_usd > max_acceptable_ask_price_usd:
        checks["price_attractive"] = False
        blocking.append(
            f"Unattractive entry price: volume-weighted ask price is ${calc.average_ask_price_usd:.4f} USD "
            f"(exceeds maximum acceptable price ${max_acceptable_ask_price_usd:.2f} USD; insufficient net payout ratio)."
        )
    elif calc.net_profit_if_win_gbp < min_net_offset_gbp:
        checks["price_attractive"] = False
        blocking.append(
            f"Insufficient downside offset: net hedge profit if contract pays is only £{calc.net_profit_if_win_gbp:.2f} "
            f"(minimum meaningful offset: £{min_net_offset_gbp:.2f})."
        )
    else:
        checks["price_attractive"] = True

    # 9. Budget & per-contract concentration limits
    limit_gbp = min(float(budget_gbp), float(max_per_contract_gbp))
    if calc.total_entry_cost_gbp <= 0.0 or calc.total_entry_cost_gbp > limit_gbp + 1e-6 or float(budget_gbp) > float(max_per_contract_gbp):
        checks["within_budget_and_limits"] = False
        if float(budget_gbp) > float(max_per_contract_gbp):
            blocking.append(
                f"Requested budget £{budget_gbp:.2f} exceeds per-contract risk limit of £{max_per_contract_gbp:.2f}."
            )
        else:
            blocking.append(
                f"Total entry cost £{calc.total_entry_cost_gbp:.2f} violates budget/limit bounds (0 < cost <= £{limit_gbp:.2f})."
            )
    else:
        checks["within_budget_and_limits"] = True

    # 10. Currency consistency check
    if calc.fx_rate_usd_per_gbp <= 0.5 or calc.fx_rate_usd_per_gbp >= 3.0:
        checks["currency_consistent"] = False
        blocking.append(f"Implausible USD/GBP exchange rate ({calc.fx_rate_usd_per_gbp}).")
    else:
        checks["currency_consistent"] = True

    passed = len(blocking) == 0
    return RiskControlResult(
        passed=passed,
        blocking_reasons=blocking,
        warnings=warnings,
        checks_run=checks,
    )
