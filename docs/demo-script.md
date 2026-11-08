# Demo script (3 minutes)

**Before you start**

- Run `scripts/demo-reset.sh`.
- Start the app with `scripts/dev.sh` and open http://localhost:3000.
- Keep **Historical scenario** selected. It is an illustrative scenario on real weather, with live models.
- If the venue wifi is bad, switch to **Replay**. It streams a recorded live run with a REPLAY label.

| Time | Click / say | Judging criterion |
|---|---|---|
| 0:00 | "This is The Faltering Fullback in Finsbury Park: a real independent pub with a famous garden. We use only its public data. The money is an illustrative scenario, modelled for a large garden pub, and labelled as such." | Relevance (a specific user) |
| 0:15 | **Onboarding → verify.** Companies House shows Bacchus Inns Ltd active, SIC 56302, with the director matched on the public register. Hover the **Cached** label: source, licence (OGL) and fetch time. | Traceable reasoning |
| 0:35 | **Run the agent.** Five ADK agents stream their tool calls live. Each step shows its model chip (Gemini 3.8 Flash for the tool calls, Gemini 4 Argon for the rationale). It takes about 40 s live. | Ambition and technical quality |
| 1:10 | **The weekend that breaks payroll.** August bank holiday 2026: 2.6 mm was forecast for Saturday afternoon and 6.1 mm fell. Dry, payroll on Fri 4 Sep clears. Wet, it is **£808 short**: a wet afternoon costs this pub about £2,433. | Relevance and impact |
| 1:30 | **Impact: "You could have made payroll."** £591.60 of rain cover pays £2,400 if it rains, so payroll clears with **£1,000 to spare**. If it stays dry, the cover costs £591.60 and payroll still clears with £2,899 to spare. | Impact, stated both ways |
| 1:50 | **Press S.** "Every number on this screen has a receipt." Every figure shows where it came from. Click a number in the rationale: the drawer shows the tool call, inputs, raw source and hash, and the grounding check. "The model writes the words. Python does the maths." | Traceable reasoning |
| 2:05 | **Approve.** The approval card runs the limit checks live (weekly spend, monthly loss, per-market concentration, each with value and cap). Over £50 needs a second confirmation. Fill: PAPER, "PAPER TRADING — no real orders". | Risk controls and oversight |
| 2:20 | **The live control.** Reset and run so a hedge is pending. In **Limits**, lower the weekly cap to £500. The hedge is **blocked at once**: "weekly spend: £591.60 would exceed the £500.00 cap". The audit log shows `limit_block`, and the hash chain verifies. | Risk controls (one control shown live) |
| 2:35 | **The offer card** (on the Recommendation step and on Today; the monitor agent mentions it in the run). "It's already looking at Thursday: England v Croatia. Half-price mains if England lose, first 80 covers: worst case £600. Real market price, so £57 of cover makes that a fixed cost." Don't click it unless asked. | Ambition |
| 2:45 | **Backtest page.** "That weekend is a scenario. Here's 24 held-out months for 12 synthetic pubs: hedging every weekend loses £1.5k a year; ours is break-even, and the warning is what moves payroll." Mention the Finance Kit challenge: 40/40 exact, F1 100%, no market edge. | Testing on unseen data |

If asked "can it trade?": "Paper only. Polymarket blocks UK users, so we read its prices. In production, execution
goes to a UK-licensed venue (Smarkets, Betfair), shown here as not connected."

If asked "are these the pub's numbers?": "No. The pub's identity is real; the money is an illustrative scenario for
a pub of this profile, and the backtest is the evidence."
