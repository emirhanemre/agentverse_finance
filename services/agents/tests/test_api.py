"""Offline chain end to end through the API: run, receipts, approval, a limit block."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import HTTPException
from fastapi.testclient import TestClient

from pubhedge_svc import app as A
from pubhedge_svc import audit
from pubhedge_svc.app import app
from pubhedge_svc.tools import window_opens

c = TestClient(app)


def run_scenario():
    events = []
    with c.stream("GET", "/api/runs/stream?mode=scenario") as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_offline_scenario_run_lowered_cap_blocks_and_is_logged():
    c.post("/api/demo/reset")
    ev = run_scenario()
    types = [e["type"] for e in ev]
    assert types[0] == "run" and types[-1] == "done" and "error" not in types
    tools = [e for e in ev if e["type"] == "tool"]
    assert len(tools) >= 15 and all(e["receipt_id"] and e["source_badge"] for e in tools)
    assert all(e["model"] == "template" for e in ev if e["type"] == "step_end")  # offline: no model calls
    r = c.get(f"/api/receipts/{tools[0]['receipt_id']}").json()
    assert r["call"] == tools[0]["call"].split("(")[0] and r["hash"]
    st = c.get("/api/state").json()
    pending = [p for p in st["proposals"] if p["status"] == "pending"]
    assert pending, "the August bank holiday scenario should propose a hedge"
    p = pending[0]
    res = c.put("/api/limits", json={"weekly_spend_cap_pence": p["cost_pence"] - 1}).json()
    assert res["blocked"] and "weekly spend" in res["blocked"][0]["reason"]
    a = c.post(f"/api/proposals/{p['id']}/approve", json={"confirm_second": True}).json()
    assert a["status"] == "blocked"
    c.put("/api/limits", json={"weekly_spend_cap_pence": 80000})
    a = c.post(f"/api/proposals/{p['id']}/approve", json={"confirm_second": True}).json()
    assert a["status"] == "filled" and a["fill"]["venue"] == "PAPER"
    calls = [row["call"] for row in c.get("/api/audit?limit=500").json()["rows"]]
    assert "limit_block" in calls and "paper_execute" in calls
    assert c.get("/api/audit").json()["verify"]["ok"]


def test_replay_streams_recorded_run_with_badge():
    ev = []
    with c.stream("GET", "/api/runs/stream?mode=replay&speed=1000") as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                ev.append(json.loads(line[6:]))
    assert ev[0]["mode"] == "replay" and ev[-1]["type"] == "done"
    assert all(e.get("replay") for e in ev if e["type"] == "tool")


BEFORE_KICKOFF = datetime.fromisoformat("2026-11-08T12:00:00+00:00").timestamp()  # recorded match: 2026-11-12 19:45Z


def test_match_offer_is_an_ordinary_capped_proposal(monkeypatch):
    monkeypatch.setattr(A, "_now", lambda: BEFORE_KICKOFF)
    q = c.post("/api/offers/queue").json()
    o = q["quote"]
    assert o["kind"] == "offer" and o["badge"].startswith("REAL")  # real market price (cached offline)
    assert 0 < o["payout_if_event_gbp"] <= o["worst_case_gbp"]  # never more cover than the offer can cost
    assert abs(o["hedge_cost_gbp"] - o["shares"] * o["cost_per_share"]) <= o["shares"] * 0.00005 + 0.01  # per-share cost shown to 4dp
    a = c.post(f"/api/proposals/{q['id']}/approve", json={"confirm_second": True}).json()
    assert a["status"] == "filled" and a["fill"]["venue"] == "PAPER"


def queue_offer(monkeypatch, now=BEFORE_KICKOFF):
    monkeypatch.setattr(A, "_now", lambda: now)
    c.post("/api/demo/reset")
    return c.post("/api/offers/queue").json()["id"]


def status(pid):
    return audit.db().execute("SELECT status FROM proposals WHERE id = ?", (pid,)).fetchone()["status"]


def test_two_approvals_at_once_fill_once(monkeypatch):
    pid = queue_offer(monkeypatch)

    def go():
        try:
            return A.approve(pid, A.Approve(confirm_second=True))["status"]
        except HTTPException as e:
            return e.status_code
    with ThreadPoolExecutor(4) as ex:
        out = list(ex.map(lambda _: go(), range(4)))
    assert out.count("filled") == 1 and out.count(409) == 3
    assert audit.db().execute("SELECT COUNT(*) FROM executions WHERE proposal_id = ?", (pid,)).fetchone()[0] == 1


def test_offer_expires_at_kickoff_and_is_logged(monkeypatch):
    pid = queue_offer(monkeypatch)
    monkeypatch.setattr(A, "_now", lambda: datetime.fromisoformat("2026-11-12T19:45:00+00:00").timestamp())
    assert c.get("/api/state").json()["proposals"][0]["status"] == "expired"
    a = c.post(f"/api/proposals/{pid}/approve", json={"confirm_second": True}).json()
    assert a["status"] == "expired" and a["reason"] == "kick-off was at 19:45 on 2026-11-12" and status(pid) == "expired"
    assert not audit.db().execute("SELECT 1 FROM executions WHERE proposal_id = ?", (pid,)).fetchone()
    assert c.post("/api/offers/queue").status_code == 409  # can't queue cover for a match that has started
    assert [x["call"] for x in c.get("/api/audit").json()["rows"]].count("expire") == 1  # logged once


def test_stale_offer_quote_is_rechecked(monkeypatch):
    pid = queue_offer(monkeypatch)
    later = BEFORE_KICKOFF + A.REQUOTE_AFTER_S + 60
    monkeypatch.setattr(A, "_now", lambda: later)
    real = A.quote_offer
    monkeypatch.setattr(A, "quote_offer", lambda *a: {**real(*a), "cost_per_share": 0.99})  # price rose
    a = c.post(f"/api/proposals/{pid}/approve", json={"confirm_second": True}).json()
    assert a["status"] == "expired" and "price rose" in a["reason"] and status(pid) == "expired"
    pid = c.post("/api/offers/queue").json()["id"]
    monkeypatch.setattr(A, "_now", lambda: later + A.REQUOTE_AFTER_S + 60)
    monkeypatch.setattr(A, "quote_offer", real)  # same cached price: the fill goes ahead
    assert c.post(f"/api/proposals/{pid}/approve", json={"confirm_second": True}).json()["status"] == "filled"


def test_changed_proposal_is_refused_and_decided_one_cannot_be_rejected(monkeypatch):
    pid = queue_offer(monkeypatch)
    audit.db().execute("UPDATE proposals SET shares = shares + 1 WHERE id = ?", (pid,))
    audit.db().commit()
    assert c.post(f"/api/proposals/{pid}/approve", json={"confirm_second": True}).status_code == 409
    pid = c.post("/api/offers/queue").json()["id"]
    assert c.post(f"/api/proposals/{pid}/approve", json={"confirm_second": True}).json()["status"] == "filled"
    assert c.post(f"/api/proposals/{pid}/reject").status_code == 409 and status(pid) == "filled"


def test_rain_window_opens_at_noon_london():
    assert window_opens("2026-08-29") == "2026-08-29T12:00:00+01:00"  # BST
    assert window_opens("2026-11-14") == "2026-11-14T12:00:00+00:00"  # GMT
