# Pub Hedge

Clickable prototype of Pub Hedge: onboarding for an independent pub, then the dashboard it lands on. All data is mocked. The demo pub is The Oak Tree, SE22.

## Run it

```bash
cd app
npm install
npm run dev
```

Open http://localhost:3000. It opens in the light theme; the moon icon in the header switches to dark.

## Flow

Onboarding (`/`)

1. Your business: pub name, postcode, owner.
2. Verification: the agent pulls Companies House, the premises licence and the nearest Met Office station, then checks the director against the owner.
3. Data sources: Toast, Monzo Business (Open Banking) and Xero, all read-only.
4. Risk analysis: five years of sales matched against weather, fixtures and duty changes. Each risk is costed in pounds a year.
5. Impact: last year with and without protection, plus the worst case if nothing pays out.
6. Recommendations: positions sized to the pub's limits, each with its reasoning and the calculation behind it.
7. Review and approve: nothing is placed until the owner signs off.

Dashboard (`/dashboard`)

The timeline control in the top bar steps through three moments: the day after onboarding, a wet Saturday where the rain position pays out, and the first year's results, losing months included.

## Code

- `app/src/lib/data.ts`: pub, agent runs, risks, positions, cashflow
- `app/src/lib/dashboard-data.ts`: forecast, activity feed, rain-day ticks, year-one history
- `app/src/components/onboarding`: wizard steps
- `app/src/components/dashboard`: shell, overview, secondary pages

Next.js 14, Tailwind, Framer Motion, Recharts, IBM Plex.

## Screenshots

See [`docs/screenshots`](docs/screenshots).
