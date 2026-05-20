import type { APIRequestContext, Page } from "@playwright/test";
import { expect } from "@playwright/test";

const FIRESTORE_BASE = "http://127.0.0.1:8090";
const AUTH_BASE = "http://127.0.0.1:9099";
const API_BASE = "http://127.0.0.1:8000";
const PROJECT = "test-project";

// ─── Firestore emulator helpers ───────────────────────────────────────────────

type TargetingRulesOverrides = {
  email_domains?: string[];
  user_emails?: string[];
  organization_ids?: string[];
  account_ids?: string[];
  rollout_percentage?: number;
  default_enabled?: boolean;
};

/** Seed (or replace) `e2e_test_flag` in the Firestore emulator. */
export async function seedFlag(
  request: APIRequestContext,
  flagKey: string,
  overrides: TargetingRulesOverrides = {},
): Promise<void> {
  const {
    email_domains = [],
    user_emails = [],
    organization_ids = [],
    account_ids = [],
    rollout_percentage = 0,
    default_enabled = false,
  } = overrides;

  const toStrArray = (arr: string[]) => ({
    arrayValue: { values: arr.map((s) => ({ stringValue: s })) },
  });

  // Use PATCH with updateMask to create-or-replace without needing DELETE first.
  const url = `${FIRESTORE_BASE}/v1/projects/${PROJECT}/databases/(default)/documents/feature_flags/${encodeURIComponent(flagKey)}`;
  const resp = await request.patch(url, {
    headers: { "Content-Type": "application/json" },
    data: {
      fields: {
        description: {
          stringValue: "E2E test flag — managed by featureFlags.spec.ts",
        },
        default_enabled: { booleanValue: default_enabled },
        is_active: { booleanValue: true },
        targeting_rules: {
          mapValue: {
            fields: {
              user_emails: toStrArray(user_emails),
              email_domains: toStrArray(email_domains),
              organization_ids: toStrArray(organization_ids),
              account_ids: toStrArray(account_ids),
              rollout_percentage: { integerValue: String(rollout_percentage) },
            },
          },
        },
        bucketing_entity: { stringValue: "account" },
        owner: { stringValue: "test@ken-e.ai" },
        expected_ga_release: { nullValue: "NULL_VALUE" },
        created_at: { stringValue: "2026-01-01T00:00:00Z" },
        updated_at: { stringValue: "2026-01-01T00:00:00Z" },
      },
    },
  });
  if (!resp.ok()) {
    throw new Error(
      `seedFlag: Firestore PATCH failed ${resp.status()} — ${await resp.text()}`,
    );
  }
}

/** Delete the flag document from the Firestore emulator (no-ops on 404). */
export async function deleteFlag(
  request: APIRequestContext,
  flagKey: string,
): Promise<void> {
  const url = `${FIRESTORE_BASE}/v1/projects/${PROJECT}/databases/(default)/documents/feature_flags/${encodeURIComponent(flagKey)}`;
  await request.delete(url);
  // Intentionally ignore 404 — cleanup should be idempotent.
}

// ─── Auth emulator helpers ────────────────────────────────────────────────────

/** Return a Firebase ID token for the given credentials via the Auth emulator REST API. */
export async function getIdToken(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const url = `${AUTH_BASE}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=test-api-key`;
  const resp = await request.post(url, {
    headers: { "Content-Type": "application/json" },
    data: { email, password, returnSecureToken: true },
  });
  if (!resp.ok()) {
    throw new Error(
      `getIdToken: Auth emulator sign-in failed ${resp.status()} for ${email} — ${await resp.text()}`,
    );
  }
  const body = (await resp.json()) as { idToken: string };
  return body.idToken;
}

// ─── Backend admin helpers ────────────────────────────────────────────────────

/** Flip is_active=false on the flag (kill switch) via the admin PUT endpoint. */
export async function flipKillSwitch(
  request: APIRequestContext,
  flagKey: string,
  bearerToken: string,
): Promise<void> {
  const url = `${API_BASE}/api/v1/admin/feature-flags/${flagKey}`;
  const resp = await request.put(url, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${bearerToken}`,
    },
    data: {
      key: flagKey,
      description: "E2E test flag — managed by featureFlags.spec.ts",
      default_enabled: false,
      is_active: false,
      targeting_rules: {
        email_domains: ["ken-e.ai"],
        user_emails: [],
        organization_ids: [],
        account_ids: [],
        rollout_percentage: 0,
      },
      bucketing_entity: "account",
      owner: "test@ken-e.ai",
    },
  });
  if (!resp.ok()) {
    throw new Error(
      `flipKillSwitch: admin PUT failed ${resp.status()} — ${await resp.text()}`,
    );
  }
}

// ─── Browser helpers ──────────────────────────────────────────────────────────

/** Clear all browser storage (localStorage, sessionStorage, IndexedDB). */
async function clearBrowserStorage(page: Page): Promise<void> {
  await page.evaluate(async () => {
    localStorage.clear();
    sessionStorage.clear();
    // Clear Firebase Auth IndexedDB so auth state doesn't bleed between tests.
    const dbs: { name?: string }[] =
      (await window.indexedDB.databases?.()) ?? [];
    await Promise.all(
      dbs.map(
        (db) =>
          new Promise<void>((resolve) => {
            if (!db.name) {
              resolve();
              return;
            }
            const req = window.indexedDB.deleteDatabase(db.name);
            req.onsuccess = () => resolve();
            req.onerror = () => resolve();
          }),
      ),
    );
  });
}

/**
 * Sign in as the given user via the application's /sign-in UI.
 *
 * Clears all browser storage first so each call starts from a signed-out state.
 * Waits for the ReCaptcha 3-second fallback to fire (the test env has no RECAPTCHA
 * site key, so the SDK never loads and the fallback auto-verifies after 3 s).
 *
 * The app redirects to `/` (→ `/chat`) after a successful sign-in.
 */
export async function signInAs(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  // Load a neutral page first so clearBrowserStorage can run on the right origin.
  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  await clearBrowserStorage(page);
  // Reload after clearing storage so Firebase SDK re-initialises without stale state.
  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });

  await page.fill("#email", email);
  await page.fill("#password", password);

  // Wait for the ReCaptcha fallback (3 s) to mark the form as safe to submit.
  // The shield-check icon appears when isVerified=true in ReCaptchaV3.
  await expect(page.locator('[data-testid="shield-check-icon"]')).toBeVisible({
    timeout: 10_000,
  });

  await page.click('button[type="submit"]');

  // Wait until the URL is no longer /sign-in (redirect on successful auth).
  await page.waitForURL((url) => !url.pathname.startsWith("/sign-in"), {
    timeout: 20_000,
  });
}

// ─── Assertion helpers ────────────────────────────────────────────────────────

/**
 * Assert the FeatureFlagStatusHarness page shows the expected hook state.
 *
 * Waits for ff-isloading to reach "false" before asserting enabled/reason so
 * the assertion doesn't fire on the initial "not-yet-evaluated" state.
 */
export async function expectHookState(
  page: Page,
  state: { enabled: boolean; reason: string },
): Promise<void> {
  await expect(page.getByTestId("ff-isloading")).toHaveText("false", {
    timeout: 15_000,
  });
  await expect(page.getByTestId("ff-enabled")).toHaveText(
    String(state.enabled),
  );
  await expect(page.getByTestId("ff-reason")).toHaveText(state.reason);
}
