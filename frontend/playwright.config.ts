import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: { baseURL: "http://127.0.0.1:3100", channel: process.env.PLAYWRIGHT_CHANNEL || "chrome", headless: true, trace: "retain-on-failure", screenshot: "only-on-failure", serviceWorkers: "block" },
  webServer: {
    command: "node scripts/e2e-server.mjs",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: false,
    timeout: 120000,
    env: { PITCHPREP_E2E: "1", NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:3100" },
  },
});
