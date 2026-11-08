"""Append-only SQLite audit log. Each row stores the SHA-256 of the previous row, so an
edited or deleted row breaks the chain and verify() says where."""
import hashlib
import json
import sqlite3
import threading
import time
import uuid

from .config import DB_PATH

_lock = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, run_id TEXT, step TEXT, call TEXT,
  args TEXT, result TEXT, badge TEXT, model TEXT, ms INTEGER, tokens_in INTEGER, tokens_out INTEGER,
  receipt_id TEXT UNIQUE, prev_hash TEXT, hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, mode TEXT, started REAL, finished REAL, wall_ms INTEGER,
  status TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, run_id TEXT, created REAL, market TEXT, shares INTEGER,
  cost_pence INTEGER, status TEXT, decided REAL, reason TEXT, receipt_id TEXT);
CREATE TABLE IF NOT EXISTS executions (id TEXT PRIMARY KEY, proposal_id TEXT, ts REAL, fill TEXT, receipt_id TEXT);
CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY, value INTEGER);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


_con = None


def db() -> sqlite3.Connection:
    global _con
    if _con is None:
        _con = connect()
    return _con


def _digest(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def append(run_id, step, call, args, result, badge, model=None, ms=0, tokens_in=0, tokens_out=0) -> dict:
    with _lock:
        con = db()
        last = con.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last["hash"] if last else "genesis"
        row = {"ts": time.time(), "run_id": run_id, "step": step, "call": call,
               "args": json.dumps(args, sort_keys=True, default=str),
               "result": json.dumps(result, sort_keys=True, default=str), "badge": badge, "model": model,
               "ms": int(ms), "tokens_in": int(tokens_in or 0), "tokens_out": int(tokens_out or 0),
               "receipt_id": "r_" + uuid.uuid4().hex[:12], "prev_hash": prev}
        row["hash"] = _digest(row)
        con.execute("INSERT INTO audit (ts, run_id, step, call, args, result, badge, model, ms, tokens_in, tokens_out,"
                    " receipt_id, prev_hash, hash) VALUES (:ts,:run_id,:step,:call,:args,:result,:badge,:model,:ms,"
                    ":tokens_in,:tokens_out,:receipt_id,:prev_hash,:hash)", row)
        con.commit()
        return row


def rows(run_id=None, limit=500) -> list:
    q = "SELECT * FROM audit" + (" WHERE run_id = ?" if run_id else "") + " ORDER BY seq DESC LIMIT ?"
    args = (run_id, limit) if run_id else (limit,)
    return [dict(r) for r in db().execute(q, args).fetchall()]


def receipt(receipt_id: str):
    r = db().execute("SELECT * FROM audit WHERE receipt_id = ?", (receipt_id,)).fetchone()
    return dict(r) if r else None


def verify() -> dict:
    prev = "genesis"
    n = 0
    for r in db().execute("SELECT * FROM audit ORDER BY seq").fetchall():
        d = dict(r)
        seq, h = d.pop("seq"), d.pop("hash")
        if d["prev_hash"] != prev or _digest(d) != h:
            return {"ok": False, "broken_at_seq": seq, "rows": n}
        prev, n = h, n + 1
    return {"ok": True, "rows": n, "head": prev}
