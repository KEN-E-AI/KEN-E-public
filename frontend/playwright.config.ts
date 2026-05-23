import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // 60 s per test (default is 30 s): the chat-page render is multi-step
  // (auth → feature-flag eval → session fetch → list render) and runs against
  // a single-worker CI stack with the FF cache disabled, so the default cap
  // collides with the inner waitFor budgets. Fast specs finish well under this.
  timeout: 60_000,
  workers: 1,
  reporter: process.env.CI
    ? [["html", { outputFolder: "test-results/html" }]]
    : "list",
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFileName}/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
      animations: "disabled",
      caret: "hide",
    },
  },
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
    // Invoke `vite` directly (not `npm run dev:development`) so the dev
    // server starts without `scripts/resolve-secrets.js`, which requires
    // gcloud + a Secret Manager service account. The E2E suite only talks
    // to the local Firebase emulator, so placeholder Firebase config is
    // sufficient — initializeApp() just needs the shape to be valid.
    command: [
      // Explicitly override any local .env.development.local or .env.local
      // that may set VITE_AUTH_BYPASS=true — that bypass breaks signInAs()
      // because the stub auth object doesn't implement signInWithEmailAndPassword.
      "VITE_AUTH_BYPASS=false",
      "VITE_API_BASE_URL=http://127.0.0.1:8000",
      "VITE_ENVIRONMENT=development",
      "VITE_USE_AUTH_EMULATOR=true",
      "VITE_FF_E2E_FIXTURE_FLAGS=e2e_test_flag",
      "VITE_FIREBASE_API_KEY=test-api-key",
      "VITE_FIREBASE_AUTH_DOMAIN=test-project.firebaseapp.com",
      "VITE_FIREBASE_PROJECT_ID=test-project",
      "VITE_FIREBASE_STORAGE_BUCKET=test-project.appspot.com",
      "VITE_FIREBASE_MESSAGING_SENDER_ID=test-sender",
      "VITE_FIREBASE_APP_ID=test-app",
      "npx vite --mode development --host 127.0.0.1 --port 8080",
    ].join(" "),
    url: "http://127.0.0.1:8080",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  outputDir: "test-results",
});
