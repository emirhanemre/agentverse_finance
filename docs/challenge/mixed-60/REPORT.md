# Finance project test report

**CHALLENGE (self-serve): hidden mixed cases**

Dataset: 60 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **40 passed, 0 failed, 0 execution errors**.
Market simulations completed: **20**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `84745cdd2f30473498d066ab907557bfd1710df29bb6b9d243de195c3d470540`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `53991bb152b44ecda2eb4b1b047b20643b81c93b`, uncommitted changes: 0
- Provenance review: **3 item(s) need a human look:**
  - `scripts/check.sh`: imports the kit's reference code; the adapter must call the team's own implementation
  - `scripts/gen_sizing_task.py`: imports the kit's reference code; the adapter must call the team's own implementation
  - `scripts/gen_sizing_task.py`: references answer keys or seed files

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
| 1bd5e8e722a570152ac7 | £4,567.98 | £599.24 | £4,996.95 | £3,968.74 | 0.51% |
| f1028727b774756b0676 | £1,742.66 | £0.00 | £1,352.46 | £1,742.66 | 0.00% |
| 9f58fe657e00da55a45a | £6,905.12 | £0.00 | £6,893.98 | £6,905.12 | 0.00% |
| 809989b986cd8d46a862 | £7,101.08 | £0.00 | £8,643.10 | £7,101.08 | 0.00% |
| bd0dd9b83fa00374bd80 | £1,149.26 | £26.78 | £1,158.56 | £1,122.48 | 10.66% |
| 7a728d1f0c27d703b662 | £3,853.33 | -£5.25 | £5,110.58 | £3,858.58 | 1.09% |
| f4b2a286287889a8dc40 | £8,781.37 | £107.46 | £10,003.60 | £8,673.91 | 0.22% |
| fe72dcc2f7816fba0678 | £7,592.87 | £0.00 | £5,745.56 | £7,592.87 | 0.00% |
| 14bb76aad18707630198 | £5,933.13 | £0.00 | £5,892.63 | £5,933.13 | 0.00% |
| f43b9e04b5730f141287 | £5,687.63 | -£2,845.89 | £7,620.34 | £8,533.52 | 36.69% |
| 261a08d096201d6d5049 | £3,568.67 | £0.00 | £3,486.52 | £3,568.67 | 0.00% |
| 061c7c62f3c49d798da4 | £9,985.74 | £53.26 | £6,984.56 | £9,932.48 | 0.09% |
| 6d4a2e25dcae5ef49335 | £5,876.11 | £1,339.03 | £7,033.00 | £4,537.08 | 0.33% |
| e4b2ef7da5ef18db993f | £2,391.73 | £0.00 | £1,638.46 | £2,391.73 | 0.00% |
| 23f2cbf42ef6ef863077 | £3,704.10 | £0.00 | £3,673.88 | £3,704.10 | 0.00% |
| b97dde3d418e9fe41c4e | £4,132.02 | -£24.16 | £5,345.91 | £4,156.18 | 33.46% |
| 0291e7fd46dd7dadc43d | £2,623.09 | -£310.85 | £2,852.23 | £2,933.94 | 10.70% |
| d2512e5c80c187127594 | £3,296.74 | £0.00 | £2,320.26 | £3,296.74 | 0.00% |
| 13a76369d19e07f317ac | £1,044.03 | £34.52 | £1,164.64 | £1,009.51 | 0.53% |
| 57db7817903886babbdc | £8,431.41 | £0.00 | £7,561.51 | £8,431.41 | 0.00% |

Showing 20 of 20 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 20 paths:** 10 wins, 10 losses, 0 ties vs buy-and-hold; beat cash on 6. Median excess -0.34% of capital; mean max drawdown 4.71%; sign-test p = 1.000.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
