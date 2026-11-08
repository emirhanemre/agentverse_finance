"""Offline chain end to end through the API: run, receipts, approval, a limit block."""
import json

from fastapi.testclient import TestClient

from pubhedge_svc.app import app

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
    c.put("/api/limits", json={"weekly_spend_cap_pence": 12000})
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
