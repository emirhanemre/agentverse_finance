"""Custom Finance Kit task `pub_hedge_sizing` (PRACTICE, authored synthetic cases).

Inputs: 1-3 markets (cost per share, value per share to the owner = probability x (1 + payroll
penalty), max shares = loss covered), a spend budget and a per-market cap, all in pence.
Answers: the optimal expected value from an independent brute-force oracle (enumerate whole
shares of every market but the last; best whole fill of the last). It shares no code with
pubhedge_core.sizing. Writes to .bench/ (gitignored); import with:
  python3 agentverse/finance/bench.py import --inputs .bench/sizing-src/inputs.jsonl \
    --answers .bench/sizing-src/answers.jsonl --source "Authored synthetic hedge sizing" --synthetic --seed 7 \
    --output .bench/sizing-task
"""
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def oracle(markets, budget, cap):
    best = 0
    lims = [min(m["max_shares"], cap // m["cost_per_share_pence"], budget // m["cost_per_share_pence"]) for m in markets]
    head, last = markets[:-1], markets[-1]
    for combo in itertools.product(*[range(n + 1) for n in lims[:-1]]):
        spent = sum(x * m["cost_per_share_pence"] for x, m in zip(combo, head))
        if spent > budget:
            continue
        val = sum(x * (m["value_per_share_pence"] - m["cost_per_share_pence"]) for x, m in zip(combo, head))
        edge = last["value_per_share_pence"] - last["cost_per_share_pence"]
        n = min(lims[-1], (budget - spent) // last["cost_per_share_pence"]) if edge > 0 else 0
        best = max(best, val + n * edge)
    return best


def main(seed=7, n=60):
    rng = random.Random(seed)
    out = ROOT / ".bench" / "sizing-src"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "inputs.jsonl", "w") as fi, open(out / "answers.jsonl", "w") as fa:
        for i in range(n):
            ms = []
            for j in range(rng.randint(1, 3)):
                k = rng.randint(3, 95)
                ms.append({"id": f"m{j}", "cost_per_share_pence": k, "value_per_share_pence": max(0, k + rng.randint(-20, 25)),
                           "max_shares": rng.randint(0, 150)})
            budget, cap = rng.randint(0, 3000), rng.randint(500, 2500)
            case = {"case_id": f"size-{i:03d}", "task": "pub_hedge_sizing",
                    "input": {"markets": ms, "budget_pence": budget, "per_market_cap_pence": cap}}
            fi.write(json.dumps(case) + "\n")
            fa.write(json.dumps({"case_id": case["case_id"], "expected": {"expected_value_pence": oracle(ms, budget, cap)}}) + "\n")
    print(f"wrote {n} cases to {out}")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
