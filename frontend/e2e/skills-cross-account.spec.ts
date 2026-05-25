/**
 * Skills cross-account isolation E2E — SK-20
 *
 * Exercises the two-layer auth guard on the skills router:
 *   Layer 1: `check_account_access` dependency → 403 for non-members
 *   Layer 2: handler-side `owner.account_id != path.account_id` → 403 owner_mismatch
 *
 * TC-1  Non-member GET  /accounts/B/skills/           → 403
 * TC-2  Non-member GET  /accounts/B/skills/{id}       → 403
 * TC-3  Non-member POST /accounts/B/skills/           → 403
 * TC-4  Member-of-A GET /accounts/A/skills/           → 200  (seeded skill in items)
 *        Member-of-A GET /accounts/A/skills/{id}       → 200  (seeded doc)
 * TC-5  Member-of-A GET /accounts/B/skills/           → 403
 * TC-6  Non-member POST /accounts/B/skills/validate   → 403
 *
 * Prerequisites (started by deployment/ci/scripts/start_e2e_stack.sh):
 *   - Firestore emulator   : 127.0.0.1:8090
 *   - FastAPI backend      : 127.0.0.1:8000
 *     (API_TEST_BYPASS_TOKEN=e2e-test-bypass-secret)
 *
 * Token conventions:
 *   BYPASS_TOKEN                → non-member UserContext (empty account_permissions)
 *   BYPASS_TOKEN:{account_id}   → member UserContext (account_permissions={account_id: "edit"})
 */

import { test, expect } from "@playwright/test";
import { seedSkillDoc } from "./helpers/skills";

const FIRESTORE_BASE = "http://127.0.0.1:8090";
const PROJECT = "test-project";
const API_BASE = "http://127.0.0.1:8000";

// Do not add a hardcoded fallback — the CI script always sets this via
// API_TEST_BYPASS_TOKEN=e2e-test-bypass-secret in start_e2e_stack.sh.
const BYPASS_TOKEN = process.env.API_TEST_BYPASS_TOKEN ?? "";

const ACCOUNT_A = "acc-sk20-a";
const ACCOUNT_B = "acc-sk20-b";
const SKILL_ID = "sk-sk20-test-001";

const nonMemberToken = BYPASS_TOKEN;
const memberOfAToken = `${BYPASS_TOKEN}:${ACCOUNT_A}`;

// ─── Guard: skip entire suite if bypass token is not configured ───────────────

test.beforeAll(() => {
  if (!BYPASS_TOKEN) {
    test.skip(
      "API_TEST_BYPASS_TOKEN is not set — skipping cross-account isolation suite",
    );
  }
});

// ─── Teardown: remove seeded Firestore documents ──────────────────────────────

test.afterAll(async ({ request }) => {
  const docPath = `accounts/${ACCOUNT_A}/skills/${SKILL_ID}`;
  const url = `${FIRESTORE_BASE}/v1/projects/${PROJECT}/databases/(default)/documents/${docPath}`;
  // Ignore errors — cleanup is best-effort and docs may not exist.
  await request.delete(url);
});

// ─── TC-1: Non-member cannot list skills for account B ────────────────────────

test("TC-1: non-member GET /accounts/B/skills → 403", async ({ request }) => {
  const resp = await request.get(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_B}/skills/`,
    { headers: { Authorization: `Bearer ${nonMemberToken}` } },
  );
  expect(resp.status()).toBe(403);
});

// ─── TC-2: Non-member cannot fetch a specific skill for account B ─────────────

test("TC-2: non-member GET /accounts/B/skills/{id} → 403", async ({
  request,
}) => {
  const resp = await request.get(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_B}/skills/any-skill-id`,
    { headers: { Authorization: `Bearer ${nonMemberToken}` } },
  );
  expect(resp.status()).toBe(403);
});

// ─── TC-3: Non-member cannot create a skill for account B ────────────────────

test("TC-3: non-member POST /accounts/B/skills → 403", async ({ request }) => {
  const resp = await request.post(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_B}/skills/`,
    {
      headers: { Authorization: `Bearer ${nonMemberToken}` },
      multipart: {
        skill_md: {
          name: "SKILL.md",
          mimeType: "text/markdown",
          buffer: Buffer.from(
            "---\nname: test-skill\ndescription: TC-3 stub\n---\n# Test",
          ),
        },
      },
    },
  );
  expect(resp.status()).toBe(403);
});

// ─── TC-4: Member of A can read own account's skills ─────────────────────────

test("TC-4: member-of-A GET /accounts/A/skills → 200 with item; GET detail → 200", async ({
  request,
}) => {
  // Seed the skill doc so both list and detail can return it.
  await seedSkillDoc(request, {
    accountId: ACCOUNT_A,
    skillId: SKILL_ID,
  });

  // List endpoint returns 200 and items contains the seeded skill.
  const listResp = await request.get(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_A}/skills/`,
    { headers: { Authorization: `Bearer ${memberOfAToken}` } },
  );
  expect(listResp.status()).toBe(200);
  const listBody = (await listResp.json()) as { items: Array<{ skill_id: string }> };
  expect(listBody.items.some((s) => s.skill_id === SKILL_ID)).toBe(true);

  // Detail endpoint returns 200 for the seeded skill.
  const detailResp = await request.get(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_A}/skills/${SKILL_ID}`,
    { headers: { Authorization: `Bearer ${memberOfAToken}` } },
  );
  expect(detailResp.status()).toBe(200);
  const detailBody = (await detailResp.json()) as { skill_id: string };
  expect(detailBody.skill_id).toBe(SKILL_ID);
});

// ─── TC-5: Member of A cannot read account B's skills ────────────────────────

test("TC-5: member-of-A GET /accounts/B/skills → 403", async ({ request }) => {
  const resp = await request.get(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_B}/skills/`,
    { headers: { Authorization: `Bearer ${memberOfAToken}` } },
  );
  expect(resp.status()).toBe(403);
});

// ─── TC-6: Non-member cannot call validate for account B ─────────────────────

test("TC-6: non-member POST /accounts/B/skills/validate → 403", async ({
  request,
}) => {
  const resp = await request.post(
    `${API_BASE}/api/v1/accounts/${ACCOUNT_B}/skills/validate`,
    {
      headers: { Authorization: `Bearer ${nonMemberToken}` },
      multipart: {
        skill_md: {
          name: "SKILL.md",
          mimeType: "text/markdown",
          buffer: Buffer.from(
            "---\nname: test-skill\ndescription: TC-6 stub\n---\n# Test",
          ),
        },
      },
    },
  );
  expect(resp.status()).toBe(403);
});
