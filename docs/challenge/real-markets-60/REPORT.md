# Finance project test report

**CHALLENGE (self-serve): hidden real-markets cases**

Dataset: 60 cases; seed: None; source: Price returns derived from Binance Vision public data (CC BY-NC-SA 4.0). Not endorsed by Binance. Months drawn: 57 (hidden until reveal)..

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `ee74742a05597eb6c3240ace657e9912227d00b36a799eb200f3cfc7620f18df`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `b951e24316d7fa84e6e6dc9c51bb9d26c2cc60e5`, uncommitted changes: 6
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / real_anonymised | 0 | 0 | 0 | 60 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| cc37ee118494cbb516a6 | £6,830.84 | -£793.93 | £6,966.49 | £7,624.77 | 12.34% |
| d25085c81e722a22d092 | £8,863.12 | -£957.26 | £8,520.36 | £9,820.38 | 13.59% |
| df99ca752ff40e296a7e | £2,448.17 | £41.88 | £2,370.05 | £2,406.29 | 3.31% |
| 27f133597a8bfa5485e0 | £9,456.79 | £772.65 | £10,476.00 | £8,684.14 | 10.18% |
| 227cd2d7f9d16e615dcb | £4,450.35 | £158.02 | £4,573.37 | £4,292.33 | 5.82% |
| 0fb98b19179a205397b2 | £2,443.36 | -£163.30 | £2,304.81 | £2,606.66 | 7.77% |
| 5337d173c3a3e9f9e4f4 | £9,211.19 | £178.86 | £9,369.21 | £9,032.33 | 1.57% |
| afa0f1374b19b597f08f | £4,296.57 | £0.00 | £4,308.13 | £4,296.57 | 0.00% |
| 6bd49294c9f9676bef89 | £2,999.33 | £0.00 | £2,629.03 | £2,999.33 | 0.00% |
| 642644a53bd78c1904e9 | £7,850.96 | £1,210.33 | £6,127.67 | £6,640.63 | 13.71% |
| 0624f14ea31df3c32331 | £6,751.99 | -£513.46 | £6,414.19 | £7,265.45 | 13.37% |
| 7e439f7b1ec56ea6d25a | £2,604.05 | -£147.53 | £2,704.32 | £2,751.58 | 6.70% |
| 61b22b58575fa563a103 | £7,097.22 | £0.00 | £5,577.54 | £7,097.22 | 0.00% |
| 2271ad38b2f07f2620e7 | £2,192.60 | -£116.52 | £2,185.64 | £2,309.12 | 6.71% |
| f6a4d890c6d744e85893 | £3,382.90 | £0.00 | £3,333.96 | £3,382.90 | 0.00% |
| 38f3558c59d67f627955 | £6,967.10 | -£743.18 | £7,336.88 | £7,710.28 | 10.59% |
| cbdc10fb0e17c776d7ca | £6,255.40 | -£821.64 | £5,728.46 | £7,077.04 | 15.04% |
| 684f461ec438df00af01 | £1,974.34 | -£13.24 | £2,237.02 | £1,987.58 | 4.30% |
| 176e61a66ce8523e81a7 | £974.80 | -£31.84 | £787.90 | £1,006.64 | 6.80% |
| 7fec3289c268e83c3505 | £5,634.83 | £47.16 | £5,877.46 | £5,587.67 | 5.20% |
| 98b06f668be0deca0911 | £4,371.27 | £130.71 | £3,802.72 | £4,240.56 | 5.87% |
| 6e97be8227f44e843bd3 | £7,913.08 | -£248.69 | £8,229.62 | £8,161.77 | 3.97% |
| 048b27bfa30002c991db | £6,951.41 | £0.00 | £6,893.85 | £6,951.41 | 0.00% |
| e76aa0337280dafd38b4 | £4,212.76 | -£194.34 | £4,469.23 | £4,407.10 | 5.85% |
| 0703446a97502d7d13b0 | £9,372.65 | -£251.18 | £9,205.51 | £9,623.83 | 3.71% |
| 91f44ef43e4846f195bd | £7,666.30 | -£510.46 | £9,167.46 | £8,176.76 | 10.13% |
| 21d5994f5cb14adf70ba | £3,357.32 | £106.16 | £3,379.10 | £3,251.16 | 4.30% |
| f5fa25c7ec8588203ed4 | £7,767.57 | £504.37 | £7,576.82 | £7,263.20 | 3.41% |
| ec2327572c73f4e86b61 | £7,497.51 | £179.68 | £8,149.57 | £7,317.83 | 11.11% |
| 5629765aa0c0e8479446 | £2,001.25 | £0.00 | £1,973.58 | £2,001.25 | 0.00% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 30 wins, 30 losses, 0 ties vs buy-and-hold; beat cash on 20. Median excess 0.01% of capital; mean max drawdown 6.55%; sign-test p = 1.000.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
