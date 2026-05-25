# SK-PRD-05 — Predefined Skill Foundation (Example Skill)

**Status:** Blocked (requires SK-PRD-01, SK-PRD-02, AH-PRD-02)
**Owner team:** Backend + Agent Platform
**Blocked by:** SK-PRD-01, SK-PRD-02, AH-PRD-02
**Parallel with:** SK-PRD-03, SK-PRD-04
**Blocks:** —
**Estimated effort:** 2–3 days

---

## 1. Context

KEN-E ships with a small set of **system-owned skills** attached to selected specialists, separate from user-authored skills. System Architecture §6 promises this; SK-PRDs 01–04 deliver the user-authored half but never seed any predefined skill.

This PRD ships exactly **one placeholder predefined skill** (`example-skill`) plus the loader path that lets the agent factory resolve system skill IDs. It exists to:

1. Validate the system-owned-skill loader path end-to-end.
2. Establish the storage convention (separate Firestore collection + GCS prefix) so future predefined skills are content-only PRs (one SKILL.md, one config update) — no schema, API, or factory change.
3. Prove the architectural claim in System Architecture §6 ("KEN-E ships with a bundled set of predefined skills").

After this PRD ships, every subsequent predefined skill is purely content — drop a new doc into `system_skills/*` via Terraform and reference its ID in a specialist's `agent_configs/*` document.

**Where system skills attach (post-AH-PRD-09).** Under [AH-PRD-09](../../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) Phase 2, the deployed root agent carries only `delegate_to_specialist` — it has no `SkillToolset` and no `list_skills` tool, so `skill_ids` on the root config has no effect. System skills therefore attach to **specialists**. v1 attaches `example-skill` to `agent_configs/google_analytics_specialist` (the R1 specialist shipped by [AH-PRD-03](../../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md)) to validate the loader end-to-end against a real specialist. Broader rollout — where every specialist receives one or more system skills automatically — is the work of a follow-up PRD that introduces a `default_global: true` skills mechanism analogous to AH-PRD-06 PR-C's `default_global` function-tool injection. v1 keeps the scope at one specialist + one skill so the validation surface is minimal.

### What this PRD is NOT

- Not a curated production skill — `example-skill`'s body is a one-paragraph placeholder. Replacing it with real domain skills (e.g., `ga-attribution-checklist`, `seo-audit`) is the work of separate content PRDs sequenced after this one.
- Not a marketplace, sharing system, or v2 import path.
- Not visible in the user-facing Skills tab — system skills are backend-only.

## 2. Scope

### In scope

- New global Firestore collection `system_skills/{skill_id}` mirroring the per-account `Skill` shape, minus the per-account fields. Read-only via a super-admin Terraform path.
- New global GCS prefix `gs://kene-skills-{env}/_system/{skill_name}/{version}/` (sibling to `accounts/`) for system-skill bundle content. Keyed by `skill_name` because system skills are unique by name globally and renames are operations-driven (Terraform diff).
- Extend `skill_loader.load_skill(account_id, skill_id)` to first check `system_skills/{skill_id}`; if found, read content from the global `_system/` GCS prefix; otherwise fall back to the existing per-account path.
- Extend `_build_skill_toolset` (SK-PRD-02) to accept a mixed list of account-scoped and system skill IDs without code changes — the loader handles the dispatch.
- Seed exactly one system skill: `example-skill` with a placeholder SKILL.md body.
- Attach `example-skill`'s ID to **`agent_configs/google_analytics_specialist`** via the existing `skill_ids: list[str]` field. (The root agent is **not** an attachment target — see §1.)
- Document the system-owned-skill convention in Skills README §7.

### Out of scope

- Authoring or editing system skills via UI — operations is a Terraform PR.
- Real domain content (the body is a placeholder string; real predefined skills are separate content PRDs).
- Per-account override of system skills (a user cannot edit or replace `example-skill`).
- Surfacing system skills in the user-facing Skills tab (`/workflows/skills`) — they remain backend-only.
- System skill versioning UI — version bumps are Terraform-driven.

## 3. Dependencies

- **SK-PRD-01** — Skill data model and loader exist; this PRD extends the loader to recognize global IDs.
- **SK-PRD-02** — Factory's `_build_skill_toolset` consumes `skill_ids` and runs the loader; this PRD seeds an ID into a specialist config and proves the dispatch.
- **AH-PRD-02** — Specialist `agent_configs/*` exist with the `skill_ids: list[str]` forward-compat field; CRUD endpoints accept the field.
- **[AH-PRD-03](../../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md)** — Ships `agent_configs/google_analytics_specialist`, the attachment target for `example-skill`. SK-PRD-05's Terraform `skill_ids` mutation lands on top of the doc AH-PRD-03 creates.
- **[AH-PRD-09](../../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) (informational)** — Establishes the post-Phase-2 root model (`delegate_to_specialist`-only). The reason this PRD attaches to a specialist rather than the root.

No frontend dependency. No new external library.

## 4. Data contract

### Pydantic addition

`api/src/kene_api/models/skill_models.py` gains:

```python
class SystemSkillOwner(BaseModel):
    """System-owned skill ownership marker. No account_id — system skills are global."""
    type: Literal["system"] = "system"


# `Skill.owner` becomes a discriminated union:
#   owner: Annotated[Union[SkillOwner, SystemSkillOwner], Field(discriminator="...")]
# (Implementation detail — pick whichever Pydantic v2 idiom is least invasive.
# A simpler alternative is two separate Pydantic classes (`Skill` + `SystemSkill`)
# with shared base; choose at sprint start based on read-path ergonomics.)
```

`status` for system skills is always `"published"`. There is no draft state.

### Firestore layout

```
system_skills/{skill_id}                       # global, not under accounts/
system_skills/{skill_id}/versions/{version}    # immutable per-version snapshot, mirrors per-account shape
```

System skills are NOT under `accounts/{account_id}/`. They are global. Reads bypass the account-access dependency; writes are not exposed via the user API.

### GCS layout

```
gs://kene-skills-{env}/
  _system/{skill_name}/{version}/
    SKILL.md
    references/                      # optional
    assets/                          # optional
    .manifest.json                   # generated on Terraform apply
```

Note: keyed by `{skill_name}` (not `{skill_id}`) because system skill names are globally unique and renames are operations events handled in Terraform diff. This is a deliberate divergence from the per-account convention (which uses `{skill_id}` to absorb arbitrary user-driven renames).

The `_system/` top-level prefix sibling to `accounts/` makes IAM straightforward: read-public-to-the-loader-service-account, write-only-via-Terraform-managed-service-account.

### Loader resolution

```python
async def load_skill(account_id: str, skill_id: str, *, version: int | None = None) -> adk_skill_models.Skill:
    # 1. Try system_skills/{skill_id}
    system_doc = await _get_system_skill_doc(skill_id)
    if system_doc is not None:
        return await _hydrate_system_skill(system_doc, version=version, account_id=account_id)
    # 2. Fall back to accounts/{account_id}/skills/{skill_id}  (existing path)
    return await _hydrate_account_skill(account_id, skill_id, version=version)
```

`account_id` is still threaded through for tracing and Weave span attribution, even when resolving a system skill.

### Tracing

The existing `skill.list` / `skill.load` / `skill.load_resource` spans (SK-PRD-02) include a new attribute `skill_owner_type: "account" | "system"` so MER-E can distinguish system-skill use from user-skill use.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/models/skill_models.py` — add `SystemSkillOwner`; widen `Skill.owner` to accept either, OR introduce a sibling `SystemSkill` class. Decide at sprint start. |
| Modify | `api/src/kene_api/services/skill_loader.py` — add system-skill path resolution; existing per-account path unchanged |
| Create | `deployment/terraform/system_skills_seed.tf` — Terraform resources that (a) write `gs://kene-skills-{env}/_system/example-skill/1/SKILL.md`, (b) seed Firestore `system_skills/{skill_id}` doc + `versions/1` subcollection doc with the same fields the per-account loader expects |
| Create | `skills/_system/example-skill/1/SKILL.md` — placeholder content. Frontmatter: `name: example-skill`, `description: "Example placeholder skill demonstrating the predefined-skill mechanism."`, `compatibility: "Any KEN-E agent"`. Body: a one-paragraph note that this is a placeholder skill, removed when real content lands. |
| Modify | `agent_configs/google_analytics_specialist` (created by AH-PRD-03) — add `example-skill`'s system ID to `skill_ids` |
| Modify | `_build_skill_toolset` (SK-PRD-02) — emit `skill_owner_type` Weave attribute. No dispatch change required (loader handles it). Lives in `app/adk/agents/agent_factory/__init__.py` on the deploy-time path and `app/adk/agents/agent_factory/specialist_runtime.py` on the runtime-resolver path (AH-PRD-09 Phase 2); the Weave-attribute change applies in both places. |
| Modify | `docs/design/components/skills/README.md` §7 Conventions — add the system-owned-skill paragraph |
| Modify | `docs/trace-structure-spec.md` — extend the three skill spans' attribute tables with `skill_owner_type` |
| Create | `app/adk/agents/test_system_skills.py` — integration test: factory builds the root agent → `list_skills` returns `example-skill` → end-to-end agent run loads its body |
| Modify | `api/tests/integration/test_skills_router.py` — assert system skill is invisible from the per-account user API (404 on direct GET, not in list response) |

## 6. API contract

No new HTTP endpoints. The user-facing Skills API is unchanged. Loader behavior is the only contract change and it is internal.

## 7. Acceptance criteria

1. **System skill seeded:** After Terraform apply against a fresh environment, Firestore has a `system_skills/{skill_id}` doc and GCS has `gs://kene-skills-{env}/_system/example-skill/1/SKILL.md`.
2. **Loader resolves system IDs:** `skill_loader.load_skill(account_id="any", skill_id="<system_id>")` returns an ADK `Skill` whose `frontmatter.name == "example-skill"`. Works for any `account_id` value (system skills are not account-scoped).
3. **Loader still resolves account IDs:** `skill_loader.load_skill(account_id, skill_id)` for an account-owned skill is unchanged.
4. **GA Specialist picks up the skill:** When the factory builds `agent_configs/google_analytics_specialist` (deploy-time via `build_hierarchy` or per turn via `specialist_runtime.resolve_agent` under AH-PRD-09), the resulting specialist's `SkillToolset.list_skills` includes `example-skill` with its L1 metadata visible. The root agent does **not** receive a `SkillToolset` — it carries only `delegate_to_specialist`.
5. **End-user cannot read system skill via the user-facing API:**
   - `GET /api/v1/accounts/{account_id}/skills` does not include system skills.
   - `GET /api/v1/accounts/{account_id}/skills/{system_skill_id}` returns 404.
   - `PUT` / `PATCH` / `DELETE` against any system-skill ID via the user API returns 404 (not 403 — leaks less).
6. **Tracing:** A `skill.list` span emitted by an agent that has the system skill attached includes the system skill's `skill_id`, `skill_name`, and `skill_owner_type="system"`. An account skill's spans get `skill_owner_type="account"`.
7. **Trace spec updated:** `docs/trace-structure-spec.md` documents the new `skill_owner_type` attribute on the three skill spans.
8. **README updated:** Skills README §7 Conventions has a "System-owned skills" subsection.
9. **All unit + integration tests pass.** `make lint` passes.

## 8. Test plan

### Unit

- `test_skill_models.py`: `Skill` accepts both `SkillOwner` and `SystemSkillOwner`; serialization round-trips both.
- `test_skill_loader.py`: extend with a `system_skills/*` Firestore fixture and a `_system/` GCS fixture; assert path-resolution branches correctly; assert `account_id` is forwarded to the Weave span even when resolving a system skill.

### Integration

- `test_system_skills.py`: seed a system skill via test fixture (Terraform-equivalent); build the root agent via `build_hierarchy(account_id=...)`; assert `list_skills` returns `example-skill`; trigger `load_skill` and assert content matches.
- `test_skills_router.py` (extension): seed a system skill and assert it is invisible from `GET /api/v1/accounts/{account_id}/skills` and that direct GETs return 404.

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Confusing UX when a user sees an L1 description of a system skill in tracing/logs | The skill's `name` makes its source obvious (`example-skill`); future predefined skills will be named with a clear `kene-` prefix to disambiguate. |
| Terraform-driven content updates are slow vs. UI authoring | Acceptable — system skills should change rarely. If frequent updates emerge, add an admin-only authoring UI in v2. |
| `Skill.owner` becoming a discriminated union ripples through every existing callsite | Pick the least-invasive Pydantic idiom at sprint start (union vs. sibling class) and benchmark by counting touched files. Prefer sibling class if union touches > 10 files. |
| System skill's `version` numbering collides with per-account semantics | `system_skills/{skill_id}/versions/*` mirrors the per-account shape; future system-skill version bumps work the same way. |
| `example-skill` as placeholder content shows up to real users in tracing | Acceptable for v1 — replace with real predefined skill content in a follow-up content PR before GA of any skill-bearing specialist. |
| Single-specialist attachment doesn't scale once R5 adds Google Ads / Meta Ads / Mailchimp specialists | v1's one-skill-per-one-specialist scope is the minimum needed to validate the loader path. A follow-up PRD introduces a `default_global: true` skills mechanism (mirroring [AH-PRD-06](../../agentic-harness/projects/AH-PRD-06-tool-mapping.md) PR-C's function-tool injection at `hierarchy.py:325` + the AH-PRD-09 Phase 3 port into `specialist_runtime.resolve_agent`) so a system skill registered with `default_global: true` reaches every runtime-resolved specialist automatically. Out of scope for this PRD; tracked as a successor work item. |

### Open questions

- **Q:** Should system skills be pinned to a version on the consuming agent config, or always latest? → **v1 answer: latest-wins, same as account skills.** Operations-controlled rollout is sufficient since Terraform-driven version bumps are deliberate. Per-attachment pinning would only be needed if we expect mid-bump A/B; not a real ask in v1.
- **Q:** Should there be a separate Firestore index or composite query for "all skills (system + account-scoped) attached to this agent"? → **v1 answer: no.** The loader iterates `skill_ids` one-by-one; that's already an O(N) GCS read per build, adding a query lookup doesn't help. Revisit if profiling surfaces a problem.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) (legacy — superseded by `README.md` and `projects/SK-PRD-*`)
- Sister sprints: [`SK-PRD-01`](./SK-PRD-01-skills-backend.md), [`SK-PRD-02`](./SK-PRD-02-agent-integration.md), [`SK-PRD-03`](./SK-PRD-03-authoring-ui.md), [`SK-PRD-04`](./SK-PRD-04-agent-builder-controls.md)
- Upstream project: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory)
- System Architecture: [§6 Skills Architecture](../../../../KEN-E-System-Architecture.md#6-skills-architecture-planned)
- Tracing: [`trace-structure-spec.md`](../../../../trace-structure-spec.md)
- CLAUDE.md rules in scope: D-1, D-2; PY-1, PY-2; T-1, T-3, T-5
