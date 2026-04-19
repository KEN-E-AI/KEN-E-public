# Sprint 2.6-A — Skills Backend: Storage, API, Loader

**Status:** Ready to start (no prerequisites)
**Owner team:** Backend
**Blocked by:** —
**Parallel with:** Sprint 9, 2.6-0, 2.6-C (against contract)
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
- Firestore collection `skills/{skill_id}` — metadata
- GCS bucket layout: `gs://kene-skills-{env}/users/{user_id}/{skill_name}/{version}/…`
- CRUD REST API under `/api/v1/skills/`
- Frontmatter validation per agentskills.io spec (name regex, description length, etc.)
- Size caps (SKILL.md ≤ 5kB, reference file ≤ 100 kB, total bundle ≤ 2 MB, ≤ 20 reference files)
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
- **No blocking external dependency** — this sprint can start day 1.

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
    type: Literal["user"]  # "org" reserved for v2
    id: str  # user_id


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
    """Firestore doc at skills/{skill_id}."""
    skill_id: str                              # UUID
    owner: SkillOwner
    name: str                                  # kebab-case; matches SKILL.md frontmatter name
    description: str                           # mirror of frontmatter description
    current_version: int                       # monotonically increasing; starts at 1
    visibility: SkillVisibility = SkillVisibility.PRIVATE
    status: SkillStatus = SkillStatus.DRAFT
    source: SkillSource = Field(default_factory=lambda: SkillSource(type="authored"))
    has_scripts: bool = False                  # true if any version's scripts/ is non-empty
    created_at: datetime
    created_by: str                            # user_id
    updated_at: datetime
    updated_by: str
    # Forward-compat, unused in v1:
    shared_with: list[str] = Field(default_factory=list)


class SkillVersion(BaseModel):
    """Immutable per-version snapshot. Stored at
    skills/{skill_id}/versions/{version_number}."""
    version: int
    gcs_prefix: str                            # e.g. users/u_123/seo-checklist/3/
    frontmatter: SkillFrontmatter
    file_manifest: list["SkillFileEntry"]
    created_at: datetime
    created_by: str
    commit_message: str | None = None


class SkillFileEntry(BaseModel):
    rel_path: str                              # e.g. "references/style-guide.md"
    kind: Literal["skill_md", "reference", "asset", "script"]
    size_bytes: int
    checksum_sha256: str
```

### Firestore layout

```
skills/{skill_id}                       # Skill doc
skills/{skill_id}/versions/{version}    # SkillVersion subcollection doc
                                        # (immutable once written)
```

Composite index (Terraform):
```
collection: skills
  fields: [owner.id ASC, status ASC, updated_at DESC]
  fields: [owner.id ASC, has_scripts ASC, updated_at DESC]
```

### GCS layout

```
gs://kene-skills-{env}/
  users/{user_id}/{skill_name}/{version}/
    SKILL.md                        # required
    references/{filename}           # optional, 0..MAX_REFERENCE_FILES files
    assets/{filename}               # optional
    scripts/{filename}              # optional
    .manifest.json                  # generated on write: list of files + checksums + sizes
```

- Each version is an **immutable snapshot**. Updating a skill creates `{version+1}/` alongside the previous version; previous versions are not deleted except by the soft-delete job.
- Soft-delete moves the skill's entire prefix to `gs://kene-skills-{env}-trash/users/...` with a 30-day GCS lifecycle rule; no human intervention needed to purge.
- Bucket has **uniform access**, no public ACLs, CMEK with the project default key.

### Frontmatter validation

Beyond Pydantic validators above, on POST / PUT:
- `name` field in SKILL.md frontmatter MUST match the skill's root-level `name` (case-sensitive).
- SKILL.md body MUST not exceed `MAX_SKILL_MD_BYTES` (5kB).
- Total reference file count ≤ `MAX_REFERENCE_FILES` (20).
- Each reference/asset/script file ≤ `MAX_REFERENCE_FILE_BYTES` (100kB).
- Total bundle ≤ `MAX_TOTAL_BUNDLE_BYTES` (2MB).
- Reference paths must be 1 level deep from the skill root (per spec).

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `api/src/kene_api/models/skill_models.py` — Pydantic models shown above |
| Create | `api/src/kene_api/routers/skills.py` — CRUD endpoints (see §6) |
| Create | `api/src/kene_api/services/skill_storage.py` — GCS read/write/delete helpers; manifest generation |
| Create | `api/src/kene_api/services/skill_validator.py` — frontmatter + bundle validation (pure functions) |
| Create | `api/src/kene_api/services/skill_loader.py` — reads Firestore + GCS, returns `models.Skill` (ADK type) with lazy L3 resources |
| Modify | `api/src/kene_api/main.py` — register `/api/v1/skills` router |
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

async def load_skill(skill_id: str, *, version: int | None = None) -> adk_skill_models.Skill:
    """Return a hydrated ADK Skill object.

    L1 (frontmatter) and L2 (instructions body) are materialized eagerly from
    Firestore + GCS. L3 resources (references/assets/scripts) are stored as
    lazy-loadable references — the returned Skill's `resources` attribute
    points to callables that fetch content on demand.
    """
```

Lazy resources are implemented via a closure that, when invoked, streams the file from GCS and returns its content. This means SkillToolset's `load_skill_resource` tool ultimately triggers a GCS read, never returns stale content, and never materializes unused files into memory.

### Upload payload

`POST /api/v1/skills` accepts multipart:
- `skill_md` (required) — the SKILL.md file
- `files` (repeated, optional) — each with a `filename` form field encoding the full rel-path inside the bundle (e.g., `references/style-guide.md`, `scripts/extract.py`)

Server-side:
1. Parse and validate SKILL.md frontmatter.
2. Enforce all size / count caps.
3. Generate manifest (`file_manifest: list[SkillFileEntry]`) with sha256 checksums.
4. Allocate `skill_id` (UUID) and `version=1`.
5. Write files to `gs://kene-skills-{env}/users/{user_id}/{frontmatter.name}/1/` with `Cache-Control: no-cache`.
6. Write `skills/{skill_id}` Firestore doc and `skills/{skill_id}/versions/1` doc in a single transaction.
7. Return the created `Skill`.

## 6. API contract

All endpoints require Firebase authentication (existing middleware). Ownership is enforced on every read and write.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/skills` | Create a new skill (version 1). Multipart: `skill_md` + `files[]`. Returns `Skill`. |
| `GET` | `/api/v1/skills` | List caller's skills. Query params: `status[]`, `has_scripts`, `cursor`, `page_size` (max 100). Returns `{items: [Skill], next_cursor}`. |
| `GET` | `/api/v1/skills/{skill_id}` | Fetch metadata only. |
| `GET` | `/api/v1/skills/{skill_id}/content` | Fetch SKILL.md body as `text/markdown`. Accept `?version=N` to pin. |
| `GET` | `/api/v1/skills/{skill_id}/resources/{rel_path}` | Fetch one reference/asset/script file. Path validated to stay within the skill prefix. Accept `?version=N`. |
| `PUT` | `/api/v1/skills/{skill_id}` | Create new version. Same multipart shape as POST plus optional `commit_message`. Increments `current_version`. Returns updated `Skill`. |
| `DELETE` | `/api/v1/skills/{skill_id}` | Soft-archive: sets `status="archived"`, moves GCS prefix to trash bucket, does NOT immediately delete. Lifecycle rule purges after 30 days. |
| `POST` | `/api/v1/skills/validate` | Dry-run validation. Same multipart shape as POST but no state is written. Returns validation report (OK or list of errors). |

Error responses follow the existing API error schema. Notable cases:
- `409 Conflict` if `POST` creates a skill whose `name` already exists for this owner.
- `422` on any frontmatter or size-cap violation, with a field-pointer in the response body.
- `403` on any cross-owner access.
- `404` on an archived skill (unless `?include_archived=true` on GET).

### Cross-owner access

`owner.id` in the Firestore doc is compared against the authenticated user's `uid`. Any mismatch → 403. No `account_id` check in v1 — skills are personal — but the check is implemented as a helper `check_skill_access(skill, user)` that takes the full user context so v2's org-sharing logic can drop in without rewriting every endpoint.

## 7. Acceptance criteria

1. **Create & list:** A user can POST a minimal skill (SKILL.md only), then GET it from `/api/v1/skills`. Metadata round-trips exactly.
2. **Frontmatter validation:** Uploading a SKILL.md with `name: PDF-Processing` returns 422 with a message referencing the regex. `name: pdf-processing` succeeds.
3. **Size caps:** Uploading a SKILL.md > 5 kB returns 422 pointing at `skill_md`. Uploading 21 reference files returns 422 pointing at `files[]`.
4. **Reference files:** A skill with `references/style-guide.md` can be fetched via `GET /api/v1/skills/{id}/resources/references/style-guide.md` with content-type `text/markdown`. A path traversal attempt like `../../../etc/passwd` returns 400.
5. **Versioning:** After a PUT, `current_version` increments, the new version's files are at a new GCS prefix, and the old version's files are still reachable via `GET …/content?version=1`.
6. **Soft-delete:** DELETE sets `status="archived"`; subsequent GET on the list endpoint (no `include_archived`) excludes it; GCS prefix is moved to the trash bucket; a GCS lifecycle inspection shows the 30-day TTL rule active.
7. **Scripts accepted:** A POST with `scripts/extract.py` succeeds. The returned `Skill.has_scripts == true`. (No execution in this sprint.)
8. **Cross-owner isolation:** User A POSTs skill X. User B's GET `/api/v1/skills/{X.id}` returns 403.
9. **Dry-run validation:** `POST /api/v1/skills/validate` with an invalid SKILL.md returns 200 with `{"valid": false, "errors": [...]}` and does not create any Firestore or GCS state.
10. **Loader:** `skill_loader.load_skill(skill_id)` returns an ADK `Skill` object whose `frontmatter.name` and `frontmatter.description` match the stored metadata. Calling `load_skill_resource("references/style-guide.md")` on the returned object streams the file from GCS.
11. **Tracing:** Every endpoint emits a W&B Weave span conforming to the existing [`trace-structure-spec.md`](../../../trace-structure-spec.md) with `skill_id` attribute.
12. **All unit + integration tests pass** under `pytest api/tests/`. Lint (`make lint`) passes.

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
- Cross-owner: user B cannot access user A's skill on any endpoint
- Validate endpoint: `POST /validate` does not create state

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
| Firebase auth middleware and the `check_skill_access` helper diverge | Add a test that asserts `check_skill_access` reads the same `uid` claim the middleware does |

### Open questions

- **Q:** Should the `name` field be **unique per owner** or globally? → **v1 answer: per owner.** A user can't have two skills named `seo-checklist`, but different users can. Enforced via Firestore (there's no unique constraint, so the POST handler checks existence and returns 409).
- **Q:** What's the policy when a user deletes a skill that's attached to an agent? → **Out of this sprint.** Sprint 2.6-D handles attach-time validation; the agent-config endpoint rejects PUTs referencing archived skill IDs. Soft-archive does NOT cascade — attached agents silently lose the skill from their L1 metadata next session.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §4 (Data model), §5 (API surface)
- Spec: [agentskills.io specification](https://agentskills.io/specification)
- Pattern files: `api/src/kene_api/routers/project_plans.py`, `api/src/kene_api/services/firestore_service.py`, `app/utils/gcs.py`
- Tracing spec: [`../../trace-structure-spec.md`](../../../trace-structure-spec.md)
- CLAUDE.md rules in scope: D-1, D-2, D-5; PY-1, PY-2, PY-5, PY-7; T-1, T-3, T-4, T-5, T-7, T-8
