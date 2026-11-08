# Pub details → Gemini → Polymarket → revenue model inputs

This builds the inputs for the revenue model in `src/inference.py` for a pub, from live Polymarket prices.

Entry point: `research(pub, start, days)` in `src/pub_market_signals.py`. `pub` is whatever the previous step passes on: free text, a dict or JSON with any fields, even just a name and a postcode. Each run makes two Gemini calls:

1. **Gemini plans.** It reads the pub and deduces the weather city, nearby clubs, sports and up to 8 searches.
2. **Python searches.** It runs every planned search on Polymarket and collects the open events (duplicates and side events removed).
3. **Gemini judges.** It sorts each result as model input, context or irrelevant, with a reason.
4. **Python checks each verdict.**
   - A "temperature" market must really be the pub's city's daily-high market.
   - An "event" must be a single fixture on one of the days.
   - Text aimed at an AI is rejected.
   - A match involving one of the pub's own teams is left to the team rules, which know home from away and the competition.

Details of each step:

1. **Gemini reads the pub** (`src/pub_profile.py`, one call, `gemini-3.8-flash`, prompt `pub_profile v4`).
   - **Stated facts** are kept only when quoted word for word from the owner's details: name, postcode, seats and opening hours.
   - The postcode is looked up on postcodes.io by Python.
   - Indoor seats are computed in Python as total minus garden.
   - **Deductions** are labelled as inferences and are used only as search terms:
     - which Polymarket weather city to use;
     - nearby clubs and the teams the pub shows, each with its sport and competition;
     - search phrases.
2. **Polymarket is searched** (`src/pub_market_signals.py`). It uses the public, read-only Gamma and CLOB endpoints: no keys and no orders.
3. **Python turns the prices into model inputs**, one `DailyFeatureInput` row per day. Every field records its source.
4. **Optionally, the saved model runs** on each row and on its seasonal dry reference, for comparison.

## What Polymarket can fill

| Model input | Source |
|---|---|
| `temp_max_c` | "Highest temperature in London on <day>?" (11 brackets, settled at London City Airport). The expected high, from bid/ask mids normalised to 100%. |
| `local_event_indicator` | 1 when one of the pub's teams has a fixture that day. The fixture must be in the team's sport and competition, either as a nearby club playing at home or as a match the pub shows. |
| `rain_mm`, `precipitation_mm` | No daily rain market exists. London rain trades only as a monthly total at Heathrow. By default these come from the model's seasonal reference, and the monthly market is reported as context. `--rain-from-market` spreads it evenly over the month instead (a weak signal: about 2 mm a day sits right on the model's 2 mm "rainy day" threshold). |
| `temp_min_c`, `temp_mean_c` | The model's seasonal reference, shifted by the market's high. |
| `wind_max_kmh`, `sunshine_hours` | The model's seasonal reference (no market exists). |
| `indoor_capacity`, `outdoor_capacity`, `opening_hours` | The pub's details, otherwise the model's defaults. |
| `is_uk_bank_holiday` | gov.uk bank-holidays.json. The model's own list only covers 2022 to 2025. |

The weather market is only used for a pub within 40 km of London City Airport.

## Run it

This module runs on its own. It needs no other file from the repository, because the few settings it takes from the revenue model (its input field names, defaults and monthly reference weather) are copied into `src/pub_market_signals.py`. On a branch without the model, 18 tests pass and 1 is skipped: the check against `src/schemas.py`, which only runs once the branches are combined. Only `--predict` needs the model itself (`src/inference.py`). The saved model was pickled with scikit-learn 1.6.0, so use that version; with 1.8.0, `joblib.load` fails.

**Any input.** Gemini decides what each piece of the input means, whatever the field names.
- Extra details it finds useful ("next to the O2 arena", "big screens") become searches, but only if they are quoted word for word from the input.
- What it cannot use is listed as `unused`, by field name and never by value.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install "scikit-learn==1.6.0" -r requirements.txt
.venv/Scripts/python -m pytest -q tests/
.venv/Scripts/python -m src.pub_market_signals --pub '{"name": "Synthetic Test Pub A", "postcode": "SE22 8HD", "outdoor_seats": 72, "shows": ["football", "rugby"]}' --days 2 --save
.venv/Scripts/python -m src.pub_market_signals --pub "Synthetic Test Pub B, a city-centre pub in Manchester M1 1AE with a small terrace. We show football." --days 2 --save
```

**Live, 7 November 2026, for 8 and 9 November:**

| Pub | Planned searches | Results judged | Fed the model | Event on 8 Nov |
|---|---|---|---|---|
| A, JSON record, SE22 8HD | 6, incl. London temperature, Millwall, Crystal Palace | 24 | London daily highs for both days; Palace v Liverpool | 1 (Palace at home) |
| B, free text, Manchester M1 1AE | 6, incl. Manchester City and United | 40 | Man Utd v Aston Villa | 1 (United at home) |
| C, JSON with unusual fields (`pub`, `where`, `notes`, `seats_inside`, `manager_email`), SE10 0DX | 7, incl. "O2 arena" from the notes | 28 | London daily highs for both days | 0 (Charlton's match was away, marked context) |

- **Pub C:** Gemini read 60 seats from `seats_inside`. It found three details in the notes: the O2 arena and big screens became searches; quiz nights had no market. It listed `manager_email` as unused.

- **Pub A:** 14 results were judged irrelevant, such as NFL "Pro Football" markets found by "England football".
- **Pub B:** no London weather market was used, and later fixtures were marked as context.

`GEMINI_API_KEY` is read from `.env`, which is never committed. To skip the Gemini call, rerun with `--profile-json` on a saved profile. `--save` writes the profile, markets and rows to `data/polymarket_cache/pub_signals_<time>.json`. The profile includes Gemini's raw reply (`gemini.raw_reply`) and, for each quote it gave, whether Python found it word for word in the details (`evidence_checks`). The Gemini log (`data/runtime/pub_signals_log.jsonl`) records field names only, never the pub's name or address.

## First live run (7 November 2026, 22:30 UTC)

**Gemini** (16.0 s):
- Kept every stated fact: 120 covers, 72 outdoor, so 48 indoor computed.
- Postcode: SE22 8HD (Southwark), 10.6 km from London City Airport.
- Teams: Crystal Palace and Millwall as nearby clubs, and England rugby as a match the pub shows.

**Polymarket** (7 calls):

| Day | Market's expected high | 10/50/90% | Fixture | Model: predicted (80% range) | vs dry reference |
|---|---|---|---|---|---|
| Sat 7 Nov | 11.0°C (day over) | 11/11/11 | none | £4,691.27 (£4,375.59 to £5,144.86) | −£72.59 |
| Sun 8 Nov | 10.09°C | 9/10/11 | Crystal Palace v Liverpool, at home | £4,029.88 (£3,714.20 to £4,483.47) | −£173.97 |
| Mon 9 Nov | 10.17°C | 9/10/12 | none | £1,713.02 (£1,397.34 to £2,166.61) | −£35.12 |

The November rain market (Heathrow) expects 61.58 mm for the month.

The revenue model was trained on **synthetic** pub revenue paired with real London weather. These predictions show the pipeline working; they are not a forecast for a real pub.
