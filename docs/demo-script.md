# Demo script (3 minutes)

**Before you start**

- Run `scripts/demo-reset.sh`.
- Start the app with `scripts/dev.sh` and open http://localhost:3000.
- Keep **Historical scenario** selected. It is deterministic data with live models.
- If the venue wifi is bad, switch to **Replay**. It streams a recorded live run with a REPLAY badge.

| Time | Click / say | Judging criterion |
|---|---|---|
| 0:00 | "This is The Faltering Fullback in Finsbury Park: a real independent pub with a famous garden. We use only its public data. Every pound you'll see is synthetic, modelled for a pub like it, and labelled." Point at the SYNTHETIC label. | Relevance (a specific user) |
| 0:15 | **Onboarding → verify.** Companies House shows Bacchus Inns Ltd active, SIC 56302, with the director matched on the public register. Click the **REAL · CACHED** badge: source, licence (OGL) and fetch time. | Traceable reasoning |
| 0:35 | **Run the agent.** Five ADK agents stream their tool calls live. Each step shows its model chip (Gemini 3.8 Flash for the tool calls, Gemini 4 Argon for the rationale). Each tool row has a provenance badge. It takes about 35 s live. | Ambition and technical quality |
| 1:10 | **The failure that hurts.** August bank holiday 2026: 2.6 mm was forecast for Saturday afternoon and 6.1 mm fell. The cashflow view shows Friday 4 Sep payroll **won't clear**: short about £2.5k even if it stays dry, and about £3.5k if the weekend is wet. "That's the call nobody makes to a landlord on a Thursday." | Relevance and impact |
| 1:35 | **What the hedge does, both ways.** If it's wet, the hedge pays £240 and the shortfall falls by about £181. If it's dry, the hedge costs £59 and the shortfall grows by that much. "It's small and capped, and it doesn't fix the cash gap. The warning does." | Testing (stated uncertainty) and honesty |
| 1:55 | **Click a number in the rationale.** The receipt drawer shows the tool call, its inputs, the raw source and the hash. The grounding check shows every number in the model's text was found in a tool output. "The model writes the words. Python does the maths." | Traceable reasoning |
| 2:10 | **Approve.** The approval card runs the limit checks live: weekly spend, monthly loss and per-market concentration, each with its value and cap. Over £50 needs a second confirmation. Fill: PAPER, "PAPER TRADING — no real orders". | Risk controls and oversight |
| 2:25 | **The live control.** Re-run, or reset and run, so a hedge is pending. In **Limits**, lower the weekly cap to £30. The pending hedge is **blocked at once**, with the reason "weekly spend: £59.16 would exceed the £30.00 cap". The audit log shows `limit_block`, and the hash chain verifies. | Risk controls (one control shown live) |
| 2:45 | **Backtest panel.** "On 24 held-out months for 12 synthetic pubs, hedging every weekend loses £1.5k a year. Ours is break-even, but it does **not** reduce payroll-shortfall weeks at these caps. We're telling you that rather than a made-up +£1,840." Mention the Finance Kit challenge: 40/40 exact, F1 100%, no market edge. | Testing on unseen data |

If asked "can it trade?": "Paper only. Polymarket blocks UK users, so we read its prices. In production, execution
goes to a UK-licensed venue (Smarkets, Betfair), shown here as not connected."
