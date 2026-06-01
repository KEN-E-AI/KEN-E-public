import type { APIRequestContext } from "@playwright/test";

const FIRESTORE_BASE = "http://127.0.0.1:8090";
const PROJECT = "test-project";

// ─── Firestore REST helpers ───────────────────────────────────────────────────

const FIRESTORE_REST = `${FIRESTORE_BASE}/v1/projects/${PROJECT}/databases/(default)/documents`;

function str(v: string) {
  return { stringValue: v };
}
function nullVal() {
  return { nullValue: "NULL_VALUE" as const };
}
function timestamp(v: string) {
  return { timestampValue: v };
}

// ─── Chat-session seeding ─────────────────────────────────────────────────────

export type ChatSessionOverrides = {
  title?: string | null;
  user_id?: string;
  // is_agent_running is derived on read from last_agent_started_at / last_agent_stopped_at
  // (no persistent boolean in ChatSessionMetadata). Set last_agent_started_at to a recent
  // ISO timestamp to make the backend compute is_agent_running=true for this session.
  last_agent_started_at?: string | null;
  last_agent_stopped_at?: string | null;
  last_agent_message_at?: string | null;
  last_viewed_at?: string | null;
  last_message_preview?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  updated_at?: string;
  created_at?: string;
  // search_text is normally computed by the side-table service as
  // casefold(title + " " + category_name + " " + latest_summary). In E2E tests
  // that seed Firestore directly (bypassing the API), pass an explicit value so
  // the backend's casefold substring filter in list_sessions() works correctly.
  // This is a test-only shortcut documented in the implementation plan (AD-5).
  search_text?: string | null;
};

/**
 * Seed (or replace) a single chat_sessions document at
 * `accounts/{accountId}/chat_sessions/{sessionId}`.
 */
export async function seedChatSession(
  request: APIRequestContext,
  opts: {
    accountId: string;
    sessionId: string;
    orgId?: string;
    overrides?: ChatSessionOverrides;
  },
): Promise<void> {
  const { accountId, sessionId, orgId = "org-test", overrides = {} } = opts;
  const now = new Date().toISOString();

  const {
    title = `Session ${sessionId}`,
    user_id = "alice-uid",
    last_agent_started_at = null,
    last_agent_stopped_at = null,
    last_agent_message_at = null,
    last_viewed_at = null,
    last_message_preview = null,
    category_id = null,
    category_name = null,
    updated_at = now,
    created_at = now,
    search_text = null,
  } = overrides;

  const url = `${FIRESTORE_REST}/accounts/${encodeURIComponent(accountId)}/chat_sessions/${encodeURIComponent(sessionId)}`;
  const resp = await request.patch(url, {
    headers: { "Content-Type": "application/json" },
    data: {
      fields: {
        session_id: str(sessionId),
        // user_id, account_id, organization_id, and deleted_at are required by
        // the backend's collection-group query (search.py) and ChatSessionMetadata
        // model. Timestamps must use timestampValue so Firestore range filters work.
        user_id: str(user_id),
        account_id: str(accountId),
        organization_id: str(orgId),
        deleted_at: nullVal(),
        title: title !== null ? str(title) : nullVal(),
        category_id: category_id !== null ? str(category_id) : nullVal(),
        category_name: category_name !== null ? str(category_name) : nullVal(),
        last_message_preview:
          last_message_preview !== null ? str(last_message_preview) : nullVal(),
        updated_at: timestamp(updated_at),
        created_at: timestamp(created_at),
        // is_agent_running is derived on read by the backend from these two timestamps.
        // Set last_agent_started_at to a recent ISO time (within 10 min) for active sessions.
        last_agent_started_at:
          last_agent_started_at !== null
            ? timestamp(last_agent_started_at)
            : nullVal(),
        last_agent_stopped_at:
          last_agent_stopped_at !== null
            ? timestamp(last_agent_stopped_at)
            : nullVal(),
        last_agent_message_at:
          last_agent_message_at !== null
            ? timestamp(last_agent_message_at)
            : nullVal(),
        last_viewed_at:
          last_viewed_at !== null ? timestamp(last_viewed_at) : nullVal(),
        // Optional pre-computed search_text for tests that need substring filtering
        // without going through the API's side-table service (see AD-5 in the CH-42
        // implementation plan). Omitting the field lets the side-table service write
        // it on the next real turn; providing it lets direct-Firestore-seeded tests
        // exercise the casefold filter path immediately.
        ...(search_text !== null && search_text !== undefined
          ? { search_text: str(search_text) }
          : {}),
      },
    },
  });
  if (!resp.ok()) {
    throw new Error(
      `seedChatSession: Firestore PATCH failed ${resp.status()} — ${await resp.text()}`,
    );
  }
}

/**
 * Seed N chat sessions for the given account.
 * Session IDs are `{prefix}{i}` (default prefix "session-").
 */
export async function seedNChatSessions(
  request: APIRequestContext,
  count: number,
  opts: {
    accountId: string;
    orgId?: string;
    idPrefix?: string;
    overrides?: (i: number) => ChatSessionOverrides;
  },
): Promise<string[]> {
  const { accountId, orgId, idPrefix = "session-", overrides } = opts;
  // Pre-allocate so concurrent pushes within a batch don't produce a
  // non-deterministic ordering in the returned array.
  const ids: string[] = new Array(count);

  // Fire in batches of 20 to avoid overwhelming the emulator with concurrent
  // HTTP requests, which causes 500s at ~1000 sessions on CI.
  const BATCH = 20;
  for (let start = 0; start < count; start += BATCH) {
    const end = Math.min(start + BATCH, count);
    await Promise.all(
      Array.from({ length: end - start }, async (_, j) => {
        const i = start + j;
        const sessionId = `${idPrefix}${i}`;
        ids[i] = sessionId;
        await seedChatSession(request, {
          accountId,
          orgId,
          sessionId,
          overrides: overrides ? overrides(i) : undefined,
        });
      }),
    );
  }
  return ids;
}

// ─── Account seeding ──────────────────────────────────────────────────────────

/**
 * Seed a minimal account document at `accounts/{accountId}`.
 * Used so the API's `require_account_access()` check finds the account without
 * needing a real org/account creation flow.
 */
export async function seedAccount(
  request: APIRequestContext,
  opts: { accountId: string; ownerUid: string; orgId?: string },
): Promise<void> {
  const { accountId, ownerUid, orgId = "org-test" } = opts;
  const url = `${FIRESTORE_REST}/accounts/${encodeURIComponent(accountId)}`;
  const resp = await request.patch(url, {
    headers: { "Content-Type": "application/json" },
    data: {
      fields: {
        account_id: str(accountId),
        organization_id: str(orgId),
        owner_uid: str(ownerUid),
        name: str(`Test Account ${accountId}`),
        status: str("active"),
        created_at: str(new Date().toISOString()),
      },
    },
  });
  if (!resp.ok()) {
    throw new Error(
      `seedAccount: Firestore PATCH failed ${resp.status()} — ${await resp.text()}`,
    );
  }
}

// ─── Auth context wiring ──────────────────────────────────────────────────────

/**
 * Inject a selectedOrgAccount into localStorage so the React app treats the
 * account as already selected — bypasses the workspace-selection screen.
 *
 * Must be called via `page.addInitScript` (before page load) or before any
 * React context reads from localStorage.
 */
export function buildSelectedOrgAccountScript(opts: {
  orgId: string;
  accountId: string;
  role?: string;
}): string {
  const { orgId, accountId, role = "admin" } = opts;
  const payload = JSON.stringify({
    orgId,
    accountId,
    metadata: {
      organization_name: "Test Org",
      account_name: `Test Account ${accountId}`,
      industry: "technology",
      status: "active",
      role,
    },
  });
  return `
    localStorage.setItem("selectedOrgAccount", ${JSON.stringify(payload)});
    localStorage.setItem("currentOrganizationId", ${JSON.stringify(orgId)});
    localStorage.setItem("hasSelectedWorkspace", "true");
  `;
}

// ─── Cleanup ──────────────────────────────────────────────────────────────────

/**
 * Delete all documents under `users/{userId}/chat_categories/` by listing and
 * deleting them individually.
 *
 * Categories are user-scoped (not account-scoped) per chat README §7.2. This
 * helper must target the `users/` path — NOT the `accounts/` path — to avoid
 * silent no-ops that leave category docs behind after a test run.
 *
 * No-ops gracefully on 404 (user or collection not found).
 */
export async function cleanupChatCategories(
  request: APIRequestContext,
  userId: string,
): Promise<void> {
  const baseUrl = `${FIRESTORE_REST}/users/${encodeURIComponent(userId)}/chat_categories`;
  let pageToken: string | undefined;

  do {
    const url = pageToken
      ? `${baseUrl}?pageToken=${encodeURIComponent(pageToken)}`
      : baseUrl;
    const listResp = await request.get(url, {
      headers: { "Content-Type": "application/json" },
    });
    if (!listResp.ok()) {
      // 404 means the collection doesn't exist — nothing to clean up.
      if (listResp.status() === 404) return;
      throw new Error(
        `cleanupChatCategories: list failed ${listResp.status()} — ${await listResp.text()}`,
      );
    }
    const body = await listResp.json();
    const docs: Array<{ name: string }> = body.documents ?? [];
    const EXPECTED_PREFIX = `projects/${PROJECT}/databases/(default)/documents/`;
    await Promise.all(
      docs.map(async (doc) => {
        // Guard against a crafted emulator response with an unexpected path that
        // could cause the cleanup helper to delete unintended Firestore documents.
        if (!doc.name.startsWith(EXPECTED_PREFIX)) {
          throw new Error(
            `cleanupChatCategories: unexpected doc.name: ${doc.name}`,
          );
        }
        const deleteUrl = `${FIRESTORE_BASE}/v1/${doc.name}`;
        const delResp = await request.delete(deleteUrl);
        if (!delResp.ok() && delResp.status() !== 404) {
          throw new Error(
            `cleanupChatCategories: DELETE failed ${delResp.status()} — ${await delResp.text()}`,
          );
        }
      }),
    );
    pageToken = body.nextPageToken;
  } while (pageToken);
}

/**
 * Delete all documents under `accounts/{accountId}/chat_sessions/` by listing
 * and deleting them individually (the Firestore emulator REST API does not
 * support recursive deletes).
 *
 * No-ops gracefully on 404 (account or collection not found).
 */
export async function cleanupChatSessions(
  request: APIRequestContext,
  accountId: string,
): Promise<void> {
  const baseUrl = `${FIRESTORE_REST}/accounts/${encodeURIComponent(accountId)}/chat_sessions`;
  let pageToken: string | undefined;

  do {
    const url = pageToken
      ? `${baseUrl}?pageToken=${encodeURIComponent(pageToken)}`
      : baseUrl;
    const listResp = await request.get(url, {
      headers: { "Content-Type": "application/json" },
    });
    if (!listResp.ok()) {
      // 404 means the collection doesn't exist — nothing to clean up.
      if (listResp.status() === 404) return;
      throw new Error(
        `cleanupChatSessions: list failed ${listResp.status()} — ${await listResp.text()}`,
      );
    }
    const body = await listResp.json();
    const docs: Array<{ name: string }> = body.documents ?? [];
    await Promise.all(
      docs.map(async (doc) => {
        // doc.name is the full resource name, e.g.
        // projects/test-project/databases/(default)/documents/accounts/a/chat_sessions/s
        const deleteUrl = `${FIRESTORE_BASE}/v1/${doc.name}`;
        await request.delete(deleteUrl);
      }),
    );
    pageToken = body.nextPageToken;
  } while (pageToken);
}
