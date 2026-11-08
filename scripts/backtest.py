"""Walk-forward backtest on unseen months. Synthetic takings, real weather.

Train (regression and rain calibration): 2021-01-01..2024-10-31, per pub.
Test (never seen by the policy):          2024-11-01..2026-10-31 (24 months).
Each Thursday the policy sees only: the archived forecast for Sat/Sun, the scheduled
payments for the next 8 days, and the model fitted on training years.

Policies: no hedge; naive (£20 on each of Sat and Sun every weekend); ours (cashflow-
triggered LP sizing under the caps). Contracts are SYNTHETIC (no London rain market
exists on Polymarket): pays £1/share if >= 3mm falls 12:00-18:00 at the pub's grid point.
Costs: price + spread + 1% slippage + Polymarket weather taker fee (0.05 x p x (1-p)).

  uv run --project services/agents python scripts/backtest.py
"""
import importlib.util
import json
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from pubhedge_svc import engines as E

ROOT = Path(__file__).resolve().parents[1]
TEST_START, TEST_END = date(2024, 11, 1), date(2026, 10, 31)
WET_MM = 6.0  # rain assumed in the "event happens" scenario
NAIVE_STAKE = 20.0
SWEEP_GBP = 5000.0  # buffer the owner keeps in the current account, scaled by pub size
LIMITS = {"weekly": 120.0, "monthly": 400.0, "market": 60.0}
BOOT = 1000

spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts" / "gen_synthetic.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def cash_by_date(pub_rows, scale):
    P = dict(gen.PARAMS)
    for k in ("rent_monthly_gbp", "utilities_monthly_gbp", "other_fixed_monthly_gbp"):
        P[k] = P[k] * scale  # fixed costs scale with the pub
    rows = [{**r, "takings_gbp": float(r["takings_gbp"])} for r in pub_rows]
    tx = gen.bank_feed(rows, E.manifest()["seed"], P)
    out = defaultdict(list)
    vat_move = P["vat_share"] * 0.62  # same net-of-input-VAT assumption as the generator
    for t in tx:
        if t["ProprietaryBankTransactionCode"] == "HMRC_VAT":
            continue  # paid from the VAT account
        if t["ProprietaryBankTransactionCode"] == "CARD_SETTLEMENT":
            t = {**t, "amount_pence": int(t["amount_pence"] * (1 - vat_move))}
        out[t["date"]].append(t)
    return out


def pot(feed, d):
    """Cash the owner keeps back on Monday d: fixed costs due within 10 days. VAT lives in a
    separate VAT account (standard advice), so it is moved out as takings settle."""
    return -sum(t["amount_pence"] for k in range(1, 11) for t in feed.get((d + timedelta(days=k)).isoformat(), [])
                if t["ProprietaryBankTransactionCode"] in ("RENT", "UTILITIES", "OTHER")) / 100


BALANCES: dict = {}  # (pub, policy) -> {date: end-of-day balance}; used by the demo scenario


def simulate(pub_id, policy):
    meta = next(p for p in E.manifest()["panel"] if p["pub_id"] == pub_id)
    loc, scale = meta["weather_location"], meta["scale"]
    rows = E.panel()[pub_id]
    fit = E.fit_takings(pub_id)
    beta_rain = -fit["coefficients"]["pm_rain_mm_weekend"]["estimate"]
    wx = E.weather(loc)
    feed = cash_by_date(rows, scale)
    sweep = SWEEP_GBP * scale
    bal = sweep
    d = TEST_START - timedelta(days=60)
    week_rows, month_net = [], defaultdict(float)
    pending_payout = 0.0
    month_premium = defaultdict(float)
    month_payout = defaultdict(float)
    cur_week = {"start": None, "pub": pub_id, "net": 0.0, "shortfall": False, "premium": 0.0, "payout": 0.0}
    while d <= TEST_END:
        iso = d.isoformat()
        in_test = d >= TEST_START
        if d.weekday() == 0:
            if in_test and cur_week["start"]:
                week_rows.append(dict(cur_week))
            cur_week = {"start": iso, "pub": pub_id, "net": 0.0, "shortfall": False, "premium": 0.0, "payout": 0.0}
            bal += pending_payout
            cur_week["net"] += pending_payout
            cur_week["payout"] += pending_payout
            month_payout[iso[:7]] += pending_payout
            pending_payout = 0.0
            # Owner sweeps surplus to savings, keeping the buffer plus the pot. Transfers, not losses.
            known = pot(feed, d)
            if bal > sweep + known:
                bal = sweep + known
        flows = sum(t["amount_pence"] for t in feed.get(iso, [])) / 100
        bal += flows
        cur_week["net"] += flows
        if in_test and d.weekday() == 3 and policy != "none" and d + timedelta(days=3) <= TEST_END:
            sat, sun = d + timedelta(days=2), d + timedelta(days=3)
            buys = decide(policy, d, sat, sun, bal, feed, fit, beta_rain, loc, wx, sweep,
                          month_premium[iso[:7]] - month_payout[iso[:7]])
            for b in buys:
                bal -= b["cost"]
                cur_week["net"] -= b["cost"]
                cur_week["premium"] += b["cost"]
                month_premium[iso[:7]] += b["cost"]
                if float(wx[b["day"]]["pm_rain_mm"] or 0) >= E.CONTRACT_MM:
                    pending_payout += b["shares"]
        if d.weekday() == 4 and any(t["ProprietaryBankTransactionCode"] == "PAYROLL" for t in feed.get(iso, [])):
            if bal < 0:
                cur_week["shortfall"] = True
                cur_week["depth"] = cur_week.get("depth", 0.0) - bal
        if in_test:
            month_net[iso[:7]] += flows
        BALANCES.setdefault((pub_id, policy), {})[iso] = round(bal, 2)
        d += timedelta(days=1)
    if cur_week["start"]:
        week_rows.append(cur_week)
    return week_rows


def market(day, loc, wx, fit_beta):
    fc = float(wx[day.isoformat()]["fc_pm_rain_mm"] or 0)
    q = E.rain_probability(loc, fc)
    px = E.synthetic_price(q)
    return {"day": day.isoformat(), "fc": fc, "q": q, "ask": px["ask"], "k": E.cost_per_share(px["ask"]),
            "loss": max(0.0, fit_beta * (WET_MM - fc))}


def project(feed, thu, sat, sun, bal, fit, wx, sweep, rain_override):
    """Thursday projection to next Friday's payroll. Known schedule from the feed for
    non-card items (payroll, suppliers, fixed costs are scheduled in advance); card takings
    from the training-years model, with rain_override (date -> mm) for the weekend."""
    events = []
    for i in range(1, 9):
        dd = thu + timedelta(days=i)
        for t in feed.get(dd.isoformat(), []):
            if t["ProprietaryBankTransactionCode"] != "CARD_SETTLEMENT":
                events.append({"id": t["TransactionId"], "date": dd.isoformat(), "amount_pence": t["amount_pence"],
                               "currency": "GBP", "kind": "payroll" if t["ProprietaryBankTransactionCode"] == "PAYROLL"
                               else "other"})
        prev = dd - timedelta(days=1)
        r = wx[prev.isoformat()]
        rain = rain_override.get(prev.isoformat(), float(r["fc_pm_rain_mm"] or 0))
        take = E.predict_day(fit, {"date": prev.isoformat(), "pm_rain_mm": rain,
                                   "tmax_c": r["fc_tmax_c"] or r["tmax_c"], "match_day": 0, "duty_rises": 3})
        vat_move = gen.PARAMS["vat_share"] * 0.62
        events.append({"id": f"card-{dd}", "date": dd.isoformat(), "amount_pence":
                       int(max(0, take) * (1 - gen.PARAMS["card_fee"]) * (1 - vat_move) * 100),
                       "currency": "GBP", "kind": "card"})
    # the owner's standing Monday sweep is part of the plan, so project it too
    mon = thu + timedelta(days=4)
    pre = E.core_cashflow.forecast(int(bal * 100), [e for e in events if e["date"] < mon.isoformat()])
    cap = int((sweep + pot(feed, mon)) * 100)
    if pre["closing_balance_pence"] > cap:
        events.append({"id": "0-sweep", "date": mon.isoformat(), "amount_pence": cap - pre["closing_balance_pence"],
                       "currency": "GBP", "kind": "sweep"})
    return E.payroll_check(int(bal * 100), events)


def decide(policy, thu, sat, sun, bal, feed, fit, beta_rain, loc, wx, sweep, month_net_loss):
    ms = [market(sat, loc, wx, beta_rain), market(sun, loc, wx, beta_rain)]
    if policy == "naive":
        return [{"day": m["day"], "shares": math.floor(NAIVE_STAKE / m["k"]),
                 "cost": round(math.floor(NAIVE_STAKE / m["k"]) * m["k"], 2)} for m in ms]
    chk = project(feed, thu, sat, sun, bal, fit, wx, sweep, {sat.isoformat(): WET_MM, sun.isoformat(): WET_MM})
    at_risk = chk["first_failed_payroll"] is not None
    mk = [{"market_id": m["day"], "cost_per_share": m["k"], "model_prob": m["q"], "causes_shortfall": at_risk,
           "loss_if_event_gbp": m["loss"]} for m in ms]
    x = 5 if policy == "ours_caps_x5" else 1  # sensitivity: same rule, caps five times larger
    sized = E.size_hedges(mk, x * LIMITS["weekly"], x * LIMITS["monthly"] - month_net_loss, x * LIMITS["market"])
    return [{"day": p["market_id"], "shares": p["shares"], "cost": p["cost_gbp"]} for p in sized["positions"]]


def metrics(weeks):
    nets = np.array([w["net"] for w in weeks])
    months = defaultdict(float)
    for w in weeks:
        months[(w["pub"], w["start"][:7])] += w["net"]
    mv = np.array(list(months.values()))
    k = max(1, int(round(len(nets) * 0.05)))
    years = len(weeks) / 52.18  # pub-years
    return {"hedge_net_gbp_per_year": float(sum(w["payout"] - w["premium"] for w in weeks) / years),
            "premium_gbp_per_year": float(sum(w["premium"] for w in weeks) / years),
            "payouts_gbp_per_year": float(sum(w["payout"] for w in weeks) / years),
            "shortfall_weeks_per_year": float(sum(w["shortfall"] for w in weeks) / years),
            "shortfall_depth_gbp_per_year": float(sum(w.get("depth", 0.0) for w in weeks) / years),
            "worst_week_gbp": float(nets.min()), "worst_month_gbp": float(mv.min()),
            "losing_months_per_year": float((mv < 0).sum() / years),
            "weekly_cash_sd_gbp": float(nets.std(ddof=1)),
            "cvar5_weekly_gbp": float(np.sort(nets)[:k].mean())}


def bootstrap(per_pub, rng):
    """Two-stage bootstrap: resample pubs, then weeks within each pub (8-week blocks)."""
    pubs = list(per_pub)
    stats = []
    for _ in range(BOOT):
        sample = []
        for p in rng.choices(pubs, k=len(pubs)):
            w = per_pub[p]
            nb = len(w) // 8
            for _b in range(nb):
                s = rng.randrange(0, len(w) - 8)
                sample += w[s:s + 8]
        stats.append(metrics(sample))
    return {k: [float(np.percentile([s[k] for s in stats], 2.5)), float(np.percentile([s[k] for s in stats], 97.5))]
            for k in stats[0]}


def main():
    rng = random.Random(20261108)
    res = {"policies": {}, "per_pub": defaultdict(dict)}
    pubs = [p["pub_id"] for p in E.manifest()["panel"]]
    for pol in ("none", "naive", "ours", "ours_caps_x5"):
        per_pub = {p: simulate(p, pol) for p in pubs}
        allw = [w for p in pubs for w in per_pub[p]]
        res["policies"][pol] = {"point": metrics(allw), "ci95": bootstrap(per_pub, rng)}
        for p in pubs:
            res["per_pub"][p][pol] = metrics(per_pub[p])
        demo = per_pub["demo"]
        res["policies"][pol]["demo_weeks_hedged"] = sum(1 for w in demo if w["premium"] > 0)
        res["policies"][pol]["weeks_hedged_all"] = sum(1 for w in allw if w["premium"] > 0)
        res["policies"][pol]["pub_weeks"] = len(allw)
    res["setup"] = {"train": ["2021-01-01", E.TRAIN_END], "test": [TEST_START.isoformat(), TEST_END.isoformat()],
                    "pubs": len(pubs), "contract_mm": E.CONTRACT_MM, "wet_scenario_mm": WET_MM,
                    "naive_stake_gbp_per_day": NAIVE_STAKE, "limits_gbp": LIMITS, "fee_rate": E.FEE_RATE,
                    "slippage": E.SLIPPAGE, "spread": E.SPREAD, "venue_margin": E.VENUE_MARGIN,
                    "bootstrap": f"{BOOT} reps, pubs then 8-week blocks", "seed": 20261108}
    out = ROOT / "data" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "backtest.json").write_text(json.dumps(res, indent=1))
    for pol, v in res["policies"].items():
        pt = v["point"]
        print(pol, {k: round(x, 1) for k, x in pt.items()}, "hedged", v["weeks_hedged_all"], "/", v["pub_weeks"])


if __name__ == "__main__":
    main()
