import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pubhedge_core import limits  # noqa: E402
from pubhedge_core.validate import InvalidInput  # noqa: E402

L = dict(limits.DEFAULT_LIMITS)


class Limits(unittest.TestCase):
    def test_within(self):
        v = limits.check(2000, "m1", L, {})
        self.assertTrue(v["allowed"])
        self.assertFalse(v["needs_second_approval"])

    def test_cap_edges_are_inclusive(self):
        self.assertTrue(limits.check(6000, "m1", L, {"spent_this_week_pence": 6000})["allowed"])
        v = limits.check(6001, "m1", L, {"spent_this_week_pence": 6000})
        self.assertFalse(v["allowed"])
        self.assertIn("weekly spend", v["reason"])

    def test_lowered_cap_blocks(self):
        v = limits.check(2000, "m1", {**L, "weekly_spend_cap_pence": 1500}, {})
        self.assertFalse(v["allowed"])
        self.assertEqual(v["reason"], "weekly spend: £20.00 would exceed the £15.00 cap")

    def test_concentration_and_threshold(self):
        v = limits.check(5500, "m1", L, {"by_market_pence": {"m1": 1000}})
        self.assertFalse(v["allowed"])
        self.assertTrue(v["needs_second_approval"])

    def test_invalid(self):
        with self.assertRaises(InvalidInput):
            limits.check(-1, "m1", L, {})
        with self.assertRaises(InvalidInput):
            limits.check(10, "m1", {**L, "weekly_spend_cap_pence": "120"}, {})


if __name__ == "__main__":
    unittest.main()
