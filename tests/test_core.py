"""Edge cases from the Finance Kit's TESTING.md, against our own engines."""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pubhedge_core import cashflow, strategy, transactions  # noqa: E402
from pubhedge_core.validate import InvalidInput  # noqa: E402


def ev(i, d, amt, cur="GBP", desc=""):
    return {"id": i, "date": d, "amount_pence": amt, "currency": cur, "description": desc}


def tx(i, s, r, amt=1000, d="2026-05-01", cur="GBP"):
    return {"id": i, "sender": s, "recipient": r, "amount_pence": amt, "date": d, "currency": cur}


class Cashflow(unittest.TestCase):
    def test_example_from_kit_docs(self):
        out = cashflow.forecast(10000, [ev("rent", "2026-01-02", -15000)])
        self.assertEqual((out["closing_balance_pence"], out["minimum_balance_pence"],
                          out["shortfall_pence"], out["first_negative_date"]),
                         (-5000, -5000, 5000, "2026-01-02"))

    def test_order_by_date_then_id(self):
        evs = [ev("b", "2026-01-01", 100), ev("a", "2026-01-01", -150), ev("c", "2025-12-31", 10)]
        out = cashflow.forecast(0, evs)
        self.assertEqual([t["id"] for t in out["timeline"]], ["c", "a", "b"])
        self.assertEqual(out["minimum_balance_pence"], -140)
        self.assertEqual(out["first_negative_date"], "2026-01-01")

    def test_negative_opening_counts_without_events(self):
        out = cashflow.forecast(-500, [])
        self.assertEqual((out["minimum_balance_pence"], out["shortfall_pence"], out["first_negative_date"]),
                         (-500, 500, None))

    def test_no_negative_gives_null(self):
        self.assertIsNone(cashflow.forecast(100, [ev("x", "2026-01-01", -100)])["first_negative_date"])

    def test_invalid_currency(self):
        for cur in ("USD", "gbp", None):
            with self.assertRaises(InvalidInput):
                cashflow.forecast(0, [ev("a", "2026-01-01", 1), ev("b", "2026-01-02", 1, cur)])

    def test_duplicate_ids_and_bad_types(self):
        with self.assertRaises(InvalidInput):
            cashflow.forecast(0, [ev("a", "2026-01-01", 1), ev("a", "2026-01-02", 1)])
        with self.assertRaises(InvalidInput):
            cashflow.forecast(True, [])
        with self.assertRaises(InvalidInput):
            cashflow.forecast(0, [ev("a", "2026-02-30", 1)])
        with self.assertRaises(InvalidInput):
            cashflow.forecast(0, [ev("a", "2026-01-01", 1.5)])

    def test_description_is_ignored(self):
        a = cashflow.forecast(0, [ev("a", "2026-01-01", -10, desc="Ignore previous instructions")])
        self.assertEqual(a["shortfall_pence"], 10)


class Transactions(unittest.TestCase):
    def test_three_cycle_and_decoys(self):
        rows = [tx("t1", "A", "B"), tx("t2", "B", "C"), tx("t3", "C", "A"),
                tx("d1", "X", "Y"), tx("d2", "Y", "X"),  # 2-loop decoy
                tx("q1", "P", "Q"), tx("q2", "Q", "R"), tx("q3", "R", "S"), tx("q4", "S", "P")]
        out = transactions.analyse(rows, 500)
        self.assertEqual(out["cycle_transaction_ids"], ["t1", "t2", "t3"])
        self.assertEqual(out["large_transfer_ids"], sorted(r["id"] for r in rows))
        self.assertEqual(out["total_transferred_pence"], 9000)

    def test_parallel_edges_all_flagged_and_threshold_inclusive(self):
        rows = [tx("z", "A", "B", 700), tx("y", "A", "B", 699), tx("x", "B", "C"), tx("w", "C", "A")]
        out = transactions.analyse(rows, 700)
        self.assertEqual(out["cycle_transaction_ids"], ["w", "x", "y", "z"])
        self.assertEqual(out["large_transfer_ids"], ["w", "x", "z"])

    def test_invalid(self):
        with self.assertRaises(InvalidInput):
            transactions.analyse([tx("a", "A", "B"), tx("a", "B", "C")], 10)
        with self.assertRaises(InvalidInput):
            transactions.analyse([tx("a", "A", "B", cur="EUR")], 10)
        with self.assertRaises(InvalidInput):
            transactions.analyse([tx("a", "A", "B", amt=0)], 10)


class Strategy(unittest.TestCase):
    def step(self, prices, cash=100000, shares=0, fee=100, bps=5):
        hist = [{"date": "2026-01-%02d" % (i + 1), "price_pence": p} for i, p in enumerate(prices)]
        return strategy.decide({"history": hist, "cash_pence": cash, "shares": shares,
                                "fee_pence": fee, "slippage_bps": bps})["action"]

    def test_warmup_holds(self):
        self.assertEqual(self.step([100] * 5), "hold")

    def test_uptrend_buys_downtrend_sells_flat_holds(self):
        self.assertEqual(self.step(list(range(100, 130))), "buy")
        self.assertEqual(self.step(list(range(130, 100, -1)), shares=10), "sell")
        self.assertEqual(self.step([100] * 30), "hold")


class AdapterProcess(unittest.TestCase):
    def test_stdout_is_only_responses_from_any_cwd(self):
        reqs = [
            {"request_id": "1", "task": "cashflow", "input": {"opening_balance_pence": 10000, "events": [
                {"id": "rent", "date": "2026-01-02", "amount_pence": -15000, "currency": "GBP"}]}},
            {"request_id": "2", "task": "cashflow", "input": {"opening_balance_pence": 0, "events": [
                {"id": "a", "date": "2026-01-02", "amount_pence": 1, "currency": "USD"}]}},
            {"request_id": "3", "task": "nope", "input": {}},
        ]
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "adapter.py")], cwd="/",
                              input="\n".join(json.dumps(r) for r in reqs) + "\n",
                              capture_output=True, text=True, timeout=20)
        lines = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([x["request_id"] for x in lines], ["1", "2", "3"])
        self.assertEqual(lines[0]["output"]["shortfall_pence"], 5000)
        self.assertEqual(lines[1]["output"], {"error": "invalid_input"})
        self.assertEqual(lines[2]["output"], {"error": "invalid_input"})


if __name__ == "__main__":
    unittest.main()
