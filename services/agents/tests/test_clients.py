"""Each client against its recorded fixture (a real response captured live, then cached)."""
from datetime import date

import pytest

from pubhedge_svc import cache
from pubhedge_svc.clients import companies_house as ch
from pubhedge_svc.clients import polymarket as pm


def test_companies_house_profile_from_fixture():
    env = ch.profile("05770953")
    assert env["badge"] == "REAL · CACHED"
    assert env["data"]["company_name"] == "BACCHUS INNS LIMITED"
    assert "56302" in env["data"]["sic_codes"]
    assert env["fetched_at"] and "Open Government Licence" in env["licence"]


def test_companies_house_officers_from_fixture():
    items = ch.officers("05770953")["data"]["items"]
    assert any(o["officer_role"] == "director" for o in items)


def test_polymarket_fixture_parses_and_fee_formula():
    env = pm.london_high_temp_event(date(2026, 11, 9))
    ms = [pm.parse_market(m) for m in env["data"][0]["markets"]]
    assert len(ms) >= 5 and all(m["yes_token"] for m in ms)
    # docs.polymarket.com/trading/fees example: 100 shares at 0.50, rate 0.05 -> 1.25
    assert pm.taker_fee(100, 0.5, 0.05) == pytest.approx(1.25)


def test_offline_without_cache_raises_not_fakes():
    with pytest.raises(LookupError):
        cache.fetch("nowhere", "missing-key", lambda: {"x": 1}, source="s", url="u", licence="l")


def test_polymarket_client_refuses_trading_paths():
    with pytest.raises(AssertionError):
        pm._fetch("/order", {})


def test_stripe_reads_recorded_test_charges_only():
    from pubhedge_svc.clients import stripe_client
    env = stripe_client.list_charges()
    assert env["badge"] == "REAL · CACHED" and len(env["data"]) >= 100
    assert all(c["livemode"] is False and c["business_date"] for c in env["data"])


def test_stripe_refuses_live_key(monkeypatch):
    from pubhedge_svc.clients import stripe_client
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_example")
    with pytest.raises(PermissionError):
        stripe_client._key()


def test_openmeteo_afternoon_window():
    from pubhedge_svc.clients import openmeteo
    env = {"data": {"hourly": {"time": ["2026-08-29T11:00", "2026-08-29T12:00", "2026-08-29T17:00", "2026-08-29T18:00"],
                               "precipitation": [5.0, 1.5, 2.0, 9.0]}}}
    assert openmeteo.afternoon_rain(env) == {"2026-08-29": 3.5}


def test_metoffice_afternoon_window_shape():
    # Met Office DataHub responses are not committed (licence); this pins the parser to the documented shape.
    from pubhedge_svc.clients import metoffice
    ts = [{"time": "2026-11-14T12:00Z", "totalPrecipAmount": 0.4, "probOfPrecipitation": 40},
          {"time": "2026-11-14T15:00Z", "totalPrecipAmount": 1.1, "probOfPrecipitation": 65},
          {"time": "2026-11-14T18:00Z", "totalPrecipAmount": 3.0, "probOfPrecipitation": 90}]
    env = {"data": {"features": [{"properties": {"timeSeries": ts}}]}}
    assert metoffice.afternoon_rain(env) == {"2026-11-14": {"mm": 1.5, "prob_max": 65}}


def test_weather_tables_cover_backtest_window():
    from pubhedge_svc import engines
    wx = engines.weather("N4")
    assert "2021-01-01" in wx and "2026-10-31" in wx and wx["2026-08-29"]["pm_rain_mm"] == "6.1"
