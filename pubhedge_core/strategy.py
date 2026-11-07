"""Hedge-timing rule for the kit's market_step task.

Trend filter with a cost-aware no-trade band, using observed history only:
  fast = mean of the last 5 closes, slow = mean of the last 20.
  Enter when fast exceeds slow by more than the band; exit when it falls below
  slow by more than the band. The band is the round-trip cost (two fees as a
  share of equity plus two slippages) plus a 1% buffer, so a signal must clear
  what a trade costs before we churn the position.
Not tuned to any generator family. Reported honestly against buy-and-hold and cash.
"""
from typing import Any, Dict

from .validate import is_int, require

FAST, SLOW, BUFFER = 5, 20, 0.01


def decide(inp: Any) -> Dict[str, Any]:
    require(isinstance(inp, dict), "input must be an object")
    hist = inp.get("history")
    require(isinstance(hist, list) and len(hist) >= 1, "history must be a nonempty list")
    prices = []
    for bar in hist:
        require(isinstance(bar, dict) and is_int(bar.get("price_pence")) and bar["price_pence"] > 0,
                "price_pence must be a positive integer")
        prices.append(bar["price_pence"])
    cash, shares = inp.get("cash_pence"), inp.get("shares")
    fee, bps = inp.get("fee_pence", 0), inp.get("slippage_bps", 0)
    for v in (cash, shares, fee, bps):
        require(is_int(v) and v >= 0, "cash, shares, fee and slippage must be non-negative integers")
    last = prices[-1]
    if len(prices) < SLOW:
        return {"action": "hold", "trace": {"reason": "warming_up", "bars": len(prices)}}
    fast = sum(prices[-FAST:]) / FAST
    slow = sum(prices[-SLOW:]) / SLOW
    equity = cash + shares * last
    band = (2 * fee / equity if equity else 1.0) + 2 * bps / 10000 + BUFFER
    gap = fast / slow - 1
    action = "hold"
    if shares == 0 and gap > band and cash - fee >= last:
        action = "buy"
    elif shares > 0 and gap < -band:
        action = "sell"
    return {"action": action,
            "trace": {"fast": round(fast, 2), "slow": round(slow, 2), "gap": round(gap, 5), "band": round(band, 5)}}
