# Self-serve challenge results

**Self-serve challenge: our own check, not official judging.** These runs used the unmodified AgentVerse Finance
Kit against the final committed adapter (commit `53991bb`, no uncommitted changes). Cases were generated in
memory from a fresh secret seed. The SHA-256 commitment was written before any case existed
(`COMMITMENT.txt`) and the seed was revealed afterwards (`SEED-REVEAL.txt`), so anyone can replay the exact cases.

```bash
python3 agentverse/finance/bench.py challenge --pack mixed --cases 60 --project . --output <dir> --adapter python3 adapter.py
python3 agentverse/finance/bench.py challenge --pack real-markets --cases 60 --project . --output <dir> --adapter python3 adapter.py
```

| Run | Exact checks | Errors | Transactions F1 | Market paths | vs buy-and-hold (W/L) | Beat cash | Sign-test p |
|---|---|---|---|---|---|---|---|
| `mixed-60` | 40/40 pass | 0 | 100% | 20 completed | 10 / 10 | 6 / 20 | 1.0 |
| `real-markets-60` | n/a (markets only) | 0 | n/a | 60 completed | 23 / 37 | 25 / 60 | 0.09 |

**What this says**

- **Cashflow and transactions pass.** These engines are the same `pubhedge_core` code the app uses, and they met
  every exact check on unseen cases.
- **The market rule has no edge.** It is a trend filter with a cost band. It completed every path without errors,
  but it has **no edge** over buy-and-hold. On real Binance windows it lost more often than it won (23 against 37,
  p = 0.09). We report that as it is and don't claim an edge.

**Provenance flags**

The kit's scan raised three items for a human to check. Here is what each one is:

- **`scripts/check.sh`** runs the kit's `bench.py` *command line* to generate practice cases and score the
  adapter. It doesn't import kit code, and the adapter never calls it.
- **`scripts/gen_sizing_task.py`** builds our custom practice task (`pub_hedge_sizing`). It *writes* its own
  answer file from an independent brute-force oracle and names `bench.py import` in its docstring. It never reads
  the kit's answers or seeds, and the adapter doesn't use it.

`adapter.py` and `pubhedge_core/` import only the Python standard library.

**Earlier runs** (`earlier/`) were made before the `pub_hedge_sizing` branch was added to the adapter. They gave
the same exact-check result (40/40, F1 100%). On markets: mixed 10/10, real-markets 30/30, p = 1.0.
