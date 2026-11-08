# Pub Hedge

An AI risk officer for independent UK pubs. It reads the till and the bank feed and measures what rain costs
the pub. It projects whether Friday's payroll will clear after the weekend and proposes small, capped weather
hedges. A human approves every one, and execution is paper only.

Agentverse 2026, Finance track. The demo pub is **The Faltering Fullback** (Bacchus Inns Ltd, 05770953, N4 3HB),
used for public identity data only. **All of its financials are synthetic: modelled for a pub of this profile,
not The Faltering Fullback's actual figures.**

## For judges: run the adapter

The Finance Kit adapter is standard library only and runs on Python 3.9+ from any working directory:

```bash
python3 agentverse/finance/bench.py challenge --pack mixed --cases 60 --project . --output /tmp/ph-challenge-$(date +%s) --adapter python3 adapter.py
```

The kit refuses an existing output folder, so each run needs a new `--output`.

`adapter.py` calls `pubhedge_core/`, the same engines the app uses. `pubhedge_core.cashflow` is the engine that
tells the owner whether payroll clears. Our own self-serve challenge results are in
[docs/challenge/](docs/challenge/README.md). They are our own check, not official judging:

- mixed pack: 40/40 exact checks, transactions F1 100%, 0 errors;
- market rule: no edge over buy-and-hold (23 wins, 37 losses on real-market windows, p = 0.09).

## Run it

Needs `uv` (Python 3.12 is pinned for the service), Node 20+ and npm.

```bash
cp .env.example .env.local   # then add your own keys; never commit this file
scripts/dev.sh               # API on :8000, app on http://localhost:3000
PUBHEDGE_OFFLINE=1 scripts/dev.sh   # no keys needed: cached data, template narration, no live calls
```

`scripts/check.sh` needs ports 3000 and 8000 free. The first time it runs, Playwright downloads Chromium.
`UPDATE_SHOTS=1 scripts/check.sh` also refreshes `docs/screenshots/`.

| Script | Purpose |
|---|---|
| `scripts/dev.sh` | Runs the app. `PUBHEDGE_OFFLINE=1 scripts/dev.sh` makes no live API or model calls: cached data only, template narration |
| `scripts/check.sh` | The gate: lint, unit tests, adapter practice run (Python 3.9 and current), tsc, lint, build, health checks, a REPLAY run over SSE, and Playwright end to end. It spends no API quota or model tokens |
| `scripts/smoke.sh` | `check.sh`, plus one live ping per API and one live agent run |
| `scripts/demo-reset.sh` | Resets proposals, paper fills and limits for the demo. The audit log is kept |

In the app, **Historical scenario** replays a real wet weekend: the August bank holiday, 29–30 Aug 2026, with
6.1 mm of rain on the Saturday afternoon (2.6 mm had been forecast). It uses the forecast that was available at the time.

- **Live** uses this coming weekend's Met Office forecast.
- **Replay** streams a recorded live run, for when venue wifi fails.

## What is real and what is synthetic

| Real | Synthetic (always badged) |
|---|---|
| Companies House profile and officer match, postcode lookup | Daily takings, bank feed and fixed costs (seeded generator, `data/synthetic/manifest.json`) |
| Met Office forecast (live), Open-Meteo weather and archived forecasts | The rain contract and its price. No London rain market exists on Polymarket |
| Polymarket London temperature markets and fees (read-only) | Paper fills (PAPER). Stripe charges are TEST MODE |
| England and Ireland match days; beer duty change dates | The 12-pub backtest panel |

Full list with licences: [docs/data-sources.md](docs/data-sources.md). Backtest on held-out months:
[docs/backtest-results.md](docs/backtest-results.md). Our policy is about break-even (+£26 a pub-year, 95% CI −£132 to +£222), against −£1,514 for
hedging every weekend, but it does not cut payroll-shortfall weeks at these caps. We say so.

## Architecture

```
app/ (Next.js)  <-SSE-  services/agents (FastAPI + Google ADK)  ->  pubhedge_core/ (stdlib engines)
                              |  verifier -> ingest -> risk -> pricer -> monitor (gemini-3.8-flash)
                              |  hedge rationale (gemini-4-argon), grounding check on every number
                              |  tools: Companies House, Met Office, Open-Meteo, Polymarket (read), Stripe (test)
                              '- SQLite audit log, hash-chained and append-only: every tool call is a receipt
adapter.py -> pubhedge_core/  (the Finance Kit adapter: cashflow, transactions, market_step)
```

- **The model never computes numbers.** Tools do the maths: OLS regression with CIs, the LP sizing, the limit
  guard, the cashflow engine and the paper exchange. A grounding check removes any number in the narration that
  doesn't appear in that run's tool outputs.
- **Limits are enforced in code** (`pubhedge_core/limits.py`): £800 a week, £2,000 a month, £600 a market. Anything
  over £50 needs a second confirmation. Lowering a cap re-checks pending hedges at once and logs the block.
- **If Gemini fails,** the deterministic pipeline still completes and the narration is badged TEMPLATE.
- **Paper trading only.** Polymarket is read-only (UK users can't trade there). Real execution would go to a
  UK-licensed venue (Smarkets, Betfair), shown as "not connected in demo".
