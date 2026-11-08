"""Any pub can be verified; the books after the verifier stay the demo's."""
import json

from fastapi.testclient import TestClient

from pubhedge_svc import tools as T
from pubhedge_svc.app import app

c = TestClient(app)


def stream(query: str) -> list:
    with c.stream("GET", "/api/runs/stream?mode=scenario&" + query) as r:
        return [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]


def results(ev: list, call: str) -> list:
    return [e for e in ev if e["type"] == "tool" and e["call"].startswith(call + "(")]


def test_identity_spots_the_demo_pub_and_keeps_a_given_number():
    demo = T.identity("the faltering fullback", "n43hb")
    assert demo["is_demo"] and demo["company_number"] == "05770953" and demo["postcode"] == "N4 3HB"
    other = T.identity("The Churchill Arms", "w8 7ln")
    assert not other["is_demo"] and other["company_number"] is None and other["postcode"] == "W8 7LN"
    assert T.identity("The Churchill Arms", "W8 7LN", "00241882")["company_number"] == "00241882"
    assert T._sim("Churchill Arms", "THE CHURCHILL ARMS LTD") == 1.0 and T._sim("The Lamb", "Horse & Wig") < 0.6


def test_another_pub_is_verified_and_the_books_stay_the_demos():
    demo = stream("")
    other = stream("pub_name=The%20Churchill%20Arms&postcode=W8%207LN&owner=Sam")
    assert other[-1]["type"] == "done" and other[0]["pub"]["entered_name"] == "The Churchill Arms"
    assert "hygiene rating 5/5" in results(other, "find_premises")[0]["result_summary"]
    assert "no company" in results(other, "find_operator")[0]["result_summary"]
    assert not results(other, "companies_house_profile")  # nothing matched, nothing looked up
    for call in ("project_payroll", "size_hedges", "price_rain_contracts"):
        assert [e["result_summary"] for e in results(other, call)] == [e["result_summary"] for e in results(demo, call)]
    st = c.get("/api/state").json()
    assert st["pub"]["trading_name"] == "Churchill Arms" and st["pub"]["owner"] == "Sam"
    assert "demo books" in st["pub"]["financials_label"] and "not Churchill Arms's" in st["pub"]["financials_label"]


def test_bad_postcode_or_company_number_is_refused():
    assert c.get("/api/runs/stream?mode=scenario&postcode=nope").status_code == 400
    assert c.get("/api/runs/stream?mode=scenario&postcode=W8%207LN&company_number=12-34").status_code == 400


def _operator(monkeypatch, at_postcode: list) -> dict:
    env = {"badge": "REAL", "source": "test", "licence": "test", "fetched_at": None}
    pub = {"BusinessName": "The Crown", "PostCode": "E1 1AA", "BusinessType": "Pub/bar/nightclub", "RatingValue": "5"}
    monkeypatch.setattr(T.fsa, "establishments", lambda **kw: {**env, "data": {"establishments": [pub]}})
    monkeypatch.setattr(T.ch, "pubs_at", lambda pc: {**env, "data": {"items": [
        {"company_number": n, "company_name": name, "company_status": "active",
         "registered_office_address": {"postal_code": "E1 1AA"}} for n, name in at_postcode]}})
    monkeypatch.setattr(T.ch, "search", lambda q: {**env, "data": {"items": []}})
    run = T.Run("t", "scenario", lambda e: None, {}, T.identity("The Crown", "E1 1AA"))
    return T.make_tools(run)["verifier"][2](pub_name="The Crown", postcode="E1 1AA")


def test_operator_is_matched_only_when_unambiguous(monkeypatch):
    assert _operator(monkeypatch, [("00000001", "ACME PUBS LTD")])["company_number"] == "00000001"
    two = _operator(monkeypatch, [("00000001", "ACME PUBS LTD"), ("00000002", "OTHER BARS LTD")])
    assert not two["matched"] and "doesn't guess" in two["summary"]
    named = _operator(monkeypatch, [("00000001", "ACME PUBS LTD"), ("00000003", "THE CROWN (E1) LTD")])
    assert named["company_number"] == "00000003"


def test_no_postcode_is_found_from_the_name_and_a_failed_lookup_says_so(monkeypatch):
    env = {"badge": "REAL", "source": "test", "licence": "test", "fetched_at": None}
    monkeypatch.setattr(T.maps, "postcode_for", lambda name: {**env, "data": {"postcode": "w8 7ln"}})
    run = T.Run("t", "scenario", lambda e: None, {}, T.identity("The Churchill Arms", ""))
    assert run.pub["entered_postcode"] == "" and not run.pub["is_demo"]
    got = T.make_tools(run)["verifier"][0](pub_name="The Churchill Arms")
    assert got["postcode"] == "W8 7LN" and run.pub["entered_postcode"] == "W8 7LN"

    def down(name):
        raise LookupError("offline")
    monkeypatch.setattr(T.maps, "postcode_for", down)
    two = [{"BusinessName": "Red Lion", "PostCode": p} for p in ("SW1A 2NH", "N1 1AA")]
    monkeypatch.setattr(T.fsa, "establishments", lambda **kw: {**env, "data": {"establishments": two}})
    run = T.Run("t", "scenario", lambda e: None, {}, T.identity("Red Lion", ""))
    miss = T.make_tools(run)["verifier"][0](pub_name="Red Lion")
    assert not miss["found"] and "add a postcode" in miss["summary"]
    assert T.identity("The Faltering Fullback", "")["is_demo"]  # the demo pub needs no postcode
