# Factual Pitch Evidence (Agentverse 2026 — Finance Track)

> **No Branding / Honest Reporting Note:** All metrics below are produced directly from `python3 -m src.training` (`artifacts/models/evaluation_report.json`) and `python3 -m src.agent_eval` (`artifacts/models/agent_evaluation_report.json`). All trades are simulated paper positions.

---

## 1. Specific User and Decision Problem

- **User:** An independent UK pub owner in London (SE1) with **90 indoor seats** and **60–70 outdoor beer garden seats**.
- **Operational Problem:** Warm, dry spring/summer weekends fill the outdoor beer garden, whereas heavy rainfall or cold snaps sharply depress outdoor seating utilisation and casual walk-in footfall while fixed staffing and stock costs remain committed.
- **Decision Question:** *"How exposed is my business to the forecast weather on a specific operating date, and would any available Polymarket contract meaningfully offset that exposure within my budget?"*

---

## 2. Data Sources & Provenance

| Component | Origin | Classification | Coverage & Details |
| :--- | :--- | :--- | :--- |
| **Daily London Weather** | Open-Meteo Historical Weather API (ERA5 / ECMWF reanalysis, `51.5074°N, -0.1278°E`) | **REAL DATA** (CC-BY 4.0) | `2022-01-01` to `2025-12-31` (1,461 daily observations; max/min/mean temp °C, precipitation/rain mm, max wind km/h, sunshine hours). |
| **Daily Pub Sales & Capacity** | `src/business_data.py` (`seed=20261107`) | **SYNTHETIC DATA** | 1,461 days of synthetic GBP revenue (`daily_revenue_gbp`), indoor/outdoor seat capacities, opening hours, UK Bank Holidays, and local event flags. Demonstrates pipeline methodology under documented synthetic assumptions; **not** real pub financial records. |
| **Prediction Markets & Order Books** | Polymarket Public Gamma API (`/events`, `/markets`) & CLOB API (`/book`, `/prices-history`) | **REAL PUBLIC DATA** (Cached Authentic Snapshots + Optional Live Refresh) | 36 authentic snapshots (`data/polymarket_cache/authentic_polymarket_snapshots.json`) retrieved `2026-11-07T19:16Z`, including active 2026 climate/hurricane contracts with Level-2 CLOB order books and historical closed Jan 2025 London City Airport (`EGLC`) daily maximum-temperature contracts (`519338`–`519601`). |
| **Controlled Test Fixtures** | `src/agent_eval.py` (`TEST_FIX_*`) | **SYNTHETIC TEST FIXTURES** (Restricted to labelled evaluation/testing) | 6 explicitly labelled test contracts used to test positive paper-hedge sizing, wrong geography, wrong date, thin book, excessive price, and prompt injection. |

---

## 3. Training & Evaluation Methodology

- **Chronological Split (1,461 days, zero lookahead):**
  - **Training (`60.03%`):** `2022-01-01` to `2024-05-26` ($n = 877$ days). Used exclusively to fit `ColumnTransformer` preprocessing (`SimpleImputer`, `OneHotEncoder`, `StandardScaler`), training-set weekday means, and weather range bounds.
  - **Validation (`19.99%`):** `2024-05-27` to `2025-03-14` ($n = 292$ days). Used to select model family, hyperparameters, and calibrate the 80% empirical residual prediction interval (`[-£315.68, +£453.59]`).
  - **Untouched Test (`19.99%`):** `2025-03-15` to `2025-12-31` ($n = 292$ days). Evaluated once after freezing the selected model (`hist_gradient_boosting`, version `1.0.0-20261107`).
- **Temporal Causality:** Lagged revenue features (`lag_7d_revenue_gbp` at $t-7$ and `rolling_14d_mean_revenue_gbp` over $[t-14, t-1]$) use strictly past observations verified by unit test (`test_strict_temporal_causality_no_lookahead`).
- **Conditional Forecast Framing:** Retrospective test evaluation uses realised historical weather from Open-Meteo and is explicitly labelled as **conditional revenue prediction**, distinct from operational weather-forecast uncertainty.

---

## 4. Baseline Comparisons (Revenue Model & Agent Strategies)

### A. Revenue Regression Models on Untouched Test Split (`2025-03-15` to `2025-12-31`, $n = 292$)

| Model | Validation MAE (£) | Validation RMSE (£) | Test MAE (£) | Test RMSE (£) | Test Median AE (£) | Test MAE Improvement vs Baseline |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `weekday_mean_baseline` | £1,063.12 | £1,301.50 | **£1,301.56** | **£1,634.44** | £1,011.24 | £0.00 (0.00%) |
| `ridge_linear_regression` ($\alpha=50.0$) | £362.37 | £474.41 | **£479.41** | **£626.93** | £355.07 | +£822.14 (+63.17%) |
| `hist_gradient_boosting` *(Selected & Frozen)* | **£244.46** | **£308.87** | **£340.18** | **£455.17** | **£264.74** | **+£961.37 (+73.86%)** |

### B. Held-Out Decision Strategy Evaluation ($n = 12$ Held-Out Cases)

| Strategy | Correct Rejections (out of 10 unsuitable/invalid cases) | Valid Controlled Hedges Recommended (out of 2) | False-Positive / Unsuitable Recommendations | Budget or Approval Violations |
| :--- | ---: | ---: | ---: | ---: |
| **1. No Hedge Baseline** | 10 / 10 | 0 / 2 (absorbs full £3,697.39 scenario downside) | 0 | 0 |
| **2. Deterministic Contract-Matching Comparator** | **10 / 10** | **2 / 2** (reduces remaining scenario downside by £371.68 net of £180 cost & 50 bps fee) | **0** | **0** |
| **3. Gemini 4 Argon (`gemini-4-argon`) Agent** | Verified 100% guard compliance in tool-loop test (`test_gemini_agent_tool_calling_and_code_guard`); live server status is honestly marked `BLOCKED_MISSING_SERVER_CREDENTIALS` until `GEMINI_API_KEY` is placed in `.env`. | — | **0** | **0** |

---

## 5. Results, Subsets, and Honest Failure Modes

1. **Subset Performance on Untouched Test Split (`hist_gradient_boosting`):**
   - **Rainy days ($\text{rain} \ge 2\text{mm}$, $n = 59$):** Model MAE **£259.02** vs Baseline MAE **£700.03** (+63.00% improvement).
   - **Heavy rain days ($\text{rain} \ge 8\text{mm}$, $n = 17$):** Model MAE **£363.43** vs Baseline MAE **£1,035.30** (+64.90% improvement).
   - **Dry warm days ($\text{temp} \ge 18^\circ\text{C}, \text{rain} < 1\text{mm}$, $n = 104$):** Model MAE **£408.92** vs Baseline MAE **£2,313.66** (+82.33% improvement).
   - **UK Bank Holidays ($n = 7$):** Model MAE **£532.44** vs Baseline MAE **£1,815.09** (+70.67% improvement).
2. **Where the Revenue Model Fails:**
   - **Unlabelled Exceptional Shocks:** On `2025-08-01` (Friday, actual £8,122.80 vs predicted £5,970.30, error **+£2,152.50**) and `2025-08-26` (error **+£1,802.72**), unscheduled private hires / local shock events cause large under-predictions that weather features cannot anticipate.
   - **Prediction Interval Under-Coverage on Test Set:** The 80% empirical residual interval calibrated on Validation (`2024-05-27` to `2025-03-14`, mostly autumn/winter) achieved **69.86% empirical coverage** on the untouched Test set (`2025-03-15` to `2025-12-31`, which contains higher-variance summer weekends and ~3.5%/yr upward revenue drift). We report this 69.86% figure directly without post-hoc tuning on the test set.
3. **Where Polymarket Hedging Fails in Practice (Market Availability & Basis Risk):**
   - **No Live London Rainfall Market Exists Today:** Searching the live Polymarket Gamma catalog shows active climate/weather markets for *global annual temperature* (`678686`) and *US landfalling hurricanes* (`1058988`), but zero active contracts for daily London rainfall. The system therefore returns **`no_suitable_hedge`** for live dates rather than forcing a bad trade.
   - **Daily Max Temperature $\ne$ Rainfall Exposure:** Polymarket's historical London weather markets (`519338`–`519601`, Jan 22–26, 2025 at London City Airport `EGLC`) settle on **daily maximum temperature in °F**, not rainfall. When tested on a mild rainy day (`2025-01-23`, 12mm rain, 11.5°C), the risk engine rejects the London temperature contract because temperature contracts do not pay out during mild wet weather (severe basis risk).

---

## 6. Agent Limitations & Deterministic Risk Controls

All numerical calculations and compliance checks execute in deterministic Python (`src/financial_calc.py`, `src/risk_controls.py`, `src/paper_execution.py`):
- **Decimal & Minor-Unit Arithmetic:** Entry costs walk the CLOB ask ladder using `Decimal` (`ROUND_HALF_UP`), applying explicit 50 bps fees and a documented `1.2800 USD/GBP` exchange rate. Midpoints and historical price series are never treated as executable depth.
- **10 Hard Risk Controls in Code:** Blocks closed/inactive markets, non-London geography, mismatched dates, mismatched weather metrics (`daily_max_temperature` vs `rainfall`), stale quotes, thin order books ($<20$ shares), unattractive ask prices ($>\$0.72$), per-contract budget breaches ($>£500$), and untrusted external prompt injections.
- **Cryptographic Human Approval Binding:** Every proposal generates a SHA-256 `proposal_hash` over `(proposal_id, market_id, outcome, paper_quantity, max_total_cost_pence, quote_timestamp)`. SQLite blocks duplicate approvals, modified quantities, and stale quotes.
