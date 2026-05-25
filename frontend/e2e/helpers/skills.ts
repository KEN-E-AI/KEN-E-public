import type { APIRequestContext } from "@playwright/test";

const FIRESTORE_BASE = "http://127.0.0.1:8090";
const PROJECT = "test-project";
const FIRESTORE_REST = `${FIRESTORE_BASE}/v1/projects/${PROJECT}/databases/(default)/documents`;

function str(v: string) {
  return { stringValue: v };
}
function bool(v: boolean) {
  return { booleanValue: v };
}
function int(v: number) {
  return { integerValue: String(v) };
}
function nullVal() {
  return { nullValue: "NULL_VALUE" as const };
}

/**
 * Seed (or replace) a Skill document at
 * `accounts/{accountId}/skills/{skillId}` in the Firestore emulator.
 *
 * All fields match the `Skill` Pydantic model stored via `model_dump(mode="json")`.
 */
export async function seedSkillDoc(
  request: APIRequestContext,
  opts: {
    accountId: string;
    skillId: string;
    ownerAccountId?: string;
    name?: string;
    description?: string;
    createdBy?: string;
    updatedBy?: string;
  },
): Promise<void> {
  const {
    accountId,
    skillId,
    ownerAccountId = accountId,
    name = `Test Skill ${skillId}`,
    description = "E2E test skill",
    createdBy = "test-user",
    updatedBy = "test-user",
  } = opts;

  const now = new Date().toISOString();
  const url = `${FIRESTORE_REST}/accounts/${encodeURIComponent(accountId)}/skills/${encodeURIComponent(skillId)}`;

  const resp = await request.patch(url, {
    headers: { "Content-Type": "application/json" },
    data: {
      fields: {
        skill_id: str(skillId),
        owner: {
          mapValue: {
            fields: {
              account_id: str(ownerAccountId),
              shared_with_accounts: { arrayValue: { values: [] } },
            },
          },
        },
        name: str(name),
        description: str(description),
        current_version: int(1),
        visibility: str("private"),
        status: str("draft"),
        source: {
          mapValue: {
            fields: {
              type: str("authored"),
              repo: nullVal(),
              sha: nullVal(),
              license: nullVal(),
            },
          },
        },
        has_scripts: bool(false),
        created_at: str(now),
        created_by: str(createdBy),
        updated_at: str(now),
        updated_by: str(updatedBy),
      },
    },
  });

  if (!resp.ok()) {
    throw new Error(
      `seedSkillDoc failed: ${resp.status()} ${await resp.text()}`,
    );
  }
}
