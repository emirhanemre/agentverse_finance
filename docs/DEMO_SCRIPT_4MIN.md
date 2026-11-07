# Four-Minute Live Demo Script for Judges

**Total Time:** 4 minutes (plus 2 minutes Q&A)  
**Launch Command:** `streamlit run app.py`

---

## Minute 0:00 – 0:45 | Problem Framing & Dependency Honesty (Header & View A)

1. **Point to the top header and three status badges:**
   - **User & Decision:** Independent UK pub owner in London SE1 (90 indoor seats, 70 outdoor beer garden seats) asking: *"How exposed is my business to the forecast weather, and would any available Polymarket contract meaningfully offset that exposure within my budget?"*
   - **Data Provenance Badge:** Point out that daily London weather (`2022–2025`, 1,461 days) is **REAL** Open-Meteo ERA5 data, while daily pub revenue is **SYNTHETIC** (`seed=20261107`) and prominently labelled so we never claim real-world pub profitability from synthetic sales.
   - **Server Credential Status:** Show the server-side Gemini 4 Argon (`gemini-4-argon`) status badge. Explain that credentials stay strictly on the server via `.env` and never reach the browser.
2. **In Tab `A. Data and Model` (Requirement 1 — Genuinely trained model & held-out results):**
   - Show the chronological 60/20/20 split (`Training: 2022-01-01 to 2024-05-26`, `Validation: 2024-05-27 to 2025-03-14`, `Untouched Test: 2025-03-15 to 2025-12-31`).
   - Show the frozen `hist_gradient_boosting` pipeline beating the weekday historical average baseline on the untouched 2025 test set (**MAE £340.18 vs £1,301.56 baseline, +73.86% improvement; RMSE £455.17 vs £1,634.44**).
   - Point out the **Rainy Days subset ($n=59$, MAE £259.02 vs £700.03 baseline)** and the **10 Largest Prediction Misses table** (honestly showing unlabelled shock days up to £2,152 error and the 69.86% empirical vs 80% nominal prediction interval coverage).

---

## Minute 0:45 – 1:45 | Entering a New Scenario & Model Exposure Estimate (View B)

1. **Switch to Tab `B. Business Assessment` (Requirement 2 & 3 — New scenario & model predictions):**
   - Select **Preset 1: Wet Summer Saturday in London (`2025-07-19`)** and customize the rainfall input (e.g., change rainfall from `14.0 mm` to `16.0 mm`, max temp `16.0°C`, paper budget `£180.00`).
   - Show that the loaded saved model immediately computes:
     - **Forecast / Adverse Scenario Revenue:** ~`£2,175` (with 80% prediction interval).
     - **Seasonal Dry Reference Revenue:** ~`£6,225` (dry July median day: `23.1°C`, `0.0 mm` rain).
     - **Estimated Scenario Downside Exposure:** ~`£4,050` model-based conditional difference, with explicit assumptions displayed.
   - Briefly select **Preset 4 (`95 mm` rain, `41.5°C`)** to show the red **Out-of-Training-Range Weather Alert** triggering automatically when inputs exceed the 2022–2024 training bounds. Switch back to **Preset 1 (`2025-07-19`)** or **Preset 2 (`2025-01-23`)**.

---

## Minute 1:45 – 2:55 | Real Polymarket Data, Tool Activity & Contract Rejection (View C)

1. **Switch to Tab `C. Agent Assessment` (Requirements 4, 5, 6 & 7 — Real Polymarket data, tool trace, rejected unsuitable contracts, defensible decision):**
   - Keep **"Include labelled synthetic test fixtures"** UNCHECKED first so only the **36 authentic Polymarket Gamma/CLOB snapshots** are searched.
   - Select **Preset 2 (`2025-01-23`, mild rainy Thursday in London: `11.5°C`, `12.0 mm` rain, `£150` budget)** and click **Run assessment**.
   - Inspect the **Actual Tool Activity Log**: show `get_business_profile` -> `compare_weather_scenarios` -> `search_markets` -> `get_market_rules` -> `get_order_book` -> `evaluate_hedge` -> `check_risk_limits` -> `save_proposal`.
   - Point to the **Contracts Rejected & Specific Safeguard Triggers** table:
     - Real Polymarket contract `519599` (*"Will the highest temperature in London be 43°F or below on January 23?"*, resolved via Weather Underground at London City Airport `EGLC`) is inspected and **rejected** because **a daily maximum-temperature market is not interchangeable with a rainfall exposure (basis risk)** and is closed for live execution.
     - Real Polymarket active contract `678686` (*"Will 2026 be the hottest year on record?"*, with live CLOB order book asks/bids) is inspected and **rejected** for **geographic mismatch (`Unspecified / Global` vs `London, UK`)** and date mismatch.
   - Highlight the defensible final status: **`no_suitable_hedge`**. We never force a positive hedge recommendation when no suitable contract exists!

---

## Minute 2:55 – 4:00 | Controlled Positive Hedge, Human Approval & Tamper Safeguard (View D)

1. **Enable the top checkbox: `Include labelled synthetic test fixtures ([SYNTHETIC TEST FIXTURE])`:**
   - In Tab B, select **Preset 3: Controlled Simulation — Suitable London Rain Contract (`2025-09-06`, `14.0 mm` rain, `£180` budget)**.
   - In Tab C, click **Run assessment**.
   - Show that the agent finds `[SYNTHETIC TEST FIXTURE] TEST_FIX_LONDON_RAIN_2025_09_06`, walks the CLOB ask book (`600` shares @ `$0.32` + `106` shares @ `$0.35`, plus `50 bps` fee at `1.2800 USD/GBP`), verifies all 10 risk checks pass, and saves a proposal with status **`recommend_paper_hedge`** and `approval_state = pending_human_approval`.
2. **Switch to Tab `D. Approval and Results` (Requirement 8 — Human paper approval & controls):**
   - Show the **3-Scenario Combined Outcome Comparison Table**:
     1. *Adverse weather + contract pays:* `706` shares pay `$706.00 USD` (`£551.56 GBP`), yielding **+£371.68 net hedge profit** after the `£179.88` entry cost and reducing remaining pub downside from `£3,697.39` to `£3,325.71`.
     2. *Adverse weather + contract fails (basis risk):* combined outcome worsens by `-£179.88`.
     3. *Benign weather + contract expires:* pub earns full reference revenue minus the `£179.88` hedge cost.
   - First click **"Test Safeguard: Attempt Tampered Quantity Approval"** — show the red banner blocking the approval because the recomputed SHA-256 `proposal_hash` rejects the modified quantity (`+25` shares) and logs `modified_proposal_approval_blocked` in the SQLite Audit Log!
   - Next click **"Approve & Record Simulated Paper Position"** — show the simulated paper position recorded in SQLite (`paper_positions`), and click it a second time to show `duplicate_approval_blocked` preventing double execution!
