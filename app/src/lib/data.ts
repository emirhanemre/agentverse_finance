export const PUB = {
  name: "The Oak Tree",
  legalName: "The Oak Tree Lordship Lane Ltd",
  owner: "Mark Thorne",
  email: "mark@theoaktree-se22.co.uk",
  postcode: "SE22 8HD",
  address: "48 Lordship Lane, London SE22 8HD",
  companyNo: "08426417",
  incorporated: "14 Mar 2013",
  licence: "860417 · Southwark Council",
  covers: 120,
  gardenCovers: 72,
  station: "Greenwich",
  stationDistance: "4.1 mi",
  vat: "GB 284 1938 22",
} as const;

export type ToolCall = { call: string; result: string };
export type RunStep = { label: string; summary: string; calls: ToolCall[] };

export const VERIFY_RUN: RunStep[] = [
  {
    label: "Fetching details about your business",
    summary: "4 sources",
    calls: [
      { call: 'companies_house.search("The Oak Tree", "SE22")', result: "1 match · 08426417" },
      { call: 'os_places.lookup("SE22 8HD")', result: "48 Lordship Lane" },
      { call: "southwark.licensing.premises(48 Lordship Lane)", result: "Licence 860417 · active" },
      { call: "places.details(The Oak Tree, SE22)", result: "120 covers · garden" },
    ],
  },
  {
    label: "Completing verification",
    summary: "3 checks passed",
    calls: [
      { call: "companies_house.officers(08426417)", result: "Mark Thorne · director" },
      { call: "hmrc.vat.check(GB284193822)", result: "Registered · active" },
      { call: "match(licence_address, registered_address)", result: "Match" },
    ],
  },
  {
    label: "Building your profile",
    summary: "Profile ready",
    calls: [
      { call: "met_office.nearest_station(51.452, -0.068)", result: "Greenwich · 4.1 mi" },
      { call: "profile.create(venue=pub, outdoor_covers=72)", result: "Created" },
    ],
  },
];

export const ANALYSIS_RUN: RunStep[] = [
  {
    label: "Reading your sales history",
    summary: "428,194 transactions",
    calls: [
      { call: "toast.sales.export(2020-07-01, 2025-06-30)", result: "1,827 trading days" },
      { call: "monzo.transactions.reconcile(card_settlements)", result: "Within 0.3% of till" },
      { call: "xero.reports.fixed_costs()", result: "£16,400 / month" },
    ],
  },
  {
    label: "Matching local weather and events",
    summary: "3 datasets joined",
    calls: [
      { call: "met_office.daily(Greenwich, 5y)", result: "Rain, temp, wind" },
      { call: "fixtures.calendar(rugby, football, 2020–2025)", result: "64 match days" },
      { call: "hmrc.duty_rates(beer, 2020–2025)", result: "4 changes" },
    ],
  },
  {
    label: "Finding risks",
    summary: "3 material risks",
    calls: [
      { call: "model.fit(revenue ~ rain + temp + fixture + duty)", result: "R² 0.74 held-out" },
      { call: "risk.isolate(rain, weekend_afternoon)", result: "−£340 per mm" },
      { call: "risk.isolate(six_nations, england_out)", result: "−£2,100 per Saturday" },
      { call: "risk.isolate(duty_change)", result: "−£4,200 per year" },
    ],
  },
  {
    label: "Pricing protection",
    summary: "3 positions sized",
    calls: [
      { call: 'polymarket.markets.search("London rain")', result: "9 markets" },
      { call: 'smarkets.markets.search("Six Nations")', result: "4 markets" },
      { call: "solver.size(spend≤£120/wk, loss≤£400/mo)", result: "3 positions" },
    ],
  },
];

export const PLACE_RUN: RunStep[] = [
  {
    label: "Checking your limits",
    summary: "Within limits",
    calls: [
      { call: "guard.spend(£55 ≤ £120/wk)", result: "Pass" },
      { call: "guard.max_loss(£55 ≤ £400/mo)", result: "Pass" },
      { call: "guard.approval(user=mark.thorne)", result: "Signed" },
    ],
  },
  {
    label: "Placing orders",
    summary: "3 filled",
    calls: [
      { call: "polymarket.order(rain-sat-12-jul, £20)", result: "Filled @ 0.11" },
      { call: "smarkets.order(6n-2026-eng-out-r4, £20)", result: "Filled @ 6.0" },
      { call: "polymarket.order(uk-beer-duty-rise, £15)", result: "Filled @ 0.40" },
    ],
  },
  {
    label: "Setting up monitoring",
    summary: "Watching 6 feeds",
    calls: [
      { call: "monitor.subscribe(toast, monzo, met_office)", result: "Live" },
      { call: "monitor.subscribe(polymarket, smarkets)", result: "Live" },
    ],
  },
];

export type Source = {
  id: string;
  name: string;
  kind: string;
  via: string;
  importing: string;
  total: number;
  result: string;
  icon: "receipt" | "bank" | "layers";
};

export const SOURCES: Source[] = [
  {
    id: "toast",
    name: "Toast",
    kind: "Point of sale",
    via: "OAuth",
    importing: "transactions",
    total: 428194,
    result: "1,827 days · 428,194 transactions",
    icon: "receipt",
  },
  {
    id: "monzo",
    name: "Monzo Business",
    kind: "Bank account",
    via: "Open Banking · TrueLayer",
    importing: "transactions",
    total: 31206,
    result: "5 years · 31,206 transactions",
    icon: "bank",
  },
  {
    id: "xero",
    name: "Xero",
    kind: "Accounting",
    via: "OAuth",
    importing: "ledger entries",
    total: 18342,
    result: "Payroll, rent, suppliers · 18,342 entries",
    icon: "layers",
  },
];

export type Risk = {
  id: string;
  name: string;
  driver: string;
  annualCost: number;
  evidence: string;
  fit: string;
  confidence: "High" | "Medium";
};

export const RISKS: Risk[] = [
  {
    id: "rain",
    name: "Wet weekend afternoons",
    driver: "Weather",
    annualCost: 11000,
    evidence: "Each mm of afternoon rain on a Friday–Sunday costs £340 in margin. The garden is 60% of summer covers.",
    fit: "R² 0.74 · n = 1,827",
    confidence: "High",
  },
  {
    id: "duty",
    name: "Beer duty rises",
    driver: "Policy",
    annualCost: 4200,
    evidence: "The August 2023 rise cost £4,200 over the following year. Prices weren't passed on.",
    fit: "4 changes since 2019",
    confidence: "Medium",
  },
  {
    id: "rugby",
    name: "England out of the Six Nations early",
    driver: "Sport",
    annualCost: 3400,
    evidence: "Takings on a match Saturday drop by £2,100 once England can no longer win.",
    fit: "n = 11 · p = 0.003",
    confidence: "Medium",
  },
];

export type Hedge = {
  id: string;
  name: string;
  venue: "Polymarket" | "Smarkets";
  market: string;
  pays: string;
  stake: number;
  payout: number;
  price: string;
  marketProb: number;
  modelProb: number;
  covers: string;
  rationale: string[];
  basisRisk: number;
  liquidity: string;
};

export const HEDGES: Hedge[] = [
  {
    id: "rain",
    name: "Rain, Saturday afternoon",
    venue: "Polymarket",
    market: "London: more than 4mm of rain, Sat 12 Jul, 12:00–18:00",
    pays: "More than 4mm of rain falls at London City between 12:00 and 18:00 on Saturday 12 July.",
    stake: 20,
    payout: 180,
    price: "0.11",
    marketProb: 0.11,
    modelProb: 0.14,
    covers: "Wet weekend afternoons",
    rationale: [
      "Rain is your largest risk: −£340 in margin for every mm on a weekend afternoon.",
      "A 4mm Saturday costs you about £1,360. The payout covers 13% of that.",
      "The market prices this at 11%. Five years of Greenwich data says 14%.",
      "Settles on Met Office readings, so there's no argument about the outcome.",
    ],
    basisRisk: 0.18,
    liquidity: "£41k matched",
  },
  {
    id: "rugby",
    name: "England out before Round 5",
    venue: "Smarkets",
    market: "Six Nations 2026: England eliminated before final round",
    pays: "England can no longer win the championship before the final weekend.",
    stake: 20,
    payout: 120,
    price: "6.0",
    marketProb: 0.167,
    modelProb: 0.22,
    covers: "England out of the Six Nations early",
    rationale: [
      "An England-out Saturday takes £2,100 less than a matched Saturday (11 cases since 2019).",
      "The payout covers about one lost Saturday of margin at £120.",
      "The exchange implies 17%. Current form and fixtures put it nearer 22%.",
      "Settles on the official tournament table.",
    ],
    basisRisk: 0.24,
    liquidity: "£18k matched",
  },
  {
    id: "duty",
    name: "Beer duty rise in the Budget",
    venue: "Polymarket",
    market: "UK raises beer duty in the Autumn Budget",
    pays: "The Autumn Budget raises duty on draught beer.",
    stake: 15,
    payout: 38,
    price: "0.40",
    marketProb: 0.4,
    modelProb: 0.45,
    covers: "Beer duty rises",
    rationale: [
      "The last rise cost you £4,200 over a year because prices weren't passed on.",
      "This is a partial offset. It doesn't replace pricing decisions.",
      "The market prices a rise at 40%. Treasury briefings point slightly higher.",
      "Held to the Budget, then closed.",
    ],
    basisRisk: 0.31,
    liquidity: "£96k matched",
  },
];

export const ev = (h: Hedge) => h.modelProb * h.payout - h.stake;

export const CASHFLOW = [
  { week: 1, month: "Jan", actual: 420, hedged: 480 },
  { week: 2, month: "Jan", actual: -180, hedged: 310 },
  { week: 3, month: "Jan", actual: 240, hedged: 390 },
  { week: 4, month: "Jan", actual: 180, hedged: 350 },
  { week: 5, month: "Feb", actual: 310, hedged: 420 },
  { week: 6, month: "Feb", actual: -340, hedged: 180 },
  { week: 7, month: "Feb", actual: 150, hedged: 290 },
  { week: 8, month: "Feb", actual: 400, hedged: 480 },
  { week: 9, month: "Mar", actual: 290, hedged: 400 },
  { week: 10, month: "Mar", actual: 580, hedged: 580 },
  { week: 11, month: "Mar", actual: -120, hedged: 240 },
  { week: 12, month: "Mar", actual: 340, hedged: 440 },
  { week: 13, month: "Apr", actual: 520, hedged: 540 },
  { week: 14, month: "Apr", actual: 610, hedged: 620 },
  { week: 15, month: "Apr", actual: 290, hedged: 410 },
  { week: 16, month: "Apr", actual: 720, hedged: 720 },
  { week: 17, month: "May", actual: 840, hedged: 830 },
  { week: 18, month: "May", actual: -210, hedged: 290 },
  { week: 19, month: "May", actual: 910, hedged: 870 },
  { week: 20, month: "May", actual: 780, hedged: 760 },
  { week: 21, month: "Jun", actual: 1040, hedged: 940 },
  { week: 22, month: "Jun", actual: 1120, hedged: 1000 },
  { week: 23, month: "Jun", actual: -480, hedged: 240 },
  { week: 24, month: "Jun", actual: 980, hedged: 920 },
  { week: 25, month: "Jul", actual: 1210, hedged: 1080 },
  { week: 26, month: "Jul", actual: -920, hedged: 180 },
  { week: 27, month: "Jul", actual: -1140, hedged: 220 },
  { week: 28, month: "Jul", actual: -680, hedged: 310 },
  { week: 29, month: "Aug", actual: 1180, hedged: 1050 },
  { week: 30, month: "Aug", actual: 1340, hedged: 1150 },
  { week: 31, month: "Aug", actual: 920, hedged: 880 },
  { week: 32, month: "Aug", actual: -240, hedged: 340 },
  { week: 33, month: "Sep", actual: 680, hedged: 680 },
  { week: 34, month: "Sep", actual: 740, hedged: 720 },
  { week: 35, month: "Sep", actual: 390, hedged: 470 },
  { week: 36, month: "Sep", actual: 520, hedged: 560 },
  { week: 37, month: "Oct", actual: 410, hedged: 480 },
  { week: 38, month: "Oct", actual: -90, hedged: 290 },
  { week: 39, month: "Oct", actual: 340, hedged: 410 },
  { week: 40, month: "Oct", actual: 290, hedged: 380 },
  { week: 41, month: "Nov", actual: 180, hedged: 310 },
  { week: 42, month: "Nov", actual: -260, hedged: 240 },
  { week: 43, month: "Nov", actual: 210, hedged: 330 },
  { week: 44, month: "Nov", actual: 290, hedged: 380 },
  { week: 45, month: "Dec", actual: 540, hedged: 560 },
  { week: 46, month: "Dec", actual: 820, hedged: 790 },
  { week: 47, month: "Dec", actual: 1180, hedged: 1050 },
  { week: 48, month: "Dec", actual: 1620, hedged: 1420 },
];

export const BACKTEST = {
  netBenefit: 1840,
  median: 1220,
  ci95Lower: 640,
  worstMonth: -340,
  losingMonths: 2,
  months: 12,
  spend: 540,
  payouts: 2380,
};

export const WEEKS_BELOW_PAYROLL = {
  actual: CASHFLOW.filter((w) => w.actual < 0).length,
  hedged: CASHFLOW.filter((w) => w.hedged < 0).length,
};

export const AVG_MONTHLY_MARGIN = Math.round(CASHFLOW.reduce((a, w) => a + w.actual, 0) / 12);

export const LIMITS = {
  weeklySpend: 120,
  monthlyLoss: 400,
  approvalOver: 50,
};

export type SetupState = { pubName: string; owner: string; hedges: string[] };

const KEY = "pubhedge.setup";

export function saveSetup(s: SetupState) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(s));
  } catch {}
}

export function loadSetup(): SetupState {
  const fallback = { pubName: PUB.name, owner: PUB.owner, hedges: HEDGES.map((h) => h.id) };
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}
