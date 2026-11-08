"""Synthetic takings, bank feed and fixed costs for Pub Hedge. Standard library only.

SYNTHETIC: modelled for a pub of this profile, not any real pub's actual figures.
Drivers are real: Open-Meteo daily weather (data/weather), real match days
(data/reference/sport_days.csv) and real duty-change dates (data/reference/duty_changes.csv).
Every parameter and the seed are written to data/synthetic/manifest.json.

  python3 scripts/gen_synthetic.py [--seed 20261108]
"""
import argparse
import csv
import hashlib
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic"

# Scale assumptions. Sources in docs/data-sources.md; where none exists it says "assumption".
PARAMS = {
    "start": "2021-01-01",
    "end": "2026-10-31",
    # Busy independent London pub: about £850k a year turnover (assumption; BBPA does not
    # publish a London independent average).
    "base_daily_takings_gbp": 2050.0,
    "dow_factor": [0.62, 0.70, 0.82, 0.95, 1.30, 1.55, 1.06],  # Mon..Sun (assumption)
    "season_amplitude": 0.10,  # +/- around a mid-July peak (assumption)
    "garden_uplift_per_c_over_14": 0.035,  # share of base per degree over 14C, garden pubs only
    "garden_uplift_cap": 0.45,
    # A wet afternoon empties the garden and some walk-ins stay home. CGA/NIQ saw pub and
    # bar sales down 13% on the wet 24 May 2025 bank holiday Saturday.
    "rain_loss_per_mm_pm": 0.045,  # share of day takings lost per mm 12:00-18:00
    "rain_loss_cap": 0.32,
    "match_uplift": 0.28,  # England/Ireland match day, live sport pub (assumption)
    "duty_price_elasticity": -0.012,  # takings change after a duty rise, per rise (assumption)
    "noise_sd": 0.07,  # lognormal day noise
    "growth_per_year": 0.025,
    # Cash costs (shares of takings), from UHY's £10 pint breakdown where possible.
    "vat_share": 0.1667,  # VAT inside a VAT-inclusive till total
    "cogs_share_of_net": 0.33,  # drinks and food cost, paid to suppliers weekly, 14-day terms
    "staff_share_of_net": 0.33,  # payroll, smoothed: paid every Friday on a 4-week trailing average
    "card_fee": 0.015,
    "rent_monthly_gbp": 9500.0,
    "utilities_monthly_gbp": 2600.0,
    "other_fixed_monthly_gbp": 2300.0,
    "vat_quarterly": True,
    "opening_balance_gbp": 18000.0,
    "sweep_target_gbp": 18000.0,  # owner sweeps cash above this to savings every Monday
}

PANEL = [  # id, location, scale, garden (0..1)
    ("demo", "N4", 3.50, 1.0),  # the demo pub: a large garden pub (illustrative profile)
    ("p01", "SE22", 0.85, 1.0), ("p02", "SE22", 1.20, 0.6), ("p03", "E2", 0.70, 0.8),
    ("p04", "E2", 1.10, 0.3), ("p05", "W12", 0.95, 0.9), ("p06", "W12", 0.60, 0.0),
    ("p07", "N4", 1.30, 0.5), ("p08", "SE22", 0.75, 0.2), ("p09", "E2", 1.00, 1.0),
    ("p10", "W12", 1.15, 0.7), ("p11", "N4", 0.80, 0.4),
]


def load_weather(loc):
    with open(ROOT / "data" / "weather" / f"{loc}.csv") as f:
        return {r["date"]: r for r in csv.DictReader(f)}


def load_matches():
    p = ROOT / "data" / "reference" / "sport_days.csv"
    with open(p) as f:
        return {r["date"] for r in csv.DictReader(f) if r["team"] in ("England", "Ireland")}


def load_duty_rises():
    with open(ROOT / "data" / "reference" / "duty_changes.csv") as f:
        return sorted(r["effective_date"] for r in csv.DictReader(f) if r["direction"] not in ("freeze", "cut"))


def f(v, default=0.0):
    return float(v) if v not in ("", None) else default


def day_takings(rng, d, w, matches, rises, scale, garden, P):
    t0 = date.fromisoformat(P["start"])
    base = P["base_daily_takings_gbp"] * scale * (1 + P["growth_per_year"]) ** ((d - t0).days / 365.25)
    season = 1 + P["season_amplitude"] * math.cos(2 * math.pi * (d.timetuple().tm_yday - 196) / 365.25)
    x = base * P["dow_factor"][d.weekday()] * season
    tmax = f(w["tmax_c"], 12.0)
    garden_up = garden * min(P["garden_uplift_cap"], max(0.0, tmax - 14) * P["garden_uplift_per_c_over_14"])
    pm = f(w["pm_rain_mm"])
    rain_loss = min(P["rain_loss_cap"], pm * P["rain_loss_per_mm_pm"] * (0.5 + 0.5 * garden))
    x *= (1 + garden_up) * (1 - rain_loss)
    if d.isoformat() in matches:
        x *= 1 + P["match_uplift"]
    n_rises = sum(1 for r in rises if r <= d.isoformat())
    x *= (1 + P["duty_price_elasticity"]) ** n_rises
    x *= math.exp(rng.gauss(0, P["noise_sd"]) - P["noise_sd"] ** 2 / 2)
    return round(x, 2)


def build_pub(pub_id, loc, scale, garden, seed, P, matches, rises):
    rng = random.Random(f"{seed}:{pub_id}")
    weather = load_weather(loc)
    d, end = date.fromisoformat(P["start"]), date.fromisoformat(P["end"])
    rows = []
    while d <= end:
        w = weather[d.isoformat()]
        rows.append({"date": d.isoformat(), "pub_id": pub_id, "takings_gbp": day_takings(rng, d, w, matches, rises,
                                                                                        scale, garden, P),
                     "pm_rain_mm": f(w["pm_rain_mm"]), "tmax_c": f(w["tmax_c"], 12.0),
                     "match_day": int(d.isoformat() in matches),
                     "duty_rises": sum(1 for r in rises if r <= d.isoformat())})
        d += timedelta(days=1)
    return rows


def bank_feed(rows, seed, P):
    """Open Banking style transactions for the demo pub (UK Open Banking v3.1 Transaction shape, flattened)."""
    rng = random.Random(f"{seed}:bank")
    tx = []

    def add(d, amount, kind, counterparty, desc):
        tid = hashlib.sha256(f"{seed}:{d}:{kind}:{len(tx)}".encode()).hexdigest()[:16]
        tx.append({"TransactionId": tid, "BookingDateTime": f"{d}T09:00:00+00:00",
                   "Amount": {"Amount": f"{abs(amount):.2f}", "Currency": "GBP"},
                   "CreditDebitIndicator": "Credit" if amount > 0 else "Debit",
                   "ProprietaryBankTransactionCode": kind, "MerchantDetails": {"MerchantName": counterparty},
                   "TransactionInformation": desc, "amount_pence": int(round(amount * 100)), "date": d})

    by_date = {r["date"]: r for r in rows}
    days = sorted(by_date)
    net = {k: by_date[k]["takings_gbp"] * (1 - P["vat_share"]) for k in days}
    for i, k in enumerate(days):
        dt = date.fromisoformat(k)
        if i > 0:  # card settlement T+1 net of fees (VAT is still inside; remitted quarterly)
            prev = by_date[days[i - 1]]["takings_gbp"]
            add(k, prev * (1 - P["card_fee"]), "CARD_SETTLEMENT", "Card acquirer", f"Card takings {days[i - 1]}")
        if dt.weekday() == 4 and i >= 28:  # Friday payroll on a 4-week trailing average
            pay = sum(net[days[j]] for j in range(i - 28, i)) / 4 * P["staff_share_of_net"]
            add(k, -pay, "PAYROLL", "Payroll bureau", "Weekly payroll")
        if dt.weekday() == 1 and i >= 21:  # Tuesday suppliers, 14-day terms on the week before
            spend = sum(net[days[j]] for j in range(i - 21, i - 14)) * P["cogs_share_of_net"]
            split = rng.uniform(0.55, 0.7)
            add(k, -spend * split, "SUPPLIER", "Drinks wholesaler", "Drinks order")
            add(k, -spend * (1 - split), "SUPPLIER", "Food supplier", "Food order")
        if dt.day == 1:
            add(k, -P["rent_monthly_gbp"], "RENT", "Landlord", "Rent")
            add(k, -P["utilities_monthly_gbp"], "UTILITIES", "Energy supplier", "Energy and water")
            add(k, -P["other_fixed_monthly_gbp"], "OTHER", "Various", "Insurance, licences, repairs")
        if P["vat_quarterly"] and dt.day == 7 and dt.month in (2, 5, 8, 11) and i > 90:
            q = [days[j] for j in range(max(0, i - 98), i - 7)]
            vat = sum(by_date[x]["takings_gbp"] for x in q) * P["vat_share"] * 0.62  # net of input VAT (assumption)
            add(k, -vat, "HMRC_VAT", "HMRC", "VAT return")
    return tx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261108)
    seed = ap.parse_args().seed
    P = PARAMS
    matches, rises = load_matches(), load_duty_rises()
    OUT.mkdir(parents=True, exist_ok=True)
    allrows = []
    for pub_id, loc, scale, garden in PANEL:
        allrows += build_pub(pub_id, loc, scale, garden, seed, P, matches, rises)
    cols = list(allrows[0])
    with open(OUT / "takings_panel.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(allrows)
    demo = [r for r in allrows if r["pub_id"] == "demo"]
    tx = bank_feed(demo, seed, P)
    (OUT / "bank_feed_demo.json").write_text(json.dumps({"Data": {"Transaction": tx}}, separators=(",", ":")))
    fixed = [{"account": "Rent", "monthly_gbp": P["rent_monthly_gbp"]},
             {"account": "Utilities", "monthly_gbp": P["utilities_monthly_gbp"]},
             {"account": "Insurance, licences, repairs", "monthly_gbp": P["other_fixed_monthly_gbp"]}]
    (OUT / "fixed_costs_demo.json").write_text(json.dumps({"Reports": [{"ReportName": "Fixed costs (Xero-style)",
                                                                         "Rows": fixed}]}, indent=1))
    digest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(OUT.glob("*.*")) if p.name != "manifest.json"}
    manifest = {
        "label": "SYNTHETIC: modelled for a pub of this profile, not any real pub's actual figures",
        "generator": "scripts/gen_synthetic.py", "seed": seed, "params": P,
        "panel": [{"pub_id": a, "weather_location": b, "scale": c, "garden": g} for a, b, c, g in PANEL],
        "drivers": {"weather": "data/weather (Open-Meteo, CC BY 4.0, real)",
                    "match_days": f"{len(matches)} England/Ireland match days (data/reference/sport_days.csv, real)",
                    "duty_rises": rises},
        "method": ("takings = base x weekday x season x growth x (1 + garden x heat uplift) x (1 - capped "
                   "afternoon-rain loss) x match uplift x duty elasticity^rises x lognormal noise; bank feed "
                   "derives card settlements (T+1), weekly payroll, 14-day supplier terms, monthly fixed costs "
                   "and quarterly VAT from those takings."),
        "files": digest,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {len(allrows)} takings rows, {len(tx)} bank transactions")


if __name__ == "__main__":
    main()
