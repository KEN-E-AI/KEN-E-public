/**
 * E2E tests verifying that Vega-Lite chart artifacts produced by the agent
 * during a chat turn render inline (ChatArtifactRenderer) in the assistant
 * message bubble.
 *
 * Note: live SSE `artifacts` events route to `chartArtifacts` ->
 * ChatArtifactRenderer (the AH-131/AH-134 inline-chart path preserved by the
 * AH-PRD-05 Wave-2 integration), NOT the `message.artifacts` -> ArtifactBlock
 * chip path (that path is reserved for session-history file artifacts). The
 * stable assertion target is the `chart-artifact-item` wrapper, which is present
 * whether VegaEmbed renders the chart or falls back to the spec view.
 *
 * The /completions endpoint is mocked via page.route() with a canned SSE
 * stream containing an `event: artifacts` frame — no GA OAuth credentials or
 * real Agent Engine are required (AC-1, AC-4 of AH-143).
 *
 * TC-1: Single-specialist turn renders one inline chart.
 * TC-4: Multiple charts in one turn render multiple inline charts.
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator : 127.0.0.1:8090
 *   - Auth emulator      : 127.0.0.1:9099
 *   - FastAPI backend    : 127.0.0.1:8000 (KENE_FF_CACHE_TTL_SECONDS=0)
 *   - Vite dev server    : 127.0.0.1:8080
 */

import { test, expect } from "@playwright/test";
import { seedFlag, deleteFlag, signInAs } from "./helpers";
import {
  seedAccount,
  cleanupChatSessions,
  buildSelectedOrgAccountScript,
} from "./helpers/chat";

// ─── Constants ─────────────────────────────────────────────────────────────────

const ALICE_EMAIL = "alice@ken-e.ai";
const ALICE_PASSWORD = "password123";
const ALICE_UID = "alice-uid";
const ORG_ID = "org_e2e-art";
const ACCOUNT_ID = "acc_e2e-art";

// ─── SSE response builders ──────────────────────────────────────────────────────

function sseArtifact(title: string, chartType = "line") {
  return JSON.stringify({
    type: "visualization",
    spec: {
      $schema: "https://vega.github.io/schema/vega-lite/v6.json",
      title,
      data: { values: [] },
      mark: chartType,
      encoding: {},
    },
    metadata: {
      chart_type_suggestion: chartType,
      title,
      data_source: "agent",
      description: null,
    },
  });
}

function buildSseBody(artifacts: Array<{ title: string; chartType?: string }>) {
  const artifactJson = JSON.stringify({
    artifacts: artifacts.map((a) =>
      JSON.parse(sseArtifact(a.title, a.chartType)),
    ),
  });
  return (
    `data: Here is your chart.\n\n` +
    `event: artifacts\n` +
    `data: ${artifactJson}\n\n` +
    `data: [DONE]\n\n`
  );
}

// ─── Setup / teardown ──────────────────────────────────────────────────────────

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
  sseBody,
}: {
  page: Parameters<Parameters<typeof test>[1]>[0]["page"];
  request: Parameters<Parameters<typeof test>[1]>[0]["request"];
  sseBody: string;
}) {
  await seedFlag(request, "chat_v2_enabled", { default_enabled: true });

  await seedAccount(request, {
    accountId: ACCOUNT_ID,
    ownerUid: ALICE_UID,
    orgId: ORG_ID,
  });

  // Mock the completions endpoint with the provided canned SSE response.
  // Must be registered before goto so the route is in place when the page
  // issues the fetch (page.route intercepts by pattern, not by timing).
  await page.route("**/api/v1/chat/completions", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
      },
      body: sseBody,
    });
  });

  await signInAs(page, ALICE_EMAIL, ALICE_PASSWORD);

  await page.addInitScript(
    buildSelectedOrgAccountScript({ orgId: ORG_ID, accountId: ACCOUNT_ID }),
  );
}

// ─── TC-1: Single chart ────────────────────────────────────────────────────────

test("TC-1: single-specialist turn renders one inline chart in the assistant reply", async ({
  page,
  request,
}) => {
  // First auth test of the serial run absorbs backend cold-start; triple the
  // per-test timeout so the (now up to 45s) signInAs redirect fits alongside the
  // chart assertions.
  test.slow();
  const sseBody = buildSseBody([
    { title: "Daily Sessions", chartType: "line" },
  ]);
  await setupPage({ page, request, sseBody });

  await page.goto("/chat");

  const chatInterface = page.locator('[data-testid="chat-interface"]');
  await chatInterface.waitFor({ state: "visible" });
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible" });

  await page.fill(
    '[aria-label="Chat input"]',
    "Show me a line chart of daily sessions for the past 7 days",
  );
  await page.click('[aria-label="Send message"]');

  // Wait for the assistant reply text to appear.
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="chat-interface"]')
        ?.textContent?.includes("Here is your chart."),
    { timeout: 15_000 },
  );

  // The inline chart should render — one chart-artifact-item wrapper. This
  // wrapper is present regardless of whether VegaEmbed succeeds or falls back
  // to the spec view, so the assertion is stable in headless Chromium.
  await expect(
    chatInterface.locator('[data-testid="chart-artifact-item"]'),
  ).toHaveCount(1, { timeout: 5_000 });
});

// ─── TC-4: Multiple charts ─────────────────────────────────────────────────────

test("TC-4: turn with two chart artifacts renders two inline charts", async ({
  page,
  request,
}) => {
  // Headroom for a cold-start sign-in if this test ends up first in the run.
  test.slow();
  const sseBody = buildSseBody([
    { title: "Daily Sessions", chartType: "line" },
    { title: "Top Pages by Traffic", chartType: "bar" },
  ]);
  await setupPage({ page, request, sseBody });

  await page.goto("/chat");

  const chatInterface = page.locator('[data-testid="chat-interface"]');
  await chatInterface.waitFor({ state: "visible" });
  await page
    .locator('[data-testid="sessions-sidebar"]')
    .waitFor({ state: "visible" });

  await page.fill(
    '[aria-label="Chat input"]',
    "Show me two charts: a line chart of daily sessions and a bar chart of top pages by traffic",
  );
  await page.click('[aria-label="Send message"]');

  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="chat-interface"]')
        ?.textContent?.includes("Here is your chart."),
    { timeout: 15_000 },
  );

  // Both charts render inline as separate chart-artifact-item wrappers.
  await expect(
    chatInterface.locator('[data-testid="chart-artifact-item"]'),
  ).toHaveCount(2, { timeout: 5_000 });
});
