# Knowledge Graph Evolution — PRDs

This directory contains the PRDs that evolve Neo4j from a write-once-at-account-creation store into a **living, account-scoped knowledge base** that:

- Has declared constraints, lookup indexes, and a hybrid-search vector index
- Tracks provenance — which session or research run produced each fact
- Carries bi-temporal validity (`valid_from` / `valid_to`) so facts can retire without being deleted
- Is readable by the orchestrator agent during conversations via four complementary tools (hierarchical context + hybrid search)
- Is writable by a **session-end workflow** that rides on the Automations platform — a seeded system template reviews completed chat sessions, proposes KB updates, and halts destructive changes for human review
- Unifies the research-on-account-creation write path with the API CRUD path so Firestore and Neo4j never drift

The work is split into **5 independently shippable PRDs**. Each publishes a contract up front so downstream teams can stub against it and run in parallel.

## Why 5 PRDs

Same logic as the Calendar and Automations sets: one foundation PRD that unblocks everything, two provenance/read PRDs that run in parallel, and two consumer PRDs (one blocked on the Automations platform, one on strategy agents).

Splitting them lets three teams work simultaneously and shrinks what each team has to hold in their head. Every PRD follows the same 10-section shape as the Calendar + Automations PRDs.

## Prerequisite: additions to the Calendar + Automations PRDs

KG-PRD-4 rides on the Automations platform and requires small additive changes to the Calendar + Automations PRDs. These have already been folded in (see the git diff on the prerequisites branch); teams should confirm them before building KG-PRD-4:

- **Calendar PRD-1:** `is_system: bool` on `ProjectPlan`; write-protection (PUT/DELETE/PATCH) for `is_system=true` plans with a status-only carve-out.
- **A-PRD-1:** `inputs: dict` on `PlanRun`; `triggered_by="system"` enum value; list endpoint's `is_system` filter default.
- **A-PRD-2:** `{inputs.*}` template substitution spec; manual-trigger endpoint accepts `triggered_by="system"` + `inputs`.
- **A-PRD-4:** `inputs` on the test-run endpoint (subsumes the previously-deferred `override_inputs`).
- **A-PRD-5:** list page filters out `is_system=true` by default.
- **A-PRD-6:** read-only rendering when `is_system=true`; HITL Mark Complete / Revision Requested still work on human tasks within system runs.

## Dependency graph

```
                                 ┌─────────────────────────────────────┐
                                 │ Prereq: Calendar PRDs 1–6 +         │
                                 │         Automations PRDs 1–7        │
                                 │         (with the additions above)  │
                                 └────────────────┬────────────────────┘
                                                  │
                                                  │ (Phase 4 only)
                                                  │
KG-PRD-1: Migrations,      ┌──> KG-PRD-3: Orchestrator Read Tools ─┐
  Constraints, Indexes,    │     (hierarchical context + hybrid)    │
  :KGNode Backfill  ───────┼──> KG-PRD-2: Provenance Spine ─────────┼──> KG-PRD-4: Session-End Automation
  (BLOCKING — ships first) │     (Session / Observation / ResearchRun│     (reviewer + applier + daily sweeper)
                           │      + GraphSyncService methods)        │     — also waits on Calendar+Automations
                           │                            │           │
                           └──> KG-PRD-5: Research-on-Creation ──────┘
                                 Refactor (strategy agents →
                                 GraphSyncService + ResearchRun)
```

| # | PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-----|------------|------------|---------------|------|
| 1 | [Migrations, Constraints, Indexes, `:KGNode` Backfill](./01-migrations-constraints-indexes.md) | Backend / Infra (foundation) | — | — | 2 days |
| 2 | [Provenance Spine + GraphSyncService Methods](./02-provenance-spine.md) | Backend (foundation) | KG-PRD-1 | KG-PRD-3 | 3–4 days |
| 3 | [Orchestrator Read Tools](./03-orchestrator-read-tools.md) | Agent / ML | KG-PRD-1, KG-PRD-2 | KG-PRD-5 | 4–5 days |
| 4 | [Session-End as a System-Triggered Automation](./04-session-end-automation.md) | Agent / ML + Backend (pair) | KG-PRDs 1, 2, 3 + Calendar PRDs 1–6 + A-PRDs 1–7 | KG-PRD-5 | 5–7 days |
| 5 | [Research-on-Creation Refactor](./05-research-on-creation-refactor.md) | Agent / ML | KG-PRD-1, KG-PRD-2 | KG-PRD-3, KG-PRD-4 | 3–4 days |

**Total effort:** ~17–22 engineer-days. With three teams in parallel, clock time is roughly:
- **Sprint 1:** KG-PRD-1 alone (critical path; 2 days).
- **Sprint 2:** KG-PRD-2 solo (foundation for 3, 4, 5) while Prereq team folds `is_system` / `inputs` into Calendar + Automations PRDs.
- **Sprint 3:** KG-PRDs 3 and 5 in parallel (different teams), KG-PRD-4 design work begins waiting on Automations platform.
- **Sprint 4 (pending Automations ship):** KG-PRD-4.

If Automations platform ships in Sprint 2–3 (13 PRDs over ~4 weeks based on the Calendar + Automations README estimates), KG-PRD-4 can start in Sprint 4 without a stall.

## Recommended team assignments

Three teams, minimal handoffs:

- **Team A — Backend Foundation** (Python / Neo4j / FastAPI)
  - Sprint 1: KG-PRD-1 (solo, 2 days)
  - Sprint 2: KG-PRD-2 (solo, 3–4 days)
  - Sprint 3+: available to pair on KG-PRD-4's backend pieces (sweeper endpoint, seed script, Terraform) or to support others

- **Team B — Agent / ML**
  - Sprint 1: review KG-PRD-1, prep KG-PRD-5 (audit current strategy_agent → raw Cypher sites)
  - Sprint 2: KG-PRD-5 starts after KG-PRD-2 ships (3–4 days)
  - Sprint 3: KG-PRD-3 (4–5 days; orchestrator read tools)
  - Sprint 4: KG-PRD-4 (pair with Team A for the backend bits; reviewer / applier agents)

- **Team C — Platform PRD support**
  - Sprint 1–2: land the additive Calendar + Automations PRD changes (`is_system`, `inputs`, etc.) so KG-PRD-4 can build cleanly on them. Estimate: < 1 day of PRD work; implementation effort lives in the Calendar / Automations sprints themselves.

If only two teams are available, Team B absorbs Team C's work in Sprint 1.

## Cross-PRD coordination points

- **KG-PRD-2 ↔ KG-PRD-3:** The `Observation` model + `:KGNode` label must stabilize before read tools can test their Cypher. KG-PRD-3 teams should stub against the Pydantic schema as soon as KG-PRD-2's PR is in review (don't wait for merge).
- **KG-PRD-2 ↔ KG-PRD-5:** Research refactor depends on `GraphSyncService.create_node(..., idempotency_key=..., research_run_id=...)` signature. KG-PRD-2 lands the signature; KG-PRD-5 lands the callers. Coordinate to avoid the two PRs landing in conflicting order.
- **KG-PRD-4 ↔ Automations platform:** KG-PRD-4 assumes `is_system` write-protection, `inputs` substitution, and Outputs-tab HITL. The Prereq additions to Calendar PRD-1 / A-PRDs 1, 2, 4, 5, 6 must land before KG-PRD-4 can integration-test.
- **KG-PRD-3 ↔ KG-PRD-4:** Reviewer agent uses the Phase 3 read tools. If KG-PRD-3 ships first (expected), KG-PRD-4 reviewer can ground itself in the real KB; if not, use mocked tools in unit tests and wait for KG-PRD-3 to merge before e2e testing.

## Recommended workflow

1. **Sprint 1** — Team A ships KG-PRD-1. Other teams review specs, prep the Calendar / Automations PRD additions (Team C), and audit the existing strategy-agent write paths (Team B, for KG-PRD-5 readiness).
2. **Sprint 2** — Team A ships KG-PRD-2. Team B starts KG-PRD-5 (the parts that don't need KG-PRD-2 — research-run lifecycle design, builder refactor planning). Team C has the Calendar / Automations PRD additions in review.
3. **Sprint 3** — Team B ships KG-PRD-5 and KG-PRD-3 in parallel (different engineers, same team). Team A is available to unblock the Automations platform team on anything KG-PRD-4 will need.
4. **Sprint 4** (pending Automations ship) — Team B + Team A pair on KG-PRD-4.

**First shippable value lands at end of Sprint 2:** KG-PRD-1 + KG-PRD-2 together give the KB its provenance spine, vector index, and constraints — the orchestrator's context-loading is unchanged but the data it reads is now traceable.

**Full user-visible value lands at end of Sprint 3:** KG-PRD-3 makes the orchestrator actually smarter during conversations; KG-PRD-5 unifies the research write path; no visible UI changes but query quality improves.

**Learning loop closes at end of Sprint 4:** KG-PRD-4 enables session-end updates; the KB grows with every conversation.

## Standard PRD shape

Every PRD in this directory follows the same structure as the Calendar + Automations PRDs:

1. **Context** — problem this PRD solves
2. **Scope** — explicit in/out
3. **Dependencies** — other PRDs, files, services
4. **Data contract** — Pydantic / TypeScript types owned or consumed
5. **Implementation outline** — files to create / modify (table)
6. **API contract** — endpoints (where applicable)
7. **Acceptance criteria** — what "done" means
8. **Test plan** — unit / integration / E2E coverage
9. **Risks & open questions**
10. **Reference** — links back to the parent plan and sibling PRDs

## Reference

- Parent plan (local, uncommitted): `/Users/kenwilliams/.claude/plans/the-purpose-of-neo4j-clever-frost.md`
- Calendar PRDs (prerequisite): [`../prd/`](../prd/)
- Automations PRDs (prerequisite for KG-PRD-4): [`../automations/prd/`](../automations/prd/)
- Neo4j docs: [Vector indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/), [Constraints](https://neo4j.com/docs/cypher-manual/current/constraints/)
- Notion stories subsumed by KG-PRD-3: [1.1.6-1](https://www.notion.so/34230fd653028175bccadb3dfd3d581f), [1.1.6-2](https://www.notion.so/34230fd65302816ea2eeeec49aedd90e)
