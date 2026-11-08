# combined-dev: what we take from luke-dev and emirhan-dev

Status: **Phases 0–3 are done (T1–T6), in lean form.** Not done: P4 "bring your own pub", which is your call.
Branched from `nick-advanced` @ 7c5da34. Differences from the plan:
- T4 settles when the owner presses "Check result", not automatically.
- The monthly ledger is unchanged: a bought position's premium is already its maximum loss.
- T5 uses a checked team table for the pinned pub (Arsenal at home, England home or away), not the Gemini profiler.
Analysed 2026-11-08 against `luke-dev` @ 96da93f and `emirhan-dev` @ 402f00b.

## 1. What the three branches are

They share no git history (each starts from the one-line initial commit), so this is a **port of ideas into
nick-advanced's structure**, not a merge. Running `git merge` would bring in a second backend and a second app.

| | nick-advanced (baseline) | luke-dev | emirhan-dev |
|---|---|---|---|
| Backend | `pubhedge_core/` (stdlib, scored by the kit adapter) + `services/agents` (FastAPI, 5-agent ADK chain) | `src/` FastAPI + SQLite, sklearn model, legacy Streamlit + Gemini agent | `src/pub_profile.py`, `src/pub_market_signals.py` (standalone) |
| Pub | One pinned demo pub (The Faltering Fullback, N4 3HB); form edits are ignored with a warning | Any pub, self-reported | Any pub, free text or JSON |
| Takings | Synthetic 5-year panel, OLS with CIs, held-out R² | Synthetic sample or **CSV import + per-business training** | Feeds luke's model |
| Hedge | Synthetic rain contract priced from calibrated forecast; real Polymarket match-day offer (England v Croatia, hard-coded) | Real Polymarket contracts parsed for suitability; order-book walk | Finds markets; doesn't hedge |
| Money view | Payroll cashflow (does Friday payroll clear?) | Operating profit (revenue − variable % − fixed) | — |
| Safety | Limits, 2nd confirmation > £50, grounding check, hash-chained audit | Binding hash, 15-min expiry, `BEGIN IMMEDIATE`, settlement | Evidence quotes, injection filter |
| Tests | 23 service + 18 core pass offline | 85 pass; lint, typecheck, build pass | 18 pass, 1 skip (`python -m pytest` only) |

## 2. Rules for combining

1. **nick-advanced's architecture stays.** New logic goes into a tool in `pubhedge_svc/tools.py` (so it gets a
   receipt and the grounding check sees it) or a small stdlib engine. No sklearn, pandas, Streamlit or second API.
2. **Leave `pubhedge_core/` alone** unless a change is purely additive: the kit adapter and the published challenge
   results (40/40, F1 100%) run on it.
3. **No new onboarding step, no new dashboard page.** Today already shows 4 KPIs and 6 panels. New detail goes into
   an existing panel or the receipt drawer. A new card only goes in if it replaces one.
4. **Real vs synthetic badging stays strict.** Nothing that animates a fake connection.
5. Every change re-records `fixtures/runs/demo-run.json`, refreshes screenshots (`UPDATE_SHOTS=1 scripts/check.sh`)
   and keeps `scripts/check.sh` green.

## 3. Decisions

### Take

| # | What | From | Why | What it changes for the user |
|---|---|---|---|---|
| T1 | **Atomic approval** | luke `application_store.py` (`BEGIN IMMEDIATE`) | `approve()` in `app.py` reads status, then fills. Two fast clicks or two tabs can fill the same proposal twice, and two proposals approved together can both pass the weekly cap. | Nothing visible. A double click returns 409 instead of a second fill. |
| T2 | **Proposal expiry + binding** | luke `paper_execution.py` (binding hash), pre-96da93f re-quote | Today a proposal stays approvable forever at its old price. | A pending card shows "valid until Sat 12:00". After that: "Expired: run again". |
| T3 | **Order-book walk for the real-market offer** | luke `financial_calc.walk_ask_book_for_budget` | `quote_offer` prices all shares at best ask + 1% slippage. On a thin book that understates cost. | The offer's cost and share count become what the book really offers; it may cover less. |
| T4 | **Paper settlement** | luke `polymarket_client` resolution rules | Positions never close, so the story stops at "approved". | Protections shows "Paid £X" or "Expired, lost £Y". The August replay can show the cover paying out on the real 6.1 mm Saturday. |
| T5 | **Fixtures for this pub** | emirhan fixture rules (`fixtures`, `_same_team`, `counts_as_local_event`) | The offer is hard-coded to England v Croatia. A pub near a stadium has its own match days. | The offer card picks the next qualifying fixture for the pub, e.g. a club near N4 at home. If none qualifies, it falls back to today's offer. |
| T6 | **Market-implied high temperature** | emirhan `distribution` / `summarise` | `check_real_weather_markets` only names the top bracket. | The receipt (not a new panel) shows "market expects 10.1 °C (9–11)". |

### Leave

| What | From | Why |
|---|---|---|
| Whole `src/` backend, sklearn joblib model, `app/src/replay/` copy, Streamlit `app.py`, `agent.py` | luke | Second backend. The model is trained on synthetic revenue. sklearn 1.6.0 has no wheel for this Mac's Python 3.14. About 2.9k lines are legacy. |
| Operating-profit card | luke 96da93f | Puts a second "impact" number (from made-up £1,000/day + 30% costs) next to the payroll view, which already uses the synthetic cost manifest. Two impact numbers make the impact less clear. |
| 96da93f's removal of re-check at approval | luke | Weakens safety. T2 keeps the re-check. |
| Daily rain ≥N mm contract parser and station list | luke `contracts.py` | Only tested with mocked HTTP. No daily London rain market exists (both other branches found the same). The synthetic contract stays, badged. |
| Toast / Monzo / Xero / Companies House "demo connect" animations | luke | They look like real integrations. |
| Luke's limit defaults (£300/£500/£200), 3-second full-state polling | luke | Ours are documented and tested. Polling sends the model's test predictions every 3 s. |
| Monthly rain spread evenly over the month | emirhan | His own doc calls it a weak signal (about 2 mm a day sits on the threshold). |
| gov.uk bank holidays as a model feature | emirhan | Changes the regression, so it changes every published figure (backtest, README, deck). Do it later, if at all, with a backtest re-run. |
| Gemini pub profiler (now) | emirhan | Useful only once the pub is editable (see P4). For the pinned pub a checked team table does the same with no model call. |

### Decision for you: P4, "bring your own pub" (not in this plan's build)

This is the one change that makes the product work for any pub: luke's CSV import and gate, emirhan's profiler and
nick's Companies House verifier. But it unpins every number on screen (backtest, payroll, replay) and touches nearly
every tool (`PUB`, `panel()["demo"]`, the manifest costs). **Recommendation: do it after the demo, as its own branch.**
If we do it:
- Use our OLS, not sklearn.
- Fix luke's gate. His baseline is weekday-only, so seasonality alone passes it. Compare against weekday + season,
  and require the rain coefficient's CI to exclude 0.

## 4. How each Take is built, and what it touches

**T1 Atomic approval** (`services/agents/src/pubhedge_svc/app.py`)
- Do the whole of `approve()` (limit re-check, fill, status update) under one lock, using `BEGIN IMMEDIATE`, or the
  existing `audit._lock`.
- The status change is `UPDATE … WHERE id=? AND status IN ('pending','blocked')`; if `rowcount` is 0, return 409.
- Tests: two concurrent approvals give 1 fill and 1 conflict. Two proposals whose sum exceeds the weekly cap give one
  `blocked`.

**T2 Expiry and binding** (`tools.queue_for_approval`, `app.queue_offer`, `app.approve`, `ApprovalCard`)
- Add `expires_at` and `binding` (sha256 of market_id, shares, cost_pence) to the proposal's `market` JSON. That needs
  no schema migration.
- **Expiry is measured on the run's clock.** Live mode uses wall time: a proposal expires when its event window opens
  (rain contract: Saturday 12:00; offer: kick-off). Scenario and replay are frozen at `decision_date`, so they never
  expire mid-demo. A plain 15-minute timer, as in luke's code, would kill the August replay, whose dates are in the
  past.
- For real-market (offer) proposals only: if the quote is over 15 minutes old at approval, re-quote (read-only GET).
  If the cost rose, return `needs_requote` and the card shows the new price for a fresh approval.
- The UI change is one line of text on `ApprovalCard`, and an expired state with a "Run again" button.

**T3 Book walk** (`clients/polymarket.py` adds `book(token_id)` via CLOB `/book`; `tools.quote_offer`)
- Port about 30 lines of luke's Decimal walk into `engines.py`, not `pubhedge_core`. It includes the fee and stops at
  the worst case and the caps.
- Record the book in `fixtures/recorded/polymarket/` so offline and replay still work.
- If the book is missing (offline cache miss), fall back to the current best-ask rule, badged `ESTIMATE`.
- Numbers that change: offer cost and shares on Today, Recommendation and Protections, and the demo-run fixture.

**T4 Settlement** (new tool `settle_positions`; `app.py` adds `POST /api/positions/settle`; Protections page)
- **Synthetic rain contract:** settle from observed 12:00–18:00 rain. Scenario mode uses `data/weather/N4.csv`
  (already in the repo); live mode uses the Open-Meteo archive client. It pays £1 a share if rain ≥ 3 mm. Checked
  against `N4.csv`: in the August replay, Saturday 29th had 6.1 mm, so that contract pays; Sunday 30th had 0.8 mm,
  so that one expires worthless.
- **Offer (real market):** settle only on a final resolution with a payout vector, using luke's rules (final state,
  no review in progress; prices never settle). Until then it shows "awaiting result".
- Write one `settle` audit row per position, idempotent: settling twice writes nothing new.
- `current_ledger` then counts realised losses. `limits.py`'s docstring already says it should; today it only counts
  premium.
- UI: a status column on the existing Protections table, and one line on `ApprovalCard` after fill. No new page.

**T5 Fixtures for this pub** (new tool `pub_fixtures` in the ingest step; `quote_offer` reads it)
- A checked team table for the pinned pub lives in `data/reference/`: club, stadium lat/lon, sport, competition tag,
  aliases. Python checks stadium distance from the pub's postcode (emirhan's code left that to Gemini).
- Port emirhan's Gamma fixture search with these fixes:
  - an alias table for team names ("Man Utd" vs "Manchester United");
  - drop women's and youth fixtures unless listed;
  - if the competition tag doesn't match, **skip the fixture**, rather than fall back to all fixtures (that fallback
    let a WSL match through in his run C);
  - the existing 300 s cache.
- The pick: the next home fixture of a nearby club, or a match the pub shows, within 14 days, whose market has a
  usable book.
- The trigger and offer text stay the owner's choice. The default is "if <home club> lose: mains half price".
- Fallback: the current England v Croatia offer.
- Record the fixtures for offline and replay. Tests: alias match, women's fixture excluded, away fixture excluded,
  fallback.

**T6 Market-implied high** (`tools.check_real_weather_markets`)
- Add `expected_high_c` and `p10/p50/p90` from emirhan's `summarise`, with two fixes:
  - skip a bracket whose bid–ask spread is over 0.2, rather than using its mid;
  - return nothing when all prices are 0 (his code returns 0 °C).
- The summary line gains "~10 °C". The numbers are only in the receipt. The model doesn't use them, so no figure
  changes.

## 5. The flow after the change

```
Onboarding (unchanged 7 steps)
  1 Business ─▶ 2 Agent run ─▶ 3 Verification ─▶ 4 Risk ─▶ 5 Impact ─▶ 6 Recommendation ─▶ 7 Review/approve
                    │
                    ├─ verifier  CH profile, officers, postcode
                    ├─ ingest    takings, Stripe test, bank feed, weather, match/duty, + pub_fixtures (T5)
                    ├─ risk      OLS fit, weekend exposure
                    ├─ pricer    forecast, real markets (+ implied high, T6), synthetic rain price, payroll, LP size
                    └─ monitor   limits, queue (+ expiry/binding, T2), offer quote (book walk T3, fixture from T5)

Approve (T1 atomic) ─▶ paper fill ─▶ [event window] ─▶ settle_positions (T4) ─▶ Protections: paid / lost
                                                         └─▶ realised loss feeds the monthly cap
```

On screen, the net change is about four lines of text and one table column. No panels are added.

## 6. Order of work and risk

| Phase | Items | Size | Changes published numbers? | Risk |
|---|---|---|---|---|
| 0 | T1, T2 | S | No | Low. Expiry on the run clock is the trap to avoid. |
| 1 | T3, T6 | S–M | T3: offer cost only | Live book may be thin, so cover can drop. Badge it. |
| 2 | T4 | M | No (adds a settled state) | The real-market resolution feed shape: record a real resolved market first. |
| 3 | T5 | M | Offer fixture may change | Gamma tagging for rugby is unverified. Football first. |
| later | P4 | L | Yes, all | Its own branch, your call. |

After each phase: `scripts/check.sh` green, the demo fixture re-recorded, screenshots refreshed, and the README
"what is real / synthetic" table updated if a source changed.

## 7. Small things to fix on the way

- `schedule_monitor` says "re-check Fri 09:00 and Sat 08:00", but the real monitor (`start_monitor` in `app.py`) only
  runs when `PUBHEDGE_MONITOR_MINUTES` is set, every N minutes. The tool should report what is actually scheduled.
- The kit's `test_kit_reference_code_is_disabled_and_flagged` fails here with `PermissionError` (sandbox, at
  `bench.py:141`). This is an environment problem, not a code bug, and `check.sh` doesn't run it.
