import { CASHFLOW } from "./data";

export type Timeline = "today" | "rain" | "year";

export const SETTLES: Record<string, string> = {
  rain: "Sat 12 Jul, 18:00",
  rugby: "Mar 2026",
  duty: "Budget, Nov 2025",
};

export type ForecastDay = {
  dow: string;
  date: number;
  rain: number;
  marker?: string;
  covered?: boolean;
  proposed?: boolean;
};

export const FORECAST: ForecastDay[] = [
  { dow: "Wed", date: 9, rain: 10 },
  { dow: "Thu", date: 10, rain: 15 },
  { dow: "Fri", date: 11, rain: 35 },
  { dow: "Sat", date: 12, rain: 71, marker: "Rain cover", covered: true },
  { dow: "Sun", date: 13, rain: 40, marker: "Football" },
  { dow: "Mon", date: 14, rain: 20 },
  { dow: "Tue", date: 15, rain: 10 },
  { dow: "Wed", date: 16, rain: 5 },
  { dow: "Thu", date: 17, rain: 25 },
  { dow: "Fri", date: 18, rain: 45 },
  { dow: "Sat", date: 19, rain: 64, marker: "Proposed", proposed: true },
  { dow: "Sun", date: 20, rain: 30 },
  { dow: "Mon", date: 21, rain: 15 },
  { dow: "Tue", date: 22, rain: 10 },
];

export const CASH_FORECAST = [
  { wk: "7 Jul", expected: 980, bad: 240 },
  { wk: "14 Jul", expected: 1120, bad: 310 },
  { wk: "21 Jul", expected: 1060, bad: 180 },
  { wk: "28 Jul", expected: 1180, bad: 420 },
  { wk: "4 Aug", expected: 1240, bad: 460 },
  { wk: "11 Aug", expected: 1310, bad: 520 },
  { wk: "18 Aug", expected: 1190, bad: 390 },
  { wk: "25 Aug", expected: 1020, bad: 300 },
];

export type FeedRow = { time: string; text: string; tone?: "positive" | "warning" | "negative" | "accent" };

export const ACTIVITY_TODAY: FeedRow[] = [
  { time: "09:12", text: "Proposed rain cover for Sat 19 Jul (£20). Waiting for your approval.", tone: "warning" },
  { time: "09:08", text: "Polymarket: Sat 12 Jul rain market at 0.11, unchanged" },
  { time: "09:05", text: "Met Office: Sat 12 Jul afternoon rain risk up to 71%", tone: "accent" },
  { time: "09:03", text: "Reconciled yesterday's card settlements with Monzo. Within 0.2%" },
  { time: "09:02", text: "Read 1,214 till transactions from Toast" },
  { time: "08:30", text: "Xero: payroll of £6,840 scheduled for Fri 11 Jul" },
  { time: "07:00", text: "Daily summary sent to mark@theoaktree-se22.co.uk" },
];

export type RainTick = { time: string; actual: number; typical: number; mmh: number };

export const RAIN_TICKS: RainTick[] = [
  { time: "12:00", actual: 0, typical: 0, mmh: 0 },
  { time: "12:30", actual: 210, typical: 240, mmh: 0 },
  { time: "13:00", actual: 480, typical: 520, mmh: 0.2 },
  { time: "13:30", actual: 720, typical: 840, mmh: 1.1 },
  { time: "14:00", actual: 860, typical: 1180, mmh: 3.4 },
  { time: "14:30", actual: 940, typical: 1510, mmh: 5.8 },
  { time: "15:00", actual: 1020, typical: 1860, mmh: 6.2 },
  { time: "15:30", actual: 1140, typical: 2180, mmh: 4.1 },
  { time: "16:00", actual: 1290, typical: 2460, mmh: 1.8 },
  { time: "16:30", actual: 1460, typical: 2720, mmh: 0.4 },
  { time: "17:00", actual: 1720, typical: 2980, mmh: 0 },
  { time: "17:30", actual: 2010, typical: 3240, mmh: 0 },
  { time: "18:00", actual: 2310, typical: 3540, mmh: 0 },
];

export const RAIN_THRESHOLD_MM = 4;
export const RAIN_PAYOUT = 180;

export const rainSoFar = (tick: number) =>
  RAIN_TICKS.slice(0, tick + 1).reduce((a, t) => a + t.mmh * 0.5, 0);

export const RAIN_EVENTS: (FeedRow & { at: number })[] = [
  { at: 0, time: "12:00", text: "Watching rain position: London City, 12:00–18:00, pays above 4mm" },
  { at: 2, time: "12:58", text: "Met Office: heavy rain warning for south-east London, 13:00–17:00", tone: "warning" },
  { at: 3, time: "13:30", text: "Takings 14% below a typical July Saturday" },
  { at: 4, time: "14:10", text: "Garden closed. 42 covers moved inside.", tone: "warning" },
  { at: 5, time: "14:30", text: "Rainfall passed 4mm. Position will pay out when the window closes.", tone: "accent" },
  { at: 7, time: "15:30", text: "Takings 48% below typical. Bar staffing is within plan." },
  { at: 12, time: "18:00", text: "Window closed at 11.5mm. Settlement requested from Polymarket." },
  { at: 12, time: "18:00", text: "Polymarket settled YES. £180 paid to Monzo ••1847.", tone: "positive" },
];

export type BankRow = { time: string; text: string; amount: number };

export const BANK_FEED: BankRow[] = [
  { time: "Sat 11:40", text: "Toast card settlement", amount: 2894 },
  { time: "Fri 17:02", text: "Payroll · 14 staff", amount: -6840 },
  { time: "Fri 09:15", text: "Bidfood", amount: -1212 },
  { time: "Thu 14:20", text: "Fuller's Brewery", amount: -2460 },
];

export const YEAR_CASHFLOW = [...CASHFLOW.slice(24), ...CASHFLOW.slice(0, 24)].map((w, i) => ({
  ...w,
  i,
}));

export const MONTHLY_NET = [
  { m: "Jul", net: 610 },
  { m: "Aug", net: 180 },
  { m: "Sep", net: -120 },
  { m: "Oct", net: 90 },
  { m: "Nov", net: 140 },
  { m: "Dec", net: 60 },
  { m: "Jan", net: 210 },
  { m: "Feb", net: 330 },
  { m: "Mar", net: -340 },
  { m: "Apr", net: 150 },
  { m: "May", net: 230 },
  { m: "Jun", net: 300 },
];

export type HistoryRow = { name: string; venue: string; settled: string; stake: number; payout: number; result: "Paid" | "Expired" };

export const HISTORY: HistoryRow[] = [
  { name: "Rain, Sat 12 Jul", venue: "Polymarket", settled: "12 Jul 2025", stake: 20, payout: 180, result: "Paid" },
  { name: "Rain, Sat 19 Jul", venue: "Polymarket", settled: "19 Jul 2025", stake: 20, payout: 0, result: "Expired" },
  { name: "Rain, Sat 26 Jul", venue: "Polymarket", settled: "26 Jul 2025", stake: 20, payout: 180, result: "Paid" },
  { name: "Rain, Sun 3 Aug", venue: "Polymarket", settled: "3 Aug 2025", stake: 20, payout: 0, result: "Expired" },
  { name: "Rain, Sat 23 Aug", venue: "Polymarket", settled: "23 Aug 2025", stake: 20, payout: 180, result: "Paid" },
  { name: "Beer duty rise in the Budget", venue: "Polymarket", settled: "26 Nov 2025", stake: 15, payout: 0, result: "Expired" },
  { name: "England out before Round 5", venue: "Smarkets", settled: "7 Mar 2026", stake: 20, payout: 0, result: "Expired" },
  { name: "Rain, Sat 30 May", venue: "Polymarket", settled: "30 May 2026", stake: 20, payout: 180, result: "Paid" },
];

export const SYNC: Record<string, string> = {
  toast: "2 min ago",
  monzo: "4 min ago",
  xero: "1 hour ago",
};

export const ACTIVITY_LOG: (FeedRow & { day: string })[] = [
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[0] },
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[1] },
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[2] },
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[3] },
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[4] },
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[5] },
  { day: "Wed 9 Jul 2025", ...ACTIVITY_TODAY[6] },
  { day: "Tue 8 Jul 2025", time: "16:42", text: "Placed 3 positions after your approval. Total stake £55.", tone: "positive" },
  { day: "Tue 8 Jul 2025", time: "16:41", text: "Approval signed by Mark Thorne" },
  { day: "Tue 8 Jul 2025", time: "16:35", text: "Proposed 3 positions: rain, Six Nations, beer duty", tone: "warning" },
  { day: "Tue 8 Jul 2025", time: "16:31", text: "Fitted revenue model. R² 0.74 on held-out year" },
  { day: "Tue 8 Jul 2025", time: "16:29", text: "Imported 5 years of sales, bank and ledger data" },
  { day: "Tue 8 Jul 2025", time: "16:24", text: "Verified The Oak Tree Lordship Lane Ltd (08426417)", tone: "positive" },
];
