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
