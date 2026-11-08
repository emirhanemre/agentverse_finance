# Data sources

Every number in the app carries a badge saying where it came from. This page lists each source, its licence,
what is real and what is synthetic, and how the synthetic data was made.

| Badge | Meaning |
|---|---|
| REAL | Live API response in this run |
| REAL · CACHED | A real API response, cached at the stated `fetched_at` |
| SYNTHETIC | Generated: generator and seed are shown |
| TEST MODE | Stripe test mode |
| PAPER | Simulated execution on our local paper exchange |
| REPLAY | A recorded run, streamed again |
| TEMPLATE | Narration written from tool outputs by a template, because the model was unavailable or switched off |

## The real pub (public identity only)

**The Faltering Fullback, 19 Perth Road, London N4 3HB.** It is operated by **Bacchus Inns Limited (company 05770953)**.

We use public identity data only: the company register, location and weather. **All of its financials in the
demo are SYNTHETIC: "modelled for a pub of this profile, not The Faltering Fullback's actual figures."** Nothing
in the demo states or implies the pub earned, lost or traded anything. Nobody at the pub was contacted. The
approving owner in the app is a demo persona, "Owner (demo)".

| Criterion | Evidence |
|---|---|
| Real, independent, London | The pub's own site describes "an Irish family-run pub" ([falteringfullback.com](https://falteringfullback.com/)). The company has a single shareholder, and no pub company or brewery link was found. |
| Beer garden (the weather exposure) | Time Out, [24 Best Beer Gardens in London 2026](https://falteringfullback.com/blog/time-out-24-best-beer-gardens-in-london/), and its [venue page](https://www.timeout.com/london/bars-and-pubs/faltering-fullback). Haringey planning application [HGY/2022/1788](https://publicregister.haringey.gov.uk/pr/s/planning-application/a0i8d000002GJDnAAO/hgy20221788) covers alterations to the existing terrace. |
| Active company that operates the pub | Companies House: active, incorporated 2006-04-05, SIC 56302 (public houses and bars). The site footer reads "© 2025 Bacchus Inns Ltd". The owner named on the site matches the company's director and person with significant control. |
| Character | [CAMRA London Pubs Group listing](https://londonpubsgroup.camra.org.uk/viewnode.php?id=48565). It is also a rugby and GAA screening pub, which gives it sport exposure. |
| Licence | Not found. Haringey is the licensing and planning authority; we found no premises licence number. |

Officer verification is shown as a match result against the public register ("1 active director · match").
No officer is named in the UI.

Runner-up: The Herne Tavern (SE22), which has a famous garden. It is run by a multi-site group, so it is not a
single independent.

## External sources

| Source | What we use | Real or synthetic | Licence and attribution | Client and cache |
|---|---|---|---|---|
| [Companies House API](https://developer.company-information.service.gov.uk/) | Profile and officers for 05770953 | REAL | Open Government Licence v3.0 | `clients/companies_house.py`, cached 7 days, recorded fixture committed |
| [postcodes.io](https://postcodes.io/) | Postcode to lat/lon and district | REAL | OGL v3.0 (ONS Postcode Directory) | `tools.locate_postcode`, cached 30 days |
| [Met Office Weather DataHub, Site Specific](https://datahub.metoffice.gov.uk/) | Live forecast for this coming weekend (three-hourly, 12:00–18:00 rain) | REAL | Met Office DataHub terms. "Powered by Met Office data" | `clients/metoffice.py`. Cached per location for 1 h; never committed; free tier about 360 calls a day |
| [Open-Meteo archive (ERA5)](https://open-meteo.com/en/docs/historical-weather-api) | Daily observed rain, 12:00–18:00 rain, max temperature, sunshine, 2021-01-01 to 2026-10-31, 4 London points | REAL | CC BY 4.0. "Weather data by Open-Meteo.com". Free non-commercial use | `clients/openmeteo.py` to `data/weather/*.csv` (`scripts/build_weather.py`) |
| [Open-Meteo historical forecast API](https://open-meteo.com/en/docs/historical-forecast-api) | What was forecast at the time, for backtest decisions and the August 2026 scenario | REAL | CC BY 4.0 | Same as above. Max temperature only exists from 2022-03 |
| [Polymarket Gamma and CLOB](https://docs.polymarket.com/) (public read API only) | Search; daily London highest-temperature ladders; price history; fee schedule | REAL | Public market data, read-only. Polymarket blocks UK users from trading, so we never call order endpoints | `clients/polymarket.py`, cached 5 min, fixtures committed |
| [Polymarket England v Croatia match markets](https://polymarket.com/event/unl-eng-hrv-2026-11-12) (public read API only) | Real "Will Croatia win on 2026-11-12?" price (best ask) for the match-day offer card; kick-off from the event | REAL / REAL · CACHED | Public market data, read-only; no order endpoint is called | `tools.quote_offer`, fixture committed |
| [Polymarket fees](https://docs.polymarket.com/trading/fees) | Taker fee `C × rate × p × (1−p)`, rate 0.05 for weather and sports | REAL (checked 7 Nov 2026) | n/a | `engines.FEE_RATE` |
| [Stripe test mode](https://docs.stripe.com/testing) | 120 daily takings charges (`metadata.business_date`) | TEST MODE (synthetic amounts) | Our own test data | `scripts/seed_stripe.py`, `clients/stripe_client.py`. Refuses any non-`sk_test_` key |
| [openfootball](https://github.com/openfootball) | England men's football match days, 2021–2026 | REAL | CC0 1.0 | `scripts/fetch_reference.py` to `data/reference/sport_days.csv` |
| Wikipedia, Six Nations 2021–2026 | England and Ireland Six Nations match days | REAL | CC BY-SA 4.0. "Wikipedia contributors" | same |
| [HMRC alcohol duty rates](https://www.gov.uk/government/statistics/alcohol-bulletin/alcohol-bulletin-historic-duty-rates), [Finance (No. 2) Act 2023 Part 2](https://www.legislation.gov.uk/ukpga/2023/30/part/2) | Beer duty changes: 1 Aug 2023 reform, 1 Feb 2025, 1 Feb 2026 | REAL | OGL v3.0 | `data/reference/duty_changes.csv` |
| Gemini API (AI Studio) | `gemini-3.8-flash` for the tool-calling agents, `gemini-4-argon` for the hedge rationale | n/a | Google AI Studio terms | `chain.py`. Model IDs listed via the API and pinned in `config.py` |
| [AgentVerse Finance Kit](../agentverse/START-HERE.md) | Practice and challenge cases for the adapter | SYNTHETIC (kit), plus real Binance Vision windows for `real-markets` | Kit terms; Binance Vision CC BY-NC-SA 4.0 | `adapter.py` |

The Met Office forecast comes from the nearest grid point. For N4 3HB that is "Harringay", about 1.5 km away;
the badge shows the distance and model run. Open-Meteo gives a grid cell, not the pub's exact point.

## Synthetic data and how it was made

**Takings panel** (`data/synthetic/takings_panel.csv`): five years and ten months of daily takings for the demo
pub plus 11 other pubs. They vary in size (0.6–1.3×), garden share (0–100%) and location (N4, SE22, E2, W12).
Generator: `scripts/gen_synthetic.py`, seed `20261108`; every parameter is in `data/synthetic/manifest.json`.

```
takings = base × weekday factor × season × growth
          × (1 + garden × heat uplift above 14 °C)
          × (1 − capped loss per mm of 12:00–18:00 rain)
          × match-day uplift (England or Ireland playing)
          × duty elasticity ^ number of duty rises so far
          × lognormal noise (s.d. 7%)
```

Drivers are real: the weather, match days and duty dates above. Scales:

| Parameter | Value | Basis |
|---|---|---|
| Turnover | about £850k a year for a panel pub at scale 1; the demo pub is a large garden pub at scale 3.5 (about £3.2M a year), an illustrative profile chosen for the demo | Assumption. BBPA publishes no London independent average |
| Rain loss | 4.5% of day takings per mm of afternoon rain, capped at 32% | Assumption, sense-checked against CGA/NIQ: pub and bar sales were down 13% on the wet 24 May 2025 bank holiday Saturday |
| Heat uplift | Garden pubs gain on warm days | Assumption, sense-checked against Tenzo: London venues with outdoor seating were +3.4% in heatwaves |
| VAT | One-sixth of a VAT-inclusive till | Rule. UHY's £10-pint breakdown puts staff at about 17% of a VAT-inclusive pint |
| Staff and stock | 33% each of net takings | Assumption for a thin-margin independent pub |
| Fixed costs | Rent £9,500, utilities £2,600, other £2,300 a month | Assumption |
| Card fee | 1.5% | Assumption |

The regression recovers the generator's rain effect: about −£406 per mm on Friday to Sunday afternoons for the demo pub, R² 0.92 on
held-out months. **That is expected on synthetic data and is not evidence about real pubs.** The duty effect is not
significant (its 95% CI includes zero), and we say so.

**Bank feed** (`data/synthetic/bank_feed_demo.json`): Open Banking v3.1 Transaction shape, derived from the demo
pub's takings:

- card settlements at T+1, net of fees;
- Friday payroll on a 4-week trailing average;
- Tuesday supplier payments on 14-day terms;
- month-start rent, utilities and other fixed costs;
- quarterly VAT.

**Fixed costs** (`data/synthetic/fixed_costs_demo.json`): Xero-style report rows.

**Rain contract** (backtest and app): SYNTHETIC. No London rain market exists on Polymarket (checked 7 Nov 2026);
only daily London temperature ladders do, and the app reads those as the real price check. The contract pays
£1 a share if at least 3 mm falls 12:00–18:00. Its price is the probability calibrated on 2021–2024 archived
forecasts against observed rain, plus a 3% venue margin and a 1% half-spread. Fills add 1% slippage and
Polymarket's weather taker fee. Real execution would go to a UK-licensed venue (Smarkets, Betfair), shown in the
app as "not connected in demo".

**Demo scenario** (August bank holiday 2026): an illustrative scenario. Real weather and the real archived
forecast; SYNTHETIC takings for a large garden pub (scale 3.5); the owner is assumed to keep an extra £11,360 in
the current account that week (`tools.SCENARIO["extra_buffer_gbp"]`), chosen so that payroll clears if dry and
is short if wet. The engine computes every figure from those inputs. The backtest does not use this buffer.

**Match-day offer** (England v Croatia, Thu 12 Nov 2026, 19:45, Wembley): the offer ("if England lose, mains half
price, first 80 covers") and the £15 average main are SYNTHETIC demo assumptions; the market price is REAL.
The hedge buys cover up to the worst case (£600) inside the caps, so the offer's cost is fixed. Paper only.

**Practice data for the kit** lives in `.bench/` (gitignored) and is labelled practice wherever it appears. Only
the challenge runs in `docs/challenge/` are quoted as results.
