import { defineConfig, devices } from "@playwright/test";

const deployedBaseUrl = process.env.COOLSPOT_E2E_BASE_URL;
const localBrowser = process.env.CI ? {} : { channel: "chrome" as const };

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: deployedBaseUrl ?? "http://127.0.0.1:3100",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  webServer: deployedBaseUrl
    ? undefined
    : [
        {
          command:
            "..\\.venv\\Scripts\\python.exe -m uvicorn api.app.main:app --app-dir .. --host 127.0.0.1 --port 8100",
          env: { ...process.env, FORTYGUARD_LIVE: "0", EXPLANATION_MODE: "template", OPENROUTER_API_KEY: "" },
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
          url: "http://127.0.0.1:8100/health",
        },
        {
          command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
          env: { ...process.env, API_BASE_URL: "http://127.0.0.1:8100" },
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          url: "http://127.0.0.1:3100",
        },
      ],
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], ...localBrowser } },
  ],
});
