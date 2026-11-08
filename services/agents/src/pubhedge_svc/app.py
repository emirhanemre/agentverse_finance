"""FastAPI service: streams agent runs over SSE and serves receipts, approvals, limits,
the audit log and results. Paper trading only: no real order is ever placed."""
import asyncio
import json
import threading
import time
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pubhedge_core.limits import DEFAULT_LIMITS

from . import audit, config
from . import engines as E
from .chain import run_chain
from .config import DATA, RUNS
from .tools import OFFER, PUB, SCENARIO, SYN, binding, current_ledger, pick_offer, quote_offer, settle

config.load_env()
app = FastAPI(title="Pub Hedge agents")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])
DEMO_FIXTURE = RUNS / "demo-run.json"
# One decision at a time: approve, reject, expiry and limit re-checks read the ledger and then write, so two
# requests in the API's thread pool could otherwise both pass a cap or fill the same proposal twice.
_decide = threading.Lock()
REQUOTE_AFTER_S = 15 * 60  # a real-market quote older than this is re-checked before a fill


def _now() -> float:
    return time.time()


def _expired(market: dict) -> bool:
    e = market.get("expires_at")
    return bool(e) and _now() >= datetime.fromisoformat(e).timestamp()


def _expire(r, market: dict, reason: str):
    row = audit.append(r["run_id"], "approval", "expire", {"proposal_id": r["id"]}, {"reason": reason}, "PAPER", None, 0)
    audit.db().execute("UPDATE proposals SET status='expired', reason=?, receipt_id=? WHERE id=?",
                       (reason, row["receipt_id"], r["id"]))


def _expire_due():
    """Proposals whose window has opened can no longer be approved. Logged once, when first noticed. Call under _decide."""
    for r in audit.db().execute("SELECT * FROM proposals WHERE status IN ('pending','blocked')").fetchall():
        m = json.loads(r["market"])
        if _expired(m):
            when = f"{m['expires_at'][11:16]} on {m['expires_at'][:10]}"
            _expire(r, m, f"kick-off was at {when}" if m.get("kind") == "offer" else f"the window opened at {when}")
    audit.db().commit()


def get_limits() -> dict:
    rows = {r["key"]: r["value"] for r in audit.db().execute("SELECT key, value FROM limits").fetchall()}
    return {**DEFAULT_LIMITS, **rows}


@app.on_event("startup")
async def start_monitor():
    """Optional scheduled monitor: PUBHEDGE_MONITOR_MINUTES=N re-runs the deterministic chain on this
    coming weekend every N minutes (template narration, no model spend). Proposals land in the
    approval queue like any other run; nothing executes without the owner."""
    import os
    minutes = float(os.environ.get("PUBHEDGE_MONITOR_MINUTES", "0") or 0)
    if minutes <= 0:
        return

    async def loop():
        while True:
            try:
                await run_chain("live", lambda e: None, get_limits(), run_id="monitor_" + uuid.uuid4().hex[:8], use_models=False)
            except Exception as exc:  # keep monitoring; the failure is in the log
                audit.append(None, "monitor", "monitor_error", {}, {"error": str(exc)[:300]}, "ERROR")
            await asyncio.sleep(minutes * 60)
    asyncio.create_task(loop())


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
    with _decide:
        _expire_due()
    run = latest_run()
    bt = json.loads((DATA / "results" / "backtest.json").read_text())
    ch_path = DATA / "results" / "challenge-summary.json"
    props = [dict(r) for r in audit.db().execute("SELECT * FROM proposals ORDER BY created DESC LIMIT 20").fetchall()]
    led, lim = current_ledger(None), get_limits()
    for p in props:
        p["market"] = json.loads(p["market"])
        if p["status"] in ("pending", "blocked"):  # limit checks are re-run on every read, not cached
            p["market"]["verdict"] = {"market_id": p["market"]["market_id"],
                                      **E.check_limits(p["cost_pence"], p["market"]["market_id"], lim, led)}
    return {
        "pub": {**PUB, "identity_badge": "REAL", "financials_label": SYN, "owner": "Owner (demo)"},
        "scenario": SCENARIO,
        "run": ({**run, "summary": json.loads(run["summary"] or "{}")} if run else None),
        "tools": results_for(run) if run else {},
        # the recorded demo weekend, for the first screen's preview (same before and after any run)
        "demo_tools": json.loads(DEMO_FIXTURE.read_text()).get("tool_results", {}) if DEMO_FIXTURE.exists() else {},
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
    with _decide:
        return _approve(pid, body)


def _approve(pid: str, body: Approve):
    _expire_due()
    p = _proposal(pid)
    if p["status"] == "expired":  # an answer the card can show, not an error
        return {"status": "expired", "reason": p["reason"], "verdict": p["market"].get("verdict")}
    if p["status"] not in ("pending", "blocked"):
        raise HTTPException(409, f"proposal is {p['status']}")
    m = p["market"]
    if m.get("binding") and m["binding"] != binding(m["market_id"], p["shares"], p["cost_pence"]):
        raise HTTPException(409, "proposal no longer matches what was shown; run the agent again")
    if m.get("kind") == "offer" and _now() - m.get("quoted_at", 0) > REQUOTE_AFTER_S:
        try:
            same = {k: m[k] for k in ("event_slug", "fixture", "competition", "venue", "trigger", "team") if k in m}
            q = quote_offer(get_limits(), current_ledger(None), {**OFFER, **same, "market_question": m["market"]})
        except Exception as exc:  # no fresh price, no fill
            raise HTTPException(503, f"couldn't re-check the market price, nothing was placed ({type(exc).__name__})") from exc
        if q["cost_per_share"] > m["cost_per_share"]:
            reason = f"the price rose from {m['cost_per_share']:.4f} to {q['cost_per_share']:.4f} a share; queue the offer again"
            _expire(p, m, reason)
            audit.db().commit()
            return {"status": "expired", "reason": reason, "verdict": m.get("verdict")}
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
    with _decide:
        p = _proposal(pid)
        if p["status"] not in ("pending", "blocked"):
            raise HTTPException(409, f"proposal is {p['status']}")
        return _reject(p)


def _reject(p):
    pid = p["id"]
    row = audit.append(p["run_id"], "approval", "reject", {"proposal_id": pid, "by": "Owner (demo)"}, {}, "PAPER", None, 0)
    audit.db().execute("UPDATE proposals SET status='rejected', decided=?, receipt_id=? WHERE id=?",
                       (time.time(), row["receipt_id"], pid))
    audit.db().commit()
    return {"status": "rejected", "receipt_id": row["receipt_id"]}


@app.post("/api/proposals/{pid}/settle")
def settle_position(pid: str):
    """Check what a filled paper position paid. Settles once; asking again returns the same result."""
    with _decide:
        p = _proposal(pid)
        if p["status"] == "settled":
            return p["market"]["settlement"]
        if p["status"] != "filled":
            raise HTTPException(409, f"proposal is {p['status']}")
        fill = json.loads(audit.db().execute("SELECT fill FROM executions WHERE proposal_id = ?", (pid,)).fetchone()["fill"])
        try:
            res = settle(p["market"], p["shares"], fill["cost_gbp"])
        except Exception as exc:
            raise HTTPException(503, f"couldn't fetch the result ({type(exc).__name__})") from exc
        if res["status"] != "settled":
            return res
        row = audit.append(p["run_id"], "settle", "settle", {"proposal_id": pid}, res, res["badge"], None, 0)
        res["receipt_id"] = row["receipt_id"]
        audit.db().execute("UPDATE proposals SET status='settled', market=? WHERE id=?",
                           (json.dumps({**p["market"], "settlement": res}), pid))
        audit.db().commit()
        return res


@app.post("/api/offers/queue")
def queue_offer():
    """Turn the priced match-day offer into an ordinary pending proposal: same limits, approval and paper fill."""
    q = quote_offer(get_limits(), current_ledger(None), pick_offer(_now()))
    if not q["shares"]:
        raise HTTPException(409, "nothing to cover inside the current caps")
    if q.get("kickoff") and _now() >= datetime.fromisoformat(q["kickoff"]).timestamp():
        raise HTTPException(409, "kick-off has passed, so there is nothing left to cover")
    run = latest_run()
    run_id = run["run_id"] if run else "offer"
    pid = f"p_offer_{uuid.uuid4().hex[:6]}"
    market = {k: q[k] for k in ("market_id", "event_slug", "kind", "fixture", "competition", "venue", "kickoff", "market",
                                "trigger", "team", "offer", "covers_cap", "worst_case_gbp", "ask", "market_prob", "fee_rate",
                                "cost_per_share",
                                "payout_if_event_gbp", "fixed_cost_gbp")}
    market["price_badge"] = q["badge"]
    cost_pence = int(round(q["hedge_cost_gbp"] * 100))
    market.update(verdict=q["verdict"], expires_at=q.get("kickoff"), quoted_at=_now(),
                  binding=binding(q["market_id"], q["shares"], cost_pence))
    row = audit.append(run_id, "offer", "queue_offer", {"market_id": q["market_id"]}, q, q["badge"], None, 0)
    audit.db().execute("INSERT INTO proposals (id, run_id, created, market, shares, cost_pence, status) VALUES (?,?,?,?,?,?,?)",
                       (pid, run_id, time.time(), json.dumps(market), q["shares"], cost_pence, "pending"))
    audit.db().commit()
    return {"status": "pending", "id": pid, "receipt_id": row["receipt_id"], "quote": q}


@app.get("/api/limits")
def limits():
    return get_limits()


@app.put("/api/limits")
def set_limits(body: dict):
    with _decide:
        return _set_limits(body)


def _set_limits(body: dict):
    _expire_due()
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
