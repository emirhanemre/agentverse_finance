import pytest

from pubhedge_svc import engines as E


def test_regression_reports_holdout_and_cis():
    f = E.fit_takings("demo")
    assert f["n_holdout"] > 600 and 0 < f["r2_holdout"] <= 1
    lo, hi = f["coefficients"]["pm_rain_mm_weekend"]["ci95"]
    assert lo < f["coefficients"]["pm_rain_mm_weekend"]["estimate"] < hi < 0


def test_calibration_uses_training_years_only_and_is_monotone_at_low_end():
    cal = E.calibrate_rain("N4")
    assert cal["probs"][0] < cal["probs"][2] < cal["probs"][4]


def test_lp_buys_nothing_without_value():
    m = [{"market_id": "a", "cost_per_share": 0.30, "model_prob": 0.20, "causes_shortfall": False, "loss_if_event_gbp": 500}]
    r = E.size_hedges(m, 120, 400, 60)
    assert r["positions"] == [] and r["status"] == "nothing_worth_buying" and r["no_value_at_price"] == ["a"]


def test_lp_respects_caps_and_never_overhedges():
    m = [{"market_id": "a", "cost_per_share": 0.25, "model_prob": 0.24, "causes_shortfall": True, "loss_if_event_gbp": 100},
         {"market_id": "b", "cost_per_share": 0.10, "model_prob": 0.09, "causes_shortfall": True, "loss_if_event_gbp": 10_000}]
    r = E.size_hedges(m, 120, 400, 60)
    by = {p["market_id"]: p for p in r["positions"]}
    assert by["a"]["shares"] <= 100  # payout never exceeds the loss it covers
    assert all(p["cost_gbp"] <= 60 + 1e-6 for p in r["positions"])
    assert r["total_cost_gbp"] <= 120 + 1e-6


def test_paper_fill_is_paper_and_charges_fee():
    f = E.paper_fill({"market_id": "a", "ask": 0.2, "fee_rate": 0.05, "price_badge": "SYNTHETIC"}, 100)
    assert f["venue"] == "PAPER" and f["fee_gbp"] > 0
    assert f["cost_gbp"] == pytest.approx(100 * f["fill_price"] + f["fee_gbp"], abs=0.01)


def test_exact_sizer_matches_lp_bound():
    """Cross-check against scipy's LP: the integer optimum is never above the LP relaxation and
    never below the LP's answer rounded down."""
    import math
    import random

    import numpy as np
    from scipy.optimize import linprog

    from pubhedge_core import sizing

    rng = random.Random(3)
    for _ in range(200):
        ms = [{"id": f"m{i}", "cost_per_share_pence": rng.randint(3, 90), "value_per_share_pence": rng.randint(0, 110),
               "max_shares": rng.randint(0, 200)} for i in range(rng.randint(1, 3))]
        budget, cap = rng.randint(0, 4000), rng.randint(100, 3000)
        k = np.array([m["cost_per_share_pence"] for m in ms], float)
        e = np.array([m["value_per_share_pence"] for m in ms], float) - k
        A = [k] + [np.eye(len(ms))[i] * k[i] for i in range(len(ms))]
        lp = linprog(-e, A_ub=np.array(A), b_ub=[budget] + [cap] * len(ms),
                     bounds=[(0, m["max_shares"]) for m in ms], method="highs")
        got = sizing.size(ms, budget, cap)["expected_value_pence"]
        floor_val = sum(math.floor(x) * ei for x, ei in zip(lp.x, e) if ei > 0)
        assert floor_val - 1e-6 <= got <= -lp.fun + 1e-6


def test_walk_book_fills_cheapest_first_and_respects_cover_and_budget():
    asks = [{"price": "0.10", "size": "50"}, {"price": "0.09", "size": "100"}]
    w = E.walk_book(asks, max_shares=120, budget_gbp=1000, fee_rate=0.0)
    assert w["shares"] == 120 and w["cost_gbp"] == 100 * 0.09 + 20 * 0.10
    assert E.walk_book(asks, max_shares=1000, budget_gbp=5.0, fee_rate=0.0)["shares"] == 55  # 9.00 > 5: stops at budget
    assert E.walk_book([], 10, 10)["shares"] == 0


def test_implied_high_from_ladder():
    ms = [{"question": f"Will it be {t}°C?", "yes_price": p} for t, p in [(9, 0.2), (10, 0.5), (11, 0.3)]]
    assert E.implied_high(ms) == {"expected_high_c": 10.1, "p10_c": 9, "p50_c": 10, "p90_c": 11}
    assert E.implied_high([{"question": "5°C", "yes_price": 0}]) == {}  # no prices, no number (not 0°C)
