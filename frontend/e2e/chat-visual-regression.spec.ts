/**
 * CH-28 — Visual regression (figma parity) for SessionsSidebar and ChatInterface.
 *
 * Five snapshots, taken inside the mcr.microsoft.com/playwright:v1.49.0-jammy
 * Docker image to produce CI-stable baselines:
 *   1. sidebar-expanded      — SessionsSidebar with active / needs-review / idle sessions
 *   2. sidebar-collapsed     — collapsed rail (64 px) with the same sessions
 *   3. chat-initial          — ChatInterface intro message (initial page load)
 *   4. chat-user-sending     — user message bubble + ThinkingBlock visible (API blocked)
 *   5. chat-assistant-reply  — user message + assistant reply (API mocked)
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator : 127.0.0.1:8090   (seeded: alice-uid, alice@ken-e.ai)
 *   - Auth emulator      : 127.0.0.1:9099
 *   - FastAPI backend    : 127.0.0.1:8000   (KENE_FF_CACHE_TTL_SECONDS=0)
 *   - Vite dev server    : 127.0.0.1:8080
 *
 * Generating baselines:
 *   Run inside the mcr.microsoft.com/playwright:v1.49.0-jammy image:
 *   npx playwright test chat-visual-regression --update-snapshots
 *   Commit the generated files under e2e/__screenshots__/.
 */

import { test, expect } from "@playwright/test";
import { seedFlag, deleteFlag, signInAs } from "./helpers";
import {
  seedChatSession,
  seedAccount,
  cleanupChatSessions,
  buildSelectedOrgAccountScript,
} from "./helpers/chat";

// ─── Test fixtures ────────────────────────────────────────────────────────────

const ALICE_EMAIL = "alice@ken-e.ai";
const ALICE_PASSWORD = "password123";
const ALICE_UID = "alice-uid";
// IDs must match branded-type validators: org_ prefix and acc_ prefix (min 10 chars).
const ORG_ID = "org_e2e-vr";
const ACCOUNT_ID = "acc_e2e-vr";

// Fixed past timestamps to keep screenshots stable across runs.
const T_ACTIVE = "2026-05-22T10:00:00.000Z";
const T_NEEDS_REVIEW = "2026-05-22T09:45:00.000Z";
const T_IDLE = "2026-05-22T09:30:00.000Z";
const T_AGENT_MSG = "2026-05-22T09:50:00.000Z";
// last_viewed_at before the agent message → needs-review
const T_LAST_VIEW_OLD = "2026-05-22T09:40:00.000Z";
// last_viewed_at after the agent message → idle
const T_LAST_VIEW_NEW = "2026-05-22T10:00:00.000Z";

// ─── Setup / teardown ─────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.removeItem("kene.ff-overrides");
  });
});

test.afterEach(async ({ request }) => {
  const results = await Promise.allSettled([
    deleteFlag(request, "chat_v2_enabled"),
    cleanupChatSessions(request, ACCOUNT_ID),
  ]);
  const errors = results
    .filter((r): r is PromiseRejectedResult => r.status === "rejected")
    .map((r) => r.reason as Error);
  if (errors.length > 0) throw new AggregateError(errors, "afterEach cleanup failed");
});

// ─── Shared setup: sign in, enable chat_v2, seed account + sessions ───────────

async function setupChatPage({
  page,
  request,
}: {
  page: Parameters<Parameters<typeof test>[1]>[0]["page"];
  request: Parameters<Parameters<typeof test>[1]>[0]["request"];
}) {
  // Enable chat_v2_enabled globally for this test.
  await seedFlag(request, "chat_v2_enabled", { default_enabled: true });

  // Seed the test account so the backend can resolve it.
  await seedAccount(request, {
    accountId: ACCOUNT_ID,
    ownerUid: ALICE_UID,
    orgId: ORG_ID,
  });

  // Seed 3 sessions: one active, one needs-review, one idle.
  await Promise.all([
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "vr-session-active",
      overrides: {
        title: "Campaign Q3 planning",
        last_message_preview: "Running performance analysis…",
        // last_agent_started_at within 10 min → backend derives is_agent_running=true
        last_agent_started_at: new Date().toISOString(),
        last_agent_message_at: T_ACTIVE,
        last_viewed_at: null,
        updated_at: T_ACTIVE,
        created_at: T_ACTIVE,
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "vr-session-needs-review",
      overrides: {
        title: "Keyword strategy review",
        last_message_preview: "Here are the top 10 keywords for your campaign.",
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: T_LAST_VIEW_OLD,
        updated_at: T_NEEDS_REVIEW,
        created_at: T_NEEDS_REVIEW,
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "vr-session-idle",
      overrides: {
        title: "Budget allocation ideas",
        last_message_preview: "I reviewed your Q2 budget allocation.",
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: T_LAST_VIEW_NEW,
        updated_at: T_IDLE,
        created_at: T_IDLE,
      },
    }),
  ]);

  // Sign in as Alice.
  await signInAs(page, ALICE_EMAIL, ALICE_PASSWORD);

  // Inject the selected org/account into localStorage so the sidebar resolves accountId.
  // addInitScript (not page.evaluate) is used here so the values are written before
  // ANY page-side JavaScript runs on the next navigation. page.evaluate runs AFTER
  // React/Firebase initialize, which means onAuthStateChanged can fire and clear
  // localStorage before the query hook reads it, leaving accountId = null and
  // disabling the sessions fetch. addInitScript bypasses that race entirely.
  await page.addInitScript(
    buildSelectedOrgAccountScript({ orgId: ORG_ID, accountId: ACCOUNT_ID }),
  );
}

// ─── Visual regression tests ──────────────────────────────────────────────────

test("sidebar-expanded", async ({ page, request }) => {
  await setupChatPage({ page, request });

  await page.goto("/chat");

  // Wait for the sidebar to be visible and sessions to load.
  const sidebar = page.locator('[data-testid="sessions-sidebar"]');
  await sidebar.waitFor({ state: "visible" });
  // Wait for at least one session row to appear.
  await page
    .locator('[data-slot="session-list-item"]')
    .first()
    .waitFor({ state: "visible", timeout: 10_000 });

  await expect(sidebar).toHaveScreenshot("sidebar-expanded.png");
});

test("sidebar-collapsed", async ({ page, request }) => {
  await setupChatPage({ page, request });

  await page.goto("/chat");

  // Wait for the sidebar first (uses 30 s default) so the feature flag has time
  // to resolve before the 10 s session-item wait starts. Without this, a slow
  // emulator response after a heavy prior test can starve the flag check.
  await page.locator('[data-testid="sessions-sidebar"]').waitFor({ state: "visible" });

  // Wait for sessions to load first so the collapsed rail shows dots.
  // 30 s allows TanStack Query's retry cycle (up to 3 retries + 5 s polling)
  // to recover from a transiently overloaded Firestore emulator.
  await page
    .locator('[data-slot="session-list-item"]')
    .first()
    .waitFor({ state: "visible", timeout: 30_000 });

  // Collapse the sidebar.
  await page.click('[aria-label="Collapse sessions sidebar"]');

  const sidebar = page.locator('[data-testid="sessions-sidebar"]');
  await sidebar.waitFor({ state: "visible" });

  await expect(sidebar).toHaveScreenshot("sidebar-collapsed.png");
});

test("chat-initial", async ({ page, request }) => {
  await setupChatPage({ page, request });

  await page.goto("/chat");

  const chatInterface = page.locator('[data-testid="chat-interface"]');
  await chatInterface.waitFor({ state: "visible" });
  // Wait for the sidebar (uses 30 s default) so chat_v2_enabled has resolved and
  // the layout is stable before taking the screenshot.
  await page.locator('[data-testid="sessions-sidebar"]').waitFor({ state: "visible" });

  // Wait for the intro message to be rendered.
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="chat-interface"]')
      ?.textContent?.includes("KEN-E"),
  );

  await expect(chatInterface).toHaveScreenshot("chat-initial.png");
});

test("chat-user-sending", async ({ page, request }) => {
  await setupChatPage({ page, request });

  // Block the completions API so the ThinkingBlock stays visible.
  // Initialize to no-op so calling unblock() after an early throw is safe.
  let unblock: () => void = () => {};
  const blocked = new Promise<void>((r) => {
    unblock = r;
  });
  await page.route("**/api/v1/chat/completions", async (route) => {
    await blocked; // hold until we take the screenshot
    await route.abort();
  });

  await page.goto("/chat");

  const chatInterface = page.locator('[data-testid="chat-interface"]');
  await chatInterface.waitFor({ state: "visible" });
  // Wait for the sidebar to be visible — confirms chat_v2_enabled has loaded and
  // the new <Chat /> route is stable (prevents remount between fill and click).
  await page.locator('[data-testid="sessions-sidebar"]').waitFor({ state: "visible" });

  // Type and send a message.
  await page.fill(
    '[aria-label="Chat input"]',
    "What campaigns are performing best?",
  );
  await page.click('[aria-label="Send message"]');

  // Wait for the user message bubble to appear (added synchronously before the fetch).
  await page.waitForFunction(() =>
    document
      .querySelector('[data-testid="chat-interface"]')
      ?.textContent?.includes("What campaigns are performing best?"),
  );

  await expect(chatInterface).toHaveScreenshot("chat-user-sending.png");

  // Unblock so the test can complete cleanly.
  unblock();
});

test("chat-assistant-reply", async ({ page, request }) => {
  await setupChatPage({ page, request });

  // Mock the completions API with a canned SSE response.
  await page.route("**/api/v1/chat/completions", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Transfer-Encoding": "chunked",
      },
      // Each SSE event MUST end with \n\n. Concatenating without separators
      // causes the parser in streamChatCompletion to emit the raw "data: ..."
      // prefix as visible text in the rendered message.
      body: "data: Your Q3 campaign for Brand Awareness is outperforming others with a 3.2× ROAS, driven by the video ad creative.\n\ndata: [DONE]\n\n",
    });
  });

  await page.goto("/chat");

  const chatInterface = page.locator('[data-testid="chat-interface"]');
  await chatInterface.waitFor({ state: "visible" });
  // Wait for the sidebar to be visible — confirms chat_v2_enabled has loaded and
  // the new <Chat /> route is stable (prevents remount between fill and click).
  await page.locator('[data-testid="sessions-sidebar"]').waitFor({ state: "visible" });

  await page.fill(
    '[aria-label="Chat input"]',
    "Which campaign is performing best?",
  );
  await page.click('[aria-label="Send message"]');

  // Wait for the assistant response to appear.
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="chat-interface"]')
        ?.textContent?.includes("ROAS"),
    { timeout: 15_000 },
  );

  await expect(chatInterface).toHaveScreenshot("chat-assistant-reply.png");
});
