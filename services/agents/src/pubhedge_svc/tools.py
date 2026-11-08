"""Agent tools. Each call is memoised per run, written to the audit log and streamed to
the UI. Tools do all the maths; the model only chooses calls and narrates."""
import functools
import importlib.util
import json
import time
from datetime import date, timedelta

import httpx

from . import audit, cache
from . import engines as E
from .clients import companies_house as ch
from .clients import metoffice as mo
from .clients import polymarket as pm
from .config import REPO, offline

PUB = {"trading_name": "The Faltering Fullback", "company_number": "05770953", "postcode": "N4 3HB",
       "address": "19 Perth Road, London N4 3HB", "lat": 51.568656, "lon": -0.108575, "weather_loc": "N4"}
SCENARIO = {"name": "August bank holiday 2026", "decision_date": "2026-08-27", "weekend": ["2026-08-29", "2026-08-30"]}
SYN = "SYNTHETIC: modelled for a pub of this profile, not The Faltering Fullback's actual figures"

_bt = None


def backtest_module():
    global _bt
    if _bt is None:
        spec = importlib.util.spec_from_file_location("ph_backtest", REPO / "scripts" / "backtest.py")
        _bt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_bt)
    return _bt


class Run:
    def __init__(self, run_id: str, mode: str, emit, limits: dict):
        self.run_id, self.mode, self.emit, self.limits = run_id, mode, emit, limits
        self.step = "setup"
        self.memo: dict = {}
        self.outputs: list = []  # every tool result, for the grounding check
        self.model = None

    # ----- recording -----
    def record(self, name, args, fn):
        key = name + json.dumps(args, sort_keys=True, default=str)
        if key in self.memo:
            return self.memo[key]
        t0 = time.time()
        try:
            res = fn()
        except Exception as exc:  # a tool failure is data, not a crash
            res = {"error": f"{type(exc).__name__}: {exc}"[:300], "badge": "ERROR"}
        ms = int((time.time() - t0) * 1000)
        badge = res.get("badge", "SYNTHETIC")
        row = audit.append(self.run_id, self.step, name, args, res, badge, self.model, ms)
        res = {**res, "receipt_id": row["receipt_id"]}
        self.memo[key] = res
        self.outputs.append(res)
        self.emit({"type": "tool", "step": self.step, "call": f"{name}({_short(args)})", "args_summary": _short(args),
                   "result_summary": res.get("summary", ""), "source_badge": badge, "receipt_id": row["receipt_id"],
                   "model": self.model, "ms": ms})
        return res

    # ----- context helpers -----
    def decision_date(self) -> date:
        return date.fromisoformat(SCENARIO["decision_date"]) if self.mode == "scenario" else date.today()

    def weekend(self):
        if self.mode == "scenario":
            return [date.fromisoformat(x) for x in SCENARIO["weekend"]]
        d = self.decision_date()
        sat = d + timedelta(days=(5 - d.weekday()) % 7 or 7)
        return [sat, sat + timedelta(days=1)]


def _short(args) -> str:
    return ", ".join(f"{k}={v}" for k, v in args.items())[:80]


def make_tools(run: Run) -> dict:
    """Returns {step: [tool functions]}. Function names and docstrings are what the model sees."""

    def tool(fn):
        @functools.wraps(fn)
        def wrapped(**kwargs):
            return run.record(fn.__name__, kwargs, lambda: fn(**kwargs))
        return wrapped

    # ---------- 1. verifier ----------
    @tool
    def companies_house_profile(company_number: str) -> dict:
        """Fetch the public Companies House profile for a company number."""
        env = ch.profile(company_number)
        d = env["data"]
        ok = d.get("company_status") == "active" and "56302" in (d.get("sic_codes") or [])
        return {"badge": env["badge"], "source": env["source"], "url": env["url"], "licence": env["licence"],
                "fetched_at": env.get("fetched_at"), "company_name": d.get("company_name"),
                "company_status": d.get("company_status"), "sic_codes": d.get("sic_codes"),
                "incorporated": d.get("date_of_creation"),
                "summary": f"{d.get('company_name')} · {d.get('company_status')} · SIC {','.join(d.get('sic_codes') or [])}",
                "checks": {"active": d.get("company_status") == "active", "sic_public_house": ok}}

    @tool
    def companies_house_officer_match(company_number: str) -> dict:
        """Check that the register lists at least one active director (names are not shown)."""
        env = ch.officers(company_number)
        items = env["data"].get("items", [])
        active = [o for o in items if o.get("officer_role") == "director" and not o.get("resigned_on")]
        return {"badge": env["badge"], "source": env["source"], "licence": env["licence"],
                "fetched_at": env.get("fetched_at"), "active_directors": len(active),
                "match": bool(active), "summary": f"{len(active)} active director on register · match"
                if active else "no active director · no match"}

    @tool
    def locate_postcode(postcode: str) -> dict:
        """Look up a UK postcode on postcodes.io (ONS Postcode Directory, OGL)."""
        pc = postcode.replace(" ", "").upper()
        env = cache.fetch("postcodes", pc, lambda: httpx.get(f"https://api.postcodes.io/postcodes/{pc}", timeout=15)
                          .raise_for_status().json(), source="postcodes.io (ONS Postcode Directory)",
                          url=f"https://api.postcodes.io/postcodes/{pc}", licence="Open Government Licence v3.0 (ONS)",
                          max_age_s=30 * 86400)
        r = env["data"]["result"]
        return {"badge": env["badge"], "source": env["source"], "licence": env["licence"],
                "fetched_at": env.get("fetched_at"), "lat": r["latitude"], "lon": r["longitude"],
                "district": r.get("admin_district"), "summary": f"{r.get('admin_district')} · {r['latitude']:.4f}, "
                f"{r['longitude']:.4f}"}

    # ---------- 2. ingest ----------
    @tool
    def load_takings_history() -> dict:
        """Load daily till takings (SYNTHETIC five-year history; recent days also seeded as Stripe test charges)."""
        rows = E.panel()["demo"]
        tot = sum(float(r["takings_gbp"]) for r in rows)
        man = E.manifest()
        return {"badge": "SYNTHETIC", "label": SYN, "generator": man["generator"], "seed": man["seed"],
                "days": len(rows), "first": rows[0]["date"], "last": rows[-1]["date"],
                "total_gbp": round(tot, 2), "avg_day_gbp": round(tot / len(rows), 2),
                "summary": f"{len(rows):,} trading days · avg £{tot / len(rows):,.0f}/day"}

    @tool
    def load_stripe_test_charges() -> dict:
        """Read recent takings seeded as Stripe TEST MODE charges (business date in metadata)."""
        from .clients import stripe_client
        env = stripe_client.list_charges()
        ch_ = [c for c in env["data"] if c.get("pub_id") == "demo" and not c["livemode"]]
        return {"badge": "TEST MODE", "source": env["source"], "fetched_at": env.get("fetched_at"),
                "charges": len(ch_), "total_gbp": round(sum(c["amount"] for c in ch_) / 100, 2),
                "summary": f"{len(ch_)} test charges · £{sum(c['amount'] for c in ch_) / 100:,.0f}"}

    @tool
    def load_bank_feed() -> dict:
        """Load the bank feed (SYNTHETIC, Open Banking shape) and summarise payroll, rent and suppliers."""
        tx = E.bank_feed()
        by = {}
        for t in tx:
            by.setdefault(t["ProprietaryBankTransactionCode"], []).append(t["amount_pence"])
        pay = by.get("PAYROLL", [0])[-4:]
        return {"badge": "SYNTHETIC", "label": SYN, "transactions": len(tx),
                "weekly_payroll_gbp": round(-sum(pay) / len(pay) / 100, 2),
                "monthly_fixed_gbp": round(-(by["RENT"][-1] + by["UTILITIES"][-1] + by["OTHER"][-1]) / 100, 2),
                "summary": f"{len(tx):,} transactions · payroll £{-sum(pay) / len(pay) / 100:,.0f}/wk"}

    @tool
    def check_bank_feed() -> dict:
        """Run the transactions engine on the last 90 days of the bank feed: payment loops and large transfers."""
        from pubhedge_core import transactions as core_tx
        tx = E.bank_feed()
        last = max(t["date"] for t in tx)
        start = (date.fromisoformat(last) - timedelta(days=90)).isoformat()
        rows = []
        for t in tx:
            if t["date"] < start:
                continue
            cp = t["MerchantDetails"]["MerchantName"]
            out = t["amount_pence"] < 0
            rows.append({"id": t["TransactionId"], "date": t["date"], "amount_pence": abs(t["amount_pence"]), "currency": "GBP",
                         "sender": "pub" if out else cp, "recipient": cp if out else "pub"})
        res = core_tx.analyse(rows, 500000)  # £5,000 and over is "large"
        kinds = {t["TransactionId"]: t["ProprietaryBankTransactionCode"] for t in tx}
        large = {}
        for i in res["large_transfer_ids"]:
            large[kinds[i]] = large.get(kinds[i], 0) + 1
        return {"badge": "SYNTHETIC", "label": SYN, "engine": "pubhedge_core.transactions (the kit-scored engine)",
                "window": [start, last], "transactions": len(rows), "payment_loops": len(res["loops"]),
                "large_transfers": len(res["large_transfer_ids"]), "large_by_kind": large,
                "summary": f"{len(res['loops'])} payment loops · {len(res['large_transfer_ids'])} transfers ≥£5,000"}

    @tool
    def load_weather_history() -> dict:
        """Load real daily weather for the pub's grid point (Open-Meteo, CC BY 4.0)."""
        wx = E.weather(PUB["weather_loc"])
        meta = json.loads((E.DATA / "weather" / "manifest.json").read_text())
        wet = sum(1 for r in wx.values() if r["pm_rain_mm"] and float(r["pm_rain_mm"]) >= E.CONTRACT_MM)
        return {"badge": "REAL · CACHED", "source": meta["source"], "licence": meta["licence"],
                "fetched_at": meta["locations"][PUB["weather_loc"]]["fetched_at"], "days": len(wx),
                "wet_afternoons": wet, "summary": f"{len(wx):,} days · {wet} afternoons ≥{E.CONTRACT_MM:g}mm"}

    @tool
    def load_match_and_duty_dates() -> dict:
        """Load real England/Ireland match days and UK beer duty change dates."""
        import csv
        with open(E.DATA / "reference" / "sport_days.csv") as f:
            n = sum(1 for _ in csv.DictReader(f))
        with open(E.DATA / "reference" / "duty_changes.csv") as f:
            duty = [r["effective_date"] for r in csv.DictReader(f)]
        return {"badge": "REAL · CACHED", "source": "openfootball (CC0), Wikipedia (CC BY-SA 4.0), HMRC/legislation.gov.uk"
                " (OGL)", "match_days": n, "duty_changes": duty, "summary": f"{n} match days · {len(duty)} duty dates"}

    # ---------- 3. risk analyst ----------
    @tool
    def fit_takings_model() -> dict:
        """Regress daily takings on weather, sport and duty; train on 2021-01..2024-10, test on later months."""
        f = E.fit_takings("demo")
        c = f["coefficients"]
        return {"badge": "SYNTHETIC", "label": "fitted on SYNTHETIC takings driven by REAL weather and dates",
                "r2_train": f["r2_train"], "r2_holdout": f["r2_holdout"], "n_train": f["n_train"],
                "n_holdout": f["n_holdout"], "holdout_period": f["holdout_period"],
                "rain_weekend_gbp_per_mm": c["pm_rain_mm_weekend"], "rain_weekday_gbp_per_mm": c["pm_rain_mm_weekday"],
                "heat_gbp_per_c": c["heat_c_over_14"], "match_day_gbp": c["match_day"], "duty_rise_gbp_per_day": c["duty_rises"],
                "summary": f"R² {f['r2_holdout']} held-out · £{-c['pm_rain_mm_weekend']['estimate']:.0f} per mm (Fri–Sun)"}

    @tool
    def weekend_rain_exposure() -> dict:
        """Cost to takings of a wet weekend afternoon at the contract threshold and in the wet scenario."""
        f = E.fit_takings("demo")
        b = -f["coefficients"]["pm_rain_mm_weekend"]["estimate"]
        lo, hi = (-x for x in f["coefficients"]["pm_rain_mm_weekend"]["ci95"])
        wet = backtest_module().WET_MM
        return {"badge": "SYNTHETIC", "gbp_per_mm": round(b, 2), "ci95_gbp_per_mm": [round(hi, 2), round(lo, 2)],
                "wet_scenario_mm": wet, "loss_wet_day_gbp": round(b * wet, 2),
                "summary": f"−£{b * wet:,.0f} on a {wet:g}mm afternoon"}

    # ---------- 4. hedge pricer ----------
    @tool
    def weekend_forecast() -> dict:
        """Afternoon (12:00-18:00) rain forecast for the coming weekend at the pub."""
        days = run.weekend()
        if run.mode == "scenario":
            wx = E.weather(PUB["weather_loc"])
            out = {d.isoformat(): {"mm": float(wx[d.isoformat()]["fc_pm_rain_mm"] or 0)} for d in days}
            return {"badge": "REAL · CACHED", "source": "Open-Meteo historical forecast archive (what was forecast then)",
                    "licence": "CC BY 4.0", "days": out, "grid_note": "Open-Meteo grid cell nearest N4 3HB",
                    "summary": " · ".join(f"{k[5:]} {v['mm']:.1f}mm" for k, v in out.items())}
        env = mo.forecast(PUB["lat"], PUB["lon"], "three-hourly")
        rain = {}
        for row in env["data"]["features"][0]["properties"]["timeSeries"]:
            t = row["time"]
            if t[:10] in [d.isoformat() for d in days] and 12 <= int(t[11:13]) < 18:
                r = rain.setdefault(t[:10], {"mm": 0.0, "prob_max": 0})
                r["mm"] = round(r["mm"] + (row.get("totalPrecipAmount") or 0.0), 2)
                r["prob_max"] = max(r["prob_max"], row.get("probOfPrecipitation") or 0)
        gp = env["grid_point"]
        return {"badge": env["badge"], "source": env["source"], "licence": env["licence"], "fetched_at": env.get("fetched_at"),
                "days": rain, "grid_note": f"nearest grid point {gp['name']}, {gp['distance_m'] / 1000:.1f} km from the pub; "
                f"model run {gp['model_run']}", "summary": " · ".join(f"{k[5:]} {v['mm']:.1f}mm ({v['prob_max']}%)"
                                                                     for k, v in rain.items()) or "no rows for weekend"}

    @tool
    def check_real_weather_markets() -> dict:
        """Search Polymarket's public read API for London weather markets on the weekend days."""
        found, notes = [], []
        for d in run.weekend():
            try:
                env = pm.london_high_temp_event(d)
                evs = env["data"]
                if evs:
                    ms = [pm.parse_market(m) for m in evs[0]["markets"]]
                    found.append({"date": d.isoformat(), "event": evs[0]["slug"], "buckets": len(ms), "badge": env["badge"],
                                  "top_bucket": max(ms, key=lambda m: m["yes_price"] or 0)["question"]})
            except Exception as exc:
                notes.append(f"{d}: {type(exc).__name__}")
        try:
            rain = pm.search("London rain")
            rain_hits = [e["slug"] for e in rain["data"].get("events", []) if "rain" in e["slug"]]
        except Exception:
            rain_hits = []
        return {"badge": "REAL" if found else "REAL · CACHED", "source": "Polymarket Gamma API (read-only)",
                "temperature_events": found, "rain_markets": rain_hits, "uk_trading": "blocked for UK users; read-only",
                "summary": f"{len(found)} temperature ladders · {len(rain_hits)} rain markets"}

    @tool
    def price_rain_contracts() -> dict:
        """Price a SYNTHETIC contract per weekend day that pays £1 if >= 3mm falls 12:00-18:00."""
        fc = weekend_forecast()
        out = []
        for d, v in fc.get("days", {}).items():
            q = E.rain_probability(PUB["weather_loc"], v["mm"])
            px = E.synthetic_price(q)
            out.append({"market_id": f"syn-rain-{d}", "date": d, "forecast_mm": v["mm"], "model_prob": round(q, 4),
                        "mid": px["mid"], "ask": px["ask"], "cost_per_share": round(E.cost_per_share(px["ask"]), 4),
                        "fee_rate": E.FEE_RATE, "price_badge": "SYNTHETIC", "rule": px["rule"]})
        return {"badge": "SYNTHETIC", "contracts": out, "method": "probability calibrated on 2021-2024 archived "
                "forecasts vs observed rain; price = probability + 3% venue margin + 1% spread",
                "summary": " · ".join(f"{c['date'][5:]} @ {c['ask']:.2f}" for c in out)}

    @tool
    def project_payroll(scenario: str) -> dict:
        """Project the cash balance to next Friday's payroll. scenario is 'dry' (forecast rain) or 'wet' (6mm each afternoon)."""
        bt = backtest_module()
        fit = E.fit_takings("demo")
        d0 = run.decision_date()
        sat, sun = run.weekend()
        fc = weekend_forecast().get("days", {})
        rain = {d.isoformat(): (bt.WET_MM if scenario == "wet" else fc.get(d.isoformat(), {}).get("mm", 0.0))
                for d in (sat, sun)}
        fri = sun + timedelta(days=5)
        if run.mode == "scenario":
            bt.simulate("demo", "none")
            bal = bt.BALANCES[("demo", "none")]
            known = max(k for k in bal if k <= d0.isoformat())
            opening = bal[known]
            feed = bt.cash_by_date(E.panel()["demo"], 1.0)
            chk = bt.project(feed, d0, sat, sun, opening, fit, E.weather(PUB["weather_loc"]), bt.SWEEP_GBP, rain)
        else:
            # live: the synthetic history ends 2026-10-31, so roll its profile forward from the
            # buffer the owner keeps (same rule as the backtest).
            known, opening = d0.isoformat(), float(bt.SWEEP_GBP)
            events = [e for e in E.upcoming_events(d0 + timedelta(days=1), 2, fit, PUB["weather_loc"], rain)
                      if e["date"] <= fri.isoformat()]
            chk = E.payroll_check(int(opening * 100), events)
        bad = chk["first_failed_payroll"]
        return {"badge": "SYNTHETIC", "label": SYN, "engine": "pubhedge_core.cashflow (the kit-scored engine)",
                "scenario": scenario, "opening_balance_gbp": opening, "opening_date": known,
                "payroll_date": fri.isoformat(), "payroll_clears": bad is None,
                "first_negative_date": chk["first_negative_date"],
                "shortfall_gbp": round(chk["shortfall_pence"] / 100, 2),
                "minimum_balance_gbp": round(chk["minimum_balance_pence"] / 100, 2),
                "timeline": [{"date": t["date"], "id": t["id"], "amount_gbp": t["amount_pence"] / 100,
                              "balance_gbp": t["balance_after_pence"] / 100} for t in chk["timeline"]],
                "summary": (f"{scenario}: payroll {fri.strftime('%a %d %b')} short £{chk['shortfall_pence'] / 100:,.0f}"
                            if bad else f"{scenario}: payroll {fri.strftime('%a %d %b')} clears")}

    @tool
    def size_hedges() -> dict:
        """Size hedges with the LP under the owner's caps. Proposes nothing if no contract is worth its price."""
        px = price_rain_contracts()
        wet = project_payroll(scenario="wet")
        project_payroll(scenario="dry")
        exp = weekend_rain_exposure()
        led = ledger()
        L = run.limits
        markets = [{"market_id": c["market_id"], "cost_per_share": c["cost_per_share"], "model_prob": c["model_prob"],
                    "causes_shortfall": not wet["payroll_clears"],
                    "loss_if_event_gbp": max(0.0, exp["gbp_per_mm"] * (exp["wet_scenario_mm"] - c["forecast_mm"]))}
                   for c in px["contracts"]]
        res = E.size_hedges(markets, L["weekly_spend_cap_pence"] / 100 - led["spent_this_week_pence"] / 100,
                            L["monthly_max_loss_pence"] / 100 - led["at_risk_this_month_pence"] / 100,
                            L["per_market_cap_pence"] / 100)
        res["inputs"] = markets
        res["badge"] = "SYNTHETIC"
        dry = project_payroll(scenario="dry")
        payout = sum(p["payout_if_event_gbp"] for p in res["positions"])
        cost = res["total_cost_gbp"]
        res["outcomes"] = {  # what the hedge does to payroll week, both ways
            "payroll_date": wet["payroll_date"],
            "wet_no_hedge_shortfall_gbp": wet["shortfall_gbp"],
            "wet_with_hedge_shortfall_gbp": round(max(0.0, wet["shortfall_gbp"] - payout + cost), 2),
            "dry_no_hedge_shortfall_gbp": dry["shortfall_gbp"],
            "dry_with_hedge_shortfall_gbp": round(dry["shortfall_gbp"] + cost, 2),
            "hedge_cost_gbp": cost, "hedge_payout_if_wet_gbp": payout}
        res["summary"] = (f"{len(res['positions'])} positions · £{res['total_cost_gbp']:.2f}" if res["positions"]
                          else "nothing worth buying at today's prices")
        return res

    # ---------- 5. monitor / proposer ----------
    @tool
    def check_limits() -> dict:
        """Run the limit guard on every sized position before it reaches the approval queue."""
        sized = size_hedges()
        led = ledger()
        out = []
        for p in sized["positions"]:
            v = E.check_limits(int(round(p["cost_gbp"] * 100)), p["market_id"], run.limits, led)
            out.append({"market_id": p["market_id"], **v})
        return {"badge": "PAPER", "verdicts": out,
                "summary": f"{sum(v['allowed'] for v in out)}/{len(out)} within limits" if out else "nothing to check"}

    @tool
    def queue_for_approval() -> dict:
        """Put limit-checked positions in the owner's approval queue. Nothing executes without a human."""
        sized = size_hedges()
        px = {c["market_id"]: c for c in price_rain_contracts()["contracts"]}
        verdicts = {v["market_id"]: v for v in check_limits()["verdicts"]}
        made = []
        for p in sized["positions"]:
            pid = f"p_{run.run_id[-6:]}_{p['market_id'][-5:]}"
            market = {**px[p["market_id"]], "payout_if_event_gbp": p["payout_if_event_gbp"],
                      "verdict": verdicts.get(p["market_id"])}
            audit.db().execute("INSERT OR REPLACE INTO proposals (id, run_id, created, market, shares, cost_pence, status)"
                               " VALUES (?,?,?,?,?,?,?)", (pid, run.run_id, time.time(), json.dumps(market), p["shares"],
                                                           int(round(p["cost_gbp"] * 100)), "pending"))
            made.append(pid)
        audit.db().commit()
        return {"badge": "PAPER", "proposals": made, "summary": f"{len(made)} awaiting owner approval" if made
                else "no proposals: nothing worth buying"}

    @tool
    def schedule_monitor() -> dict:
        """Schedule re-checks of forecast and prices before the weekend."""
        days = run.weekend()
        return {"badge": "PAPER", "checks": [f"{(days[0] - timedelta(days=1)).isoformat()} 09:00",
                                             f"{days[0].isoformat()} 08:00"],
                "summary": "re-check Fri 09:00 and Sat 08:00"}

    def ledger() -> dict:
        return current_ledger(run.decision_date())

    return {
        "verifier": [companies_house_profile, companies_house_officer_match, locate_postcode],
        "ingest": [load_takings_history, load_stripe_test_charges, load_bank_feed, check_bank_feed, load_weather_history,
                   load_match_and_duty_dates],
        "risk": [fit_takings_model, weekend_rain_exposure],
        "pricer": [weekend_forecast, check_real_weather_markets, price_rain_contracts, project_payroll, size_hedges],
        "monitor": [check_limits, queue_for_approval, schedule_monitor],
    }


def current_ledger(d: date) -> dict:
    """Paper positions committed this week and month (executed paper fills)."""
    con = audit.db()
    rows = con.execute("SELECT p.market, p.cost_pence, e.ts FROM executions e JOIN proposals p ON p.id = e.proposal_id"
                       ).fetchall()
    week0 = time.time() - 7 * 86400
    month0 = time.time() - 30 * 86400
    by = {}
    for r in rows:
        m = json.loads(r["market"])["market_id"]
        by[m] = by.get(m, 0) + r["cost_pence"]
    return {"spent_this_week_pence": sum(r["cost_pence"] for r in rows if r["ts"] >= week0),
            "at_risk_this_month_pence": sum(r["cost_pence"] for r in rows if r["ts"] >= month0), "by_market_pence": by}


def offline_ok() -> bool:
    return offline()
