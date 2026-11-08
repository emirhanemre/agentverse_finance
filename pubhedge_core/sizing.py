"""Hedge sizing, standard library only.

Maximise sum x_i (w_i - k_i) over whole shares x_i, subject to sum k_i x_i <= budget,
k_i x_i <= per-market cap and 0 <= x_i <= max_shares (payout never exceeds the loss covered).
This is the integer version of the sizing LP. It is solved exactly as a bounded knapsack by
dynamic programming over the budget in pence (binary-split share bundles), because rounding
the LP's fractional answer down is not always optimal. Ties go to the lower spend. Pence.
"""
from typing import Any, Dict, List

from .validate import is_int, require


def size(markets: Any, budget_pence: Any, per_market_cap_pence: Any) -> Dict[str, Any]:
    require(isinstance(markets, list), "markets must be a list")
    require(is_int(budget_pence) and budget_pence >= 0, "budget_pence must be a non-negative integer")
    require(is_int(per_market_cap_pence) and per_market_cap_pence >= 0, "per_market_cap_pence must be a non-negative integer")
    ids = set()
    for m in markets:
        require(isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"] not in ids, "unique market ids")
        ids.add(m["id"])
        require(is_int(m.get("cost_per_share_pence")) and m["cost_per_share_pence"] > 0, "cost_per_share_pence > 0")
        require(is_int(m.get("value_per_share_pence")) and m["value_per_share_pence"] >= 0, "value_per_share_pence >= 0")
        require(is_int(m.get("max_shares")) and m["max_shares"] >= 0, "max_shares >= 0")
    # bundles of 1, 2, 4, ... shares per market (binary splitting of the bound)
    bundles = []
    for m in sorted(markets, key=lambda m: m["id"]):
        k, edge = m["cost_per_share_pence"], m["value_per_share_pence"] - m["cost_per_share_pence"]
        n = min(m["max_shares"], per_market_cap_pence // k, budget_pence // k)
        if edge <= 0 or n <= 0:
            continue
        c = 1
        while n > 0:
            take = min(c, n)
            bundles.append((m["id"], take, take * k, take * edge))
            n -= take
            c *= 2
    best = [0] * (budget_pence + 1)  # best[b]: max value with spend <= b
    taken = []
    for _, _, cost, val in bundles:
        row = bytearray(budget_pence + 1)
        for b in range(budget_pence, cost - 1, -1):
            if best[b - cost] + val > best[b]:
                best[b] = best[b - cost] + val
                row[b] = 1
        taken.append(row)
    shares = {m["id"]: 0 for m in markets}
    b = budget_pence
    while b > 0 and best[b] == best[b - 1]:
        b -= 1  # cheapest spend that reaches the optimum
    for i in range(len(bundles) - 1, -1, -1):
        if taken[i][b]:
            mid, take, cost, _ = bundles[i]
            shares[mid] += take
            b -= cost
    pos: List[Dict[str, Any]] = [{"id": i, "shares": n} for i, n in sorted(shares.items()) if n > 0]
    cost = sum(n * next(m["cost_per_share_pence"] for m in markets if m["id"] == i) for i, n in shares.items())
    value = sum(n * next(m["value_per_share_pence"] for m in markets if m["id"] == i) for i, n in shares.items())
    return {"positions": pos, "total_cost_pence": cost, "expected_value_pence": value - cost}
