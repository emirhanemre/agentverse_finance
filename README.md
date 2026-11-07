# UK Pub Weather Exposure & Polymarket Paper Hedge Assessment

A working Python machine-learning and decision-agent web application built for the **Agentverse 2026 Finance Track**.

It helps an **independent UK pub owner with outdoor beer garden seating (London SE1)** answer a specific financial risk question:

> *"How exposed is my business to the forecast weather, and would any available Polymarket contract meaningfully offset that exposure within my budget?"*

---

## Prominent Disclosures (Data Provenance & Paper Trading)

1. **Synthetic Business Revenue Data:** Daily pub revenue (`daily_revenue_gbp`), seating capacity schedules, opening hours, and event indicators are synthetically generated (`src/business_data.py`, `seed=20261107`). They are paired with **real historical daily London weather observations** (`2022-01-01` to `2025-12-31`, 1,461 days) from the Open-Meteo ERA5 archive (`data/raw/london_weather_real_2022_2025.csv`, CC-BY 4.0). Model metrics demonstrate pipeline performance under stated synthetic assumptions and **never imply predictive accuracy for real pubs**.
2. **Real Polymarket Public Data:** Market discovery and order-book inspection use Polymarket's public read-only Gamma (`https://gamma-api.polymarket.com`) and CLOB (`https://clob.polymarket.com`) endpoints, with 36 authentic timestamped snapshots cached in `data/polymarket_cache/authentic_polymarket_snapshots.json` for reproducible offline demonstration.
3. **Human-Approved Paper Trading Only:** All positions are simulated paper records stored in local SQLite (`data/runtime/app_state.db`). No wallet keys are requested, no blockchain transactions are signed, and no real orders are ever submitted.
4. **Never Promises Universal Protection:** On live Polymarket data today, no active London daily rainfall contract exists; the system honestly returns `no_suitable_hedge` after inspecting and rejecting unsuitable contracts (such as global temperature or historical London daily max-temperature contracts that carry basis risk against rainfall).

---

## Quick Start (Beginner-Friendly Local Launch)

### 1. Install Dependencies

From the project root (`/Users/lukecamilleri/Desktop/agentverse_finance`), run:

```bash
pip3 install -r requirements.txt
```

### 2. Optional: Configure Server-Side Gemini 4 Argon Credentials (`.env`)

Never paste API keys into chat or commit them to Git. `.env` is ignored by `.gitignore`.
If you have an event-provided `GEMINI_API_KEY` for standalone Python server calls to `gemini-4-argon`:

```bash
cp .env.example .env
```

Then open `.env` in your local text editor (outside chat) and set `GEMINI_API_KEY=<your-key-here>`.
*(If `.env` has no key configured, the web app clearly marks Live Gemini Server Integration as `BLOCKED` and lets you run the clearly labelled **Deterministic Contract-Matching Comparator** across the exact same 10 tools without faking a Gemini response.)*

### 3. Re-Run Dataset Generation, Model Training & Held-Out Agent Evaluation (Optional — Artifacts Already Saved)

```bash
python3 -m src.business_data
python3 -m src.training
python3 -m src.agent_eval
```

### 4. Run the Automated Test Suite (`pytest`)

```bash
python3 -m pytest -v
```

### 5. Launch the Browser Application (`Streamlit`)

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit (typically `http://localhost:8501`) in your browser.

---

## Repository Structure

```text
agentverse_finance/
├── app.py                                      # Streamlit browser interface (Views A, B, C, D)
├── requirements.txt                            # Pinned compatible Python dependencies
├── .env.example                                # Safe empty placeholders for server credentials
├── .gitignore                                  # Excludes .env, private keys, and runtime SQLite DBs
├── src/
│   ├── schemas.py                              # Pydantic v2 input/output schemas & secret redaction
│   ├── weather_data.py                         # Real Open-Meteo London weather loader & range checks
│   ├── business_data.py                        # Reproducible synthetic pub sales generator (seed=20261107)
│   ├── features.py                             # Strictly causal feature engineering & WeekdayMeanBaseline
│   ├── training.py                             # Chronological 60/20/20 split, model selection & saving
│   ├── evaluation.py                           # MAE/RMSE, subset analysis & 80% residual intervals
│   ├── inference.py                            # Saved-model loader & scenario exposure comparator
│   ├── polymarket_client.py                    # Public Gamma/CLOB connector, snapshot cache & injection scan
│   ├── financial_calc.py                       # Decimal ask-ladder walking, bps fees, FX & scenario P&L
│   ├── risk_controls.py                        # 10 deterministic risk & suitability checks enforced in code
│   ├── paper_execution.py                      # SQLite persistence & SHA-256 human approval binding
│   ├── agent.py                                # Gemini 4 Argon tool-calling agent & deterministic comparator
│   └── agent_eval.py                           # 12 held-out evaluation cases & comparator benchmark
├── scripts/
│   └── fetch_external_data.py                  # Script used to fetch real Polymarket & Open-Meteo data
├── data/
│   ├── raw/
│   │   ├── london_weather_real_2022_2025.csv   # Real daily London weather (1,461 days, Open-Meteo ERA5)
│   │   └── london_weather_provenance.json      # Weather source metadata, coordinates, and CC-BY 4.0 licence
│   ├── processed/
│   │   ├── uk_pub_daily_dataset.csv            # Combined weather + synthetic pub revenue dataset
│   │   └── dataset_provenance_and_assumptions.json
│   └── polymarket_cache/
│       └── authentic_polymarket_snapshots.json # 36 authentic Polymarket Gamma + CLOB snapshots
├── artifacts/
│   └── models/
│       ├── fitted_pipeline.joblib              # Saved frozen scikit-learn model bundle
│       ├── feature_schema.json                 # Validated model feature schema
│       ├── training_config.json                # Split dates, hyperparameter search & SHA-256 fingerprints
│       ├── evaluation_report.json              # Full validation/test/subset metrics & worst misses
│       ├── test_set_predictions.csv            # Out-of-sample test predictions (2025-03-15 to 2025-12-31)
│       └── agent_evaluation_report.json        # Held-out agent evaluation results across 12 cases
├── docs/
│   ├── MODEL_EVALUATION.md                     # Detailed revenue model evaluation report
│   ├── AGENT_EVALUATION.md                     # Held-out agent & risk control evaluation report
│   ├── PITCH_EVIDENCE.md                       # Factual pitch deck evidence & failure analysis
│   ├── DEMO_SCRIPT_4MIN.md                     # Four-minute step-by-step judge demo script
│   └── SECRET_SCAN_REPORT.md                   # Secret scan verification report
└── tests/
    └── test_suite.py                           # 15 pytest tests covering all Section 16 requirements
```
