# Secret Scan & Credential Protection Report

**Scanner:** Official Gitleaks `v8.30.1` + Agentverse Read-Only Preflight Scanner (`preflight.py`)  
**Repository:** `/Users/lukecamilleri/Desktop/agentverse_finance`  
**HEAD Commit Scanned:** `99ec6136164b64c100d6a665867c05c950b554ee`

---

## 1. Credential Protection Controls Established

1. **`.gitignore` Coverage Verified (`git check-ignore -v`):**
   - Local environment files: `.env`, `.env.*` (while allowing sanitized `.env.example`).
   - Private keys & credential files: `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials.json`, `service-account.json`, `secrets.json`, `secrets.yaml`.
   - Runtime SQLite databases: `data/runtime/*.db`, `data/runtime/*.sqlite`, `data/runtime/*.sqlite3`.
   - Python bytecode & caches: `__pycache__/`, `.pytest_cache/`, `.venv/`, `venv/`.
2. **`.env.example` Sanitization:**
   - Contains only empty placeholders (`GEMINI_API_KEY=`, `GEMINI_MODEL=gemini-4-argon`).
3. **Deterministic Redaction in Code (`src/schemas.py`):**
   - `redact_sensitive_text()` strips Google API keys (`AIza...`), bearer tokens, secret assignments, and URL query keys before logging or UI display, verified by `test_dummy_secret_redaction_never_exposes_value`.

---

## 2. Gitleaks `v8.30.1` Scan Summary Across All Scopes

| Scope | Candidate Entries | Scanner Status | Secret Findings | Incomplete Entries |
| :--- | ---: | :--- | ---: | ---: |
| **Git Index (Staged)** | 1 | `completed` | **0** | 0 |
| **Working Tree (Tracked & Unignored)** | 38 | `completed` | **0** | 0 |
| **Git Commit History (`--full-history`)** | All commits | `completed` | **0** | 0 |
| **Historical Git Blobs** | 1 | `completed` | **0** | 0 |

- **`findings_count`:** `0`
- **`incomplete_count`:** `0`
- **`setup_needed_count`:** `0`

---

## 3. Separate Inspection of Binary Model Artifact (`needs_review` Resolution)

Because `artifacts/models/fitted_pipeline.joblib` is a binary scikit-learn pipeline bundle (`408,273` bytes), Gitleaks flags it under `needs_review` for separate content inspection. We inspected the exact bytes via `python3 -m scripts.verify_project_and_secrets`:

- **File:** `artifacts/models/fitted_pipeline.joblib`
- **SHA-256:** `b38d3076b5db3fcb4e122180c8e71ba7fc6762a48d100027c2465177d8014e12`
- **Method:** Deserialized bundle via `joblib.load` (`scripts/verify_project_and_secrets.py`), verified top-level dictionary keys and estimator classes (`WeekdayMeanBaseline`, `Ridge`, `HistGradientBoostingRegressor`), and scanned all serialized metadata strings against `_SECRET_PATTERNS`.
- **Evidence:** `Top-level keys=['all_fitted_models', 'dataset_sha256', 'feature_schema', 'model_version', 'monthly_reference_weather', 'prediction_interval_80', 'selected_model_name', 'selected_pipeline', 'train_weekday_means', 'trained_at_utc', 'training_weather_bounds']; estimator=Pipeline; secret_regex_matches=0`
- **Result:** **CLEAN** (Contains only fitted scikit-learn numerical arrays, feature schema, and training summary statistics; zero credentials or private records).
