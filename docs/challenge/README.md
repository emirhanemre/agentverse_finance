# Self-serve challenge results

**Self-serve challenge: our own check, not official judging.** Run with the unmodified AgentVerse Finance Kit
after the adapter was frozen. Cases were generated in memory from a fresh secret seed; the SHA-256 commitment was
written before any case existed (`COMMITMENT.txt`) and the seed revealed afterwards (`SEED-REVEAL.txt`), so anyone
can replay the exact cases. The kit's provenance scan flagged nothing.

Command (from any directory):

```bash
python3 agentverse/finance/bench.py challenge --pack mixed --cases 60 --project . --output <dir> --adapter python3 adapter.py
python3 agentverse/finance/bench.py challenge --pack real-markets --cases 60 --project . --output <dir> --adapter python3 adapter.py
```

| Run | Exact checks | Errors | Transactions F1 | Market paths | vs buy-and-hold (W/L) | Beat cash | Sign-test p |
|---|---|---|---|---|---|---|---|
| `mixed-60` | 40/40 pass | 0 | 100% | 20 completed | 10 / 10 | 8 / 20 | 1.0 |
| `real-markets-60` | n/a (markets only) | 0 | n/a | 60 completed | 30 / 30 | 20 / 60 | 1.0 |

What this says: the cashflow and transaction engines (the same `pubhedge_core` code the app uses) met every exact
check on unseen cases. The market-timing rule completed every path with no errors but has **no measurable edge**
over buy-and-hold: half wins, half losses, p = 1.0. That is the honest result; we don't claim one.

The `mixed-60` report records "uncommitted changes: 6": those were front-end files being edited at the time,
not the adapter or `pubhedge_core` (both committed and unchanged since).
