import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [["html", { outputFolder: "test-results/html" }]]
    : "list",
  use: {
    baseURL: "http://localhost:8080",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: [
      "VITE_USE_AUTH_EMULATOR=true",
      "VITE_FF_E2E_FIXTURE_FLAGS=e2e_test_flag",
      "VITE_ENVIRONMENT=development",
      "npm run dev:development",
    ].join(" "),
    url: "http://localhost:8080",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  outputDir: "test-results",
});
