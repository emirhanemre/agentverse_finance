import { defineConfig, devices } from "playwright/test";

// Assumes the Pub Hedge API is already running on :8000 (NEXT_PUBLIC_API_URL).
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    viewport: { width: 1600, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // PW_VIDEO=1 records the demo path (docs/demo-walkthrough.webm is made this way)
    video: process.env.PW_VIDEO ? { mode: "on", size: { width: 1600, height: 1000 } } : "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } } }],
  webServer: {
    command: "npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
