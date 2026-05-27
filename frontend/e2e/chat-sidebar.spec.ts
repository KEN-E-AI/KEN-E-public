/**
 * Playwright E2E integration tests for SessionsSidebar.
 *
 * Five scenarios:
 *   TC-1  sidebar-loads-within-1s    — sidebar renders ≤1 000 ms after navigation
 *   TC-2  dot-state-rendering        — active=teal, needs-review=coral, idle=empty
 *   TC-3  cross-tab-polling          — status updates propagate via the 5 s poll interval
 *   TC-4  100-session-pagination     — infinite scroll + heap delta <50 MB
 *   TC-5  mark-read-transition       — needs-review → idle via IntersectionObserver on latest assistant message
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator : 127.0.0.1:8090
 *   - Auth emulator      : 127.0.0.1:9099
 *   - FastAPI backend    : 127.0.0.1:8000 (KENE_FF_CACHE_TTL_SECONDS=0)
 *   - Vite dev server    : 127.0.0.1:8080
 *
 * Seeded users:
 *   alice@ken-e.ai / password123  (alice-uid, super_admin)
 */

import { test, expect } from "@playwright/test";
import { seedFlag, deleteFlag, signInAs } from "./helpers";
import {
  seedChatSession,
  seedNChatSessions,
  seedAccount,
  cleanupChatSessions,
  buildSelectedOrgAccountScript,
} from "./helpers/chat";

// ─── Constants ────────────────────────────────────────────────────────────────

const ALICE_EMAIL = "alice@ken-e.ai";
const ALICE_PASSWORD = "password123";
const ALICE_UID = "alice-uid";
// IDs must match branded-type validators: org_ prefix and acc_ prefix (min 10 chars).
const ORG_ID = "org_e2e-sb";
const ACCOUNT_ID = "acc_e2e-sb";

// Fixed timestamps (ISO 8601 UTC).
const T_RECENT = "2026-05-22T10:00:00.000Z";
const T_AGENT_MSG = "2026-05-22T09:55:00.000Z";
const T_VIEWED_BEFORE = "2026-05-22T09:40:00.000Z";
const T_VIEWED_AFTER = "2026-05-22T10:00:00.000Z";

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
  if (errors.length > 0)
    throw new AggregateError(errors, "afterEach cleanup failed");
});

// ─── Shared sign-in + env wiring ──────────────────────────────────────────────

async function setupAuth({
  page,
  request,
}: {
  page: Parameters<Parameters<typeof test>[1]>[0]["page"];
  request: Parameters<Parameters<typeof test>[1]>[0]["request"];
}) {
  await seedFlag(request, "chat_v2_enabled", { default_enabled: true });
  await seedAccount(request, {
    accountId: ACCOUNT_ID,
    ownerUid: ALICE_UID,
    orgId: ORG_ID,
  });
  await signInAs(page, ALICE_EMAIL, ALICE_PASSWORD);
  // addInitScript writes localStorage BEFORE React/Firebase run on the next
  // page load, preventing onAuthStateChanged from clearing selectedOrgAccount
  // before the sessions query hook reads accountId.
  await page.addInitScript(
    buildSelectedOrgAccountScript({ orgId: ORG_ID, accountId: ACCOUNT_ID }),
  );
}

// ─── TC-1: Sidebar loads within 1 s ──────────────────────────────────────────

test("TC-1: sidebar-loads-within-1s", async ({ page, request }) => {
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId: "sb-load-session-01",
    overrides: {
      title: "Load test session",
      updated_at: T_RECENT,
      created_at: T_RECENT,
    },
  });

  await setupAuth({ page, request });

  await page.goto("/chat");

  // The sidebar must be visible within 1 000 ms of navigation completing.
  // This is the authoritative timing check — page.goto resolves at
  // "networkidle", so the 1 s budget is measured from fully-loaded DOM.
  await expect(page.locator('[data-testid="sessions-sidebar"]')).toBeVisible({
    timeout: 1_000,
  });
});

// ─── TC-2: Dot-state rendering ────────────────────────────────────────────────

test("TC-2: dot-state-rendering", async ({ page, request }) => {
  // Seed one session in each state.
  await Promise.all([
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "sb-dot-active",
      overrides: {
        title: "Active session",
        // last_agent_started_at within last 10 min → backend derives is_agent_running=true
        last_agent_started_at: new Date().toISOString(),
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: null,
        updated_at: T_RECENT,
        created_at: T_RECENT,
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "sb-dot-needs-review",
      overrides: {
        title: "Needs review session",
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: T_VIEWED_BEFORE,
        updated_at: "2026-05-22T09:56:00.000Z",
        created_at: "2026-05-22T09:56:00.000Z",
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "sb-dot-idle",
      overrides: {
        title: "Idle session",
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: T_VIEWED_AFTER,
        updated_at: "2026-05-22T09:30:00.000Z",
        created_at: "2026-05-22T09:30:00.000Z",
      },
    }),
  ]);

  await setupAuth({ page, request });
  await page.goto("/chat");

  // Wait for session rows to load.
  await page
    .locator('[data-slot="session-list-item"]')
    .first()
    .waitFor({ state: "visible", timeout: 10_000 });

  // active: data-status="active"
  const activeRow = page.locator(
    '[data-slot="session-list-item"][data-status="active"]',
  );
  await expect(activeRow).toBeVisible();
  // teal dot — aria-label "Agent working"
  await expect(activeRow.locator('[aria-label="Agent working"]')).toBeVisible();

  // needs-review: data-status="needs-review"
  const needsReviewRow = page.locator(
    '[data-slot="session-list-item"][data-status="needs-review"]',
  );
  await expect(needsReviewRow).toBeVisible();
  // coral dot — aria-label "Unread reply"
  await expect(
    needsReviewRow.locator('[aria-label="Unread reply"]'),
  ).toBeVisible();

  // idle: data-status="idle"
  const idleRow = page.locator(
    '[data-slot="session-list-item"][data-status="idle"]',
  );
  await expect(idleRow).toBeVisible();
  // Idle state renders an empty placeholder div with no aria-label.
  await expect(idleRow.locator("[aria-label]")).not.toBeAttached();
});

// ─── TC-3: Cross-tab polling ──────────────────────────────────────────────────

test("TC-3: cross-tab-polling", async ({ page, request }) => {
  const sessionId = "sb-poll-session-01";

  // Start with an idle session.
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId,
    overrides: {
      title: "Polling test session",
      last_agent_message_at: null,
      last_viewed_at: null,
      updated_at: T_RECENT,
      created_at: T_RECENT,
    },
  });

  await setupAuth({ page, request });
  await page.goto("/chat");

  // Wait for the session row to appear as idle.
  await page
    .locator(`[data-slot="session-list-item"][data-status="idle"]`)
    .filter({ hasText: "Polling test session" })
    .waitFor({ state: "visible", timeout: 10_000 });

  // Simulate a "second tab" update: patch the Firestore doc to mark the agent as running.
  // last_agent_started_at set to now (within 10-min threshold) so the backend derives
  // is_agent_running=true on the next poll.
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId,
    overrides: {
      title: "Polling test session",
      last_agent_started_at: new Date().toISOString(),
      last_agent_message_at: T_RECENT,
      last_viewed_at: null,
      updated_at: new Date().toISOString(),
      created_at: T_RECENT,
    },
  });

  // The sidebar polls every 5 s. Wait up to 12 s for the dot to change.
  await expect(
    page
      .locator(`[data-slot="session-list-item"][data-status="active"]`)
      .filter({ hasText: "Polling test session" }),
  ).toBeVisible({ timeout: 12_000 });
});

// ─── TC-4: 100-session pagination + memory ────────────────────────────────────

test("TC-4: 100-session-pagination", async ({ page, request }) => {
  // 100 sessions give 5 full pages of 20, which is sufficient to exercise the
  // infinite-scroll + sliding-window pagination path. Seeding 1 000 sessions
  // caused the Firestore emulator cleanup to briefly degrade subsequent tests
  // in the combined suite.
  await seedNChatSessions(request, 100, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    idPrefix: "sb-bulk-session-",
    overrides: (i) => ({
      title: `Bulk session ${i}`,
      updated_at: new Date(Date.now() - i * 1_000).toISOString(),
      created_at: new Date(Date.now() - i * 1_000).toISOString(),
    }),
  });

  await setupAuth({ page, request });
  await page.goto("/chat");

  // Wait for the first page to render.
  await page
    .locator('[data-slot="session-list-item"]')
    .first()
    .waitFor({ state: "visible", timeout: 30_000 });

  // Capture baseline heap.
  // performance.memory is Chromium-only — skip measurement gracefully on other browsers.
  const heapBefore: number | undefined = await page.evaluate(
    () => (performance as any).memory?.usedJSHeapSize,
  );

  // Scroll the Radix ScrollArea viewport to the bottom to trigger the
  // IntersectionObserver sentinel. keyboard.press("End") scrolls the
  // focused element (often <body>), not the inner scroll container.
  // We do 5 scroll-to-bottom iterations (5 × 20 = ~100 sessions loaded)
  // to exercise the pagination path without seeding all 1 000 sessions
  // through the UI.
  for (let i = 0; i < 5; i++) {
    await page.evaluate(() => {
      const viewport = document.querySelector(
        '[data-testid="sessions-sidebar"] [data-radix-scroll-area-viewport]',
      );
      if (viewport) viewport.scrollTop = viewport.scrollHeight;
    });
    // 1 200 ms exceeds the 1 000 ms rate-limit inside the IntersectionObserver
    // callback so every iteration can trigger fetchNextPage independently.
    await page.waitForTimeout(1_200);
  }

  // useChatSessions uses maxPages:1 (sliding window) — only one page is retained
  // at a time, so row count stays at ~20 and the *specific* visible page depends
  // on how many of the 5 scrolls successfully triggered a fetch. Pinning a
  // single index (e.g. "Bulk session 20") races the sliding window: after 2+
  // successful paginations that row is already discarded. Instead, wait for
  // *any* row with index ≥ 20 to appear: `[2-9]\d` covers 20–99 (the valid
  // indices in this 100-session test) and `\d{3,}` is defensive for larger
  // seeds. The pattern cannot match indices 0–19 — `[2-9]\d` requires the
  // first digit to be 2–9 and `\d{3,}` requires 3+ digits — so if pagination
  // never advanced, the visible rows (0–19) won't match and the assertion
  // correctly fails.
  await expect(
    page
      .locator('[data-slot="session-list-item"]')
      .filter({ hasText: /Bulk session ([2-9]\d|\d{3,})/ }),
  ).toBeVisible({ timeout: 10_000 });

  // Heap delta check (Chromium only).
  const heapAfter: number | undefined = await page.evaluate(
    () => (performance as any).memory?.usedJSHeapSize,
  );
  if (heapBefore !== undefined && heapAfter !== undefined) {
    const deltaBytes = heapAfter - heapBefore;
    const deltaMiB = deltaBytes / (1024 * 1024);
    expect(deltaMiB).toBeLessThan(50);
  }
});

// ─── TC-5: Mark-read transition ───────────────────────────────────────────────
// Exercises the IntersectionObserver-based mark-read mechanism:
// open a needs-review session, receive an assistant reply (via mocked SSE),
// let the auto-scroll bring the reply into view, wait ≥500 ms for the IO
// threshold, and assert that POST /mark-read fires and the sidebar dot flips
// from needs-review to idle.
//
// Regression guard for the IntersectionObserver re-attach behavior: it would
// fail if the observer stopped re-binding to the latest assistant message node
// (the defect that caused mark-read never to fire for in-session replies).

test("TC-5: mark-read-transition", async ({ page, request }) => {
  const sessionId = "sb-mark-read-session";

  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId,
    overrides: {
      title: "Mark read test session",
      last_agent_message_at: T_AGENT_MSG,
      last_viewed_at: T_VIEWED_BEFORE,
      updated_at: T_RECENT,
      created_at: T_RECENT,
    },
  });

  await setupAuth({ page, request });

  // Mock the SSE streaming endpoint so the test doesn't block on real LLM
  // latency. The mock returns a single chunk that the streamChatCompletion
  // generator parses into the text "Mocked reply", followed by [DONE].
  await page.route("**/api/v1/chat/completions", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
      },
      body: "data: Mocked reply\n\ndata: [DONE]\n\n",
    });
  });

  // Arm the request listener before navigation so no mark-read request can
  // slip through before the listener is live.
  const markReadPromise = page.waitForRequest(
    (req) =>
      req.url().includes(`/conversations/${sessionId}/mark-read`) &&
      req.method() === "POST",
    { timeout: 15_000 },
  );

  await page.goto(`/chat?session=${sessionId}`);

  // Confirm the session is in needs-review state before we interact.
  await expect(
    page
      .locator('[data-slot="session-list-item"][data-status="needs-review"]')
      .filter({ hasText: "Mark read test session" }),
  ).toBeVisible({ timeout: 10_000 });

  // Send a message to produce an assistant reply.
  await page.locator('[aria-label="Chat input"]').fill("Hello");
  await page.locator('[aria-label="Send message"]').click();

  // Wait for the mocked assistant reply to appear. The chat container
  // auto-scrolls to the bottom after each message, keeping the latest reply
  // in the viewport. useMarkRead arms an IntersectionObserver on the latest
  // assistant message node; once it has been continuously visible for ≥500 ms
  // the POST /mark-read is dispatched.
  await expect(page.getByText("Mocked reply")).toBeVisible({
    timeout: 10_000,
  });
  // 600 ms exceeds the 500 ms IO visibility threshold.
  await page.waitForTimeout(600);

  // Assert that mark-read was dispatched to the backend.
  await markReadPromise;

  // After mark-read updates last_viewed_at in Firestore, the sessions query
  // refetches and the sidebar dot must transition to idle.
  await expect(
    page
      .locator('[data-slot="session-list-item"][data-status="idle"]')
      .filter({ hasText: "Mark read test session" }),
  ).toBeVisible({ timeout: 8_000 });
});
