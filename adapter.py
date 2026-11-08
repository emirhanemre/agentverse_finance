#!/usr/bin/env python3
"""Finance Kit adapter for Pub Hedge. Standard library only; Python 3.9+.

Reads one JSON request per line on stdin, writes one JSON response per line on
stdout. Nothing else is ever written to stdout; diagnostics go to stderr.
Calls our own engines in pubhedge_core (found relative to this file).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pubhedge_core import cashflow, sizing, strategy, transactions  # noqa: E402
from pubhedge_core.validate import InvalidInput  # noqa: E402


def handle(task, inp):
    if not isinstance(inp, dict):
        raise InvalidInput("input must be an object")
    if task == "cashflow":
        out = cashflow.forecast(inp.get("opening_balance_pence"), inp.get("events"))
        out.pop("timeline")
        return out
    if task == "transactions":
        out = transactions.analyse(inp.get("rows"), inp.get("large_transfer_pence"))
        out["trace"] = {"loops": len(out.pop("loops"))}
        return out
    if task == "market_step":
        return strategy.decide(inp)
    if task == "pub_hedge_sizing":  # our custom kit task (practice, synthetic)
        return sizing.size(inp.get("markets"), inp.get("budget_pence"), inp.get("per_market_cap_pence"))
    raise InvalidInput("unknown task")


def respond(line):
    try:
        req = json.loads(line)
    except ValueError:
        return {"request_id": None, "output": {"error": "invalid_input"}}
    rid = req.get("request_id") if isinstance(req, dict) else None
    try:
        out = handle(req.get("task"), req.get("input"))
    except InvalidInput as exc:
        print(f"invalid_input: {exc}", file=sys.stderr)
        out = {"error": "invalid_input"}
        if req.get("task") == "market_step":
            out = {"action": "hold", "error": "invalid_input"}
    return {"request_id": rid, "output": out}


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        sys.stdout.write(json.dumps(respond(line), separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
