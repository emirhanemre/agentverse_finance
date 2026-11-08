"""Limit guard. Every proposed hedge is checked here before a human can approve it,
and again at execution. Pure function: same inputs, same verdict."""
from typing import Any, Dict, List

from .validate import is_int, require

DEFAULT_LIMITS = {
    "weekly_spend_cap_pence": 80000,   # £800 a week
    "monthly_max_loss_pence": 200000,  # £2,000 a month
    "per_market_cap_pence": 60000,     # no more than £600 in one market
    "approval_threshold_pence": 5000,  # above £50 needs a second, explicit confirmation
}


def check(cost_pence: Any, market_id: Any, limits: Dict[str, int], ledger: Dict[str, Any]) -> Dict[str, Any]:
    """ledger: spent_this_week_pence, at_risk_this_month_pence (open premium plus realised
    losses this month), by_market_pence {market_id: pence already committed}."""
    require(is_int(cost_pence) and cost_pence >= 0, "cost_pence must be a non-negative integer")
    require(isinstance(market_id, str) and market_id != "", "market_id required")
    for k in DEFAULT_LIMITS:
        require(is_int(limits.get(k)) and limits[k] >= 0, f"{k} must be a non-negative integer")
    week = ledger.get("spent_this_week_pence", 0) + cost_pence
    month = ledger.get("at_risk_this_month_pence", 0) + cost_pence
    market = ledger.get("by_market_pence", {}).get(market_id, 0) + cost_pence
    checks: List[Dict[str, Any]] = [
        {"name": "weekly_spend", "value_pence": week, "cap_pence": limits["weekly_spend_cap_pence"],
         "pass": week <= limits["weekly_spend_cap_pence"]},
        {"name": "monthly_max_loss", "value_pence": month, "cap_pence": limits["monthly_max_loss_pence"],
         "pass": month <= limits["monthly_max_loss_pence"]},
        {"name": "per_market_concentration", "value_pence": market, "cap_pence": limits["per_market_cap_pence"],
         "pass": market <= limits["per_market_cap_pence"]},
    ]
    blocked = [c for c in checks if not c["pass"]]
    reason = None
    if blocked:
        c = blocked[0]
        reason = (f"{c['name'].replace('_', ' ')}: £{c['value_pence'] / 100:.2f} would exceed the "
                  f"£{c['cap_pence'] / 100:.2f} cap")
    return {"allowed": not blocked, "checks": checks, "reason": reason,
            "needs_second_approval": cost_pence > limits["approval_threshold_pence"]}
