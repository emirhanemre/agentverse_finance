# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 57 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `1f050866366bc47cfd708f577433e286c3cc75e6c5f0a982cf5a37a10db45d36`
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
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| a97b86aee3df73553a9f | £9,967.45 | £166.74 | £11,364.73 | £9,800.71 | 5.49% |
| d3111d65a5db586b1f17 | £5,871.02 | £65.46 | £4,921.80 | £5,805.56 | 4.12% |
| 35152e57ee865e9bc651 | £9,340.23 | £529.49 | £11,331.74 | £8,810.74 | 12.63% |
| 0908388f85b59aefd0ad | £7,037.19 | -£209.66 | £7,318.92 | £7,246.85 | 6.40% |
| 11cac40f1f5805099a4b | £1,522.34 | £2.34 | £1,349.18 | £1,520.00 | 2.69% |
| 10d8edde2ed6d5ec4f79 | £5,195.02 | -£123.32 | £4,542.78 | £5,318.34 | 4.89% |
| 5e45d95c189d788d788c | £3,629.45 | £113.82 | £3,730.46 | £3,515.63 | 5.56% |
| ef9299409d1b7908d6d0 | £8,315.33 | £128.94 | £8,744.11 | £8,186.39 | 11.51% |
| 29466bb9747abc5e2980 | £1,232.94 | -£63.70 | £1,306.22 | £1,296.64 | 6.53% |
| efd2e2de798e8fd3fada | £1,453.61 | -£12.09 | £1,415.56 | £1,465.70 | 2.30% |
| cea6230a4ec00c1d6b4e | £2,054.95 | £0.00 | £1,835.72 | £2,054.95 | 0.00% |
| 0520c9f50db5dc9958e3 | £5,938.60 | £0.00 | £5,647.71 | £5,938.60 | 0.00% |
| a4372b712c20479192b6 | £7,624.37 | £0.00 | £7,413.99 | £7,624.37 | 0.00% |
| e4986f9ae0cb636a33cb | £7,523.34 | -£186.38 | £7,643.70 | £7,709.72 | 3.82% |
| 7be8fb5b2295ab39145a | £7,961.82 | -£1.16 | £8,726.22 | £7,962.98 | 12.23% |
| d6a5ce8b7f2f9aad83ae | £4,234.17 | £367.00 | £4,384.65 | £3,867.17 | 2.36% |
| a43ba4938abe09fe42e1 | £2,761.77 | £0.00 | £2,496.29 | £2,761.77 | 0.00% |
| 8c7bcb9e227b0aaff61d | £5,179.74 | £403.17 | £5,575.53 | £4,776.57 | 5.75% |
| a3edeb14a6f44746eb45 | £1,464.76 | -£64.50 | £1,468.68 | £1,529.26 | 6.40% |
| d1ef07104aa8b0c63013 | £8,526.35 | £145.33 | £9,028.80 | £8,381.02 | 7.80% |
| fa68c0054f8a4544bb9b | £3,245.16 | £89.15 | £3,060.75 | £3,156.01 | 2.07% |
| be2d5180443565f350c9 | £6,953.25 | -£1,556.11 | £6,912.02 | £8,509.36 | 18.46% |
| d1ec8a42b5a670e714e7 | £4,001.33 | £5.47 | £3,605.14 | £3,995.86 | 10.38% |
| 77fd732c080984b54967 | £9,230.16 | £671.08 | £9,626.28 | £8,559.08 | 16.38% |
| 2d01573bce04ccb643cc | £5,954.60 | £0.00 | £5,679.88 | £5,954.60 | 0.00% |
| 4de2d87fd159bdfa4fd7 | £7,687.42 | £0.00 | £6,660.68 | £7,687.42 | 0.00% |
| c71a41830d35d7a1b16b | £1,587.27 | -£212.95 | £1,758.68 | £1,800.22 | 15.49% |
| 703e5c49bde760c57431 | £9,226.52 | -£589.63 | £8,484.79 | £9,816.15 | 10.07% |
| 5a33f465e3827a4c8e2d | £9,052.99 | £98.06 | £9,141.96 | £8,954.93 | 5.06% |
| c1c232230d2eb4e940bf | £8,702.83 | £100.44 | £8,998.09 | £8,602.39 | 10.17% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 23 wins, 37 losses, 0 ties vs buy-and-hold; beat cash on 25. Median excess -0.90% of capital; mean max drawdown 7.04%; sign-test p = 0.092.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
