"""Cashflow forecast: the same engine scores the kit task and tells the owner
whether payroll clears."""
from typing import Any, Dict, List

from .validate import gbp, is_int, iso_date, require, unique_ids


def forecast(opening_balance_pence: Any, events: Any) -> Dict[str, Any]:
    require(is_int(opening_balance_pence), "opening_balance_pence must be an integer")
    rows = unique_ids(events)
    for ev in rows:
        require(is_int(ev.get("amount_pence")), "amount_pence must be an integer")
        gbp(ev.get("currency"))
        iso_date(ev.get("date"))
    # Order by date then id; free-text descriptions are never read.
    ordered = sorted(rows, key=lambda ev: (ev["date"], ev["id"]))
    balance = opening_balance_pence
    minimum = balance
    first_negative = None
    timeline: List[Dict[str, Any]] = []
    for ev in ordered:
        balance += ev["amount_pence"]
        if balance < minimum:
            minimum = balance
        if balance < 0 and first_negative is None:
            first_negative = ev["date"]
        timeline.append({"id": ev["id"], "date": ev["date"], "amount_pence": ev["amount_pence"],
                         "balance_after_pence": balance})
    return {
        "closing_balance_pence": balance,
        "minimum_balance_pence": minimum,
        "shortfall_pence": max(0, -minimum),
        "first_negative_date": first_negative,
        "timeline": timeline,
    }
