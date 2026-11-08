# Custom kit task: `pub_hedge_sizing` (PRACTICE)

**Practice, not a result.** These are authored synthetic cases, and the answer files sit on disk.

- **Task:** given 1–3 markets (cost per share, value per share to the owner, maximum shares = loss covered), a
  spend budget and a per-market cap, all in pence, return the sizing with the highest expected value in whole shares.
- **Answers:** an independent brute-force oracle (`scripts/gen_sizing_task.py`). It enumerates the shares of every
  market but the last, then takes the best whole fill of the last. It shares no code with `pubhedge_core.sizing`.
  Only `expected_value_pence` is checked, because ties make the positions themselves non-unique.
- **Implementation tested:** `pubhedge_core.sizing.size`, through `adapter.py`. The agent service's `size_hedges`
  tool uses the same code.

| Run | Cases | Pass | Fail | Errors | Notes |
|---|---|---|---|---|---|
| v1, greedy fill by value per £ then floor | 60 (seed 7) | 59 | 1 | 0 | Rounding the LP down missed the integer optimum on a tight budget (434p) |
| v2, exact bounded-knapsack DP | 60 (seed 7) | 60 | 0 | 0 | |
| v2, exact bounded-knapsack DP, Python 3.9 | 200 (seed 99) | 200 | 0 | 0 | |

The v1 failure is why the sizer is now an exact integer solver. A unit test cross-checks it against scipy's LP
on 200 random instances: the result is never above the LP relaxation and never below the LP's answer rounded down.

Reproduce:

```bash
python3 scripts/gen_sizing_task.py 7 60
python3 agentverse/finance/bench.py import --inputs .bench/sizing-src/inputs.jsonl --answers .bench/sizing-src/answers.jsonl \
  --source "Authored synthetic hedge sizing" --synthetic --seed 7 --output .bench/sizing-task
python3 agentverse/finance/bench.py run --dataset .bench/sizing-task --output .bench/sizing-run --limit 60 --adapter python3 adapter.py
```
