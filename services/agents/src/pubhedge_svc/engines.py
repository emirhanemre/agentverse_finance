"""Deterministic engines exposed as agent tools. The model never computes numbers:
everything a narration may quote comes out of these functions."""
import csv
import json
import math
from datetime import date, timedelta
from functools import lru_cache

import numpy as np

from pubhedge_core import cashflow as core_cashflow
from pubhedge_core import limits as core_limits
from pubhedge_core import sizing as core_sizing

from .config import DATA

TRAIN_END = "2024-10-31"  # train on 2021-01..2024-10; the last 24 months are held out
CONTRACT_MM = 3.0  # synthetic contract: >= 3mm of rain 12:00-18:00 on the day
VENUE_MARGIN = 0.03  # synthetic venue overround on top of the calibrated probability
SPREAD = 0.02  # synthetic bid/ask spread
SLIPPAGE = 0.01  # adverse fill, as a share of price
FEE_RATE = 0.05  # Polymarket weather/sports taker fee rate: fee = C x rate x p x (1-p)
SHORTFALL_PENALTY = 0.5  # £1 that keeps payroll whole is worth £1.50 to the owner (assumption)


# ---------- data ----------
@lru_cache(maxsize=None)
def panel() -> dict:
    out: dict = {}
    with open(DATA / "synthetic" / "takings_panel.csv") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["pub_id"], []).append(r)
    return out


@lru_cache(maxsize=None)
def weather(loc: str) -> dict:
    with open(DATA / "weather" / f"{loc}.csv") as f:
        return {r["date"]: r for r in csv.DictReader(f)}


@lru_cache(maxsize=None)
def manifest() -> dict:
    return json.loads((DATA / "synthetic" / "manifest.json").read_text())


def pub_location(pub_id: str) -> str:
    return next(p["weather_location"] for p in manifest()["panel"] if p["pub_id"] == pub_id)


@lru_cache(maxsize=None)
def bank_feed() -> list:
    return json.loads((DATA / "synthetic" / "bank_feed_demo.json").read_text())["Data"]["Transaction"]


def _f(v, d=0.0):
    return float(v) if v not in ("", None) else d


# ---------- regression ----------
FEATURES = ["intercept", "trend_years", "season_cos", "season_sin", "tue", "wed", "thu", "fri", "sat", "sun",
            "pm_rain_mm_weekend", "pm_rain_mm_weekday", "heat_c_over_14", "match_day", "duty_rises"]


def design(rows):
    t0 = date(2021, 1, 1)
    X, y, dates = [], [], []
    for r in rows:
        d = date.fromisoformat(r["date"])
        wd = d.weekday()
        doy = d.timetuple().tm_yday
        rain = _f(r["pm_rain_mm"])
        wknd = wd >= 4
        X.append([1.0, (d - t0).days / 365.25, math.cos(2 * math.pi * doy / 365.25),
                  math.sin(2 * math.pi * doy / 365.25)] + [1.0 if wd == k else 0.0 for k in range(1, 7)] +
                 [rain if wknd else 0.0, 0.0 if wknd else rain, max(0.0, _f(r["tmax_c"], 12) - 14),
                  float(r["match_day"]), float(r["duty_rises"])])
        y.append(float(r["takings_gbp"]))
        dates.append(r["date"])
    return np.array(X), np.array(y), dates


def fit_takings(pub_id: str = "demo", train_end: str = TRAIN_END) -> dict:
    """OLS of daily takings on weather, sport and duty. Reports 95% CIs and R² on the
    training years and on the held-out later months."""
    rows = panel()[pub_id]
    X, y, dates = design(rows)
    train = np.array([d <= train_end for d in dates])
    Xt, yt = X[train], y[train]
    beta, *_ = np.linalg.lstsq(Xt, yt, rcond=None)
    resid = yt - Xt @ beta
    n, k = Xt.shape
    sigma2 = resid @ resid / (n - k)
    se = np.sqrt(np.diag(sigma2 * np.linalg.inv(Xt.T @ Xt)))

    def r2(Xs, ys):
        e = ys - Xs @ beta
        return float(1 - e @ e / ((ys - ys.mean()) @ (ys - ys.mean())))

    coefs = {name: {"estimate": round(float(b), 2), "ci95": [round(float(b - 1.96 * s), 2), round(float(b + 1.96 * s), 2)]}
             for name, b, s in zip(FEATURES, beta, se)}
    return {"pub_id": pub_id, "n_train": int(train.sum()), "n_holdout": int((~train).sum()),
            "train_period": [dates[0], train_end],
            "holdout_period": [next(d for d in dates if d > train_end), dates[-1]],
            "r2_train": round(r2(Xt, yt), 3), "r2_holdout": round(r2(X[~train], y[~train]), 3),
            "residual_sd_gbp": round(float(math.sqrt(sigma2)), 2), "coefficients": coefs,
            "_beta": beta.tolist()}


def predict_day(fit: dict, row: dict) -> float:
    X, _, _ = design([{**row, "takings_gbp": 0}])
    return float(X[0] @ np.array(fit["_beta"]))


# ---------- pricing ----------
@lru_cache(maxsize=None)
def calibrate_rain(loc: str, train_end: str = TRAIN_END, mm: float = CONTRACT_MM) -> dict:
    """P(observed 12-18h rain >= mm | archived forecast bucket), training years only."""
    edges = [0.0, 0.2, 1.0, 2.0, 3.0, 5.0, 8.0, 1e9]
    hits = [0] * (len(edges) - 1)
    tot = [0] * (len(edges) - 1)
    for d, r in weather(loc).items():
        if d > train_end or r["fc_pm_rain_mm"] == "" or r["pm_rain_mm"] == "":
            continue
        fc = float(r["fc_pm_rain_mm"])
        b = next(i for i in range(len(edges) - 1) if edges[i] <= fc < edges[i + 1])
        tot[b] += 1
        hits[b] += float(r["pm_rain_mm"]) >= mm
    # Laplace smoothing so empty buckets stay sensible
    probs = [(h + 1) / (t + 2) for h, t in zip(hits, tot)]
    return {"edges": edges, "probs": probs, "n": tot}


def rain_probability(loc: str, forecast_pm_mm: float, train_end: str = TRAIN_END) -> float:
    cal = calibrate_rain(loc, train_end)
    e = cal["edges"]
    b = next(i for i in range(len(e) - 1) if e[i] <= forecast_pm_mm < e[i + 1])
    return cal["probs"][b]


def synthetic_price(prob: float) -> dict:
    """SYNTHETIC contract price rule: calibrated probability + venue margin, then spread."""
    mid = min(0.97, max(0.02, prob + VENUE_MARGIN))
    return {"mid": round(mid, 4), "ask": round(min(0.99, mid + SPREAD / 2), 4),
            "rule": f"calibrated P(rain>={CONTRACT_MM}mm | forecast) + {VENUE_MARGIN} margin, ±{SPREAD / 2} spread"}


def cost_per_share(ask: float, fee_rate: float = FEE_RATE) -> float:
    fill = ask * (1 + SLIPPAGE)
    return fill + fee_rate * fill * (1 - fill)


# ---------- sizing ----------
def size_hedges(markets: list, weekly_cap_gbp: float, month_room_gbp: float, per_market_cap_gbp: float) -> dict:
    """Maximise expected value to the owner, sum x_i (w_i - k_i), where k_i is the all-in cost per
    £1 share and w_i = q_i x (1 + penalty if the event would cause a payroll shortfall). Subject to:
    payout <= loss in the event (no speculation), spend <= weekly cap and remaining monthly loss
    budget, spend per market <= concentration cap. Solved exactly in whole shares by
    pubhedge_core.sizing (the same code the kit's pub_hedge_sizing task scores); costs round up
    to the penny, values round down, so the solver never overstates value."""
    if not markets:
        return {"status": "no_markets", "positions": [], "total_cost_gbp": 0.0}
    by = {m["market_id"]: m for m in markets}
    core_in = []
    for m in markets:
        w = m["model_prob"] * (1 + (SHORTFALL_PENALTY if m["causes_shortfall"] else 0))
        core_in.append({"id": m["market_id"], "cost_per_share_pence": max(1, math.ceil(m["cost_per_share"] * 100)),
                        "value_per_share_pence": math.floor(w * 100), "max_shares": max(0, math.floor(m["loss_if_event_gbp"]))})
    budget = max(0, math.floor(min(weekly_cap_gbp, month_room_gbp) * 100))
    res = core_sizing.size(core_in, budget, max(0, math.floor(per_market_cap_gbp * 100)))
    pos = [{"market_id": p["id"], "shares": p["shares"], "cost_gbp": round(p["shares"] * by[p["id"]]["cost_per_share"], 2),
            "payout_if_event_gbp": float(p["shares"])} for p in res["positions"]]
    no_value = [c["id"] for c in core_in if c["value_per_share_pence"] <= c["cost_per_share_pence"]]
    return {"status": "ok" if pos else "nothing_worth_buying", "positions": pos,
            "solver": "pubhedge_core.sizing (exact, whole shares)",
            "total_cost_gbp": round(sum(p["cost_gbp"] for p in pos), 2), "no_value_at_price": no_value,
            "expected_value_pence": res["expected_value_pence"]}


# ---------- paper exchange ----------
def paper_fill(market: dict, shares: int) -> dict:
    ask = market["ask"]
    fill = round(ask * (1 + SLIPPAGE), 4)
    fee = round(shares * market.get("fee_rate", FEE_RATE) * fill * (1 - fill), 2)
    return {"venue": "PAPER", "market_id": market["market_id"], "shares": shares, "fill_price": fill,
            "fee_gbp": fee, "cost_gbp": round(shares * fill + fee, 2), "price_source": market["price_badge"],
            "note": "PAPER TRADING: no real order was placed"}


# ---------- cashflow ----------
def upcoming_events(start: date, weeks: int, fit: dict, loc: str, scenario: dict) -> list:
    """Scheduled cash events for the next weeks, in pence, derived from the synthetic
    profile: expected card settlements (from the regression), Friday payroll, Tuesday
    suppliers and month-start fixed costs. `scenario` maps date -> pm rain mm."""
    P = manifest()["params"]
    hist = {r["date"]: r for r in panel()["demo"]}
    last = max(hist)
    trailing = sorted(hist)[-28:]
    avg_net_week = sum(float(hist[d]["takings_gbp"]) for d in trailing) / 4 * (1 - P["vat_share"])
    events = []
    d = start
    for _ in range(weeks * 7):
        iso = d.isoformat()
        # climatology for unknown future days: same calendar day's weather last year
        ref = weather(loc).get(iso) or weather(loc).get((d - timedelta(days=364)).isoformat()) or {}
        row = {"date": iso, "pm_rain_mm": scenario.get(iso, _f(ref.get("pm_rain_mm"))),
               "tmax_c": _f(ref.get("tmax_c"), 12), "match_day": hist.get(iso, {}).get("match_day", 0),
               "duty_rises": hist[last]["duty_rises"]}
        take = max(0.0, predict_day(fit, row))
        nxt = (d + timedelta(days=1)).isoformat()
        events.append({"id": f"card-{nxt}", "date": nxt, "amount_pence": int(take * (1 - P["card_fee"]) * 100),
                       "currency": "GBP", "kind": "card_settlement", "rain_mm": row["pm_rain_mm"]})
        if d.weekday() == 4:
            events.append({"id": f"payroll-{iso}", "date": iso, "currency": "GBP", "kind": "payroll",
                           "amount_pence": -int(avg_net_week * P["staff_share_of_net"] * 100)})
        if d.weekday() == 1:
            events.append({"id": f"suppliers-{iso}", "date": iso, "currency": "GBP", "kind": "suppliers",
                           "amount_pence": -int(avg_net_week * P["cogs_share_of_net"] * 100)})
        if d.day == 1:
            fixed = P["rent_monthly_gbp"] + P["utilities_monthly_gbp"] + P["other_fixed_monthly_gbp"]
            events.append({"id": f"fixed-{iso}", "date": iso, "currency": "GBP", "kind": "fixed_costs",
                           "amount_pence": -int(fixed * 100)})
        d += timedelta(days=1)
    return events


def payroll_check(opening_pence: int, events: list) -> dict:
    """Runs the same cashflow engine the kit scores, and reports the first payroll that
    doesn't clear."""
    out = core_cashflow.forecast(opening_pence, [{k: e[k] for k in ("id", "date", "amount_pence", "currency")}
                                                 for e in events])
    kinds = {e["id"]: e["kind"] for e in events}
    first_bad = next((t for t in out["timeline"] if kinds[t["id"]] == "payroll" and t["balance_after_pence"] < 0), None)
    return {"closing_balance_pence": out["closing_balance_pence"], "minimum_balance_pence": out["minimum_balance_pence"],
            "shortfall_pence": out["shortfall_pence"], "first_negative_date": out["first_negative_date"],
            "first_failed_payroll": first_bad, "timeline": out["timeline"]}


check_limits = core_limits.check
