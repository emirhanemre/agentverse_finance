# Finance project test report

**CHALLENGE (self-serve): hidden mixed cases**

Dataset: 60 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **40 passed, 0 failed, 0 execution errors**.
Market simulations completed: **20**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `427c8668c9bebd33021a1e44f8d11bd715df75822466eb7fe0b12a9a200358bf`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `b951e24316d7fa84e6e6dc9c51bb9d26c2cc60e5`, uncommitted changes: 6
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| cashflow / invalid_currency | 3 | 0 | 0 | 0 |
| cashflow / late_income | 4 | 0 | 0 | 0 |
| cashflow / negative_opening | 3 | 0 | 0 | 0 |
| cashflow / regular | 4 | 0 | 0 | 0 |
| cashflow / same_day | 3 | 0 | 0 | 0 |
| cashflow / small_business | 3 | 0 | 0 | 0 |
| markets / falling | 0 | 0 | 0 | 4 |
| markets / flat | 0 | 0 | 0 | 3 |
| markets / jump | 0 | 0 | 0 | 3 |
| markets / regime_change | 0 | 0 | 0 | 3 |
| markets / rising | 0 | 0 | 0 | 4 |
| markets / volatile | 0 | 0 | 0 | 3 |
| transactions / decoy_loops | 3 | 0 | 0 | 0 |
| transactions / duplicate_id | 3 | 0 | 0 | 0 |
| transactions / large_ordinary | 3 | 0 | 0 | 0 |
| transactions / multiple_cycles | 3 | 0 | 0 | 0 |
| transactions / one_cycle | 4 | 0 | 0 | 0 |
| transactions / ordinary | 4 | 0 | 0 | 0 |

## Transaction-cycle evidence

Record precision: 100.0%; recall: 100.0%; F1: 100.0%. False alerts: 0; missed cycle records: 0.
Judge detection by recall and F1, not the pass count: a detector that flags nothing still passes every case with no cycle.
These labels identify planted graph patterns, not actual fraud or regulatory compliance.

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 835a8bf67a7c487474be | £8,402.81 | £329.57 | £9,623.01 | £8,073.24 | 0.39% |
| d74f0e7baa211a74a0c7 | £6,555.93 | £0.00 | £3,947.43 | £6,555.93 | 0.00% |
| 7719007b8cc8cdb0bee9 | £3,451.58 | £0.00 | £3,428.72 | £3,451.58 | 0.00% |
| 9f142f41181b37967d2c | £3,811.75 | -£1,751.22 | £5,649.76 | £5,562.97 | 31.47% |
| c3e448a0fba0d603a443 | £9,892.56 | £634.81 | £8,079.31 | £9,257.75 | 10.00% |
| 9498960b52e80ada0270 | £1,556.36 | £17.17 | £1,950.30 | £1,539.19 | 1.94% |
| 8f7cbccc3b474dc07fa5 | £11,179.26 | £1,841.40 | £12,931.18 | £9,337.86 | 0.67% |
| d4dd5269fb8af08b866e | £4,136.94 | £0.00 | £3,551.90 | £4,136.94 | 0.00% |
| b16f252e7c7c9edc46f4 | £2,174.29 | £0.00 | £2,163.09 | £2,174.29 | 0.00% |
| e1a59af6b0ba4a41d4c2 | £1,436.77 | -£285.90 | £1,954.55 | £1,722.67 | 21.86% |
| 955295d7e84b04c99cd0 | £7,752.14 | £0.00 | £7,697.66 | £7,752.14 | 0.00% |
| cb4b8680424855882357 | £5,988.94 | -£52.79 | £7,613.81 | £6,041.73 | 0.92% |
| fdcc247ebf2ffd168b53 | £6,397.26 | £1,690.88 | £7,281.69 | £4,706.38 | 0.57% |
| 9bd23fffd39659146afa | £6,888.98 | £0.00 | £4,988.23 | £6,888.98 | 0.00% |
| a7310e8a5863cc766b6e | £5,481.96 | £0.00 | £5,434.12 | £5,481.96 | 0.00% |
| b5f6ee6b095a7568b148 | £2,392.38 | -£79.74 | £2,560.12 | £2,472.12 | 3.22% |
| c70075d1feb9e12bc600 | £3,383.06 | £360.38 | £3,082.98 | £3,022.68 | 9.50% |
| 907cff68625da67acfa4 | £6,830.70 | £205.77 | £8,694.51 | £6,624.93 | 0.77% |
| 9bddc952bccb6596755f | £4,399.99 | £1,426.55 | £4,868.86 | £2,973.44 | 0.69% |
| cbc550ed2d0e7bb6ab62 | £4,154.64 | £0.00 | £3,143.39 | £4,154.64 | 0.00% |

Showing 20 of 20 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 20 paths:** 10 wins, 10 losses, 0 ties vs buy-and-hold; beat cash on 8. Median excess -3.14% of capital; mean max drawdown 4.10%; sign-test p = 1.000.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
