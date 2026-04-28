# CH-PRD-06 — Documentation Link Integrity & CI Enforcement

**Status:** Substantially shipped — CH-1 (chat-PRD forward-reference cleanup, verified clean by lychee against `main`) + CH-2 (`lychee.toml`) + CH-3 (`pr_checks.yaml` step) + CH-5 (`CLAUDE.md` G-4) complete. CH-4 (negative-test verification on a throwaway PR) is the only item remaining; that's a runtime verification done after this PR merges, not a code change. Note: a cross-repo cleanup of 9 unrelated broken links (`deployment/README.md` × 2, `deployment/redis/README.md`, `AH-PRD-05`, `SK-PRD-05` × 2, `UI-PRD-07`, `frontend/README.md` × 2) was bundled into the same PR so the new CI gate exits 0 on `main`.
**Owner team:** Chat component team (docs-quality scope; tooling work bundled here because the immediate doc-cleanup is in chat/)
**Blocked by:** none (PR #241 merge is the trigger event, not a strict blocker)
**Parallel with:** any other docs work
**Blocks:** none
**Estimated effort:** 0.5 days (single-PR scope)

---

## 1. Context

PR #241 (`docs/restructure-and-dashboards`) restructured the design directory around a 15-component model and rewrote ~30 outbound Notion URLs as in-repo `DESIGN-REVIEW-LOG.md` Review anchors. The "0 broken links" claim in that PR was a manual verification — there is no CI gate enforcing it, so future regressions are easy.

A local link scan during PR #241 review surfaced **123 broken relative links** total across `docs/`, of which 94 are in `docs/figma-export/` (tool-generated artifacts), 20 in `docs/archive/` (intentionally references retired files), and **9 are in `docs/design/components/chat/**`** — all forward-references to implementation files that don't exist yet (`api/src/kene_api/routers/chat.py`, `app/adk/session/recovery.py`, etc.). A link to a non-existent file is misleading for human readers and noise for automated tooling.

CH-PRD-06 is a **tooling PRD bundled under Chat** because (a) Chat is where the 9 immediate doc-cleanup edits land, and (b) there is no first-class "tooling" or "DevEx" component in the 15-component model. The PRD is small-scoped (one CI step + one config file + nine link-to-inline-code conversions + one CLAUDE.md bullet) and exists primarily to lock in the link-integrity guarantee from PR #241 before it decays.

The validation checkpoint is that a PR introducing a deliberate broken link to a docs file fails the new CI gate, and the current `main` continues to pass.

## 2. Scope

### In scope

- **Convert 9 chat-PRD forward-references from broken markdown links to inline code** — 5 files in `docs/design/components/chat/`. Concrete list in [CH-1](https://linear.app/ken-e/issue/CH-1/convert-chat-prd-forward-references-from-broken-links-to-inline-code).
- **`lychee.toml` config at repo root** — `--offline` mode (no remote URL checking); excludes `docs/figma-export/**`, `docs/archive/**`, `**/node_modules/**`, `.git/**`; scans `docs/**/*.md` and root-level `*.md` (`CLAUDE.md`, `README.md`, `REVIEW.md`).
- **New `markdown-link-check` step in `deployment/ci/pr_checks.yaml`** — runs `lycheeverse/lychee:latest` Docker image; hard-fail on broken links; runs on every PR (no path filter).
- **Negative-test verification** — a deliberate broken-link PR is confirmed to fail the new step before CH-PRD-06 closes. Throwaway branch only; no production diff.
- **`CLAUDE.md` §6 Tooling Gates entry as G-4** — wording matches G-1/G-2/G-3 style; includes local-install instructions (`brew install lychee` / `cargo install lychee`).

### Out of scope

- **Online URL checking** — `--offline` mode is the design choice. Rate-limit flakiness and the need to allowlist intentional historical Notion URLs (see `agentic-harness/mcp-architecture.md`, `knowledge-graph/README.md`, `data-management/README.md`) make online checks unsuitable for a per-PR gate. If external link rot becomes a concern, that's a separate scheduled job, not this PRD.
- **`docs/figma-export/` cleanup** — generated content (94 broken refs); not authored by humans; not worth fixing.
- **`docs/archive/` cleanup** — historical content that intentionally references retired files; the broken refs are accurate-for-their-time records.
- **`make lint` integration** — keeping `make lint` Python/JS-focused; conflating it complicates the local-dev story for contributors who don't have lychee installed. The CI gate is higher leverage.
- **lychee version pin** — `:latest` is acceptable for v1; pinning to a specific tag is a follow-up if reproducibility becomes a concern.
- **GitHub Actions workflow** — this repo runs CI through Cloud Build (`deployment/ci/pr_checks.yaml`), not GitHub Actions. There is no `.github/workflows/` directory.
- **Pre-creating the chat forward-reference target files** to satisfy the link checker — the right fix is the formatting change, not the file creation. Those files land with their respective implementation PRDs (CH-PRD-01 → CH-PRD-05).

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **PR #241** | Establishes the 0-broken-link baseline this PRD locks in. CH-PRD-06 has no value without #241 merged. | [PR #241](https://github.com/KEN-E-AI/KEN-E/pull/241) |
| Cloud Build | `deployment/ci/pr_checks.yaml` runs as the PR checks pipeline. New step pulls `lycheeverse/lychee:latest` from Docker Hub. | `deployment/ci/pr_checks.yaml` |
| `lychee` (external tool) | Markdown link checker; Rust binary; offline mode supported since 0.10. Public Docker image at `lycheeverse/lychee`. | https://lychee.cli.rs/ |
| **No KEN-E component dependencies** | This PRD does not depend on any other component's data, contracts, or services. | — |

## 4. Data contract

N/A — tooling PRD, no data models or schema changes.

The closest analogue is the `lychee.toml` config schema, which is defined and consumed by lychee itself (see [lychee config docs](https://github.com/lycheeverse/lychee/blob/master/lychee.example.toml)). Required fields documented in §5.

## 5. Implementation outline

### 5.1 `lychee.toml` config (repo root)

```toml
# Markdown link checker configuration.
# Scope: docs/**/*.md and root-level *.md.
# Mode: offline only — does NOT validate http(s) URLs.
#   Rationale: deterministic CI, no network flakiness, no need to allowlist
#   the historical Notion URLs intentionally retained as archive markers
#   (see CLAUDE.md "Documentation Model" section).

include_verbatim = true

# Exclude generated content + intentionally-stale archives + dependencies.
exclude_path = [
    "docs/figma-export",   # tool-generated; ~94 broken refs are not authored
    "docs/archive",        # historical; intentionally references retired files
    "node_modules",
    ".git",
]
```

### 5.2 Cloud Build step (`deployment/ci/pr_checks.yaml`)

Append a new step alongside the existing test/lint steps:

```yaml
  # Validate markdown link integrity using lychee.
  # Config at repo-root lychee.toml. Offline mode only.
  - name: "lycheeverse/lychee:latest"
    id: markdown-link-check
    entrypoint: lychee
    args:
      - "--offline"
      - "--config"
      - "lychee.toml"
      - "."
```

Order is not load-bearing (no inter-step dependencies). Conventionally place after the language-specific checks.

### 5.3 Chat PRD forward-reference cleanup

Nine edits across five files in `docs/design/components/chat/`. Each edit converts a markdown link `[name](path/to/unbuilt/file)` to inline code `` `name` `` (or `` `path/to/unbuilt/file` `` when the path adds context). Surrounding prose may need light rephrasing to read naturally without the link.

Concrete file/target list in CH-1's issue body. The `{signed_url}` template-literal false positive in `CH-PRD-04-session-status-view.md` gets wrapped in backticks at the same time.

### 5.4 `CLAUDE.md` §6 G-4 entry

Append a single bullet matching the existing style:

```markdown
- **G-4 (MUST)** `lychee --offline --config lychee.toml .` passes for any change
  that touches `docs/**` or root-level `.md` files. Runs in CI on every PR;
  install locally via `brew install lychee` or `cargo install lychee`.
```

## 6. API contract

N/A — no new API endpoints.

The closest analogue is the **CI step contract**: the `markdown-link-check` step exits 0 on success, non-zero on broken links. No external services, no webhooks, no events.

## 7. Acceptance criteria

These map 1:1 to the Linear issues under [CH-PRD-06](https://linear.app/ken-e/project/ch-prd-06-documentation-link-integrity-and-ci-enforcement-73dcf25e70f6):

1. **CH-1** — All 9 chat-PRD forward-references converted to inline code; 0 unresolvable relative links remain in `docs/design/components/chat/**` (verified by local scan or by §7.2 below passing).
2. **CH-2** — `lychee.toml` exists at repo root with offline mode + the four documented exclusions; running `lychee --offline --config lychee.toml .` against `main` (post-CH-1 merge) exits 0.
3. **CH-3** — `markdown-link-check` step appears in `deployment/ci/pr_checks.yaml` using `lycheeverse/lychee:latest`; runs on every PR; hard-fails on broken links.
4. **CH-4** — A deliberate broken-link PR is confirmed to fail the new step (Cloud Build log artifact attached to the issue); throwaway branch deleted; no test fixture leaks into `main`.
5. **CH-5** — `CLAUDE.md` §6 has a new G-4 bullet matching the G-1/G-2/G-3 style and including local-install instructions.

## 8. Test plan

### Unit (config)

- `lychee.toml` parses without error: `lychee --config lychee.toml --dump`.
- `include_verbatim` and `exclude_path` exclusions apply correctly: a synthetic broken link inside `docs/figma-export/_test.md` does not fail the checker; the same link inside `docs/design/_test.md` does.

### Integration (CI step)

- **Positive case (current main):** with CH-1 + CH-2 merged, run the Cloud Build pipeline against the post-merge `main`. The `markdown-link-check` step exits 0.
- **Negative case (CH-4):** open a throwaway PR adding `[broken](./does-not-exist.md)` to `docs/_lychee-test.md`. The `markdown-link-check` step fails with a clear error pointing at the bad link. No other CI step is incidentally affected.

### E2E

- N/A — tooling PRD, no user-facing flow.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| `lycheeverse/lychee:latest` introduces a breaking change in a future release that fails the build with no related code change | `:latest` accepted for v1 simplicity; if churn becomes a problem, pin to a specific version tag in a follow-up. Cloud Build pulls fresh per build, so a regression is detectable. |
| Cloud Build pulls a stale image from a cached registry layer | Cloud Build image pulls are typically uncached for `:latest`. If observed, force-pull via `--pull` equivalent or pin to a digest. |
| Future PRD docs add forward-references to unbuilt files (same problem as CH-1) | G-4 in CLAUDE.md makes the gate visible; future authors get the lint signal locally before pushing. The convention "forward-refs are inline code, not links" should be added to `README-TEMPLATE.md` as a follow-up. |
| `--offline` mode misses a class of broken external link (Notion link rot, retired tool docs) | Accepted: offline is the design choice. External link health is out of scope. If ever needed, add a separate scheduled job. |
| The 9 chat forward-refs have prose that depends on the link rendering | Mitigated in CH-1 acceptance criteria: "Surrounding prose still reads naturally — if a sentence depended on the link, rephrase to keep the file path present." |
| Adding a CI step adds ~5–15 seconds to every PR build | Acceptable. Lychee is fast; offline mode skips network. |

### Open questions

- **Q:** Should the gate fire on PRs that touch zero docs files, or be path-filtered? → **Proposal:** no path filter — running on every PR is cheap (~10 seconds) and catches the case where a code-PR removes a file referenced from docs. Cloud Build doesn't natively support path filters anyway without additional logic.
- **Q:** Add a `README-TEMPLATE.md` line about "forward-refs to unbuilt files should be inline code, not links"? → **Proposal:** yes, as a follow-up issue under whichever component owns README-TEMPLATE next. Out of scope for CH-PRD-06.
- **Q:** Should we propagate the chat README's PRD list and PROJECT-PLANNER.md to include CH-PRD-06? → **Proposal:** yes, but as part of CH-1 (the only PR that needs to land before the CI step) so the doc set is internally consistent on merge. Or run `update-design-docs` skill once the PRD doc is finalized.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Linear project: [CH-PRD-06: Documentation Link Integrity & CI Enforcement](https://linear.app/ken-e/project/ch-prd-06-documentation-link-integrity-and-ci-enforcement-73dcf25e70f6)
- Source review: [PR #241](https://github.com/KEN-E-AI/KEN-E/pull/241) — the docs/restructure that established the 0-broken-link baseline.
- Upstream: PR #241 merge (trigger event)
- Downstream: none
- External: lychee docs https://lychee.cli.rs/ ; example config https://github.com/lycheeverse/lychee/blob/master/lychee.example.toml
- CLAUDE.md rules in scope: G-1 (existing pattern for tooling gates), G-4 (this PRD adds it), GH-1 (Conventional Commits)
