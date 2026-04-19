# Feature 2.6 — User-Authored Skills PRDs

This directory contains the 5 PRDs for **Feature 2.6 — User-Authored Skills**: a way for end-users to author, save, and attach modular skill bundles (SKILL.md + optional references, assets, and scripts) to their custom specialist agents.

> **Prerequisite:** Feature 2.2 (Agent Factory — Sprint 9) must ship the **forward-compat schema fields** (`skill_ids`, `sandbox_code_executor_enabled`) before Sprint 2.6-B can start. See the parent plan ([`../skills-implementation-plan.md`](../skills-implementation-plan.md)) §7 for the Sprint 9 asks.

## Why 5 PRDs

We split by team boundary and dependency arc, so that multiple dev teams can work in parallel without stepping on each other. The sandbox spike is isolated because its findings can block or reshape Sprint 2.6-B; pulling it out as a sprint-0 artifact means the team that owns 2.6-B gets its answers in advance.

- **Sprint 2.6-0 (spike)** de-risks the `AgentEngineSandboxCodeExecutor` — the most unknown dependency.
- **Sprint 2.6-A (backend)** publishes the Skills API contract. Every other team stubs against it.
- **Sprint 2.6-B (agent integration)** is the only sprint that requires Sprint 9 to be done. It's also the only sprint that depends on the spike.
- **Sprint 2.6-C (authoring UI)** runs in parallel with 2.6-B against the contract from 2.6-A.
- **Sprint 2.6-D (builder controls + E2E)** closes the loop: picks up where Sprint 9's agent builder left off, wires the skill picker and the sandbox toggle, and runs the end-to-end test.

## Dependency graph

```
                  ┌─ Sprint 2.6-0 (Sandbox Spike) ──┐
(parallel ──────► │                                 ├─┐
 to Sprint 9)     └─ Sprint 2.6-A (Skills Backend)  ─┘ │
                                                       │
                                                       ▼
                  Sprint 9 (Feature 2.2 Agent ──► Sprint 2.6-B (Agent ──┐
                  Factory, ships first)              Integration)       │
                                                                        ▼
                                Sprint 2.6-A ─────► Sprint 2.6-C (Authoring UI)
                                                                        │
                                                                        ▼
                                                  Sprint 2.6-D (Builder + E2E)
                                                    (needs 9 + A + B + C)
```

ASCII collapsed:

```
[Sprint 9]──┐
[2.6-0]─────┼──►[2.6-B]──┐
[2.6-A]──┬──┘            │
         │               ├──►[2.6-D]
         └─► [2.6-C]─────┘
```

## PRD table

| # | PRD | Owner team | Blocked by | Parallel with | Est. effort |
|---|-----|------------|------------|---------------|-------------|
| 0 | [Sandbox Spike](./00-sandbox-spike.md) | Platform + Security | — | 9, A, C | 3–5 days |
| A | [Skills Backend — Storage, API, Loader](./01-skills-backend.md) | Backend | — | 9, 0, C | 6–8 days |
| B | [Agent Factory — Skills & Sandbox Integration](./02-agent-integration.md) | Agent Platform | **Sprint 9, 2.6-A, 2.6-0** | C | 5–7 days |
| C | [Skills Authoring UI](./03-authoring-ui.md) | Frontend | 2.6-A (contract) | 9, B | 6–8 days |
| D | [Agent Builder Controls + E2E](./04-agent-builder-controls.md) | Frontend + Backend | **Sprint 9, 2.6-A, 2.6-B, 2.6-C** | — | 4–5 days |

## Cross-PRD coordination points

A few touchpoints don't fit cleanly in one PRD and need an owning team to consciously sync:

- **Agent config schema extensions** (2.6-B ↔ Sprint 9 stories 2.2-1, 2.2-8): Sprint 9 ships the two fields (`skill_ids`, `sandbox_code_executor_enabled`) as passive placeholders. Sprint 2.6-B lights up the constructor wiring; Sprint 2.6-D lights up attach-time validation. The Sprint 9 team must be looped in before either starts.
- **Agent builder form layout** (2.6-D ↔ Sprint 9 stories 2.2-10, 2.2-11): Sprint 9 reserves two disabled rows ("Skills", "Sandbox code execution"). Sprint 2.6-D swaps them for interactive controls. Coordinate with whoever owns `AgentsPage.tsx` / `AgentCreatePage.tsx`.
- **Tracing spans** (2.6-B ↔ [`trace-structure-spec.md`](../../../trace-structure-spec.md)): Skill load/invoke spans must conform to the Weave span contract consumed by MER-E. Extend the spec in the same PR that adds the spans.
- **Sandbox spike findings feeding 2.6-B** (2.6-0 ↔ 2.6-B): If the spike returns a blocking answer (e.g., network egress cannot be restricted), Sprint 2.6-B scope changes: scripts become read-only reference files only. Document the outcome in DESIGN-REVIEW-LOG.md and update this README.

## Recommended workflow

1. **Sprint 0 (parallel with Sprint 9):** Kick off 2.6-0 (spike) and 2.6-A (backend) on day 1. They have no blockers. Sprint 9 runs its planned course. 2.6-A publishes its Pydantic + API contract mid-sprint so 2.6-C can stub against it.
2. **Sprint 1 (after Sprint 9 merges):** Start 2.6-B (needs Sprint 9 + 2.6-A + spike findings) and 2.6-C (needs 2.6-A only). Both run in parallel.
3. **Sprint 2:** 2.6-D closes the loop. End-to-end test: user creates a skill → attaches to a custom specialist → runs a query → agent discovers and loads the skill → response reflects the skill's instructions.

## Standard PRD shape

Every PRD in this directory follows the shared structure used across Calendar / Automations / Knowledge Graph:

1. **Context** — problem this PRD solves
2. **Scope** — explicit in/out
3. **Dependencies** — other PRDs, files, services
4. **Data contract** — Pydantic / TypeScript types owned or consumed
5. **Implementation outline** — files to create / modify (table)
6. **API contract** — endpoints (where applicable)
7. **Acceptance criteria** — what "done" means
8. **Test plan** — unit / integration / E2E coverage
9. **Risks & open questions**
10. **Reference** — links back to the parent plan and related docs

## Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md)
- Feature 2.2 prerequisite: Notion Sprint 9 — Agent Factory
- Research: [agentskills.io](https://agentskills.io/specification), [ADK Skills](https://adk.dev/skills/), [ADK developer guide](https://developers.googleblog.com/developers-guide-to-building-adk-agents-with-skills/)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) (Workflows page, Agents tab)
