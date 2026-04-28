# Sprint 2.6-A — Skills Backend: Storage, API, Loader

**Status:** Blocked — resumes once DM-PRD-00 and DM-PRD-05 ship
**Owner team:** Backend
**Blocked by:** DM-PRD-00 (Shape B convention + `skills` index registry), DM-PRD-05 (recursive-delete coverage for the new subcollections)
**Parallel with:** AH-PRD-02, 2.6-0, 2.6-C (against contract)
**Blocks:** 2.6-B, 2.6-C, 2.6-D
**Estimated effort:** 6–8 days

---

## 1. Context

This PRD delivers the **foundation** of the Skills feature: a Firestore + GCS storage model, a REST API for CRUD operations, and a skill loader service that hydrates skills into the `models.Skill` objects the ADK `SkillToolset` consumes.

After this sprint ships, a user's skills are fully persisted and served via API, but not yet attached to any agent (Sprint 2.6-B wires the agent factory) and not yet authorable in the UI (Sprint 2.6-C builds the frontend). Both of those downstream sprints stub against the contract published here.

Skills follow the [`agentskills.io`](https://agentskills.io/specification) spec: a directory with a required `SKILL.md` (YAML frontmatter + Markdown body) and optional `references/`, `assets/`, `scripts/` subdirectories.

## 2. Scope

### In scope
- Pydantic models for skill metadata and frontmatter
- Account-scoped Firestore subcollection `accounts/{account_id}/skills/{skill_id}` — metadata (Shape B layout per [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1))
- GCS bucket layout: `gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/{version}/…` (keyed by `skill_id`, not `skill_name`, so renames don't split a skill's version history across two prefixes)
- CRUD REST API under `/api/v1/accounts/{account_id}/skills/` (consistent with `agent-configs`)
- Frontmatter validation per agentskills.io spec (name regex, description length, etc.)
- Size caps (SKILL.md ≤ 5 kB, individual file ≤ 100 kB, total bundle ≤ 2 MB; references-only file count ≤ 20 — assets and scripts are constrained by the total-bundle cap, not a per-directory file count)
- Skill loader service — reads metadata + GCS content, returns `models.Skill` instance with lazy L3 resources
- Soft-delete with 30-day retention
- Immutable versioning — each PUT creates a new version; previous versions remain in GCS
- `scripts/` directory is accepted and stored **but not validated for execution** in this sprint (Sprint 2.6-B / 2.6-D own attach-time enforcement)
- Integration tests against real Firestore + GCS (per CLAUDE.md T-5)
- Unit tests for validators, loader, and pagination

### Out of scope
- Frontend UI (Sprint 2.6-C)
- Agent factory integration (Sprint 2.6-B)
- Agent-builder attach-time validation (Sprint 2.6-D)
- Org sharing (v2) — but fields are forward-compat
- Skill import from external sources (v2)
- Prompt-injection content scanning (Sprint 2.6-D — after wiring is proven)

## 3. Dependencies

- **DM-PRD-00 (Migration Foundation) — hard prerequisite.** Lands the Shape B convention (`accounts/{account_id}/{resource}/…`) in `api/CLAUDE.md` and ships the shared `skills` collection-scope composite indexes via `_migrate_shape_b/resources.py` + Terraform. This PRD's Firestore paths (`accounts/{account_id}/skills/{skill_id}` + `…/versions/{version}`) and index section assume DM-PRD-00's registry is already authoritative. See [`../../data-management/projects/DM-PRD-00-migration-foundation.md`](../../data-management/projects/DM-PRD-00-migration-foundation.md).
- **DM-PRD-05 (Deletion Sweep Rewrite) — hard prerequisite.** Replaces the enumerated per-collection account-deletion sweep in `api/src/kene_api/routers/accounts.py` with `firestore.recursive_delete(accounts/{account_id})`. AC #13 (account-deletion sweep purges `accounts/{account_id}/skills/*` + `…/versions/*`) depends on that rewrite having landed. The matching GCS-prefix purge (`gs://kene-skills-{env}/accounts/{account_id}/…`) is added here via the existing `storage_service.delete_account_documents` helper. See [`../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md).
- **Existing files to study:**
  - `api/src/kene_api/models/` — Pydantic model conventions
  - `api/src/kene_api/routers/` — router patterns, Firebase auth dependency
  - `api/src/kene_api/services/firestore_service.py` — Firestore client patterns, cursor pagination helper
  - `app/utils/gcs.py` — GCS client patterns (reuse for skill content)
- **External:**
  - `google-cloud-storage` (already in use)
  - `google-cloud-firestore` (already in use)
  - `pyyaml` (frontmatter parsing)
  - Nothing new — all deps already present

## 4. Data contract

### Pydantic models

```python
# api/src/kene_api/models/skill_models.py

from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MAX_COMPATIBILITY_LEN = 500
MAX_SKILL_MD_BYTES = 5_000
MAX_REFERENCE_FILE_BYTES = 100_000
MAX_TOTAL_BUNDLE_BYTES = 2_000_000
MAX_REFERENCE_FILES = 20


class SkillOwner(BaseModel):
    """Account-scoped ownership. Skills belong to an account, not an individual user;
    `created_by` on the Skill doc captures the authoring user for audit purposes.

    `shared_with_accounts` is forward-compat for v2 cross-account sharing. Persisted
    but ignored in v1; no API surface reads or writes it.
    """
    account_id: str
    shared_with_accounts: list[str] = Field(default_factory=list)


class SkillSource(BaseModel):
    """Provenance info. None for user-authored in v1; populated by v2 import."""
    type: Literal["authored", "github"]
    repo: str | None = None          # for github type
    sha: str | None = None           # for github type
    license: str | None = None       # for github type


class SkillFrontmatter(BaseModel):
    """Parsed SKILL.md YAML frontmatter. Mirrors agentskills.io spec."""
    name: str = Field(max_length=MAX_NAME_LEN)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LEN)
    license: str | None = None
    compatibility: str | None = Field(default=None, max_length=MAX_COMPATIBILITY_LEN)
    metadata: dict[str, str] | None = None
    allowed_tools: str | None = Field(default=None, alias="allowed-tools")

    @field_validator("name")
    @classmethod
    def _name_regex(cls, v: str) -> str:
        if not SKILL_NAME_PATTERN.match(v):
            raise ValueError(
                f"name must be kebab-case, a-z0-9 and hyphens only, no leading/trailing/consecutive hyphens"
            )
        return v


class SkillStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SkillVisibility(str, Enum):
    PRIVATE = "private"
    # ORG = "org"  # v2


class Skill(BaseModel):
    """Firestore doc at accounts/{account_id}/skills/{skill_id}."""
    skill_id: str                              # UUID
    owner: SkillOwner                          # { account_id }
    name: str                                  # kebab-case; matches SKILL.md frontmatter name
    description: str                           # mirror of frontmatter description
    current_version: int                       # monotonically increasing; starts at 1
    visibility: SkillVisibility = SkillVisibility.PRIVATE
    status: SkillStatus = SkillStatus.DRAFT
    source: SkillSource = Field(default_factory=lambda: SkillSource(type="authored"))
    has_scripts: bool = False                  # true if any version's scripts/ is non-empty
    created_at: datetime
    created_by: str                            # user_id of the authoring user (audit only)
    updated_at: datetime
    updated_by: str                            # user_id of the user who last edited
    # `shared_with_accounts` lives on `SkillOwner` (forward-compat for v2 cross-account sharing).


class SkillVersion(BaseModel):
    """Immutable per-version snapshot. Stored at
    accounts/{account_id}/skills/{skill_id}/versions/{version_number}."""
    version: int
    gcs_prefix: str                            # e.g. accounts/acc_123/sk_8c3f.../3/
                                               # Keyed by skill_id (not skill_name) so renames
                                               # don't split a skill's version history across
                                               # two GCS prefixes.
    frontmatter: SkillFrontmatter
    file_manifest: list["SkillFileEntry"]
    created_at: datetime
    created_by: str                            # user_id of the user who cut this version
    commit_message: str | None = None


class SkillFileEntry(BaseModel):
    rel_path: str                              # e.g. "references/style-guide.md"
    kind: Literal["skill_md", "reference", "asset", "script"]
    size_bytes: int
    checksum_sha256: str
```

### Firestore layout

> **Revised 2026-04-20** — Firestore paths follow the Shape B layout (`accounts/{account_id}/{resource}/...`). See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for rationale.

```
accounts/{account_id}/skills/{skill_id}                       # Skill doc
accounts/{account_id}/skills/{skill_id}/versions/{version}    # SkillVersion subcollection doc
                                                              # (immutable once written)
```

Account-scoped under Shape B. Account deletion uses `firestore.recursive_delete(db.collection("accounts").document(account_id))`, which sweeps every subcollection (skills, versions, and any future resources) in one call — the existing hand-rolled per-collection sweep in `api/src/kene_api/routers/accounts.py` collapses to that single call.

Composite indexes (Terraform) — collection-scoped on the account's `skills` subcollection. Queries inside a single account use the collection scope; if future cross-account admin queries need all skills, a collection-group index on `skills` covers them:
```
collection: accounts/*/skills   (queryScope: COLLECTION)
  fields: [status ASC, updated_at DESC]
  fields: [has_scripts ASC, updated_at DESC]
```

### GCS layout

```
gs://kene-skills-{env}/
  accounts/{account_id}/{skill_id}/{version}/
    SKILL.md                        # required
    references/{filename}           # optional, 0..MAX_REFERENCE_FILES files
    assets/{filename}               # optional, no separate file-count cap (constrained by total-bundle cap only)
    scripts/{filename}              # optional, no separate file-count cap (constrained by total-bundle cap only)
    .manifest.json                  # generated on write: list of files + checksums + sizes
```

- The GCS prefix is keyed by `{skill_id}`, not `{skill_name}`. Renaming a skill (changing `name` in frontmatter on a PUT) does **not** move existing versions; every version's `gcs_prefix` is recorded on its `SkillVersion` doc and is stable for the life of that version.
- Each version is an **immutable snapshot**. Updating a skill creates `{version+1}/` alongside the previous version; previous versions are not deleted except by the soft-delete job.
- Soft-delete moves the skill's entire prefix to `gs://kene-skills-{env}-trash/accounts/{account_id}/{skill_id}/...` with a 30-day GCS lifecycle rule; archive is effectively permanent — no UI restoration is provided in v1.
- Bucket has **uniform access**, no public ACLs, CMEK with the project default key.

### Frontmatter validation

Beyond Pydantic validators above, on POST / PUT:
- `name` field in SKILL.md frontmatter MUST match the skill's root-level `name` (case-sensitive).
- `name` MUST be unique within the calling account at write-time (409 on conflict — see §6). `name` is mutable across versions: a PUT may change it (subject to the same regex + uniqueness rules); existing versions retain their original GCS prefixes (keyed by `skill_id`, not `name`).
- SKILL.md body MUST not exceed `MAX_SKILL_MD_BYTES` (5 kB).
- Files in `references/` MUST be ≤ `MAX_REFERENCE_FILES` (20). `assets/` and `scripts/` have **no per-directory file-count cap** — they are constrained by the total-bundle cap only.
- Each individual file (reference, asset, or script) ≤ `MAX_REFERENCE_FILE_BYTES` (100 kB). The constant is named for the original validation surface and applies uniformly to all bundle files.
- Total bundle ≤ `MAX_TOTAL_BUNDLE_BYTES` (2 MB).
- Reference paths must be 1 level deep from the skill root (per spec).

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `api/src/kene_api/models/skill_models.py` — Pydantic models shown above |
| Create | `api/src/kene_api/routers/skills.py` — CRUD endpoints (see §6) |
| Create | `api/src/kene_api/services/skill_storage.py` — GCS read/write/delete helpers; manifest generation |
| Create | `api/src/kene_api/services/skill_validator.py` — frontmatter + bundle validation (pure functions) |
| Create | `api/src/kene_api/services/skill_loader.py` — reads Firestore + GCS, returns `models.Skill` (ADK type) with lazy L3 resources |
| Modify | `api/src/kene_api/main.py` — register `/api/v1/accounts/{account_id}/skills` router |
| Modify | `api/src/kene_api/routers/accounts.py` — the account-deletion flow will already purge `accounts/{account_id}/skills/*` via `firestore.recursive_delete` once the flow is switched over (see the multi-tenant migration plan). This sprint additionally deletes the matching GCS prefix (`gs://kene-skills-{env}/accounts/{account_id}/…`). |
| Create | `deployment/terraform/gcs_skills_bucket.tf` — buckets (primary + trash), lifecycle policy, IAM, CMEK |
| Create | `deployment/terraform/firestore_indexes_skills.tf` — composite indexes |
| Create | `api/tests/unit/test_skill_validators.py` |
| Create | `api/tests/unit/test_skill_frontmatter_parse.py` |
| Create | `api/tests/unit/test_skill_loader.py` |
| Create | `api/tests/integration/test_skills_router.py` |
| Create | `api/tests/integration/test_skill_storage.py` |

### Skill loader — what it returns

The loader's job is to convert a stored skill into an ADK-consumable object. Sprint 2.6-B will import this loader.

```python
# api/src/kene_api/services/skill_loader.py

from google.adk.skills import models as adk_skill_models
# ↑ actual import path TBD against ADK v1.25.0+; verify at sprint start

async def load_skill(
    account_id: str,
    skill_id: str,
    *,
    version: int | None = None,
) -> adk_skill_models.Skill:
    """Return a hydrated ADK Skill object.

    `account_id` is required — it resolves the Firestore subcollection
    (`accounts/{account_id}/skills`) and the GCS prefix (`accounts/{account_id}/…`).
    Callers (e.g., the agent factory in Sprint 2.6-B) pass the account context
    they already have.

    L1 (frontmatter) and L2 (instructions body) are materialized eagerly from
    Firestore + GCS. L3 resources (references/assets/scripts) are stored as
    lazy-loadable references — the returned Skill's `resources` attribute
    points to callables that fetch content on demand.
    """
```

Lazy resources are implemented via a closure that, when invoked, streams the file from GCS and returns its content. This means SkillToolset's `load_skill_resource` tool ultimately triggers a GCS read, never returns stale content, and never materializes unused files into memory.

### Upload payload

`POST /api/v1/accounts/{account_id}/skills` accepts multipart:
- `skill_md` (required) — the SKILL.md file
- `files` (repeated, optional) — each with a `filename` form field encoding the full rel-path inside the bundle (e.g., `references/style-guide.md`, `scripts/extract.py`)

Server-side:
1. Parse and validate SKILL.md frontmatter.
2. Enforce all size / count caps.
3. Generate manifest (`file_manifest: list[SkillFileEntry]`) with sha256 checksums.
4. Allocate `skill_id` (UUID) and `version=1`.
5. Write files to `gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/1/` with `Cache-Control: no-cache`.
6. Run a Firestore transaction (see §9 Concurrent PUTs) that writes both `accounts/{account_id}/skills/{skill_id}` and `accounts/{account_id}/skills/{skill_id}/versions/1`. The version doc records the explicit `gcs_prefix` (so future renames don't break version-pinned reads).
7. Return the created `Skill`.

## 6. API contract

All endpoints require Firebase authentication (existing middleware) and are scoped by `account_id` in the path. Access control is enforced on every read and write via the existing account-access dependency (see `check_strategy_access` in `api/src/kene_api/routers/strategy.py` for the pattern to mirror).

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/accounts/{account_id}/skills` | Create a new skill (version 1). Multipart: `skill_md` + `files[]`. Returns `Skill`. |
| `GET` | `/api/v1/accounts/{account_id}/skills` | List account's skills. Query params: `status[]`, `has_scripts`, `cursor`, `page_size` (max 100). Returns `{items: [Skill], next_cursor}`. |
| `GET` | `/api/v1/accounts/{account_id}/skills/{skill_id}` | Fetch metadata only. |
| `GET` | `/api/v1/accounts/{account_id}/skills/{skill_id}/content` | Fetch SKILL.md body as `text/markdown`. Accept `?version=N` to pin. |
| `GET` | `/api/v1/accounts/{account_id}/skills/{skill_id}/resources/{rel_path}` | Fetch one reference/asset/script file. Path validated to stay within the skill prefix. Accept `?version=N`. |
| `PUT` | `/api/v1/accounts/{account_id}/skills/{skill_id}` | Create new version. Same multipart shape as POST plus optional `commit_message`. Increments `current_version`. Returns updated `Skill`. |
| `PATCH` | `/api/v1/accounts/{account_id}/skills/{skill_id}` | Status transition only — body `{"status": "draft" \| "published"}`. Idempotent. Does **not** create a new version. Used by the SK-PRD-03 "Publish" button. Returns updated `Skill`. |
| `DELETE` | `/api/v1/accounts/{account_id}/skills/{skill_id}` | Soft-archive: sets `status="archived"`, moves GCS prefix to trash bucket, does NOT immediately delete. Lifecycle rule purges after 30 days; archive is effectively permanent (no UI restore in v1). |
| `POST` | `/api/v1/accounts/{account_id}/skills/validate` | Dry-run validation. Same multipart shape as POST but no state is written. Returns validation report (OK or list of errors). |

Error responses follow the existing API error schema. Notable cases:
- `409 Conflict` if `POST` creates a skill whose `name` already exists in this account.
- `422` on any frontmatter or size-cap violation, with a field-pointer in the response body.
- `403` on any cross-account access (user is not a member of `account_id`, or skill's `owner.account_id` does not match the path).
- `404` on an archived skill (unless `?include_archived=true` on GET).

### Cross-account access

Access control is a two-layer check:
1. The **account-access dependency** (`check_account_access(account_id, user)` — reuse the strategy router's pattern) confirms the caller is a member of `account_id` with the appropriate role.
2. The handler then asserts `skill.owner.account_id == path.account_id`. Any mismatch → 403.

This means the path's `account_id` is the single source of truth for which collection is read/written, and skills can never be accessed through a different account's path. The `SkillOwner.shared_with_accounts` field is persisted but ignored in v1; v2's cross-account sharing logic hooks in here (add `or account_id in skill.owner.shared_with_accounts` to the second check).

## 7. Acceptance criteria

1. **Create & list:** A caller with access to `account_id=A` can POST a minimal skill (SKILL.md only), then GET it from `/api/v1/accounts/A/skills`. Metadata round-trips exactly; the Firestore doc lives at `accounts/A/skills/{skill_id}`.
2. **Frontmatter validation:** Uploading a SKILL.md with `name: PDF-Processing` returns 422 with a message referencing the regex. `name: pdf-processing` succeeds.
3. **Size caps:** Uploading a SKILL.md > 5 kB returns 422 pointing at `skill_md`. Uploading 21 reference files returns 422 pointing at `files[]`.
4. **Reference files:** A skill with `references/style-guide.md` can be fetched via `GET /api/v1/accounts/{account_id}/skills/{id}/resources/references/style-guide.md` with content-type `text/markdown`. A path traversal attempt like `../../../etc/passwd` returns 400.
5. **Versioning:** After a PUT, `current_version` increments, the new version's files are at a new GCS prefix, and the old version's files are still reachable via `GET …/content?version=1`.
6. **Soft-delete:** DELETE sets `status="archived"`; subsequent GET on the list endpoint (no `include_archived`) excludes it; GCS prefix is moved to `gs://kene-skills-{env}-trash/accounts/{account_id}/…`; a GCS lifecycle inspection shows the 30-day TTL rule active.
7. **Scripts accepted:** A POST with `scripts/extract.py` succeeds. The returned `Skill.has_scripts == true`. (No execution in this sprint.)
8. **Cross-account isolation:** A skill created in account A cannot be read, updated, or deleted via account B's path. `GET /api/v1/accounts/B/skills/{X.id}` returns 404 (not 403 — leaks less). A user who is not a member of account A receives 403 from the account-access dependency on any `/api/v1/accounts/A/skills/*` path.
9. **Name uniqueness:** POSTing a skill with `name: seo-checklist` to account A twice returns 409 on the second call. POSTing the same `name` to account B succeeds (uniqueness is per-account).
10. **Dry-run validation:** `POST /api/v1/accounts/{account_id}/skills/validate` with an invalid SKILL.md returns 200 with `{"valid": false, "errors": [...]}` and does not create any Firestore or GCS state.
11. **Loader:** `skill_loader.load_skill(account_id, skill_id)` returns an ADK `Skill` object whose `frontmatter.name` and `frontmatter.description` match the stored metadata. Calling `load_skill_resource("references/style-guide.md")` on the returned object streams the file from GCS under the correct account prefix.
12. **Tracing:** Every endpoint emits a W&B Weave span conforming to the existing [`trace-structure-spec.md`](../../../../trace-structure-spec.md) with `account_id` and `skill_id` attributes.
13. **Account deletion sweep:** Deleting an account (existing `routers/accounts.py` flow) purges `accounts/{account_id}/skills/*` via `firestore.recursive_delete` and the account's GCS prefix via the existing `storage_service.delete_account_documents` helper.
14. **All unit + integration tests pass** under `pytest api/tests/`. Lint (`make lint`) passes.

## 8. Test plan

### Unit tests (`api/tests/unit/`)

**`test_skill_validators.py`:**
- `name`: valid kebab-case cases; invalid (uppercase, leading hyphen, consecutive hyphens, >64 chars, empty)
- `description`: valid (1 char, 1024 chars); invalid (empty, >1024 chars)
- `compatibility`: valid (None, short string); invalid (>500 chars)
- `allowed-tools` alias: POST body using `allowed-tools` maps to model field `allowed_tools`
- Bundle caps: 0/1/20/21 reference files → OK/OK/OK/422; each file 0/100kB/100kB+1 → OK/OK/422
- Frontmatter `name` mismatching the POST-level `name` → 422

**`test_skill_frontmatter_parse.py`:**
- Round-trips each sample in the agentskills.io spec's examples
- Gracefully handles: no frontmatter, malformed YAML, frontmatter without `---` closer

**`test_skill_loader.py`:**
- Mocked GCS returns for SKILL.md body → ADK `Skill.instructions` is the Markdown body after the frontmatter
- Lazy resource callable is not invoked during `load_skill()`; only invoked when `load_skill_resource(rel_path)` is called
- Version pinning: `load_skill(skill_id, version=2)` reads from `…/2/` prefix

### Integration tests (`api/tests/integration/`)

Real Firestore (emulator OK) and real GCS (emulator or a test bucket per T-5).

**`test_skills_router.py`:**
- Full CRUD round-trip: POST → GET list → GET detail → PUT v2 → GET `?version=1` (old content) → DELETE → GET list (archived excluded) → GET `?include_archived=true` (included)
- Cross-account isolation:
  - A user who is not a member of account A gets 403 on any `/api/v1/accounts/A/skills/*` path (account-access dependency).
  - A member of both accounts A and B cannot read a skill created in A via the B path (404).
  - `owner.account_id` mismatch (inconsistent doc — simulated via direct Firestore write) returns 403.
- Name uniqueness: POSTing `name: seo-checklist` twice to the same account → 409; same name in different accounts → 201 both times.
- Account deletion sweep: deleting account A purges `accounts/A/skills/*` in Firestore and `gs://kene-skills-{env}/accounts/A/**` in GCS.
- Validate endpoint: `POST /validate` does not create state.

**`test_skill_storage.py`:**
- Uploaded bundle has correct GCS prefix structure
- Manifest file lists every uploaded file with correct sha256
- Path-traversal attempts on `GET /resources/{path}` (`..`, URL-encoded, etc.) all return 400
- Soft-delete moves prefix to trash bucket; original location returns 404

### Load characteristics (sanity, not formal load test)

Confirm a single POST of a 2MB bundle completes in <3s against a local Firestore emulator + real GCS.

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| `google.adk.skills` import path changes between ADK versions | Pin the ADK version at sprint start; re-verify the import path before writing loader code |
| Frontmatter YAML parser silently accepts tab indentation, which the agentskills.io spec doesn't comment on | Use `yaml.safe_load`; explicitly reject tabs in the indented section via a regex check before parse |
| Large reference files slow first-session load | L3 resources are lazy — no impact on L1/L2 session overhead; only the specific resource gets read |
| Users upload a 2MB image as an asset and blow the bundle cap | Document the cap in the authoring UI (Sprint 2.6-C); validate at upload |
| Accidental storage cost runaway | 30-day GCS lifecycle rule on trash bucket; per-user skill count cap (none in v1 — monitor) |
| Firebase auth middleware and the account-access dependency diverge | Reuse the existing `check_strategy_access` pattern verbatim (single source of truth for account-membership resolution); add a test asserting the skills dependency and the strategy dependency agree on access for the same `(user, account)` pair. |
| A user belongs to multiple accounts and expects skills to follow them | Account-scoped storage is deliberate — skills stay with the account they were authored in. If a real "move skill across accounts" use case emerges, build an explicit "copy skill to account" action (v2); do NOT widen the ownership model. |
| Concurrent PUTs racing on `current_version` | A Firestore transaction wraps each PUT: (1) read the `Skill` doc to get `current_version=N`; (2) write the new `versions/{N+1}` subcollection doc using `transaction.create()` (fails if the path already exists); (3) update `Skill.current_version = N+1` atomically. Firestore retries on contention, and the loser observes `current_version=N+1` and re-attempts with `N+2`. The GCS write happens **before** the transaction commits, using the predicted `{skill_id}/{N+1}/` prefix; on retry the GCS write re-runs with `{N+2}/`. Orphan GCS prefixes from failed transactions are cleaned by a daily sweeper job that compares Firestore `versions/*` against GCS prefixes and deletes prefixes with no matching version doc older than 1 hour. |
| User deletion (DM-PRD-05) leaves orphan `created_by` / `updated_by` IDs on Skill / SkillVersion docs | Acceptable — these fields are audit-only string IDs. Skills does **not** register an `on_user_removed` hook (unlike Integrations) because skills are account-scoped and persist with the account. Document the policy in the README. |
| User edits a skill's content and breaks every agent that has it attached (latest-wins skill version pinning) | See §9 latest-wins note in the README + SK-PRD-03 UI warning + SK-PRD-04 user-guide section. v1 ships latest-wins by deliberate trade-off; per-attachment version pinning is reserved for a v2 enhancement. |

### Open questions

- **Q:** Should the `name` field be **unique per account** or globally? → **v1 answer: per account.** An account can't have two skills named `seo-checklist`, but different accounts can. Enforced at the POST handler via a query on `accounts/{account_id}/skills` before write; returns 409 on conflict.
- **Q:** What's the policy when a user deletes a skill that's attached to an agent? → **Out of this sprint.** Sprint 2.6-D handles attach-time validation; the agent-config endpoint rejects PUTs referencing archived skill IDs. Soft-archive does NOT cascade — attached agents silently lose the skill from their L1 metadata next session.
- **Q:** Do we need a separate audit collection (`skills_audit_{account_id}`)? → **v1 answer: no.** The `versions/` subcollection already captures who changed what and when (created_by, created_at, commit_message on each version doc). Skills opts out of DM-PRD-07's audit substrate by design; per-version `created_by` + `commit_message` is the audit trail. Add a dedicated audit collection only if v2 requirements surface (e.g., who viewed a skill, non-version-bumping field edits).

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §4 (Data model), §5 (API surface)
- Spec: [agentskills.io specification](https://agentskills.io/specification)
- Pattern files: `api/src/kene_api/routers/project_plans.py`, `api/src/kene_api/services/firestore_service.py`, `app/utils/gcs.py`
- Tracing spec: [`trace-structure-spec.md`](../../../../trace-structure-spec.md)
- CLAUDE.md rules in scope: D-1, D-2, D-5; PY-1, PY-2, PY-5, PY-7; T-1, T-3, T-4, T-5, T-7, T-8
