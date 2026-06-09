import { chromium, type FullConfig } from "@playwright/test";
import { signInAs } from "./helpers";

// Seeded by deployment/ci/scripts/start_e2e_stack.sh.
const ALICE_EMAIL = "alice@ken-e.ai";
const ALICE_PASSWORD = "password123";

// The cold first sign-in can exceed even the 45s per-test signInAs ceiling under
// the AH-151 parallel-DAG CPU contention (AH-159), so give the warm-up a wide
// budget and one retry for transient stack-readiness.
const WARMUP_REDIRECT_TIMEOUT_MS = 180_000;
// 3 attempts: the first sign-in often fails on transient stack readiness (the
// auth-emulator/backend warming behind the cold Vite compile) and succeeds once
// warm — observed in CI (AH-159). Failed attempts return fast, so extra retries
// are cheap insurance against a both-attempts-fail build failure.
const WARMUP_ATTEMPTS = 3;
const FALLBACK_BASE_URL = "http://localhost:8080";

/**
 * CI-only stack warm-up (AH-159).
 *
 * The e2e webServer runs Vite in dev mode, which compiles the app's module graph
 * lazily on first navigation. Under the AH-151 parallel-DAG CPU contention that
 * first compile — plus the cold Firebase-auth-emulator and cold FastAPI — can
 * exceed the 45s per-test signInAs redirect ceiling, failing whichever spec runs
 * first. Absorb that cold-start here, before any test counts, with a wide budget
 * so the suite proper starts warm.
 *
 * No-op outside CI: local runs reuse a hot dev server (reuseExistingServer), so a
 * warm-up sign-in would only add latency.
 */
async function globalSetup(config: FullConfig): Promise<void> {
  if (!process.env.CI) return;

  const baseURL = config.projects[0]?.use?.baseURL ?? FALLBACK_BASE_URL;
  const browser = await chromium.launch();
  try {
    let lastError: unknown;
    for (let attempt = 1; attempt <= WARMUP_ATTEMPTS; attempt++) {
      const context = await browser.newContext({ baseURL });
      // This is the deliberate cold path: the first page.goto pays the Vite
      // dev-mode compile of the sign-in route, so raise the default navigation
      // ceiling well above the 30s default.
      context.setDefaultNavigationTimeout(WARMUP_REDIRECT_TIMEOUT_MS);
      try {
        const page = await context.newPage();
        await signInAs(page, ALICE_EMAIL, ALICE_PASSWORD, {
          redirectTimeoutMs: WARMUP_REDIRECT_TIMEOUT_MS,
        });
        console.log(
          `[global-setup] Stack warm-up sign-in succeeded (attempt ${attempt}).`,
        );
        return;
      } catch (error) {
        lastError = error;
        console.warn(
          `[global-setup] Warm-up sign-in attempt ${attempt} failed; ${
            attempt < WARMUP_ATTEMPTS ? "retrying" : "giving up"
          }.`,
        );
      } finally {
        await context.close();
      }
    }
    throw new Error(
      `[global-setup] Stack warm-up failed after ${WARMUP_ATTEMPTS} attempts: ${String(
        lastError,
      )}`,
    );
  } finally {
    await browser.close();
  }
}

export default globalSetup;
