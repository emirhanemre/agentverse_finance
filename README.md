# Pub Hedge — local weather paper trading

Nick’s Next.js interface, connected to the reusable Python weather model and paper-trading services on `luke-dev`.

Business setup → sample sales or CSV import → train/evaluate imported sales → weather scenario / current forecast → conditional revenue analysis → market suitability → recommendation or explained rejection → human decision → persisted paper position → dashboard. You can complete setup without a hedge.

## Install and launch

Use Python 3.10–3.12 and Node.js 22 LTS. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix app ci
cp -n .env.example .env
python3 scripts/start.py
```

Open **http://localhost:3000**. API documentation: **http://127.0.0.1:8000/docs**. Ctrl-C stops both services. No credentials are required for the primary application. Fonts are self-hosted, using the exact IBM Plex files and fallback metrics from Nick’s current application; builds do not need Google Fonts access.

Run the launcher once, in one terminal. If either port is occupied, it reports the conflict before starting any new services. An already running app can be opened at the address above; stop its original launcher with Ctrl-C before restarting. The ready URLs are printed only after both services respond successfully.

For a production build running locally:

```bash
npm --prefix app run build
python3 scripts/start.py --production
```

Keep the services bound to loopback. This is a single-operator local application, not an authenticated multi-user deployment. Run one API process; interrupted analysis jobs become failed on restart and can be retried.

## First journey

1. Enter your business details and weather coordinates, or explicitly choose **Use sample business**. Review the self-reported details. A Companies House visual connection demo is available; actual company, licensing and identity checks are unavailable.
2. Select **Use synthetic sample sales**, or import a CSV in the existing data-source panel. Toast, Monzo and Xero have explicit demo connection animations. These do not access accounts or import records. For an import, use at least 180 daily records and click **Train and evaluate sales model**; inspect the chronological holdout report before analysis.
3. Choose a target date and an explicit manual weather scenario, or retrieve a current Open-Meteo forecast. Choose live discovery, cached inspection, or a labelled synthetic test market.
4. Run analysis. Progress reflects saved backend task events. Review the conditional revenue comparison, assumptions and candidate rejection reasons.
5. For a controlled approval example choose **Synthetic test · suitable contract**, with 14mm daily rain and a £100 budget. The fictional contract pays at ≥10mm at a fictional business-site gauge. Select it, acknowledge the paper risk and approve. For a no-hedge example choose **Synthetic test · no suitable hedge**, which deliberately uses a mismatched location.
6. Complete setup and open the dashboard. Profiles, sales, runs, decisions, settings, positions and activity survive reloads and service restarts. Test positions remain visibly labelled synthetic and unresolved.

Nick’s original demonstration is available at **/replay** and **/replay/setup**, behind an explicit fictional-replay label. It has no access to current API records. Its fictional timeline, provider connections and payouts are not evidence of real integrations.

## Sales CSV

The exact columns are `date,revenue_gbp,currency`:

```csv
date,revenue_gbp,currency
2026-10-01,1200.00,GBP
2026-10-02,1600.50,GBP
```

Use real ISO calendar dates, no future sales, one row per day, GBP only, finite nonnegative amounts with at most two decimals. Maximum 10,000 rows and 2 MB. Invalid imports explain the row/column issue and preserve the previously selected dataset. The frontend includes a downloadable template. Records are user-supplied and their authenticity is unverified.

Imports supply sales totals and monthly history immediately. **Train and evaluate sales model** joins sales to Open-Meteo historical weather at your saved coordinates. The oldest 60% fits two candidate models; the next 20% selects by MAE; the newest 20% evaluates the selected model once. Activation requires at least 180 matched days and ≥5% lower holdout MAE than a training-only weekday baseline. Missing days are excluded, not filled with zero sales. Failed evaluations remain visible and do not activate a model. Changing sales or business details requires new training. This is internal evaluation on unverified records, not proof of weather causality or external validation. A downloadable four-year **synthetic training sample** is provided for testing. Uploading it does not make it real business data.

## Evidence, assumptions and supported scope

- **Revenue model:** accepted per-business Ridge or histogram gradient boosting models are stored with their evaluation and weather provenance. Automatic analysis uses the accepted model for the exact current profile/data fingerprint; imports without one receive an actionable training requirement. The explicit synthetic demo option retains the original London-only fitted pipeline (`artifacts/models/fitted_pipeline.joblib`, scikit-learn 1.6.0). Its training revenue is synthetic. Both approaches produce conditional comparisons, not proven causal losses. Model version, validation-derived intervals and out-of-range assumptions are shown. Calendar extrapolation remains uncertain.
- **Business records:** synthetic sample sales and user imports have different, visible provenance. Neither is presented as verified private financial data.
- **Weather:** current [Open-Meteo forecasts](https://open-meteo.com/en/docs) include coordinates, source, retrieval time, units, timezone and horizon. Failed retrieval returns an explicitly labelled cache for the same coordinates, or unavailable. A stale cache is never silently treated as current. Manual scenarios are assumptions. Historical observations remain in `data/raw` with provenance records.
- **Markets:** bounded public Gamma weather searches target the configured location, with dated-list fallback. Search is not exhaustive. Eligible contracts require a fresh CLOB order book when assessed; caches are inspection-only. Approval records a simulated fill at the exact reviewed assessment quote, without another exchange request or live repricing. Subsequent market changes do not block the demo. Proposal expiry, exact quantity/cost binding and current portfolio limits still apply.
- **Supported live contracts:** explicit binary Yes/No daily maximum-temperature brackets, or daily rainfall ≥N mm, at EGLC, EGLL, EGCC, EGBB, EGPH or EGPF. Rules must specify the station, event day, local observation window, units and supported rounding. Station distance is calculated and capped by a setting (30km default). METAR routine/SPECI/remark rules are checked. Other/ambiguous contracts get specific rejection reasons. Pure total-precipitation contracts are rejected because snow is not equivalent to rain. Yes/No payoff direction and sizing use the relevant temperature/rain contribution to the conditional downside, rather than all estimated weather loss. An airport station and gridded forecast can diverge; suitability does not guarantee protection.
- **Paper settlement:** Refresh settlements checks the official Polymarket final-resolution feed, requiring a final state, transaction and valid payout vector. Historical final records without vectors additionally require matching closed CLOB records with explicit unambiguous winner flags; prices never establish settlement. Recorded payouts/net P&L use entry-time fixed FX and include original paper costs. Disputed, provisional, unavailable and synthetic records remain unresolved. Recording is atomic and idempotent; no actual redemption/payment occurs.
- **Monitoring and alerts:** opt in under Settings, choose interval (5–1440 minutes), horizon (1–7 days) and budget. While the single API process runs, monitoring fetches current forecasts, checks settlements, assesses the largest positive conditional downside and saves deduplicated in-app alerts/proposals. It never approves positions. Status, next check and failures persist. It is not an operating-system background service, push/email delivery or an always-on hosted worker.
- **Probability / value:** no exact-event contract probability, expected value, numeric basis-risk score or historical saving is fabricated. A forecast’s probability of any precipitation is not the probability of an exact contract threshold, station and window. Order-book prices are prices, not calibrated model probabilities.
- **Financial assumptions:** GBP accounts; configurable fixed USD/GBP simulation rate (default 1.28), configurable flat paper fee (default 50 bps). Decimal order-book walking supplies quantity, cost and conditional payout. These are not actual exchange fees or live FX quotes. Estimated operating profit is calculated separately using editable demo costs: predicted daily revenue − (revenue × variable-cost percentage) − fixed daily costs. Defaults are illustrative £1,000/day fixed + 30% variable, clearly labelled and editable from the Impact card, dashboard or Settings. Costs persist per business and reset when the business identity changes. Negative profits are retained; margin is undefined when revenue is zero. Model uncertainty ranges hold costs fixed. This is before tax/financing and excludes paper hedges; actual expenses and cash payment timing are not imported or forecast.
- **Execution:** deterministic Python orchestration with a frozen regression model. The primary application does not use an LLM or claim Gemini access. The legacy agent and Streamlit code remain development references.
- **Demo-only / unsupported:** Toast, Monzo, Xero and Companies House connections are visual demos at your request. Company/licence/identity checks, sports, beer duty, cashflow forecasting, real-money trading and LLM orchestration remain outside the implemented weather-paper workflow.

## Paper controls and persistence

Authoritative records live in SQLite at `data/runtime/weather_app.db` (override with `APP_DB_PATH`). Browser storage holds the theme only; replay uses its separate legacy demo preference. Back up the SQLite database with services stopped. Runtime databases are ignored by Git.

Proposals bind the exact contract, outcome, quantity, maximum cost and quote timestamp. They expire after 15 minutes. Business, dataset, accepted model or financial risk-setting changes invalidate dependent analysis and pending approvals. Monitoring schedule changes do not invalidate approvals. Analysis completion verifies that its input revision is still current.

A SQLite `BEGIN IMMEDIATE` transaction serializes approvals, rejections, reservations and profile changes. Tampered, expired, stale, already-decided and duplicate approvals are rejected. Calculations and risk checks remain server-side. Every paper position requires human approval, including small positions.

Risk limits apply across all local portfolio records:

- Weekly spend: entry costs approved since Monday 00:00 Europe/London, plus unexpired pending reservations.
- Monthly worst-case loss allowance: current-month entry costs, plus earlier unresolved entry costs, earlier positions’ realized paper losses settled this month, and unexpired pending reservations. Hypothetical payouts never credit this allowance.
- Per-contract concentration: unresolved positions and unexpired pending proposals in that market.

Rejected, invalidated and expired proposals do not reserve new spending. Existing positions remain in the portfolio after profile edits so they cannot evade limits. There is no automatic exchange submission, wallet signing or payment operation.

## Verification

```bash
.venv/bin/python -m pytest -q
npm --prefix app run lint
npm --prefix app run typecheck
npm --prefix app run build
.venv/bin/python -m scripts.check_live
.venv/bin/python -m scripts.verify_weather_live
```

`tests/test_application.py` and `tests/test_weather_features.py` use isolated temporary databases and mocked transport for deterministic failure tests. Existing backend tests are retained. Live provider checks are separate in `docs/live-verification.json`; passing mocked tests does not verify an external integration.

For browser tests, launch with a **fresh test database**, then run the acceptance script (install Playwright Chromium first; set `CHROME_PATH` to use another compatible browser):

```bash
APP_DB_PATH=/tmp/pub-hedge-browser-test.sqlite3 python3 scripts/start.py --production
# In another terminal:
node scripts/browser_acceptance.cjs
```

Install the matching browser first with `(cd app && npx playwright install chromium)`. The script refuses an existing business profile and never clears a user's records. Baseline captures, comparison methodology and test results are documented in [docs/INTEGRATION.md](docs/INTEGRATION.md) and [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Retained development work

The original Streamlit app is available with `.venv/bin/python -m streamlit run app.py`. It is not the primary interface and uses its own legacy defaults and database. Historical setup notes are preserved in [docs/STREAMLIT_REFERENCE.md](docs/STREAMLIT_REFERENCE.md); their old model-access and universal-market claims are not current evidence. Existing model evaluation, source datasets, provenance and tests remain intact. No remote branches were modified.
