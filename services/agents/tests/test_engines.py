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
