/**
 * Playwright E2E integration tests for the Chat Categories flow (CH-PRD-03).
 *
 * Four scenarios (PRD §8 E2E rows, CH-42 acceptance gate):
 *   SC-1  create → assign → filter → delete → re-appear under "All sessions" with no label
 *   SC-2  delete category while status view is open on a session carrying that category
 *   SC-3  search + filter combo — AC-7 reinforcement
 *   SC-4  flag off — category surface absent, server returns 404
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator : 127.0.0.1:8090
 *   - Auth emulator      : 127.0.0.1:9099
 *   - FastAPI backend    : 127.0.0.1:8000 (KENE_FF_CACHE_TTL_SECONDS=0)
 *   - Vite dev server    : 127.0.0.1:8080
 *
 * Seeded users:
 *   alice@ken-e.ai / password123  (alice-uid, super_admin)
 *
 * Design decisions:
 *   - No mocking for category endpoints — the live FastAPI + Firestore emulator stack
 *     exercises the real POST/GET/DELETE /categories and PUT /conversations/{id}/category
 *     paths (contrast with chat-todos-and-artifacts.spec.ts which mocks GCS-backed routes).
 *   - SC-4 omits seedFlag(chat_categories_enabled) entirely, keeping both client and
 *     server in flag-off state (AD-4 in the CH-42 implementation plan).
 *   - search_text is pre-seeded in SC-3 to avoid requiring an API-round-trip for the
 *     casefold denormalization (AD-5 / D7).
 *   - Selectors prefer role/aria attributes (CH-37's a11y contract) over data-testid;
 *     structural anchors use data-testid where CH-37 / CH-40 explicitly expose them (D2/D3).
 */

import { test, expect } from "@playwright/test";
import { seedFlag, deleteFlag, getIdToken, signInAs } from "./helpers";
import {
  seedChatSession,
  seedAccount,
  cleanupChatSessions,
  cleanupChatCategories,
  buildSelectedOrgAccountScript,
} from "./helpers/chat";

// ─── Constants ────────────────────────────────────────────────────────────────

const ALICE_EMAIL = "alice@ken-e.ai";
const ALICE_PASSWORD = "password123";
const ALICE_UID = "alice-uid";
const ORG_ID = "org_e2e-cat";
const ACCOUNT_ID = "acc_e2e-cat";

// Base URL for direct API calls in the SC-4 server probe and SC-2 pre-seeding.
const API_BASE = "http://127.0.0.1:8000";

// ─── Setup / teardown ─────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.removeItem("kene.ff-overrides");
  });
});

test.afterEach(async ({ request }) => {
  const results = await Promise.allSettled([
    deleteFlag(request, "chat_v2_enabled"),
    deleteFlag(request, "chat_categories_enabled"),
    cleanupChatSessions(request, ACCOUNT_ID),
    cleanupChatCategories(request, ALICE_UID),
  ]);
  const errors = results
    .filter((r): r is PromiseRejectedResult => r.status === "rejected")
    .map((r) => r.reason as Error);
  if (errors.length > 0)
    throw new AggregateError(errors, "afterEach cleanup failed");
});

// ─── Shared setup helper ──────────────────────────────────────────────────────

/**
 * Seed flags, account, sign in Alice, and inject the selected-org localStorage
 * script so React sees the account as already selected.
 *
 * `withCategoriesFlag` controls whether chat_categories_enabled is seeded.
 * SC-4 passes false (or omits) to exercise the flag-off path (AD-4).
 */
async function setupBaseStack({
  page,
  request,
  withCategoriesFlag = true,
}: {
  page: Parameters<Parameters<typeof test>[1]>[0]["page"];
  request: Parameters<Parameters<typeof test>[1]>[0]["request"];
  withCategoriesFlag?: boolean;
}) {
  await seedFlag(request, "chat_v2_enabled", { default_enabled: true });
  if (withCategoriesFlag) {
    await seedFlag(request, "chat_categories_enabled", {
      default_enabled: true,
    });
  }
  await seedAccount(request, {
    accountId: ACCOUNT_ID,
    ownerUid: ALICE_UID,
    orgId: ORG_ID,
  });
  await signInAs(page, ALICE_EMAIL, ALICE_PASSWORD);
  // addInitScript runs BEFORE the next page load so localStorage is set before
  // React/Firebase reads it (prevents onAuthStateChanged from clearing the
  // selected account before the sessions query hook reads accountId).
  await page.addInitScript(
    buildSelectedOrgAccountScript({ orgId: ORG_ID, accountId: ACCOUNT_ID }),
  );
}

// ─── SC-1: Create → assign → filter → delete → re-appear ─────────────────────
//
// PRD §7 ACs covered: AC-1 (create), AC-3 (assign), AC-5 (delete),
// AC-6 (filter narrowing), AC-8 (trash-icon confirm), AC-11 (flag on).

// Re-enabled in CH-64. Root cause: the CI Playwright image does not honour
// prefers-reduced-motion by default, so Radix DropdownMenu portal animations
// run at full speed in CI while the dev machine's browser collapses them.
// Fix: `reducedMotion: "reduce"` in playwright.config.ts triggers the repo's
// src/index.css:524 @media(prefers-reduced-motion) block (animation/transition
// duration → 1ms), plus `[data-state="open"]` open-state signal replaces
// the less-deterministic getByRole("menu").toBeVisible() wait.
test("SC-1: create → assign → filter → delete → session re-appears under All sessions with no label", async ({
  page,
  request,
}) => {
  // Seed two sessions: one that will be categorized, one as control.
  await Promise.all([
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "cat-sc1-uncat",
      overrides: {
        title: "Uncategorized session SC1",
        updated_at: new Date(Date.now() - 2_000).toISOString(),
        created_at: new Date(Date.now() - 2_000).toISOString(),
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "cat-sc1-categorized",
      overrides: {
        title: "To-be-categorized session SC1",
        updated_at: new Date(Date.now() - 1_000).toISOString(),
        created_at: new Date(Date.now() - 1_000).toISOString(),
      },
    }),
  ]);

  await setupBaseStack({ page, request, withCategoriesFlag: true });
  await page.goto("/chat");

  // ── Step 1: Wait for sidebar and assert category filter dropdown is present.
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  // The filter dropdown trigger must be present when the flag is on.
  const filterTrigger = page.locator(
    '[data-testid="categories-dropdown-filter-trigger"]',
  );
  await expect(filterTrigger).toBeVisible({ timeout: 10_000 });

  // ── Step 2: Open the filter dropdown and create "Q3 Campaigns".
  await filterTrigger.click();
  // Wait for the Radix portal to reach data-state="open" on the Content node
  // before reaching into the menu. data-state="open" is the canonical signal
  // that Radix has promoted the content past the entering-animation
  // pointer-events lock (more deterministic than getByRole("menu").toBeVisible,
  // which fires as soon as the portal is in the DOM rather than when interactive).
  await expect(
    page.locator('[data-slot="dropdown-menu-content"][data-state="open"]'),
  ).toBeVisible({ timeout: 15_000 });
  // The "+ New category" create control renders as role="button" with accessible
  // name "New category" — the "+" is a decorative icon with no accessible text.
  const newCategoryButton = page.getByRole("button", {
    name: /New category/i,
  });
  await newCategoryButton.waitFor({ state: "visible", timeout: 15_000 });
  await newCategoryButton.click();

  // The inline create form opens inside the dropdown.
  // Use getByRole("textbox") + accessible name because the input's HTML
  // placeholder ("Category name…") differs from its aria-label ("New category
  // name") — getByPlaceholder would not match.
  const nameInput = page.getByRole("textbox", { name: /new category name/i });
  await nameInput.waitFor({ state: "visible", timeout: 5_000 });
  await nameInput.fill("Q3 Campaigns");
  await nameInput.press("Enter");

  // After creation the new option should appear in the menu.
  await expect(
    page.getByRole("menuitem", { name: "Q3 Campaigns" }),
  ).toBeVisible({ timeout: 8_000 });

  // Close the dropdown by pressing Escape.
  await page.keyboard.press("Escape");

  // ── Step 3: Open the categorized session and assign "Q3 Campaigns" via the
  // status-view assign dropdown (CH-40 slot).
  await page.goto(`/chat?session=cat-sc1-categorized`);
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  // Toggle to status view.
  await page.click('[aria-label="Toggle view"]');

  // Scope to the status-view container to avoid matching the sidebar filter.
  const statusViewSlot = page.locator(
    '[data-testid="status-view-category-assign-slot"]',
  );
  await statusViewSlot.waitFor({ state: "visible", timeout: 10_000 });

  // Open the assign dropdown and select "Q3 Campaigns".
  const assignTrigger = statusViewSlot.locator(
    '[data-testid="categories-dropdown-assign-trigger"]',
  );
  await assignTrigger.click();
  await page.getByRole("menuitem", { name: "Q3 Campaigns" }).click();

  // The assign trigger should now reflect the selected category.
  await expect(assignTrigger).toContainText("Q3 Campaigns", { timeout: 8_000 });

  // ── Step 4: Return to sidebar, apply the "Q3 Campaigns" filter.
  await page.goto("/chat");
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  await filterTrigger.click();
  await page.getByRole("menuitem", { name: "Q3 Campaigns" }).click();

  // Sidebar should narrow to exactly one session (the categorized one).
  await expect(page.locator('[data-slot="session-list-item"]')).toHaveCount(1, {
    timeout: 10_000,
  });
  await expect(
    page.locator('[data-slot="session-list-item"]').filter({
      hasText: "To-be-categorized session SC1",
    }),
  ).toBeVisible();

  // Wait for the filter dropdown menu to fully detach from the DOM after the
  // Step 4 DropdownMenuItem click closed it. Radix UI's pointer-events-disabled
  // overlay from the close animation can swallow the next trigger click if the
  // click happens before the animation completes — the same race that Step 6
  // guards against with the identical pattern. The sidebar-narrowing assertions
  // above complete quickly (Firestore emulator responds before the CSS animation
  // finishes), so an explicit not.toBeAttached wait is required here.
  await expect(page.getByRole("menu")).not.toBeAttached({ timeout: 5_000 });

  // ── Step 5: Delete "Q3 Campaigns" via the trash icon in the filter dropdown.
  await filterTrigger.click();

  // The trash icon has aria-label="Delete category Q3 Campaigns".
  await page.getByRole("button", { name: /Delete category Q3 Campaigns/i }).click();

  // Confirm popover appears — click the confirm button.
  const confirmButton = page.getByRole("button", { name: /confirm|delete/i });
  await confirmButton.waitFor({ state: "visible", timeout: 5_000 });
  await confirmButton.click();

  // ── Step 6: Assert post-delete state.

  // Wait for the AlertDialog portal (BOTH content AND overlay) to fully detach.
  //
  // Radix AlertDialog renders two independent portal elements via separate
  // Radix Presence lifecycles:
  //   • AlertDialogOverlay — `div[data-slot="alert-dialog-overlay"]` (no role).
  //                          Covers the full viewport with pointer-events:all
  //                          while mounted. Blocks clicks when present.
  //   • AlertDialogContent — `[role="alertdialog"][data-slot="alert-dialog-content"]`
  //
  // Each Presence waits for its own `animationend` event. With
  // reducedMotion:"reduce" (→ animation-duration:1ms via index.css:524),
  // both animations complete in ~1 frame, BUT they fire two separate
  // `animationend` events scheduled in separate microtask queue positions.
  // The content animationend resolves first, so [role="alertdialog"] detaches
  // one microtask ahead of the overlay. The overlay then stays mounted with
  // pointer-events:all for one more microtask — long enough for the next
  // filterTrigger.click() to be intercepted by `<html>` (Playwright error:
  // "<html> intercepts pointer events").
  // Waiting for BOTH guards ensures the entire portal is clear before clicking.
  await expect(page.locator('[role="alertdialog"]')).not.toBeAttached({
    timeout: 10_000,
  });
  // The overlay has data-slot="alert-dialog-overlay" (alert-dialog.tsx:17).
  // This is the element that was intercepting pointer-events after iteration 4's
  // single-guard fix. Explicitly wait for it to detach.
  // Timeout matches the content guard (10_000 ms): with animation-duration:1ms
  // (index.css:528) both Presence lifecycles resolve within a single frame.
  await expect(
    page.locator('[data-slot="alert-dialog-overlay"]'),
  ).not.toBeAttached({ timeout: 10_000 });

  // Reopen the filter dropdown via keyboard focus + Space key.
  //
  // Why keyboard, not pointer: Radix's Presence lifecycle fires animationend
  // for each portal element (overlay, content) in separate microtask queue
  // positions. Even after both not.toBeAttached guards pass, the Radix
  // cleanup cycle (scroll-lock removal, focus-scope teardown) runs in a
  // subsequent useLayoutEffect that may not have committed by the time a
  // pointer-based click is attempted — causing Playwright to report
  // "<html> intercepts pointer events" for the full 60s retry budget.
  //
  // filterTrigger.focus() calls element.focus() directly (JavaScript API, no
  // pointer events). Space key is the WAI-ARIA trigger for DropdownMenuTrigger.
  // Together these open the menu without relying on the pointer-events surface.
  await filterTrigger.focus();
  await page.keyboard.press("Space");
  await expect(
    page.locator('[data-slot="dropdown-menu-content"][data-state="open"]'),
  ).toBeVisible({ timeout: 15_000 });

  // "Q3 Campaigns" must no longer appear in the filter dropdown options.
  await expect(
    page.getByRole("menuitem", { name: "Q3 Campaigns" }),
  ).not.toBeAttached({ timeout: 5_000 });
  // Close the dropdown via keyboard.
  await page.keyboard.press("Escape");

  // Both sessions should reappear under "All sessions" filter.
  await expect(page.locator('[data-slot="session-list-item"]')).toHaveCount(2, {
    timeout: 10_000,
  });

  // The previously-categorized session must not show a category label.
  const categorizedRow = page
    .locator('[data-slot="session-list-item"]')
    .filter({ hasText: "To-be-categorized session SC1" });
  await expect(categorizedRow).toBeVisible();
  // The category label line renders as data-slot="session-category-label".
  await expect(
    categorizedRow.locator('[data-slot="session-category-label"]'),
  ).not.toBeAttached();
});

// ─── SC-2: Delete category while status view is open ─────────────────────────
//
// PRD §7 AC-9 covered.

// Re-enabled in CH-64 — same root cause and fix as SC-1: reducedMotion + data-state="open".
test("SC-2: delete category while status view is open — status view refreshes without error", async ({
  page,
  request,
}) => {
  // Seed one session.
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId: "cat-sc2-watch",
    overrides: {
      title: "Watch-cat session SC2",
      updated_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    },
  });

  await setupBaseStack({ page, request, withCategoriesFlag: true });

  // Pre-create category and assign it via the API, so we don't need to drive UI
  // through the creation flow again in this scenario (reduces inter-step race surface).
  const token = await getIdToken(request, ALICE_EMAIL, ALICE_PASSWORD);
  const bearerHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const createResp = await request.post(`${API_BASE}/api/v1/chat/categories`, {
    headers: bearerHeaders,
    data: { name: "Watch Me" },
  });
  if (!createResp.ok()) {
    throw new Error(
      `SC-2 category creation failed ${createResp.status()} — ${await createResp.text()}`,
    );
  }
  const { category_id } = (await createResp.json()) as {
    category_id: string;
    name: string;
  };

  const assignResp = await request.put(
    `${API_BASE}/api/v1/chat/conversations/cat-sc2-watch/category`,
    {
      headers: bearerHeaders,
      data: { category_id },
    },
  );
  if (!assignResp.ok()) {
    throw new Error(
      `SC-2 category assignment failed ${assignResp.status()} — ${await assignResp.text()}`,
    );
  }

  // Navigate to the session and open status view.
  await page.goto(`/chat?session=cat-sc2-watch`);
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  await page.click('[aria-label="Toggle view"]');

  // Status view must be open and show "Watch Me" as the current category.
  const assignSlot = page.locator(
    '[data-testid="status-view-category-assign-slot"]',
  );
  await assignSlot.waitFor({ state: "visible", timeout: 10_000 });
  await expect(assignSlot).toContainText("Watch Me", { timeout: 8_000 });

  // From the sidebar filter dropdown, delete "Watch Me".
  const filterTrigger = page.locator(
    '[data-testid="categories-dropdown-filter-trigger"]',
  );
  await filterTrigger.click();
  // Wait for data-state="open" on the DropdownMenuContent node — the canonical
  // Radix signal that the menu has exited the entering-animation pointer-events
  // lock and inner buttons are hittable (same fix as SC-1, lines ~171 and ~290).
  await expect(
    page.locator('[data-slot="dropdown-menu-content"][data-state="open"]'),
  ).toBeVisible({ timeout: 15_000 });
  // The trash icon aria-label is "Delete category Watch Me" — the component
  // includes "category" in the accessible name for screen-reader context.
  const deleteButton = page.getByRole("button", { name: /Delete category Watch Me/i });
  await deleteButton.waitFor({ state: "visible", timeout: 15_000 });
  await deleteButton.click();

  const confirmButton = page.getByRole("button", { name: /confirm|delete/i });
  await confirmButton.waitFor({ state: "visible", timeout: 15_000 });
  await confirmButton.click();

  // The status view must refresh within one sidebar poll cycle (~5 s), showing
  // the session no longer carries the "Watch Me" category.
  // The assign dropdown's trigger text should fall back to "Uncategorized" or empty.
  await expect(assignSlot).not.toContainText("Watch Me", { timeout: 10_000 });

  // No error toast should be visible.
  await expect(page.getByRole("alert")).toHaveCount(0, { timeout: 3_000 });
});

// ─── SC-3: Search + filter combo (AC-7 reinforcement) ─────────────────────────
//
// PRD §7 AC-7 covered.

test("SC-3: search + filter combo — only sessions matching both category AND query are shown", async ({
  page,
  request,
}) => {
  // Seed three sessions with explicit search_text values so the backend's
  // casefold substring filter works on directly-seeded docs (AD-5).
  // Sessions: Q3 Plan A (will be categorized), Q3 Plan B (uncategorized), Other (control).
  await Promise.all([
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "cat-sc3-q3a",
      overrides: {
        title: "Q3 Plan A",
        search_text: "q3 plan a campaigns",
        updated_at: new Date(Date.now() - 3_000).toISOString(),
        created_at: new Date(Date.now() - 3_000).toISOString(),
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "cat-sc3-q3b",
      overrides: {
        title: "Q3 Plan B",
        search_text: "q3 plan b",
        updated_at: new Date(Date.now() - 2_000).toISOString(),
        created_at: new Date(Date.now() - 2_000).toISOString(),
      },
    }),
    seedChatSession(request, {
      accountId: ACCOUNT_ID,
      orgId: ORG_ID,
      sessionId: "cat-sc3-other",
      overrides: {
        title: "Other session SC3",
        search_text: "other",
        updated_at: new Date(Date.now() - 1_000).toISOString(),
        created_at: new Date(Date.now() - 1_000).toISOString(),
      },
    }),
  ]);

  await setupBaseStack({ page, request, withCategoriesFlag: true });

  // Pre-create "Campaigns" and assign Q3 Plan A via the API.
  const token = await getIdToken(request, ALICE_EMAIL, ALICE_PASSWORD);
  const bearerHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const createResp = await request.post(`${API_BASE}/api/v1/chat/categories`, {
    headers: bearerHeaders,
    data: { name: "Campaigns" },
  });
  if (!createResp.ok()) {
    throw new Error(
      `SC-3 category creation failed ${createResp.status()} — ${await createResp.text()}`,
    );
  }
  const { category_id } = (await createResp.json()) as {
    category_id: string;
    name: string;
  };

  const assignResp = await request.put(
    `${API_BASE}/api/v1/chat/conversations/cat-sc3-q3a/category`,
    {
      headers: bearerHeaders,
      data: { category_id },
    },
  );
  if (!assignResp.ok()) {
    throw new Error(
      `SC-3 assignment failed ${assignResp.status()} — ${await assignResp.text()}`,
    );
  }

  await page.goto("/chat");
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  const filterTrigger = page.locator(
    '[data-testid="categories-dropdown-filter-trigger"]',
  );

  // ── Step 1: Filter by "Campaigns" → only Q3 Plan A visible.
  await filterTrigger.click();
  await page.getByRole("menuitem", { name: "Campaigns" }).click();

  await expect(page.locator('[data-slot="session-list-item"]')).toHaveCount(1, {
    timeout: 10_000,
  });
  await expect(
    page
      .locator('[data-slot="session-list-item"]')
      .filter({ hasText: "Q3 Plan A" }),
  ).toBeVisible();

  // ── Step 2: Type "Q3" in the search input while "Campaigns" filter is active →
  // should still show exactly one row (Q3 Plan A matches both).
  const searchInput = page.getByPlaceholder("Search sessions...");
  await searchInput.fill("Q3");

  await expect(page.locator('[data-slot="session-list-item"]')).toHaveCount(1, {
    timeout: 10_000,
  });
  await expect(
    page
      .locator('[data-slot="session-list-item"]')
      .filter({ hasText: "Q3 Plan A" }),
  ).toBeVisible();

  // ── Step 3: Clear search → "Campaigns" filter still shows only Q3 Plan A.
  await searchInput.clear();

  await expect(page.locator('[data-slot="session-list-item"]')).toHaveCount(1, {
    timeout: 10_000,
  });

  // ── Step 4: Clear category filter → "All sessions"; type "Q3" → two rows.
  // Wait for the filter dropdown menu from step 1 ("Campaigns" selection) to
  // fully detach before re-clicking the trigger. The Radix close animation holds
  // the page's pointer-events lock temporarily. Steps 2–3 assertions resolve
  // faster than the animation, so without this guard the step 4 trigger click
  // fires into the animation window and the menu never opens — the same pattern
  // as SC-1 step 4→5 (guarded at line 233).
  await expect(page.getByRole("menu")).not.toBeAttached({ timeout: 5_000 });
  await filterTrigger.click();
  await page.getByRole("menuitem", { name: /all sessions/i }).click();

  await searchInput.fill("Q3");

  await expect(page.locator('[data-slot="session-list-item"]')).toHaveCount(2, {
    timeout: 10_000,
  });
  await expect(
    page
      .locator('[data-slot="session-list-item"]')
      .filter({ hasText: "Q3 Plan A" }),
  ).toBeVisible();
  await expect(
    page
      .locator('[data-slot="session-list-item"]')
      .filter({ hasText: "Q3 Plan B" }),
  ).toBeVisible();
});

// ─── SC-4: Flag off ────────────────────────────────────────────────────────────
//
// PRD §7 AC-11 covered. The chat_categories_enabled flag is NOT seeded (AD-4),
// which puts both client (useFeatureFlag returns false) and server (endpoint
// returns 404) into flag-off state.

test("SC-4: flag off — category filter hidden, server returns 404", async ({
  page,
  request,
}) => {
  // Seed one session so the sidebar renders (chat_v2_enabled is on).
  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId: "cat-sc4-session",
    overrides: {
      title: "SC4 test session",
      updated_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    },
  });

  // ── Assertion 2 setup: Arm the /categories request listener BEFORE navigation
  // so it covers the full page-load lifecycle. Attaching after page.goto would
  // miss requests fired during initial render (the defect this assertion guards).
  const categoryRequests: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/chat/categories")) {
      categoryRequests.push(req.url());
    }
  });

  // Deliberately omit withCategoriesFlag — per AD-4 this keeps both client and
  // server in flag-off state without relying on a URL-only client-side override.
  await setupBaseStack({ page, request, withCategoriesFlag: false });
  await page.goto("/chat");

  // Wait for the sidebar to render (confirms chat_v2_enabled is on and the page loaded).
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  // ── Assertion 1: The category filter dropdown trigger must NOT be rendered.
  await expect(
    page.locator('[data-testid="categories-dropdown-filter-trigger"]'),
  ).toHaveCount(0, { timeout: 5_000 });

  // The search input must still be present (only the category surface is gated).
  await expect(page.getByPlaceholder("Search sessions...")).toBeVisible();

  // ── Assertion 2: No GET /categories request should have fired from the client.
  // waitForLoadState("networkidle") provides a deterministic boundary: once all
  // in-flight requests have settled, the listener has captured every /categories
  // request for the full navigation + render lifecycle. No sleep() is needed.
  await page.waitForLoadState("networkidle");
  expect(categoryRequests).toHaveLength(0);

  // ── Assertion 3: The server-side gate returns 404 for direct API requests.
  const token = await getIdToken(request, ALICE_EMAIL, ALICE_PASSWORD);
  const resp = await request.get(`${API_BASE}/api/v1/chat/categories`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.status()).toBe(404);
});
