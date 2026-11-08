"""FastAPI service: streams agent runs over SSE and serves receipts, approvals, limits,
the audit log and results. Paper trading only: no real order is ever placed."""
import asyncio
import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pubhedge_core.limits import DEFAULT_LIMITS

from . import audit, config
from . import engines as E
from .chain import run_chain
from .config import DATA, RUNS
from .tools import PUB, SCENARIO, SYN, current_ledger

config.load_env()
app = FastAPI(title="Pub Hedge agents")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])
DEMO_FIXTURE = RUNS / "demo-run.json"


def get_limits() -> dict:
    rows = {r["key"]: r["value"] for r in audit.db().execute("SELECT key, value FROM limits").fetchall()}
    return {**DEFAULT_LIMITS, **rows}


@app.get("/api/health")
def health():
    return {"ok": True, "audit": audit.verify()["ok"], "offline": config.offline(), "paper_only": True}


# ---------------- runs ----------------
def _sse(obj) -> str:
    return f"data: {json.dumps(obj, default=str)}\n\n"


@app.get("/api/runs/stream")
async def stream(mode: str = "scenario", speed: float = 4.0):
    if mode not in ("live", "scenario", "replay"):
        raise HTTPException(400, "mode must be live, scenario or replay")
    q: asyncio.Queue = asyncio.Queue()

    async def produce():
        try:
            if mode == "replay":
                await replay(q.put_nowait, speed)
            else:
                events = []

                def emit(e):
                    events.append(e)
                    q.put_nowait(e)
                await run_chain(mode, emit, get_limits())
                record_fixture(events)
        except Exception as exc:  # surface, never hang the stream
            q.put_nowait({"type": "error", "message": f"{type(exc).__name__}: {exc}"[:300]})
        q.put_nowait(None)

    task = asyncio.create_task(produce())

    async def gen():
        while True:
            e = await q.get()
            if e is None:
                break
            yield _sse(e)
        await task

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def record_fixture(events):
    """Keep every completed run with live models so REPLAY has a real run to fall back to."""
    run = next((e for e in events if e["type"] == "run"), None)
    if not run or not run.get("live_models") or not any(e["type"] == "done" for e in events):
        return
    RUNS.mkdir(parents=True, exist_ok=True)
    props = [dict(r) for r in audit.db().execute("SELECT * FROM proposals WHERE run_id = ?", (run["run_id"],))]
    out = {"events": events, "proposals": props, "tool_results": tool_results(run["run_id"])}
    (RUNS / f"{run['run_id']}.json").write_text(json.dumps(out, indent=1, default=str))


async def replay(emit, speed: float):
    """Stream a recorded live run. Every event is re-logged to the audit log as REPLAY."""
    src = json.loads(DEMO_FIXTURE.read_text())
    run_id = "replay_" + uuid.uuid4().hex[:8]
    audit.db().execute("INSERT INTO runs (run_id, mode, started, status) VALUES (?,?,?,?)", (run_id, "replay", time.time(),
                                                                                             "running"))
    last_ms = 0
    narr = {}
    for e in src["events"]:
        e = {**e}
        if e["type"] == "run":
            e.update(run_id=run_id, mode="replay", recorded_run_id=src["events"][0]["run_id"])
        if e["type"] in ("tool", "step_end", "rationale"):
            row = audit.append(run_id, e.get("step", "rationale"), e.get("call", "narration"), {"replay_of": e.get("receipt_id")},
                               e, "REPLAY", e.get("model"), e.get("ms", 0))
            e["recorded_receipt_id"] = e.get("receipt_id")
            e["receipt_id"] = row["receipt_id"]
            e["replay"] = True
            await asyncio.sleep(min(1.5, (e.get("ms", 0) or 0) / 1000 / max(speed, 0.1)))
        if e["type"] == "step_end":
            narr[e["step"]] = {"text": e["narration"], "badge": "REPLAY", "receipt_id": e["receipt_id"]}
        if e["type"] == "rationale":
            narr["rationale"] = {"text": e["text"], "badge": "REPLAY", "receipt_id": e["receipt_id"], "model": e["model"]}
        if e["type"] == "done":
            e["run_id"] = run_id
            last_ms = e["wall_ms"]
            for p in src["proposals"]:
                audit.db().execute("INSERT OR REPLACE INTO proposals (id, run_id, created, market, shares, cost_pence, status)"
                                   " VALUES (?,?,?,?,?,?,?)", (f"{p['id']}_{run_id[-4:]}", run_id, time.time(), p["market"],
                                                               p["shares"], p["cost_pence"], "pending"))
            audit.db().execute("UPDATE runs SET finished=?, wall_ms=?, status=?, summary=? WHERE run_id=?",
                               (time.time(), last_ms, "done", json.dumps({"run_id": run_id, "mode": "replay",
                                                                          "narration": narr}), run_id))
            audit.db().commit()
        emit(e)


# ---------------- state ----------------
def latest_run():
    r = audit.db().execute("SELECT * FROM runs WHERE status='done' ORDER BY finished DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def tool_results(run_id) -> dict:
    out = {}
    for r in reversed(audit.rows(run_id, 1000)):
        if r["call"] != "narration":
            res = json.loads(r["result"])
            if r["badge"] == "REPLAY":
                continue
            out.setdefault(r["call"], []).append({**res, "receipt_id": r["receipt_id"]})
    return out


def results_for(run):
    """Tool results of a run; a replay uses the recorded run's receipts from the fixture."""
    if run["mode"] != "replay":
        return tool_results(run["run_id"])
    src = json.loads(DEMO_FIXTURE.read_text())
    return src.get("tool_results", {})


@app.get("/api/state")
def state():
    run = latest_run()
    bt = json.loads((DATA / "results" / "backtest.json").read_text())
    ch_path = DATA / "results" / "challenge-summary.json"
    props = [dict(r) for r in audit.db().execute("SELECT * FROM proposals ORDER BY created DESC LIMIT 20").fetchall()]
    for p in props:
        p["market"] = json.loads(p["market"])
    return {
        "pub": {**PUB, "identity_badge": "REAL", "financials_label": SYN, "owner": "Owner (demo)"},
        "scenario": SCENARIO,
        "run": ({**run, "summary": json.loads(run["summary"] or "{}")} if run else None),
        "tools": results_for(run) if run else {},
        "proposals": props,
        "limits": get_limits(),
        "ledger": current_ledger(None),
        "backtest": bt,
        "challenge": json.loads(ch_path.read_text()) if ch_path.exists() else None,
        "synthetic_manifest": {k: E.manifest()[k] for k in ("label", "generator", "seed", "method")},
    }


@app.get("/api/receipts/{receipt_id}")
def receipt(receipt_id: str):
    r = audit.receipt(receipt_id)
    if not r:
        raise HTTPException(404, "no such receipt")
    r["args"], r["result"] = json.loads(r["args"]), json.loads(r["result"])
    return r


@app.get("/api/audit")
def audit_log(limit: int = 200, run_id: str = None):
    return {"rows": audit.rows(run_id, limit), "verify": audit.verify()}


# ---------------- approvals and limits ----------------
class Approve(BaseModel):
    confirm_second: bool = False


def _proposal(pid):
    r = audit.db().execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
    if not r:
        raise HTTPException(404, "no such proposal")
    p = dict(r)
    p["market"] = json.loads(p["market"])
    return p


@app.post("/api/proposals/{pid}/approve")
def approve(pid: str, body: Approve):
    p = _proposal(pid)
    if p["status"] not in ("pending", "blocked"):
        raise HTTPException(409, f"proposal is {p['status']}")
    verdict = E.check_limits(p["cost_pence"], p["market"]["market_id"], get_limits(), current_ledger(None))
    if not verdict["allowed"]:
        row = audit.append(p["run_id"], "approval", "limit_block", {"proposal_id": pid}, verdict, "PAPER", None, 0)
        audit.db().execute("UPDATE proposals SET status='blocked', reason=?, receipt_id=? WHERE id=?",
                           (verdict["reason"], row["receipt_id"], pid))
        audit.db().commit()
        return {"status": "blocked", "reason": verdict["reason"], "verdict": verdict, "receipt_id": row["receipt_id"]}
    if verdict["needs_second_approval"] and not body.confirm_second:
        return {"status": "needs_second_approval", "verdict": verdict}
    fill = E.paper_fill(p["market"], p["shares"])
    row = audit.append(p["run_id"], "approval", "paper_execute", {"proposal_id": pid, "approved_by": "Owner (demo)"},
                       {"fill": fill, "verdict": verdict}, "PAPER", None, 0)
    audit.db().execute("INSERT INTO executions (id, proposal_id, ts, fill, receipt_id) VALUES (?,?,?,?,?)",
                       ("x_" + uuid.uuid4().hex[:10], pid, time.time(), json.dumps(fill), row["receipt_id"]))
    audit.db().execute("UPDATE proposals SET status='filled', decided=?, receipt_id=? WHERE id=?",
                       (time.time(), row["receipt_id"], pid))
    audit.db().commit()
    return {"status": "filled", "fill": fill, "verdict": verdict, "receipt_id": row["receipt_id"]}


@app.post("/api/proposals/{pid}/reject")
def reject(pid: str):
    p = _proposal(pid)
    row = audit.append(p["run_id"], "approval", "reject", {"proposal_id": pid, "by": "Owner (demo)"}, {}, "PAPER", None, 0)
    audit.db().execute("UPDATE proposals SET status='rejected', decided=?, receipt_id=? WHERE id=?",
                       (time.time(), row["receipt_id"], pid))
    audit.db().commit()
    return {"status": "rejected", "receipt_id": row["receipt_id"]}


@app.get("/api/limits")
def limits():
    return get_limits()


@app.put("/api/limits")
def set_limits(body: dict):
    new = {**get_limits()}
    for k, v in body.items():
        if k not in DEFAULT_LIMITS or type(v) is not int or v < 0:
            raise HTTPException(422, f"bad limit {k}")
        new[k] = v
    for k, v in new.items():
        audit.db().execute("INSERT OR REPLACE INTO limits (key, value) VALUES (?,?)", (k, v))
    row = audit.append(None, "limits", "set_limits", body, new, "PAPER", None, 0)
    # re-check every pending proposal immediately; a lowered cap blocks with a logged reason
    blocked = []
    for r in audit.db().execute("SELECT * FROM proposals WHERE status IN ('pending','blocked')").fetchall():
        m = json.loads(r["market"])
        v = E.check_limits(r["cost_pence"], m["market_id"], new, current_ledger(None))
        if not v["allowed"]:
            b = audit.append(r["run_id"], "limits", "limit_block", {"proposal_id": r["id"]}, v, "PAPER", None, 0)
            audit.db().execute("UPDATE proposals SET status='blocked', reason=?, receipt_id=? WHERE id=?",
                               (v["reason"], b["receipt_id"], r["id"]))
            blocked.append({"id": r["id"], "reason": v["reason"], "receipt_id": b["receipt_id"]})
        else:
            audit.db().execute("UPDATE proposals SET status='pending', reason=NULL WHERE id=? AND status='blocked'", (r["id"],))
    audit.db().commit()
    return {"limits": new, "blocked": blocked, "receipt_id": row["receipt_id"]}


@app.post("/api/demo/reset")
def demo_reset():
    con = audit.db()
    for t in ("proposals", "executions", "limits"):
        con.execute(f"DELETE FROM {t}")
    con.commit()
    return {"ok": True}
