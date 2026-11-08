# Deck updates (pitch-v3)

Two parts: slide-by-slide text changes, then every claim the build can't support, with suggested wording.
Numbers come from `docs/backtest-results.md`, `docs/challenge/` and the recorded run in
`fixtures/runs/demo-run.json`.

## Slide by slide

**1. Title**

- Keep the hook. Change the subline to: "An AI agent that reads your till, measures what a washout costs, and
  tells you before Friday's payroll won't clear. Small, capped weather hedges, with you approving every one."
- Fill in `[Team] · Agentverse 2026, Finance track · 8 Nov 2026`.

**2. The problem**

- "The Oak Tree … lost £11,000 to the rain last July" is fictional. Replace it with a real pattern and a
  modelled number:
  - Headline: "£695". Under it: "what one 6 mm wet afternoon takes out of a busy London garden pub's
    weekend (modelled)."
  - Footnote: "SYNTHETIC: modelled for a pub of this profile; real London weather."
- "1 in 8 UK pubs closed in the last 12 months" can't be sourced. Use BBPA: "about 2 pubs closed a day in Q1
  2026; 44,656 pubs at end of 2025" ([BBPA](https://www.beerandpub.com/news-insights-research/news/two-pubs-closed-a-day/)).
- "£3,400 the Six Nations Saturday …" is unsupported, and in our data match days *raise* takings. Cut it, or
  use: "Match days move takings by hundreds of pounds a day: in either direction, depending on the result."
- "7p last Budget's beer duty hike …" doesn't match the record. Duty rose by RPI (3.66%) on 1 Feb 2026, which is
  about 2p a pint on draught at 4.5%. Use: "Duty rose again on 1 Feb 2026 (+3.66%); another +4.55% is announced
  for Feb 2027 (HMRC)."

**3. The customer.** Card 04, "Polymarket + Smarkets live for UK users", is wrong for Polymarket. Use: "Legal UK
venues exist (Smarkets, Betfair). Polymarket prices are public, but UK users can't trade there."

**4. The solution.** Change "sells you a £20 hedge on Polymarket" to "proposes a small capped hedge, priced off
public markets, executed on a UK venue". Change "Reads Toast, Square, Lightspeed POS" to "Reads a till export and
an Open Banking feed (demo: Stripe test mode plus a synthetic Open Banking feed)."

**5. Why an agent.**

- "Orchestrates six external tools": the build has 18 tools across 5 agents. Use: "Five agents, 18 tool calls,
  one plan."
- "Runs 24/7": the build has a scheduled re-check (Fri 09:00, Sat 08:00) in the plan, not a running daemon. Use
  "Re-checks before the weekend."
- Keep "Every action over £50 waits for approval", but note that in the build *every* action waits for
  approval, and over £50 needs a second confirmation.

**6. How it works**

- "in 60 seconds": measured live runs took **35–44 s** end to end (the recorded demo run: 42 s, 8 Nov 2026).
  Use: "in under a minute (about 40 s measured)."
- Replace "Every 1°C below 20°C: −£340/day · R² = 0.74" with: "Each mm of weekend afternoon rain: −£116
  (95% CI −£128 to −£104) · R² 0.92 on held-out months, on synthetic takings."
- Change the source chips to: Companies House · Met Office · Open-Meteo · Polymarket (read-only) · Stripe
  (test) · HMRC duty dates.

**7. The product**

- Change the title to: "The Faltering Fullback, August bank holiday 2026. What the agent sees, says and does."
- Footnote: "Real pub, public data only. Financials are synthetic."
- Screenshots: `docs/screenshots/01-agent-sees.png`, `02-agent-recommends.png`, `03-human-approves.png`.

**8. Architecture**

- Make it read "Data → ADK agents (Gemini 3.8 Flash; Gemini 4 Argon for the rationale) → LP + limit guard in code
  → human approval card → paper exchange".
- Replace "Polymarket order" with "Paper fill (UK venue in production)".
- Replace "0 unverified trades" with: "Every number has a receipt; an append-only, hash-chained audit log."

**9. The moat.**

- "Polymarket + Smarkets + Betfair. Single-venue tools miss best price on 30% of contracts": the 30% is
  unsupported, so cut it.
- "Cross-pub training-data flywheel" is a plan, not a build. Label it "Next".

**10. Market**

- 45,000 is close to BBPA's 44,656 *total* pubs, not "independent & family pubs with gardens". Use "44,656 UK pubs
  (BBPA, end 2025)".
- 8,500 and 120 are unsourced. Label them as assumptions or cut them.
- Fuller's and Greene King reps visiting "every pub weekly" is unsourced, and both are managed or tenanted
  estates, not our customer. Use "brewery and wholesaler reps (to be validated)".

**11. Traction / backtest.** Replace every placeholder. The block is in `docs/backtest-results.md`, "Deck-ready
block":

| Placeholder | Replace with |
|---|---|
| +£1,840 /pub/yr | **+£42 /pub/yr** net (95% CI −£30 to +£146, i.e. break-even), against −£1,514 for hedging every weekend |
| Median £1,220 | Payroll-shortfall weeks: **10.4 a year, with or without our hedge** |
| 95% CI lower £640 | Weeks hedged: **51 of 1,260** pub-weeks |
| Worst month −£340 | Worst week: −£13.7k across the panel; the hedge doesn't move it |
| 2 of 12 losing months | Cut it. No 4-week window lost money before owner drawings |

- Header: "12 synthetic pubs · held-out Nov 2024–Oct 2026 · real London weather".
- Caption: "Synthetic takings driven by real weather; synthetic rain-contract prices with real Polymarket fees.
  Our policy is cheap because it only hedges weeks when payroll is at risk, but at £60-a-market caps it doesn't
  cut shortfall weeks. The warning is the product."
- Add the kit result: "Finance Kit self-serve challenge: cashflow and transactions 40/40 exact, F1 100%; our
  market-timing rule shows no edge (30/30 vs buy-and-hold on real-market windows)." Label it "our own check,
  not official judging".

**12. The ask.** "Two legal prediction markets" is wrong. Use "UK-licensed betting exchanges". "One LA ice-cream
shop pays 43% of their rent…" is unsourced: cut it or source it.

## Claims the build can't support

| Claim (slide) | Problem | Suggested wording |
|---|---|---|
| Polymarket "live for UK users", "UK-legal", "Polymarket order" (3, 4, 8) | Polymarket geoblocks the UK (`/api/geoblock` returned `blocked: true, GB`). We only read public prices. | "Prices from public markets; execution on UK-licensed venues (not connected in the demo). Demo fills are paper." |
| Toast / Square / Lightspeed (4, 6, 10) | No POS integration exists. The demo uses Stripe test charges and synthetic data. | "Reads a till export or card processor (demo: Stripe test mode)." |
| "in 60 seconds" (6) | Measured live: 35–44 s over four runs. Argon latency varies (4–40 s per call). | "Under a minute (about 40 s measured live)." Replay mode is available if wifi fails. |
| "50 UK pubs · 2022–2024 · Polymarket historical prices" (11) | 12 synthetic pubs; test window Nov 2024–Oct 2026; no London rain market exists, so prices are synthetic. | "12 synthetic pubs, real weather, synthetic contract prices with real fees." |
| +£1,840 a pub-year, "saved" (11) | Ours is break-even (+£42, CI −£30 to +£146); hedging every weekend loses £1,514. | Use the real block above. |
| "£11,000 lost to rain", "The Oak Tree" (2, 7) | Fictional. | Real pub, public identity only; modelled numbers labelled synthetic. |
| "Sells you a £20 hedge" (1, 4, 12) | The recorded run proposes one £59.16 position (240 shares at 0.24) on the bank holiday Saturday. That needs a second confirmation (over £50). | "Small, capped hedges (£120 a week cap)". Or show the real proposal. |
| "Runs 24/7, not on a prompt" (5) | The monitor schedules re-checks; no daemon runs in the demo. | "Re-checks before the weekend; notifies only when exposure × price crosses the line" (as designed). |
| "Six Nations / sport hedges", "tariffs, rates" (1, 2, 5) | Built and tested: weather only. Sport and duty are in the regression (sport raises takings; the duty effect isn't significant) but are not hedged. | "Weather today; sport and duty measured, hedges next." |
| "Multi-venue routing … 30% of contracts" (9) | Not built; the figure is unsourced. | Cut it, or "Next: route to the best UK venue." |
| "Cross-pub flywheel" (9) | Not built. | Label "Next". |
| 45,000 / 8,500 / 120 pubs (1, 10, 12) | Only the BBPA total is sourced (44,656). | "44,656 UK pubs (BBPA)". Label the rest as assumptions. |
| "1 in 8 pubs closed", "7p duty hike", "£3,400 Six Nations Saturday" (2) | Unsourced or contradicted (see slide 2). | See slide 2 above. |
