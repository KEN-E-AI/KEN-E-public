/**
 * E2E integration tests for ArtifactsPanel + TodoListsPanel in the status view.
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator : 127.0.0.1:8090
 *   - Auth emulator      : 127.0.0.1:9099
 *   - FastAPI backend    : 127.0.0.1:8000 (KENE_FF_CACHE_TTL_SECONDS=0)
 *   - Vite dev server    : 127.0.0.1:8080
 *
 * The /todos and /artifacts endpoints are mocked via page.route() — no GCS
 * emulator is available in the CI stack (AC-12).
 */

import { test, expect } from "@playwright/test";
import { seedFlag, deleteFlag, signInAs } from "./helpers";
import {
  seedChatSession,
  seedAccount,
  cleanupChatSessions,
  buildSelectedOrgAccountScript,
} from "./helpers/chat";

const ALICE_EMAIL = "alice@ken-e.ai";
const ALICE_PASSWORD = "password123";
const ALICE_UID = "alice-uid";
const ORG_ID = "org_e2e-ta";
const ACCOUNT_ID = "acc_e2e-ta";
const SESSION_ID = "ta-session-01";

const MOCK_TODOS = {
  todo_lists: [
    {
      list_id: "list_e2e_1",
      title: "Q3 Campaign Tasks",
      is_current: true,
      created_at: "2026-05-01T09:00:00Z",
      items: [
        {
          item_id: "item_1",
          text: "Analyse performance data",
          completed: true,
          completed_at: "2026-05-01T10:00:00Z",
        },
        {
          item_id: "item_2",
          text: "Draft recommendations",
          completed: false,
          completed_at: null,
        },
      ],
    },
  ],
};

const MOCK_ARTIFACTS = {
  items: [
    {
      artifact_index: {
        artifact_id: "artifact_e2e_1",
        session_id: SESSION_ID,
        filename: "campaign-report.pdf",
        mime_type: "application/pdf",
        size_bytes: 204800,
        version: 0,
        gcs_path: `gs://bucket/app/alice-uid/${SESSION_ID}/campaign-report.pdf/0`,
        created_by_tool: "generate_report",
        created_at: "2026-05-01T09:00:00Z",
      },
      signed_url:
        "https://storage.googleapis.com/bucket/signed?token=e2e-abc",
      signed_url_expires_at: "2026-05-01T10:00:00Z",
    },
  ],
};

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

async function setupPage({
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

  await seedChatSession(request, {
    accountId: ACCOUNT_ID,
    orgId: ORG_ID,
    sessionId: SESSION_ID,
    overrides: {
      title: "E2E artifacts test session",
      last_message_preview: "Session with artifacts and todos.",
    },
  });

  // Mock /todos and /artifacts — no GCS emulator available in CI stack.
  await page.route(`**/api/v1/chat/conversations/*/todos`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_TODOS),
    });
  });
  await page.route(
    `**/api/v1/chat/conversations/*/artifacts`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_ARTIFACTS),
      });
    },
  );

  await signInAs(page, ALICE_EMAIL, ALICE_PASSWORD);

  await page.addInitScript(
    buildSelectedOrgAccountScript({ orgId: ORG_ID, accountId: ACCOUNT_ID }),
  );
}

// ─── TC-1: ArtifactsPanel renders in status view ─────────────────────────────

test("TC-1: ArtifactsPanel renders artifact rows after switching to status view", async ({
  page,
  request,
}) => {
  await setupPage({ page, request });

  await page.goto(`/chat?session=${SESSION_ID}`);

  // Wait for the sidebar so chat_v2_enabled has resolved and layout is stable.
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  // Switch to status view.
  await page.click('[aria-label="Toggle view"]');

  // ArtifactsPanel must appear.
  await page
    .locator('[data-testid="artifacts-panel"]')
    .waitFor({ state: "visible", timeout: 10_000 });

  // The mocked artifact filename should be visible.
  await expect(page.getByText("campaign-report.pdf")).toBeVisible();
  // KEN-E badge should be visible.
  await expect(page.getByText("KEN-E").first()).toBeVisible();
});

// ─── TC-2: TodoListsPanel renders in status view ──────────────────────────────

test("TC-2: TodoListsPanel renders todo lists after switching to status view", async ({
  page,
  request,
}) => {
  await setupPage({ page, request });

  await page.goto(`/chat?session=${SESSION_ID}`);

  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  // Switch to status view.
  await page.click('[aria-label="Toggle view"]');

  // TodoListsPanel must appear.
  await page
    .locator('[data-testid="todo-lists-panel"]')
    .waitFor({ state: "visible", timeout: 10_000 });

  // The mocked todo list title should be visible.
  await expect(page.getByText("Q3 Campaign Tasks")).toBeVisible();
});

// ─── TC-3: Both panels visible simultaneously ─────────────────────────────────

test("TC-3: ArtifactsPanel and TodoListsPanel are both visible simultaneously", async ({
  page,
  request,
}) => {
  await setupPage({ page, request });

  await page.goto(`/chat?session=${SESSION_ID}`);

  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  // Switch to status view.
  await page.click('[aria-label="Toggle view"]');

  await page
    .locator('[data-testid="artifacts-panel"]')
    .waitFor({ state: "visible", timeout: 10_000 });
  await page
    .locator('[data-testid="todo-lists-panel"]')
    .waitFor({ state: "visible", timeout: 10_000 });

  await expect(page.locator('[data-testid="artifacts-panel"]')).toBeVisible();
  await expect(page.locator('[data-testid="todo-lists-panel"]')).toBeVisible();
});

// ─── TC-4: Artifact row links to signed_url ───────────────────────────────────

test("TC-4: artifact row href points to the signed URL from the API", async ({
  page,
  request,
}) => {
  await setupPage({ page, request });

  await page.goto(`/chat?session=${SESSION_ID}`);

  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible", timeout: 30_000 });

  await page.click('[aria-label="Toggle view"]');

  await page
    .locator('[data-testid="artifacts-panel"]')
    .waitFor({ state: "visible", timeout: 10_000 });

  const link = page.getByRole("link", { name: "campaign-report.pdf" });
  await expect(link).toHaveAttribute(
    "href",
    "https://storage.googleapis.com/bucket/signed?token=e2e-abc",
  );
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
});
