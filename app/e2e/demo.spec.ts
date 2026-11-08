import path from "node:path";
import { expect, test, type Page } from "playwright/test";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Refresh the committed docs screenshots only on request (UPDATE_SHOTS=1); the gate must not dirty the tree.
const SHOTS = path.resolve(__dirname, process.env.UPDATE_SHOTS ? "../../docs/screenshots" : "../test-results/shots");

type Proposal = { id: string; status: string; created: number };

async function latestPending(page: Page) {
  const s = await (await page.request.get(`${API}/api/state`)).json();
  const pending = (s.proposals as Proposal[]).filter((p) => p.status === "pending").sort((a, b) => b.created - a.created);
  expect(pending.length, "a pending proposal").toBeGreaterThan(0);
  return pending[0].id;
}

async function hasBadge(page: Page, panel: string) {
  await expect(page.getByTestId(panel).getByTestId("badge").first(), `${panel} has a provenance badge`).toBeVisible();
}

test("owner runs the agent, approves cover, and a lowered cap blocks the next one", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));

  expect((await request.post(`${API}/api/demo/reset`)).ok()).toBeTruthy();

  // Onboarding: identity comes from the API
  await page.goto("/");
  await expect(page.locator("input").first()).toHaveValue("The Faltering Fullback");
  await page.getByRole("button", { name: "Look up my pub" }).click();

  // Agent run over SSE, historical scenario
  await expect(page.getByTestId("mode-scenario")).toHaveAttribute("aria-selected", "true");
  await page.getByTestId("run-start").click();
  await expect(page.getByTestId("run-done")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("step-monitor").getByTestId("model-chip")).toHaveText(/template|gemini/);
  await expect(page.getByTestId("run-rationale")).toBeVisible();
  await page.getByRole("button", { name: "See what it found" }).click();

  // What the agent sees
  await hasBadge(page, "panel-verify");
  await hasBadge(page, "panel-sources");
  await expect(page.getByTestId("panel-sources")).toContainText("Not connected in demo");
  await expect(page.getByTestId("panel-sources").locator('[data-badge="TEST MODE"]')).toBeVisible();
  await page.waitForTimeout(500); // let the step fade-in finish
  await page.screenshot({ path: `${SHOTS}/01-agent-sees.png` });

  // Quiet view by default; S switches to the audit view, where every figure shows its badge and opens its receipt, with the hash chain
  await page.keyboard.press("s");
  await expect(page.getByTestId("audit-switch")).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("panel-verify").getByTestId("badge").nth(1).click();
  await expect(page.getByTestId("receipt-drawer")).toContainText("hash");
  await expect(page.getByTestId("receipt-drawer")).toContainText("companies_house");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("receipt-drawer")).toBeHidden();
  await page.keyboard.press("s");
  await expect(page.getByTestId("audit-switch")).toHaveAttribute("aria-checked", "false");
  await page.getByRole("button", { name: "Confirm details" }).click();

  // Risks
  await hasBadge(page, "panel-risks");
  await page.getByRole("button", { name: "See the impact" }).click();

  // Impact: payday either side of the payroll line, how cover gets there, and the exact table
  await hasBadge(page, "panel-payday");
  await hasBadge(page, "panel-bridge");
  await expect(page.getByTestId("panel-bridge")).toContainText("SYNTHETIC — modelled for a pub of this profile");
  await expect(page.getByTestId("outcomes")).toContainText("Dry");
  await page.getByRole("button", { name: "See the recommendation" }).click();

  // Recommendation with rationale
  await hasBadge(page, "panel-recommendation");
  await expect(page.getByTestId("rationale")).not.toBeEmpty();
  // Match-day offer: a real market price makes the offer a fixed cost
  await hasBadge(page, "panel-offer");
  await expect(page.getByTestId("panel-offer")).toContainText("England v Croatia");
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/02-agent-recommends.png` });
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await page.getByRole("button", { name: "Open dashboard" }).click();

  // Dashboard opens in the owner's Simple view: one sentence, the payday bars, one decision
  await page.waitForURL("**/dashboard");
  await expect(page.getByTestId("simple-headline")).toContainText("Payroll is at risk this weekend.");
  await expect(page.getByTestId("simple-decision")).toContainText("PAPER TRADING — no real orders");
  // Advanced: the full working, approve with limit checks, paper only
  await page.getByTestId("view-switch").click();
  await expect(page.getByTestId("view-switch")).toHaveAttribute("aria-checked", "true");
  const first = await latestPending(page);
  const approval = page.getByTestId("panel-approval");
  await expect(page.getByTestId(`approve-${first}`)).toBeVisible();
  await hasBadge(page, "panel-approval");
  await hasBadge(page, "panel-cashflow");
  await expect(page.getByTestId("panel-cashflow")).toContainText("SYNTHETIC — modelled for a pub of this profile");
  await expect(approval).toContainText("PAPER TRADING — no real orders");
  await expect(approval.getByTestId("check-weekly_spend")).toBeVisible();
  await expect(approval.getByTestId("check-per_market_concentration")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/03-human-approves.png` });

  await page.getByTestId(`approve-${first}`).click();
  await page.getByTestId(`confirm-second-${first}`).click();
  await expect(page.getByTestId(`status-${first}`)).toHaveText("filled");
  await expect(page.getByTestId("filled-note")).toContainText("PAPER");

  // The agent runs again for the same weekend: a new pending proposal
  const rerun = await request.get(`${API}/api/runs/stream?mode=scenario&speed=4`, { timeout: 120_000 });
  expect(await rerun.text()).toContain('"type": "done"');
  await page.reload();
  const second = await latestPending(page);
  await expect(page.getByTestId(`approve-${second}`)).toBeVisible();

  // Owner lowers the weekly cap below the pending cover: it is blocked at once, with the reason
  await page.getByTestId("limit-weekly").fill("30");
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId(`status-${second}`)).toHaveText("blocked");
  await expect(page.getByTestId("blocked-reason")).toContainText("weekly spend");
  await expect(page.getByTestId(`approve-${second}`)).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/04-limit-blocks.png` });

  // The honest backtest moved from the impact step to the dashboard's Backtest page
  await page.getByRole("button", { name: "Backtest", exact: true }).click();
  await expect(page.getByTestId("backtest-honest")).toContainText("does not reduce");

  expect(errors, "console errors").toEqual([]);
});
