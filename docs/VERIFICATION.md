# Verification and handover — 8 November 2026

## Implemented workflow

Nick’s Next.js interface uses the existing fonts, themes, shell, onboarding, panels, tables and charts. Python/FastAPI and SQLite own profiles, imports, training jobs/models/evaluation, analysis/progress, proposals, decisions, paper positions, settings, settlement evidence and in-app alerts. Browser storage is not the financial ledger.

The weather workflow supports bounded live contract matching, imported-sales model training with chronological evaluation, official paper settlement and opt-in forecast monitoring. At the user's request, paper approval now records a simulated fill at the reviewed assessment quote without live repricing or an exchange request. Expiry, binding and portfolio checks remain enforced. Toast, Monzo, Xero and Companies House provide explicitly labelled visual connection demos, as requested. They do not access accounts or import data.

Launch from the repository root with `python3 scripts/start.py --production` after `npm --prefix app run build`. See [README](../README.md) for installation, supported contract grammar, source distinctions and financial assumptions.

## Automated checks

- **85 tests passed**, including all original tests. Focused coverage includes persistence/restart; profile/data/model invalidation; CSV validation; chronological fitting and holdout gates; unsupported station/rules/window/distance; temperature/rain payoff direction; reviewed-quote paper approvals despite later price/rules/status/depth changes or offline mode, with no exchange request; provisional/disputed outcomes; explicit historical winner evidence; transactional/idempotent settlement; approval tampering/concurrency/portfolio limits; monitoring deduplication/rejection; demo connections that never import records; and operating-profit rounding, losses, zero revenue, cost boundaries/validation, restart persistence and recalculation without invalidating analysis or approvals.
- Frontend ESLint and TypeScript passed. The Next.js production build passed with self-hosted fonts.
- `.venv/bin/python -m scripts.check_launcher` exercises real startup, a rejected duplicate launch, health of the first instance, and clean shutdown. It uses an isolated database and leaves default ports free.
- Tests use temporary databases and mocked transport for deterministic external failure cases. NumPy/pandas deprecation warnings remain in inherited dependencies.

## Browser verification

Production builds were exercised in Playwright’s matching Chromium against `/private/tmp/pubhedge-v2-browser.db` and `/private/tmp/pubhedge-v3-browser.db`, separate from user records:

1. Sample business → invalid CSV error → synthetic sample sales → no suitable hedge → finish setup → empty dashboard → reload.
2. Suitable explicitly synthetic contract → review → human paper approval → persisted position → reload.
3. Companies House demo in business review and visual demo connections for all three sales providers, with zero account imports; current forecast refresh; all six dashboard pages in both themes at 1440×1000 and 1024×768; settings persistence and unresolved synthetic settlement.
4. Upload the downloadable 1,461-day **synthetic** training CSV → fetch actual historical weather → fit/evaluate → accepted model survives reload → cold scenario with actual live market discovery and the imported model → enabled scheduled monitoring → stored in-app alerts/read state → disable monitoring.

The first three journeys passed with zero browser page errors: [acceptance.json](screenshots/functional-v2/acceptance.json). The training/monitoring journey’s result is [weather-features.json](screenshots/functional-v2/weather-features.json); screenshots share that directory. An initial test-server network restriction produced an actionable archive-retrieval failure, preserving the import. The run was repeated with network access. Repeat-run testing also found and fixed a stale evaluation report after replacing sales data; the historical report remains accessible by job ID but is no longer shown as the current selection’s evaluation.

Reproduce with `node scripts/browser_acceptance.cjs URL docs/screenshots/functional-v2` on a **fresh isolated** database, then `node scripts/browser_weather_features.cjs URL` against its resulting named test business. The acceptance script refuses an existing profile and never clears user records.

## Genuine public-source checks

Separate read-only external checks are recorded in [live-functional-check.json](implementation-evidence/live-functional-check.json):

- Current Open-Meteo forecast: source, coordinates, units, local timezone, retrieval time and 14-day horizon returned successfully.
- Gamma targeted weather discovery and CLOB order books: actual London contract **6772770**, EGLC, 9 November 2026, daily maximum ≤6°C, 10.64km from the configured test business. A manual 4°C stress scenario produced a paper recommendation; fresh contract/book revalidation allowed an isolated paper approval. No exchange order was submitted. Subsequent resolution remained `posed`, so no payout was recorded.
- Actual Open-Meteo historical archive joined 1,461 rows of deliberately **synthetic** repository revenue. The selected histogram gradient boosting model’s chronological holdout MAE was £512.38 versus £1,299.16 for its weekday baseline (60.56% improvement). This verifies plumbing and evaluation, not a real pub’s predictive accuracy.
- Historical closed market **519338**: official final resolution plus matching closed CLOB explicit winner flags returned canonical Yes/No payout shares `[0,1]`. Indicative prices were ignored. Evidence: [raw sources](implementation-evidence/closed-market-resolution.json), [parsed outcome](implementation-evidence/closed-resolution-parsed.json). Atomic position settlement is covered in isolated integration tests; the live newly approved position has not matured.

These are point-in-time checks, not guarantees that a current matching contract or quote remains available. The earlier [live-verification.json](live-verification.json) describes the superseded broad discovery check; the targeted implementation above supersedes its lack of weather results.

## Visual preservation and source safety

Pinned commits and recoverable checkpoints are in [INTEGRATION.md](INTEGRATION.md). All existing model artifacts, source datasets and provenance were retained. No commit, push, deployment or remote branch change was made.

Nick’s 27 original screenshots were verified byte-for-byte against the pinned `nick-demo` commit. **24 identical-fixture replay comparisons passed** (six pages × two themes × two viewports), excluding only the 30px fictional replay disclosure. Paired font/colour/sidebar/radius metrics matched. See [comparison/results.json](screenshots/comparison/results.json) and [comparison/metrics.json](screenshots/comparison/metrics.json).

Those comparisons establish preservation of the replay’s visual implementation; they do not claim pixel identity for connected panels containing different server results, forms or truthful empty states. Connected pages were separately rendered and reviewed at both viewport sizes/themes. The original labelled replay never accesses current records.

## Practical limits

This is a single-operator loopback application. Monitoring runs only while its one API process is running; it saves in-app alerts and never approves positions. It is not a hosted worker or email/push service. Supported live contracts use the explicitly bounded station/measurement/rules grammar documented in the README. Other contracts fail with specific reasons. Forecast grids and airport observations can diverge. Search is bounded, not exhaustive.

No calibrated exact-event probabilities, EV, numerical basis-risk score, causal losses or fabricated annual savings are claimed. The regression predicts revenue. A separate operating-profit scenario subtracts explicit, editable demo fixed and variable costs, with defaults of £1,000/day and 30%; it is not an expense regression or actual account import. Negative results and revenue-model ranges are retained with costs held fixed. Cashflow/payment timing, tax/financing and business-record validation remain outside that scenario. Provider/company/licensing integrations, sports, beer duty and real-money trading remain outside this weather-paper workflow. Synthetic fixtures cannot acquire authoritative exchange settlements.

## Operating-profit follow-up

The Impact page’s unfinished profit/cashflow card is replaced with **Estimated operating profit**, labelled **Demo costs**, using server-side Decimal arithmetic. Defaults and edits are visible. The same component appears on the dashboard, Scenarios and Settings. Saving costs does not retrain the revenue model, rerun market discovery, invalidate proposals or book a paper trade.

Focused browser verification: `node scripts/browser_operating_profit.cjs http://127.0.0.1:3100`, against a fresh isolated database. The preview build uses `.next-profit` and port 8100 for its API, leaving the user’s running 3000/8000 services untouched. Evidence and screenshots are in `docs/screenshots/operating-profit/`. The normal production frontend was also rebuilt after ports 3000/8000 became free. Relaunch with the existing database selection to use the feature on the default ports.
