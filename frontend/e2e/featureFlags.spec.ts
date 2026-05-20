/**
 * Feature Flags E2E — FF-30 / FF-PRD-03 §5.4
 *
 * Exercises the full admin-to-hook loop:
 *   SC-1  @ken-e.ai user    → domain_match (targeting rule fires)
 *   SC-2  external user     → default      (no rule matches, flag off)
 *   SC-3  kill switch       → kill_switch  (is_active=false overrides all rules)
 *   SC-4  dev URL override  → dev_override (client-side short-circuit)
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator   : 127.0.0.1:8090
 *   - Firebase Auth emulator: 127.0.0.1:9099
 *     Seeded users: alice@ken-e.ai / password123   (super-admin by email suffix)
 *                   bob@example.com / password123   (regular user)
 *   - FastAPI backend      : 127.0.0.1:8000 (KENE_FF_CACHE_TTL_SECONDS=0)
 *   - Vite dev server      : 127.0.0.1:8080 (VITE_USE_AUTH_EMULATOR=true,
 *                                             VITE_FF_E2E_FIXTURE_FLAGS=e2e_test_flag)
 *
 * Risk mitigations per PRD §9:
 *   - sessionStorage cleared in beforeEach to prevent override bleed.
 *   - IndexedDB (Firebase auth) cleared in signInAs to prevent auth bleed.
 *   - kill-switch scenario uses TTL=0 so the cache is always cold — no fixed wait needed.
 */

import { test, expect } from "@playwright/test";
import {
  seedFlag,
  deleteFlag,
  getIdToken,
  flipKillSwitch,
  signInAs,
  expectHookState,
} from "./helpers";

const FLAG_KEY = "e2e_test_flag";
const HARNESS_PATH = "/__dev__/feature-flag-status";

// ─── Setup / teardown ─────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  // Prevent sessionStorage override bleeding across scenarios (PRD §9 AC-1).
  await page.addInitScript(() => {
    sessionStorage.removeItem("kene.ff-overrides");
  });
});

test.afterEach(async ({ request }) => {
  // Remove the test flag so each test starts with a clean slate.
  await deleteFlag(request, FLAG_KEY);
});

// ─── Scenarios ────────────────────────────────────────────────────────────────

test("SC-1: @ken-e.ai user sees domain_match", async ({ page, request }) => {
  // Seed flag with domain targeting for ken-e.ai.
  await seedFlag(request, FLAG_KEY, {
    email_domains: ["ken-e.ai"],
    default_enabled: false,
  });

  // Sign in as a @ken-e.ai user (Alice).
  await signInAs(page, "alice@ken-e.ai", "password123");

  // Navigate to the dev harness page and assert.
  await page.goto(HARNESS_PATH);
  await expectHookState(page, { enabled: true, reason: "domain_match" });
});

test("SC-2: external user sees default (disabled)", async ({
  page,
  request,
}) => {
  // Same flag — no rule matches bob@example.com.
  await seedFlag(request, FLAG_KEY, {
    email_domains: ["ken-e.ai"],
    default_enabled: false,
  });

  await signInAs(page, "bob@example.com", "password123");
  await page.goto(HARNESS_PATH);
  await expectHookState(page, { enabled: false, reason: "default" });
});

test("SC-3: kill switch propagates to kill_switch", async ({
  page,
  request,
}) => {
  await seedFlag(request, FLAG_KEY, {
    email_domains: ["ken-e.ai"],
    default_enabled: false,
  });

  // Sign in as Alice (super-admin by @ken-e.ai suffix).
  await signInAs(page, "alice@ken-e.ai", "password123");
  await page.goto(HARNESS_PATH);

  // Verify the baseline is domain_match before the kill switch.
  await expectHookState(page, { enabled: true, reason: "domain_match" });

  // Flip is_active=false via the admin API using Alice's token.
  const aliceToken = await getIdToken(request, "alice@ken-e.ai", "password123");
  await flipKillSwitch(request, FLAG_KEY, aliceToken);

  // Trigger a re-evaluation via the refetch button (invalidates TanStack Query).
  // TTL=0 means the backend cache is always cold — no fixed wait needed.
  const responsePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes("/api/v1/feature-flags/evaluate") &&
      resp.status() === 200,
    { timeout: 10_000 },
  );
  await page.click('[data-testid="ff-refetch"]');
  await responsePromise;

  await expect(page.getByTestId("ff-enabled")).toHaveText("false", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("ff-reason")).toHaveText("kill_switch");
});

test("SC-4: dev URL override ?ff.e2e_test_flag=on wins over default", async ({
  page,
  request,
}) => {
  // Bob would normally get default (flag is off for external emails).
  await seedFlag(request, FLAG_KEY, {
    email_domains: ["ken-e.ai"],
    default_enabled: false,
  });

  await signInAs(page, "bob@example.com", "password123");

  // Navigate with the URL override param — the dev override short-circuits
  // server evaluation entirely (VITE_ENVIRONMENT=development in this stack).
  await page.goto(`${HARNESS_PATH}?ff.${FLAG_KEY}=on`);

  await expectHookState(page, { enabled: true, reason: "dev_override" });
});
