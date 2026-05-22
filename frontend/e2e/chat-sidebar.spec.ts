/**
 * CH-28 — Playwright E2E integration tests for SessionsSidebar.
 *
 * Five scenarios:
 *   TC-1  sidebar-loads-within-1s    — sidebar renders ≤1 000 ms after navigation
 *   TC-2  dot-state-rendering        — active=teal, needs-review=coral, idle=empty
 *   TC-3  cross-tab-polling          — status updates propagate via the 5 s poll interval
 *   TC-4  1000-session-pagination    — infinite scroll + heap delta <50 MB
 *   TC-5  mark-read-transition       — needs-review → idle on click (fixme: CH-27)
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
const ORG_ID = "e2e-org-sidebar";
const ACCOUNT_ID = "e2e-account-sb";

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
  await Promise.all([
    deleteFlag(request, "chat_v2_enabled"),
    cleanupChatSessions(request, ACCOUNT_ID),
  ]);
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
  await page.evaluate(
    buildSelectedOrgAccountScript({ orgId: ORG_ID, accountId: ACCOUNT_ID }),
  );
}

// ─── TC-1: Sidebar loads within 1 s ──────────────────────────────────────────

test("TC-1: sidebar-loads-within-1s", async ({ page, request }) => {
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    sessionId: "sb-load-session-01",
    overrides: {
      title: "Load test session",
      updated_at: T_RECENT,
      created_at: T_RECENT,
    },
  });

  await setupAuth({ page, request });

  const start = Date.now();
  await page.goto("/chat");

  // The sidebar must be present in the DOM within 1 000 ms of navigation completing.
  await expect(page.locator('[data-testid="sessions-sidebar"]')).toBeVisible({
    timeout: 1_000,
  });

  const elapsed = Date.now() - start;
  expect(elapsed).toBeLessThan(1_000);
});

// ─── TC-2: Dot-state rendering ────────────────────────────────────────────────

test("TC-2: dot-state-rendering", async ({ page, request }) => {
  // Seed one session in each state.
  await Promise.all([
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      sessionId: "sb-dot-active",
      overrides: {
        title: "Active session",
        is_agent_running: true,
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: null,
        updated_at: T_RECENT,
        created_at: T_RECENT,
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      sessionId: "sb-dot-needs-review",
      overrides: {
        title: "Needs review session",
        is_agent_running: false,
        last_agent_message_at: T_AGENT_MSG,
        last_viewed_at: T_VIEWED_BEFORE,
        updated_at: "2026-05-22T09:56:00.000Z",
        created_at: "2026-05-22T09:56:00.000Z",
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      sessionId: "sb-dot-idle",
      overrides: {
        title: "Idle session",
        is_agent_running: false,
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
  // No status dot in idle state (empty placeholder only).
  await expect(idleRow.locator("[aria-label]")).not.toBeVisible();
});

// ─── TC-3: Cross-tab polling ──────────────────────────────────────────────────

test("TC-3: cross-tab-polling", async ({ page, request, context }) => {
  const sessionId = "sb-poll-session-01";

  // Start with an idle session.
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    sessionId,
    overrides: {
      title: "Polling test session",
      is_agent_running: false,
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
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    sessionId,
    overrides: {
      title: "Polling test session",
      is_agent_running: true,
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

// ─── TC-4: 1000-session pagination + memory ───────────────────────────────────

test("TC-4: 1000-session-pagination", async ({ page, request }) => {
  // Seed 1 000 sessions (batched in the helper to avoid overloading the emulator).
  await seedNChatSessions(request, 1_000, {
    accountId: ACCOUNT_ID,
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

  // Scroll to the bottom to trigger multiple pages of infinite scroll.
  // We stop after 5 scrolls (5 × 20 = 100 sessions loaded) to keep the test fast
  // while still exercising the pagination path.
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press("End");
    // Brief pause for the IntersectionObserver sentinel to trigger fetchNextPage.
    await page.waitForTimeout(800);
  }

  // Verify more sessions loaded (more than the initial page of 20).
  const rowCount = await page
    .locator('[data-slot="session-list-item"]')
    .count();
  expect(rowCount).toBeGreaterThan(20);

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
// fixme: depends on CH-27 (POST /api/v1/chat/conversations/{id}/mark-read)
// The mark-read endpoint is not yet wired from the sidebar click handler.
// Un-fixme and complete when CH-27 ships.

test.fixme("TC-5: mark-read-transition", async ({ page, request }) => {
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    sessionId: "sb-mark-read-session",
    overrides: {
      title: "Mark read test session",
      is_agent_running: false,
      last_agent_message_at: T_AGENT_MSG,
      last_viewed_at: T_VIEWED_BEFORE,
      updated_at: T_RECENT,
      created_at: T_RECENT,
    },
  });

  await setupAuth({ page, request });
  await page.goto("/chat");

  // Confirm the session starts as needs-review.
  const row = page.locator(
    '[data-slot="session-list-item"][data-status="needs-review"]',
  );
  await expect(row).toBeVisible({ timeout: 10_000 });

  // Click the session to open it — this should trigger mark-read.
  await row.click();

  // The dot should transition to idle once mark-read completes.
  await expect(
    page
      .locator('[data-slot="session-list-item"][data-status="idle"]')
      .filter({ hasText: "Mark read test session" }),
  ).toBeVisible({ timeout: 5_000 });
});
