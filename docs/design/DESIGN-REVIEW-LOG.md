# Design Review Log

Hybrid decision log and document changelog. Tracks what changed in the design docs, when, and why. **This is the canonical decision log going forward** — new architectural decisions are captured as Review entries with their full rationale. Reviews 1–20 reference a legacy Notion Design Decisions database that is retained as a historical archive only; new entries should not link out to it.

---

## Review 1: PR #222 — Agentic Harness Overhaul + Design Docs

**Date:** March 10, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**PR:** #222
**Commit status:** Changes uncommitted (review additions pending)
**Participants:** Darshan Valia + Claude Code review session
**Scope:** Full review of harness doc v2.0 and 3 new design docs for accuracy, feasibility, and completeness

### 1. What Was Reviewed

| Document | Lines | Content |
|----------|-------|---------|
| `docs/KEN-E-System-Architecture.md` | 912 | Root design doc — rewritten from 3,771 lines, fictional classes removed |
| `docs/design/mcp-architecture.md` | 188 | MCP internals, platform decisions, token budget strategy |
| `docs/design/agent-hierarchy.md` | 164 | Agent tree, registry, dispatch pattern, planned specialist layer |
| `docs/design/api-gateway-multi-channel.md` | 130 | API architecture, channel-agnostic design, Slack/Voice plans |
| `docs/decisions/mcp-architecture-decisions.md` | 17 | Redirect stub to canonical design doc |

### 2. File Path Verification

15 of 16 referenced file paths exist on `main`. The 16th (`app/adk/agents/registry.py`) exists only on the `feat/sprint-3b-agent-config-optimization` branch (PR #217).

Additional features that exist only on sprint-3b (not yet merged to main):
- `_make_instruction_provider` closure pattern in `ken_e_agent.py`
- `ReflectAndRetryToolPlugin` in `deploy_ken_e.py`
- `token_threshold=50000` and `event_retention_size=10` in `EventsCompactionConfig`
- `ORG_CONTEXT_QUERY` in `shared/context_utils.py`

**Action taken:** Added dependency note at top of harness doc.

### 3. External Technology Claims — Verification Results

| Claim | Verdict | Source |
|-------|---------|--------|
| HubSpot MCP at `mcp.hubspot.com`, OAuth 2.1, read-only CRM | Accurate | [developers.hubspot.com/mcp](https://developers.hubspot.com/mcp) |
| Google Ads MCP official at `googleads/google-ads-mcp`, read-only | Accurate | [github.com/googleads/google-ads-mcp](https://github.com/googleads/google-ads-mcp) |
| Pipeboard Meta Ads MCP, BSL 1.1 license | Accurate | [github.com/pipeboard-co/meta-ads-mcp](https://github.com/pipeboard-co/meta-ads-mcp) |
| Pipecat for voice pipeline orchestration | Accurate | [pipecat.ai](https://www.pipecat.ai/) |
| Recall.ai / Meeting BaaS for meeting bots | Accurate (both real, separate services) | [recall.ai](https://www.recall.ai/), [meetingbaas.com](https://www.meetingbaas.com/) |
| Slack Bolt SDK for Python | Accurate | [github.com/slackapi/bolt-python](https://github.com/slackapi/bolt-python) |
| Cartesia TTS | Accurate (sub-100ms TTFB) | [cartesia.ai](https://cartesia.ai/) |
| Deepgram sub-200ms STT | **Inaccurate** — STT is sub-300ms; the sub-200ms figure is for their Aura TTS TTFB | [deepgram.com](https://deepgram.com/) |

**Action taken:** Fixed Deepgram latency claim in `api-gateway-multi-channel.md`.

### 4. ADK Internals — Key Findings

Traced ADK source code to verify `McpToolset` behavior. Key findings:

- `get_tools()` per-turn resolution is intentional (per-user permissions). A redundant-calls bug exists pre-v1.26.0 — we're on 1.23.0 and need to upgrade.
- MCP server connections are fixed at agent construction time. Dynamic tool *selection* (not connection) is supported via `tool_filter` on `BaseToolset`.
- Designed `tool_filter` + ToolRegistry architecture for per-turn dynamic tool selection.

See [Decision 7 (Token Budget)](https://www.notion.so/32030fd6530281da97cef1729242ccd1) and [Decision 8 (ToolRegistry)](https://www.notion.so/32030fd65302813ab406cf15f7e1e7f6) for full rationale.

**Action taken:** Added Section 5a to `mcp-architecture.md`, updated `agent-hierarchy.md` Section 6 and 8, updated harness doc Section 4.3.

### 5. Other Findings

#### Voice Latency Gap
Current Agent Engine response time is ~7-13s. Voice requires <2s end-to-end. The docs don't address this gap. Voice would likely need a separate, more lightweight agent path or a different serving strategy. Not fixed in this review — flagged as an existing issue.

#### Cost Model
The ~$1.20/hour per meeting estimate for voice doesn't account for Recall.ai/Meeting BaaS pricing (can be $50-100+/month per bot seat). Infrastructure cost estimates in Section 9.2 are for "moderate usage" without defining what moderate means. Not fixed — noted for future refinement.

### 6. Architecture Gaps Identified

Structural gaps found and tracked. Most were addressed in Review 2 (see below).

| Gap | Status |
|-----|--------|
| **6a. Error handling / resilience** | Addressed in Review 2 — harness doc Section 10.1 |
| **6b. MCP security model** | Addressed in Review 2 — harness doc Section 10.2 |
| **6c. Cost model** | Addressed in Review 2 — harness doc Section 9.2 |
| **6d. Workflow management** | Addressed in Review 2 — harness doc Section 7 |
| **6e. Rate limiting** | Addressed in Review 2 — harness doc Section 10.3 |
| **6f. Agent factory design** | Addressed in Review 2 — `agent-hierarchy.md` Section 8 |
| **6g. UsageTracker scalability** | Open — needs daily rollup Cloud Function |

### 7. Documents Modified in This Review

| File | Changes |
|------|---------|
| `docs/design/mcp-architecture.md` | v1.0 → v1.1: Rewrote Section 2 (ADK internals) with version-specific behavior and issue references. Added Section 5a (tool_filter + ToolRegistry). Updated MCPServerManager disposition. Added open questions 4-6. Updated references. |
| `docs/design/agent-hierarchy.md` | v1.0 → v1.1: Rewrote Section 6 (ToolRegistry role) with tool_filter driver design. Updated Section 8 (Agent Factory) with limitations note. |
| `docs/design/api-gateway-multi-channel.md` | Fixed Deepgram STT latency: sub-200ms → sub-300ms. Added TTS TTFB specs. |
| `docs/KEN-E-System-Architecture.md` | v2.0 → v2.1: Added sprint-3b dependency note. Rewrote Section 4.3 (Tool Discovery) with tool_filter architecture. Added glossary entries. Updated document history. |
| `docs/design/DESIGN-REVIEW-LOG.md` | Created — this file. |

### 8. Open Questions (Active)

1. **ADK version bump to `>=1.26.0`** — Needed for per-invocation tool caching fix.
2. ~~**`tool_filter` integration pattern** — Needs prototyping before Sprint 5-6.~~ **Resolved (Review 9, Experiment #4).**
3. **Per-account MCP server sets** — Agent factory may need session-time assembly.
4. **Voice latency budget** — 7-13s Agent Engine response is incompatible with <2s voice target.
5. **UsageTracker scalability** — Needs daily rollup Cloud Function before heavy scale.
6. **KMS encryption migration** — `EncryptionService` uses Fernet in dev, KMS path is TODO.
7. **Circuit breaker pattern** — No circuit breaker for MCP servers or Agent Engine.

---

## Review 2: Architecture Gap Resolution

**Date:** March 10, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Commit status:** Changes uncommitted
**Scope:** Address gaps 6a-6g identified in Review 1

### Actions Taken

| Gap | Action | Location |
|-----|--------|----------|
| **6a. Error handling** | Documented all existing patterns (dispatch retry, MCP health, API fallbacks, security hooks). Identified circuit breaker as key missing pattern. | Harness doc Section 10.1 |
| **6b. Security model** | Documented full OAuth lifecycle (authorization → callback → storage → injection → refresh → reauth). Identified gaps: proactive refresh, token rotation, KMS, cross-tenant isolation. Added multi-tenant credential design for specialist agents. | Harness doc Section 10.2 |
| **6c. Cost model** | Defined 3 usage tiers with concrete assumptions. Built moderate tier cost breakdown. Added scaling considerations including voice costs. Flagged UsageTracker scalability. | Harness doc Section 9.2 |
| **6d. Workflow management** | Expanded from 4 paragraphs to full design: Firestore data model, persistence/recovery table, idempotency approach, n8n webhook contract, failure handling. | Harness doc Section 7 |
| **6e. Rate limiting** | Documented existing rate limiting (auth, external APIs, Firestore retry). Added marketing platform quota table (Google Ads, Meta, HubSpot, GA) with recommendations for per-platform tracking. | Harness doc Section 10.3 |
| **6f. Agent factory** | Expanded from 6 bullet points to full design: current construction pattern, proposed assembly flow, config-to-constructor mapping, header provider factory, limitations table. | `agent-hierarchy.md` Section 8 |
| **6g. UsageTracker** | Flagged scalability concern. Recommended daily rollup Cloud Function. | DESIGN-REVIEW-LOG gap 6g |

### Remaining Open Items

Items 1-4, 11-13 from the open questions list above are NOT yet resolved and carry forward to the next iteration.

---

## Review 3: Google Ads Integration Decision Revision

**Date:** March 11, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Revise Google Ads integration decision based on post-review research

### Finding

Google's official MCP servers are read-only with no public write roadmap. Revised to hybrid approach (MCP reads + SDK writes).

### Decision

See [Decision 3: Google Ads — Hybrid MCP + SDK](https://www.notion.so/32030fd6530281fe91eaf7773665729f) in the Design Decisions database for full rationale.

### Documents Updated

| File | Changes |
|------|---------|
| `docs/design/mcp-architecture.md` | Updated Section 4 platform table (hybrid), Section 5 diagram (Execution Specialist gets SDK tools), Section 8 (rewritten read-only limitations — Google Ads now has write path), Section 9 (added `google-ads` SDK dependency) |
| `docs/design/agent-hierarchy.md` | Updated Section 7 specialist table (Execution Specialist gets Google Ads SDK for writes) |
| `docs/KEN-E-System-Architecture.md` | Updated Section 2.4, 4.1, 4.4 specialist tables and Appendix A (Google Ads → hybrid) |

### Impact on Decision 1 (Platform Integration Framework)

The hybrid Google Ads approach reveals that the 4-tier framework is not mutually exclusive — a single platform can use multiple tiers (MCP for reads, SDK for writes). Decision 1 updated in Notion Design Decisions database to acknowledge hybrid tier combinations.

---

## Review 4: Context Loading — Keyword Detection → Agent-Driven Loading

**Date:** March 11, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Revise Level 2/3 context loading trigger mechanism

### Finding

The Level 2 context loading implementation uses English keyword substring matching in the API preprocessing layer (`should_load_campaigns()`, `should_load_section()` with `SECTION_KEYWORDS` and `CAMPAIGN_KEYWORDS` in `shared/context_utils.py`). Two problems:

1. **English-only** — Users typing in Spanish, German, or any non-English language would never trigger section loading (e.g., "¿Cómo van mis campañas?" contains no English keywords)
2. **Brittle to paraphrases** — Even in English, indirect references or creative phrasing can miss the keyword list

### Decision

See [Decision 17: Context Management — Hierarchical Context Loading](https://www.notion.so/32030fd6530281dca919d68aa0e27094) in the Design Decisions database for full rationale, decision, and consequences.

### Documents Updated

| File | Changes |
|------|---------|
| `docs/KEN-E-System-Architecture.md` | Updated Section 3.2 HCL diagram (Level 2/3 → "Agent-Driven Loading"). Updated Section 3.3 implementation status with deprecation note and design revision explanation. |
| `docs/design/agent-hierarchy.md` | Updated Section 2 file inventory — context_loader.py description reflects agent-driven loading. |

---

## Review 5: Architecture Accuracy Pass — Harness Doc v2.2 → v2.3

**Date:** March 11, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Ensure harness doc accurately reflects both current implementation and target architecture; expand session state documentation; add billing/usage tracking plan.

### Changes Made

| Area | Change | Location |
|------|--------|----------|
| **Document framing** | Reframed as "architecture reference" with explicit `[PLANNED]` convention. Updated `CLAUDE.md` docs/ description and workflow step. | Section 1.1, `CLAUDE.md` |
| **Section 1.3** | Renamed "Solution Overview" → "Agentic Harness Overview". Split into 1.3.1 Current + 1.3.2 [PLANNED] with separate diagrams. | Section 1.3 |
| **Section 2.1** | Rewrote system architecture diagram — replaced GA-specific content with target architecture (specialist agents, generic platform credentials, multiple MCP servers). | Section 2.1 |
| **Section 2.3** | Split into 2.3.1 Current Request Flow (GA dispatch) + 2.3.2 [PLANNED] (specialist routing, tool_filter, multi-MCP). | Section 2.3 |
| **Section 3.6** | Expanded from 3-row table to 5 subsections: current keys (11 entries with Set By / Read By), planned target model, what's NOT in state, token usage visibility, billing/usage tracking. | Section 3.6.1–3.6.5 |

### Decisions Created

| Decision | Status | Link |
|----------|--------|------|
| Decision 19: Token Usage Visibility in UI | Proposed | [Notion](https://www.notion.so/32030fd65302815ca0d6fe5291fdfc54) |
| Decision 20: Unified Usage Tracking for Billing | Proposed | [Notion](https://www.notion.so/32030fd6530281bfa31cf19af537b206) |

### Key Findings

- **Token data gap:** Token usage data exists at every layer (Vertex AI, Weave, ConversationSummarizer) but never crosses the API boundary to the frontend. `ChatResponse` model has no token fields.
- **Billing data gap:** Two separate Firestore tracking systems (`tool_usage_events` and `usage_records`) are never unified. `usage_records` lacks `organization_id` and `session_id`, making org-level billing aggregation impossible.
- **Session state completeness:** Documented 11 current session state keys (vs. the previous 3-row table) including internal flags (`_tool_start_time`, `_requires_reauth`, `_reauth_service`) and strategy artifacts.

---

## Review 6: Task Delegation with Review Loops

**Date:** March 11, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Design review loop pattern for specialist agent delegation using ADK native workflow agents; document multi-step workflow orchestration with parallel execution and user approval checkpoints.

### Finding

The current dispatch pattern runs specialists once and relays output verbatim — no quality gate exists. The Root Agent cannot verify that a specialist's response meets the user's intent before presenting it. For multi-step workflows (e.g., cross-platform budget optimisation), there is no mechanism for parallel data gathering, synthesis, user approval, or execution phasing.

### Research

Reviewed ADK documentation and source code. Confirmed the following native constructs are available in ADK 1.26.0 (installed version):

| Construct | Purpose |
|-----------|---------|
| `LoopAgent` | Iterative cycle until `exit_loop` or `max_iterations` |
| `SequentialAgent` | Chain specialist → reviewer inside loop |
| `ParallelAgent` | Run independent steps concurrently |
| `output_key` | Named state keys for inter-agent data passing |
| `exit_loop` | Built-in tool that terminates LoopAgent |

Google's recommended **Generator-Critic** pattern maps directly to the specialist + reviewer review loop.

### Decision

See [Decision 21: Task Delegation with Review Loops](https://www.notion.so/32030fd6530281a8a30fc8e12c3f931e) in the Design Decisions database for full rationale, alternatives considered, and consequences.

### Documents Updated

| File | Changes |
|------|---------|
| `docs/KEN-E-System-Architecture.md` | v2.3 → v2.4: Updated Section 2.3.2 request flow with review loop steps (3a specialist + 3b reviewer inside LoopAgent). Added Section 4.6 [PLANNED] Review Loop Pattern (Generator-Critic) with structure, termination rules, token impact. Rewrote Section 7.1 with ADK workflow agent architecture, ParallelAgent, Meta Ads optimisation example, `execute_workflow()` tool, dependency graph parsing, second example. |
| `docs/design/agent-hierarchy.md` | v1.1 → v1.2: Added Section 9 [PLANNED] Review Loop & Workflow Orchestration — review loop pattern (9.1), multi-step workflow pattern with ParallelAgent (9.2), key files table (9.3). |
| `docs/design/DESIGN-REVIEW-LOG.md` | Added this entry (Review 6). |
| `docs/design/review-loop-implementation-plan.md` | Created — comprehensive implementation plan for future roadmap/story creation. |

### Key Design Decisions

1. **Root Agent stays LlmAgent** — review pipelines are built inside dispatch handlers, not by replacing the Root Agent with a SequentialAgent. This preserves the conversational interface.
2. **User approval via conversation turns** — rather than ADK `pause_invocation`, multi-phase workflows naturally split across turns. Root presents results, user approves, next turn executes.
3. **Backward compatible** — `acceptance_criteria=None` (default) preserves current single-pass behavior. Review loops only activate when criteria are provided.
4. **Unique `output_key` per step** — avoids state collisions in parallel execution (e.g., `step_1a_draft`, `step_1b_draft`).

---

## Review 7: Transitional Agent Annotations, Meta Ads Shared Access, Skills Architecture

**Date:** March 11, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Four documentation improvements: (1) Mark GA and Company News agents as transitional, (2) correct Meta Ads SDK shared access across specialists, (3) add ADK Skills Architecture as new Section 6, (4) renumber all subsequent sections and cross-references.

### Issues Addressed

| # | Issue | Resolution |
|---|-------|------------|
| 1 | Google Analytics Agent has no lifecycle annotation — will be replaced by Analytics Specialist in Sprint 5-6 | Added `[TRANSITIONAL]` convention alongside `[PLANNED]`. Annotated GA Agent in all diagrams, tables, and flow descriptions with successor = Analytics Specialist. |
| 2 | Company News Agent has no lifecycle annotation — will be replaced by Automation Specialist (n8n workflow) + predefined `research-company-news` Skill | Annotated News Agent as `[TRANSITIONAL]`. Tied transition to both Automation Specialist (scheduled pipeline) and new Skills Architecture (Section 6). |
| 3 | Meta Ads SDK only assigned to Execution Specialist, but Analytics Specialist also needs read access for reporting | Added `facebook-business` SDK (reads) to Analytics Specialist tool sources in all specialist tables. Clarified Execution gets reads + writes. Added `tool_filter` explanatory notes. |
| 4 | ADK recently added Skills support — need architecture for predefined + custom skills | Added new Section 6: Skills Architecture [PLANNED] with 6 subsections covering progressive disclosure, predefined skills, custom skills, agent integration, and frontend skill builder. |

### Decision

See [Decision 22: ADK Skills Architecture](https://www.notion.so/32030fd653028114827be82c2731ea72) in the Design Decisions database for full rationale.

### Documents Updated

| File | Changes |
|------|---------|
| `docs/design/mcp-architecture.md` | v1.1 → v1.2: Updated Section 4 platform table (Meta Ads → shared). Updated Section 5 diagram (Meta Ads SDK reads under Analytics Specialist). Rewrote Section 8 (Analytics Specialist uses read-only SDK tools for Meta Ads reporting). Added `tool_filter` note for Meta Ads. |
| `docs/design/agent-hierarchy.md` | v1.1 → v1.3: Added `[TRANSITIONAL]` convention note. Annotated News Agent and GA Agent in agent tree. Added "Lifecycle" column to Key Files and Registered Agents tables. Updated specialist table with Meta Ads shared access. Added skills loading step to agent factory assembly flow. |
| `docs/KEN-E-System-Architecture.md` | v2.4 → v2.5: Added `[TRANSITIONAL]` convention. Annotated transitional agents in all diagrams and tables. Updated Meta Ads shared access in Sections 2.1, 4.4, 4.5, and Appendix A. **Inserted new Section 6: Skills Architecture [PLANNED]** (6 subsections). Renumbered Sections 6→7 through 12→13 with all subsections and cross-references. Updated ToC, roadmap, glossary, and document history. |
| `docs/design/review-loop-implementation-plan.md` | Added open question 7: skills interaction with review loops. Updated cross-references for section renumbering. |
| `docs/design/DESIGN-REVIEW-LOG.md` | Added this entry (Review 7). |

### Key Design Decisions

1. **`[TRANSITIONAL]` convention** — New tag for agents that exist today but will be subsumed. Distinct from `[PLANNED]` (not yet built) — transitional agents ARE built but have a planned successor.
2. **Meta Ads SDK shared access** — Parallels Google Ads pattern (MCP reads shared with Analytics). `tool_filter` controls which tools each specialist sees from the same `facebook-business` SDK.
3. **Skills progressive disclosure** — L1 metadata (~50-100 tokens) loaded at startup; L2 instructions (<5,000 tokens) loaded on activation; L3 resources on-demand. Minimizes baseline token overhead.
4. **Two-tier skill storage** — Predefined skills bundled in deployment (`app/adk/skills/`), custom skills in GCS + Firestore per-org. Loaded via `SkillToolset` during agent factory assembly.
5. **News Agent → Skill transition** — `research-company-news` predefined skill replaces the standalone Company News Agent. Combined with Automation Specialist (scheduled n8n workflow) for automated news retrieval.

---

## Review 8: ADK 1.26.0 Experiment Corrections — Review Loops & Workflow Management

**Date:** March 18, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Correct 3 structural errors and fill documentation gaps in Sections 4.6 and 8 (and related docs) based on validated ADK 1.26.0 experiments with review loop and parallel workflow patterns.

### Finding

A dev team member conducted ADK experiments (google-adk 1.26.0) validating the review loop and parallel workflow patterns described in the design docs. The experiments revealed 3 structural errors:

1. **`SequentialAgent` wrappers inside `LoopAgent` are unnecessary and harmful** — `LoopAgent` already iterates sub-agents sequentially and checks `escalate` between each. A `SequentialAgent` wrapper swallows the `escalate` signal from `exit_loop`.
2. **Reviewer agents need `include_contents='none'`** — without it, the reviewer sees the full conversation history (all prior turns, tool calls, review loop back-and-forth), producing inconsistent evaluations.
3. **Synthesizer agents need `include_contents='none'` + strong instructions** — without `include_contents='none'`, the synthesizer sees full conversation history from all parallel branches. With it but a weak instruction, the model doesn't understand the injected data is final. The instruction must explicitly frame it as "completed research."

Additionally, 5 documentation gaps were identified:
- `{feedback?}` optional template syntax (avoids `KeyError` on first iteration)
- `output_key` + `exit_loop` interaction pitfall (`exit_loop` produces no text, overwrites state with `""`)
- `SequentialAgent` ignores `escalate` pitfall
- LLM call cost/latency analysis
- `build_review_pipeline()` and `build_workflow_pipeline()` factory implementations

### Documents Updated

| File | Version | Changes |
|------|---------|---------|
| `docs/KEN-E-System-Architecture.md` | v2.5 → v2.6 | **Section 4.6**: Removed `SequentialAgent` wrapper from diagram and constructs table. Added `include_contents='none'` to reviewer. Fixed `{step_N_feedback}` → `{step_N_feedback?}`. Added "Why no SequentialAgent", "Why include_contents='none'", "Why `?` suffix" explanations. Added LLM call cost table. **Section 8.1**: Rewrote all workflow diagrams — removed `SequentialAgent` inside `LoopAgent`, added `include_contents='none'` on reviewers, added explicit synthesizer agent with `include_contents='none'`, added pipeline `SequentialAgent` wrappers for `ParallelAgent` branches. **Section 8.2 (NEW)**: `build_review_pipeline()` factory implementation, `build_workflow_pipeline()` composition pattern, synthesizer agent pattern. **Section 8.3 (NEW)**: 3 validated ADK Pitfalls with rules. **Section 8.4 (NEW)**: LLM call cost & latency tables. Renumbered 8.2-8.5 → 8.5-8.8. |
| `docs/design/agent-hierarchy.md` | v1.3 → v1.4 | **Section 9.1**: Removed `SequentialAgent` wrapper, added `include_contents='none'` on reviewer, fixed template syntax, added key details. **Section 9.2**: Rewrote multi-step workflow diagram — added pipeline wrappers, synthesizer agent, `include_contents='none'`, key details. Updated cross-references. |
| `docs/design/review-loop-implementation-plan.md` | v1.0 → v1.1 | **Section 2**: Updated `LoopAgent` description (iterates sequentially), added `SequentialAgent` caveat (ignores `escalate`), added `LlmAgent` `include_contents` parameter, updated `exit_loop` description (no text output), added `SequentialAgent` key behavior. **Section 3.1**: Removed `SequentialAgent` wrapper, added `include_contents='none'`, fixed template syntax. **Section 3.2**: Same fixes. **Section 3.3**: Same fixes plus synthesizer agent, pipeline wrappers. **Story 1.1**: Updated acceptance criteria and implementation code. **Section 8**: Added 3 new risks (`output_key`+`exit_loop`, `SequentialAgent` swallows `escalate`, synthesizer history confusion). |
| `docs/design/DESIGN-REVIEW-LOG.md` | — | Added this entry (Review 8). |

### Key Corrections

1. **All workflow diagrams** now show specialist + reviewer as direct `LoopAgent` sub-agents (no `SequentialAgent` wrapper).
2. **All reviewer agents** now show `include_contents='none'`.
3. **All synthesizer agents** now show `include_contents='none'` + strong instruction framing injected data as "completed research."
4. **Template variables** use `{key?}` optional syntax for first-iteration safety.
5. **`build_review_pipeline()`** factory code included with validated implementation.
6. **Pipeline wrappers** — each `LoopAgent` wrapped in a `SequentialAgent` inside `ParallelAgent` for future extensibility.
7. **3 ADK pitfalls** documented with rules.
8. **LLM call cost table** present with per-step and parallel execution latency estimates.

---

## Review 9: Experiment #4 — tool_filter Integration Pattern Resolution

**Date:** March 18, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Resolve the open design question for how ToolRegistry search drives `tool_filter`, based on Experiment #4 findings.

### Finding

Experiment #4 tested 4 options for triggering ToolRegistry search to populate `tool_filter_state`:

| Option | Mechanism | Verdict |
|--------|-----------|---------|
| 1: InstructionProvider | ReadonlyContext (read-only) | Cannot write state |
| 2: Root agent writes state | Root's LLM turn sets state | Works for dispatch, not per-turn within specialist |
| 3: Specialist tool call | Tool writes state | One-turn delay; wastes an LLM call |
| **4: before_agent_callback** | **CallbackContext (mutable)** | **Recommended — per-turn, pre-resolution** |

Key insight: `ReadonlyContext.state` is a `MappingProxyType` wrapping the same `session.state` dict. Writes from `CallbackContext` in `before_agent_callback` are immediately visible to `InstructionProvider` and `tool_filter` — no copy, no propagation delay.

### Decision

See [Decision 23: tool_filter Integration Pattern](https://www.notion.so/32730fd6530281999389eb3116e7585c) in the Design Decisions database for full rationale.

### Documents Updated

| File | Version | Changes |
|------|---------|---------|
| `docs/design/mcp-architecture.md` | v1.2 → v1.3 | Replaced "Open Design Question" in Section 5a with resolved 4-option comparison, production code pattern, execution order, anti-patterns. Struck through Open Question #5. |
| `docs/KEN-E-System-Architecture.md` | v2.6 → v2.7 | Updated `tool_filter_state` Set By (Section 3.6.2). Resolved `[PLANNED] tool_filter driver` (Section 4.3). Added execution order note and callback chaining note (Sections 4.2-4.3). Added ReadonlyContext, CallbackContext, before_agent_callback glossary entries (Appendix D). |
| `docs/design/agent-hierarchy.md` | v1.4 → v1.5 | Added revision callout to Section 6 (tool_filter Driver) noting `before_agent_callback` replaces root-agent-writes pattern. |

### Open Questions Resolved

- **DESIGN-REVIEW-LOG Review 1, Open Question #2** (`tool_filter` integration pattern) — resolved as `before_agent_callback`.
- **mcp-architecture.md Open Question #5** — resolved and struck through.

---

## Review 10: Align agent-hierarchy.md with Harness Design Doc + Cross-References

**Date:** March 18, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Ensure the hierarchy doc reflects all concepts from the harness doc (including Experiment #4 corrections) and add bidirectional cross-references between the two documents.

### Changes Made

| File | Version | Changes |
|------|---------|---------|
| `docs/design/agent-hierarchy.md` | v1.5 → v1.6 | Added component responsibilities cross-reference to harness doc Section 2.2. Added two-tier tool management framing (Level 1 specialist routing, Level 2 `tool_filter`) matching harness doc Section 4.3. Renamed Section 6 subsections: "Current Role" → "6.1 Current", "Planned Role" → "6.2 Resolved" (aligns with harness doc v2.7 removing `[PLANNED]` from `tool_filter` driver). Fixed body text contradiction in Section 6.2 — changed "root agent interprets user intent, queries the ToolRegistry" to "each specialist's `before_agent_callback` runs a ToolRegistry search" (matching the revision callout from Experiment #4). Added LLM call cost note to Section 9.1 referencing harness doc Sections 4.6 and 8.4. Disambiguated cross-reference to harness doc Section 8.2 with specific factory names. Added dispatch-time pipeline building note to Section 8.2 step 4. |
| `docs/KEN-E-System-Architecture.md` | — | Added 6 targeted cross-references to `agent-hierarchy.md`: Section 2.2 → Sections 2-6, Section 2.3.1 → Section 3, Section 4.2 → Sections 4-5, Section 4.3 → Section 6, Section 4.4 → Sections 7-8, Section 4.6 → Section 9. |
| `docs/design/DESIGN-REVIEW-LOG.md` | — | Added this entry (Review 10). |

### Key Corrections

1. **Section 6 body text** now matches the Experiment #4 revision callout — both describe `before_agent_callback` as the mechanism for writing ToolRegistry results to state.
2. **Section 6.2 heading** says "Resolved" (not "Planned"), matching harness doc v2.7 where `[PLANNED]` was removed from the `tool_filter` driver description.
3. **Two-tier framing** added to Section 6, matching harness doc Section 4.3's explicit Level 1/Level 2 description.
4. **No content duplication** — all additions are cross-references pointing to the harness doc, not copies of its content.

---

## Review 11: Align review-loop-implementation-plan.md with Harness Design Doc + Cross-References

**Date:** March 18, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Resolve 4 misalignments in the implementation plan and add 3 cross-references from the harness doc to the implementation plan.

### Misalignments Resolved

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | Design References table missing harness doc Sections 8.2, 8.3, 8.4 | Added 3 rows for ADK Implementation Details, ADK Pitfalls, and LLM Call Cost & Latency | `review-loop-implementation-plan.md` |
| 2 | Section 3.6 token/latency estimates unclear whether overhead-only or total | Added paragraph clarifying these are overhead-only numbers, with blockquote cross-referencing harness doc Sections 4.6 and 8.4 for total-time estimates | `review-loop-implementation-plan.md` |
| 3 | Story 4.1 `build_workflow_pipeline()` code places `LoopAgent` directly in `ParallelAgent` — inconsistent with Section 3.3 diagram which shows pipeline `SequentialAgent` wrappers | Wrapped each `LoopAgent` in a `SequentialAgent` pipeline before placing in `ParallelAgent`; updated test description accordingly | `review-loop-implementation-plan.md` |
| 4 | Open Question 5 (Firestore persistence for workflow state) still marked as open — answered by harness doc Sections 8.5-8.7 | Marked as answered with inline note: harness doc defines the long-term model; Story 4.2's session-state approach is the initial incremental step | `review-loop-implementation-plan.md` |

### Cross-References Added

| # | Location | Reference Added |
|---|----------|----------------|
| 5 | Harness doc Section 4.6 (after `agent-hierarchy.md` reference) | Pointer to implementation plan for phased delivery details (13 stories, 5 phases) |
| 6 | Harness doc Section 8 status blockquote | Pointer to implementation plan as the delivery plan for Sections 8.1-8.4 |
| 7 | Harness doc Section 12.3 roadmap, "Workflow management" row | Appended link to implementation plan |

### Documents Updated

| File | Version | Changes |
|------|---------|---------|
| `docs/design/review-loop-implementation-plan.md` | v1.1 (no version bump — alignment fixes only) | 4 edits: design refs table, latency clarification, pipeline wrappers in code, open question resolved |
| `docs/KEN-E-System-Architecture.md` | — | 3 cross-references added at Sections 4.6, 8, and 12.3 |
| `docs/design/DESIGN-REVIEW-LOG.md` | — | Added this entry (Review 11) |

### Verification

- Section 3.3 diagram (lines 122-137) already shows pipeline `SequentialAgent` wrappers — confirming the Story 4.1 code fix resolves an internal inconsistency.
- No duplicate cross-references exist in the harness doc — the 3 new references point to the implementation plan from locations that previously had no such link.

---

## Review 12: Data Visualization & Artifacts — Design Document Updates

**Date:** March 18, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Add data visualization and artifact delivery capability to the architecture design documents. No code changes — documentation only.

### Design Decisions

| # | Decision | Status |
|---|----------|--------|
| 1 | Vega-Lite as visualization spec format | Proposed — Notion entry TBD |
| 2 | Agent suggests chart type, frontend can override | Proposed — Notion entry TBD |
| 3 | Additive `ChatResponse` extension (`artifacts` field, backward-compatible) | Proposed — Notion entry TBD |
| 4 | Review loop evaluates visualization quality alongside text | Proposed — Notion entry TBD |

### Documents Created

| File | Content |
|------|---------|
| `docs/design/data-visualization.md` | New detail doc (v1.0). Artifact model (Vega-Lite spec + metadata), `create_visualization()` tool signature and implementation pattern, data flow (agent → session state → API → frontend), ChatResponse extension, review loop integration (reviewer instruction template, acceptance criteria), multi-step workflow integration (per-step artifacts, synthesizer references), frontend rendering decision (react-vega vs Recharts translation), channel considerations (Web: inline, Slack: PNG, Voice: verbal), open questions. |

### Documents Updated

| File | Version | Changes |
|------|---------|---------|
| `docs/KEN-E-System-Architecture.md` | v2.7 → v2.8 | Added Vega-Lite decision to Section 1.4 Key Design Decisions. Updated Section 2.3.2 request flow (create_visualization in specialist step 3a, artifacts extraction in response step 4). Added `response_artifacts` to Section 3.6.2 session state. Added visualization blockquote to Section 4.4. Added "Visualization Artifacts in Review Loops" subsection after Section 4.6. Added data visualization row to Section 12.3 roadmap. Added Vega-Lite, Artifact, create_visualization glossary entries (Appendix D). Added v2.8 document history entry. |
| `CLAUDE.md` | — | Added `data-visualization.md` to design docs table. |
| `docs/design/agent-hierarchy.md` | v1.6 → v1.7 | Added `create_visualization()` blockquote after Section 7 specialist table. Added artifact evaluation bullet to Section 9.1 review loop key details. |
| `docs/design/api-gateway-multi-channel.md` | v1.0 → v1.1 | Updated Section 2 response format (added artifacts). Added ChatResponse artifacts row and per-channel rendering blockquote to Section 6. |
| `docs/design/review-loop-implementation-plan.md` | v1.1 (no bump) | Added artifact evaluation bullet to Section 3.1 key details. Added `{step_N_artifacts?}` template variable to Story 1.1 acceptance criteria. Added artifact size risk to Section 8. Added open question 8 (artifact formatting for reviewer). |
| `docs/design/mcp-architecture.md` | v1.3 (no bump) | Added `create_visualization()` cross-reference blockquote after Section 4 SDK function tools pattern. |
| `docs/design/DESIGN-REVIEW-LOG.md` | — | Added this entry (Review 12). |

### Key Design Decisions

1. **Vega-Lite as the spec format** — declarative, JSON-based, well-supported ecosystem. Separates data from presentation, allowing the frontend to override chart types.
2. **Additive ChatResponse extension** — `content: str` unchanged; new `artifacts: list[Artifact] | None` field is backward-compatible. Old clients that don't parse artifacts continue to work.
3. **Agent suggests, frontend overrides** — the agent has data context to suggest appropriate chart types; the frontend has UX context to override via the Vega-Lite `mark` property.
4. **Review loop evaluates artifacts** — reviewer evaluates visualization quality alongside text, using an optional `{step_N_artifacts?}` template variable. Acceptance criteria can require specific chart types.
5. **`create_visualization()` is a function tool, not MCP** — follows the SDK function tools pattern. Writes to `response_artifacts` session state, consistent with `output_key` patterns.
6. **Frontend rendering is an implementation-time decision** — Vega-Lite spec is the contract. Whether to use `react-vega`/`vega-embed` or translate to existing Recharts is deferred.

---

## Review 13: Gemini Native Code Execution for Specialist Agents

**Date:** March 18, 2026
**Branch:** `docs/harness-cleanup-design-docs`
**Scope:** Document Gemini's native code execution as a third tool type for specialist agents. No code changes — documentation only.

### Finding

When a user asks KEN-E how well their website performed, the Analytics Specialist retrieves raw data from Google Analytics via MCP tools. To compute percentage changes, averages, or trend analysis, the agent must rely on the LLM doing arithmetic — which is unreliable. No code execution capability exists anywhere in the current architecture or design docs.

**Solution:** Gemini's built-in code execution generates Python code and runs it in a Google-managed sandbox, returning results. Zero infrastructure required (Google handles sandboxing and security). Integrates naturally with ADK via `GenerateContentConfig.tools = [Tool(code_execution=ToolCodeExecution())]`.

### Documents Updated

| File | Version | Changes |
|------|---------|---------|
| `docs/KEN-E-System-Architecture.md` | v2.8 → v2.9 | Added code execution decision (Section 1.4). Added Tool Type Taxonomy table (Section 4.3). Updated Analytics Specialist (Sections 4.4, 4.5). Added code execution in review loop (Section 4.6). Added Section 9.2.1 Code Execution Traces. Added cost bullet (Section 10.2). Added roadmap row (Section 12.3) and Appendix A row. Added 3 glossary entries (Appendix D). |
| `docs/design/mcp-architecture.md` | v1.3 → v1.4 | Added Gemini Code Execution to platform table (Section 4). Added built-in capabilities paragraph and tree entry (Section 5). Added infrastructure row (Section 9). |
| `docs/design/agent-hierarchy.md` | v1.7 → v1.8 | Updated Analytics row in specialist table (Section 7). Added code execution blockquote. Added `GenerateContentConfig` step to factory assembly (Section 8.2). Added `code_execution_enabled` config mapping (Section 8.3). |
| `docs/trace-structure-spec.md` | v1.1 → v1.2 | Added Section 4.4.1 Code Execution Parts (part types table, trace structure, MER-E extraction guidance, key differences from tool calls). Added checklist item 5b. |
| `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` | v2.0 → v2.1 | Updated Analytics Specialist intro to reference Gemini native code execution. Expanded calculation correctness step. Added `code_execution_validation` and `code_review` to eval config. |
| `docs/design/DESIGN-REVIEW-LOG.md` | — | Added this entry (Review 13). |

### Key Design Decisions

1. **Third tool type taxonomy** — MCP Tools, SDK Function Tools, and Built-in Model Capabilities. Built-in capabilities are orthogonal to `tool_filter` and carry zero context overhead.
2. **Analytics Specialist only (initially)** — code execution enabled on Analytics Specialist. Content Specialist may get it later. Root Agent does NOT get code execution.
3. **No infrastructure** — Google manages the sandbox. No Cloud Run deployments, no container images, no security configuration.
4. **Config-driven enablement** — `agents/{id}.code_execution_enabled` in Firestore drives `GenerateContentConfig.tools` assembly in the agent factory.
5. **Trace extraction pattern** — `executable_code` and `code_execution_result` are content parts within `generate_content` spans, not separate L3 spans. MER-E extracts and pairs them for evaluation.

---

## Review 14: ADK Experiment Findings Integration (ADK v1.27.4 Validation)

**Date:** March 27, 2026
**Branch:** `docs/integrate-adk-experiment-findings`
**Scope:** Integrate findings from 9 ADK experiment branches (`adk_experiments` repo). All experiments re-validated on ADK v1.27.4 with zero regressions. Most findings were already incorporated in Reviews 8-13 (March 18); this review adds remaining gaps.

### New Content Added

1. **Dynamic agent creation findings** (`agent-hierarchy.md` §8.5) — Three experiment branches (ephemeral, persistent sub-agents, combined) validated that pre-declared specialists are the recommended pattern. Added:
   - Comparison table: pre-declared vs ephemeral vs persistent dynamic
   - Runner pattern for ephemeral sub-tasks (code example)
   - Three pitfalls to avoid (parent_agent linkage, duplicate names, ADK v2 migration)

2. **Token savings metric** (`mcp-architecture.md` §5a) — MCP tool management experiment measured ~21 tokens per tool declaration. Added measured savings note with experiment reference.

3. **ADK v1.27.4 validation notes** — Updated experiment references from "ADK v1.26.0" to "re-validated v1.27.4" in mcp-architecture.md.

### Documents Updated

| File | Changes |
|------|---------|
| `docs/design/agent-hierarchy.md` | Added §8.5 "Dynamic Agent Creation: Why Pre-Declared Specialists" with Runner pattern, pitfall documentation. Renumbered §8.5 → §8.6 (Limitations). |
| `docs/design/mcp-architecture.md` | Added ~21 tokens/tool savings metric to §5a. Updated experiment version references to include v1.27.4 re-validation. |
| `docs/design/DESIGN-REVIEW-LOG.md` | Added this entry (Review 14). |

### Already Documented (No Changes Needed)

The following experiment findings were already incorporated in Reviews 8-13 (March 18, 2026):

| Experiment | Already In | Review |
|-----------|-----------|--------|
| Review loop (LoopAgent, exit_loop, include_contents) | Harness §4.6, implementation plan §2 | Review 8 |
| Parallel workflow (ParallelAgent, output_key, synthesizer) | Harness §8.1-8.3 | Review 8 |
| ADK pitfalls (output_key+exit_loop, SequentialAgent escalate) | Harness §8.3 | Review 8 |
| tool_filter execution order (before_agent_callback as Option 4) | mcp-architecture §5a | Review 9 |
| Compaction verification (EventsCompactionConfig on v1.26.0) | Already known, documented in memory | — |

### Notion Design Decision

[Agent Engine Python Version Migration: 3.10 → 3.13](https://www.notion.so/33030fd6530281b8ad51f2482a0bd0b2) — created during ADK upgrade session, documents the weave/polyfile/gql dependency chain and Python version migration.

---

## Review 15: Multi-Tenant Data Model Shape — Firestore Subcollections (Shape B) + GCS Prefix (G1)

**Date:** April 20, 2026
**Scope:** Architectural decision + PRD realignment. No code changes yet — research, decision, migration plan, and PRD path edits.

### Finding

A codebase inventory surfaced **five coexisting Firestore multi-tenant shapes** (Shape A flat-per-account, Shape D nested-in-org-doc, a degenerate Shape B-like pattern, Shape C filtered-global, and user-scoped Shape B). Two concrete bugs were already live under Shape A:

1. `api/src/kene_api/routers/accounts.py:968-997` — account deletion sweeps only 1 of 7+ per-account collections, silently orphaning the rest (latent GDPR issue).
2. `api/src/kene_api/services/audit_service.py:189` — `db.collection_group("strategy_audit")` returns empty because Shape A collections are named `strategy_audit_{account_id}`, not `strategy_audit`. Silent dead query.

With a 10k+ account scale target and no production users, the decision was made to realign all account-scoped Firestore data under **Shape B** (`accounts/{account_id}/{resource}/...`), keep Shape C for cross-cutting event streams (`notifications`, `usage_records`), migrate `organizations/{org_id}` nested accounts map to per-account docs, and keep GCS on the existing G1 pattern.

### Documents Updated

| File | Changes |
|------|---------|
| `docs/design/multi-tenant-data-model-research-brief.md` | Unchanged — research brief (historical). |
| `docs/design/multi-tenant-data-model-research-findings.md` | Created — Q1 & Q2 inventory, answers to five product/arch questions, final recommendation. |
| `docs/design/components/data-management/multi-tenant-migration-plan.md` | Created — per-resource migration table, phases 0–6, Terraform index changes, per-environment cutover approach. |
| `docs/design/components/skills/projects/SK-PRD-01-skills-backend.md` | 11 Firestore path references (`skills_{account_id}/*` → `accounts/{account_id}/skills/*`); Firestore layout callout; account-deletion section rewritten to use `recursive_delete`; index section switched from per-account collection to collection scope on the subcollection. |
| `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md` | 2 path references updated; Notion callout added to §3. |
| `docs/design/components/skills/projects/SK-PRD-04-agent-builder-controls.md` | 5 path references (`replace_all skills_{account_id}` → `accounts/{account_id}/skills`); Notion callout added to §4. |
| `docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md` | Firestore layout block (lines 120–124 in prior version) rewritten; AC #1 path updated; Notion callout added. |
| `docs/design/components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md` | Scheduler now uses collection-group query over `project_plans` (Shape B); the per-account-iteration fallback row removed from the Risks table. |
| `docs/design/components/automations/projects/A-PRD-01-data-model-and-api.md` | Firestore layout block rewritten; composite-index block updated to `accounts/*/project_plans` + `accounts/*/plan_runs` collection scope; Notion callout added. |
| `docs/design/components/automations/projects/A-PRD-03-task-artifact-system.md` | `plan_runs_{account_id}` → `accounts/{account_id}/plan_runs` in Dependencies + AC #3; Notion callout added. |
| `docs/design/components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md` | No path changes (consumes the Automations API, not Firestore directly). Notion callout added to §3 for reader context. |
| `docs/design/project-planning-implementation-plan.md` | Firestore Collection Structure block rewritten; Notion callout added. |
| `docs/design/components/knowledge-graph/projects/KG-PRD-05-research-on-creation-refactor.md` | AC #4 path reference updated + Notion callout. |
| `docs/design/DESIGN-REVIEW-LOG.md` | This entry. |

### Key Design Decisions

1. **Shape B is the primary shape** — `accounts/{account_id}/{resource}/...` for strategy_docs, strategy_audit, skills, project_plans, plan_runs, agent_analytics, cost_aggregations, performance_profiles, strategy_processing_state, monitoring_topics, alert_configurations, and all future account-scoped resources.
2. **Shape C is retained** only for genuinely cross-cutting event streams: `notifications` and `usage_records`. Already working; do not migrate.
3. **Shape D (nested accounts-map in `organizations/{org_id}`) is deprecated.** Migration splits funnel/KPI config into `accounts/{account_id}` doc fields (or subcollections if the funnel tree grows past ~500 KiB).
4. **GCS stays on G1.** 10k+ accounts rules out G2 (1k bucket soft cap), no compliance driver, uniform retention makes bucket-level lifecycle sufficient.
5. **Account isolation stays enforced in Python** (`has_account_access` + `is_super_admin` bypass). No move to Firestore security rules as the primary defense.
6. **Migration is a single cutover per environment** — no production users, so no dual-write, no version shim, no downtime window.

### Notion Design Decision

[Multi-Tenant Data Model Shape: Firestore Subcollections (Shape B) + GCS Prefix (G1)](https://www.notion.so/34830fd653028177bc0dc2a1637c7f60)

---

## Review 16: Feature Flags Component — Targeted Rollout with Per-Entity Stickiness

**Date:** April 20, 2026
**Scope:** New architectural component added to Release 1: Foundation. No code changes — PRD authoring only.

### Finding

The engineering team needed a way to ship new capabilities behind a toggle so a feature can reach a small set of users (a specific account allowlist, an email domain for internal dogfood, or a deterministic percentage bucket) before going generally available. No such mechanism existed in the codebase — a survey found zero feature-flag infrastructure, only one-off `VITE_*_ENABLED` env vars and a single `ORGANIZATION_CREATION_PERMISSION` permission-style env gate.

A first-pass design proposed percentage-rollout stickiness on `user_id`. Pressure-testing against the "enable for 3 high-priority accounts; an agency employee sees the feature on those accounts but not on the other 47 they manage" scenario surfaced the problem: user-level stickiness is wrong for any flag whose rollout is conceptually per-account. The design was revised to make stickiness configurable per flag via a `bucketing_entity` field (`account` default, `organization` or `user` opt-in), with the evaluator hashing on the chosen entity's ID. The evaluation context was also widened to include `(user_id, organization_id, account_id)` so the frontend hook re-evaluates on active-account switch — a subtle but critical requirement for multi-account users.

### Documents Created

| File | Purpose |
|------|---------|
| `docs/design/components/feature-flags/README.md` | New component PRD — architecture, data flow, API contracts, key abstractions, conventions. |
| `docs/design/components/feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md` | Pydantic models, evaluator precedence, sha256 bucketing, `POST /evaluate`, `is_feature_enabled()` helper, in-process cache. |
| `docs/design/components/feature-flags/projects/FF-PRD-02-admin-api-and-ui.md` | Super-admin CRUD API, `feature_flag_audit` diff writer, `/admin/feature-flags` React page, super-admin-gated sidebar entry. |
| `docs/design/components/feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md` | `FeatureFlagsProvider` + `useFeatureFlag`, `KNOWN_FLAGS` registry, non-production URL override, Playwright E2E, runbook updates. |

### Documents Updated

| File | Changes |
|------|---------|
| `docs/design/components/PROJECT-PLANNER.md` | Three new rows (FF-PRD-01, FF-PRD-02, FF-PRD-03) with `release = 1: Foundation` and the `blocked_by` chain (`FF-PRD-01 → FF-PRD-02 + FF-PRD-03`; `FF-PRD-02` also blocked by `UI-PRD-01`). |
| `docs/design/DESIGN-REVIEW-LOG.md` | This entry. |

### Key Design Decisions

1. **Shape C (global), not Shape B (account-scoped)** — flags are platform configuration, not account data. `feature_flags/{flag_key}` and `feature_flag_audit/{audit_id}` live at the root, matching the `notifications` / `usage_records` carve-out.
2. **Per-flag `bucketing_entity`** — default `"account"`, opt-in `"user"` or `"organization"`. Flags whose rollout is per-account (most product flags) stick on account so multi-account users get consistent per-account behavior. Flags that travel with a person (profile settings) opt into `"user"`.
3. **Targeting precedence (highest first):** kill switch → email → domain → org → account → percentage → default. Allowlists compose with percentage (e.g., `@ken-e.ai` + 5% of external accounts on the same flag).
4. **Deterministic bucketing** — `sha256(flag_key:entity_id)[:8] % 100`. Same entity always lands in the same bucket across sessions, devices, and backend/frontend callers.
5. **Boolean flags only for Release 1** — multi-variant / string / JSON flags deferred to a future PRD to keep the initial surface area small.
6. **60 s kill-switch SLO** — in-process LRU cache on the backend + TanStack Query `staleTime` on the frontend. No Redis or Firestore listener in Release 1; worst-case propagation is bounded by TTL. Acceptable trade-off for a team of this size.
7. **Super-admin-only management** — reuses the existing `is_super_admin` email-suffix check. Org-admin self-service is out of scope.
8. **Context is server-built, not client-sent** — the evaluate endpoint derives `EvaluationContext` from the auth token so callers cannot spoof a different identity into an evaluation.
9. **Non-production dev override** — `?ff.<key>=on|off` hard-gated on `VITE_ENVIRONMENT !== 'production'`. Persisted to `sessionStorage` for the tab.
10. **Zero Data Management dependency** — FF-PRD-01 is unblocked on day one of Release 1, runs in parallel with DM-PRD-00 through DM-PRD-06 and UI-PRD-01.

### Notion Design Decision

[Feature Flag Targeting Model — Allowlist + Per-Entity Percentage Rollout](https://www.notion.so/<TBD>) — to be created in the Design Decisions database (data source `a88ce7c8-1ebb-4634-a422-2c1abcd2daf9`) capturing the `bucketing_entity` choice, the precedence ladder, the Shape-C placement, and the 60 s SLO trade-off. This PRD set should be re-linked in §6 of each document once the Notion page exists.

---

## Review 17: Retirement of `agent-hierarchy.md` — Consolidation into Agentic-Harness Component

**Date:** 2026-04-20
**Scope:** Consolidate all still-valid agent-hierarchy content into the agentic-harness component docs and delete the legacy `docs/design/agent-hierarchy.md` file.

### Why

Three clarifications made most of the doc's content obsolete or misleading:

1. **The current agent tree is being dismantled.** §1–§5 (current tree, registry, dispatch trampoline, InstructionProvider, current config loading) described a system actively being torn down.
2. **No per-turn `tool_filter`; description-based routing.** Each specialist now receives a fixed curated tool roster (≤30 tools) at construction. The ToolRegistry is a **build-time metadata catalog** the factory reads to assemble those rosters — it is not a runtime router. Root-agent routing is specialist-description-based: the root LLM reasons over each specialist's `agent_configs/{id}.description` to pick a `dispatch_to_{name}()` call. (This refines [Notion 2.2.4](https://www.notion.so/2-2-4-ToolRegistry-as-Root-Agent-routing-index-32930fd65302816284c1c8fd981d4a40)'s "ToolRegistry as routing index" framing, which created ambiguity when two specialists shared a tool — resolving scope at the specialist level is cleaner.) Together, these changes made §6 of the legacy doc (ToolRegistry + `tool_filter` theory) obsolete.
3. **Narrow per-platform specialists, not broad capability specialists.** Future specialists are Google Ads / Meta Ads / Mailchimp (Release 5), not Content / Execution / Automation. This made §7's specialist catalog wrong.

After these corrections, the uniquely valuable content collapsed to: the factory internals (header provider, `Runner` ephemeral-agent pattern, dynamic-agent pitfalls), the review-loop structural rules (already in AH-PRD-01), and the multi-step workflow pattern (already in `review-loop-implementation-plan.md` §Phase 4).

### What moved where

| Content | Old location | New home |
|---------|--------------|----------|
| Config-to-constructor mapping | §8.3 | [AH-PRD-02 §5.2](components/agentic-harness/projects/AH-PRD-02-agent-factory.md) |
| Header provider factory code | §8.4 | AH-PRD-02 §5.3 |
| Dynamic-agent creation analysis + Runner pattern | §8.5 | AH-PRD-02 §5.4 |
| Factory limitations & open questions | §8.6 | AH-PRD-02 §5.5 |
| Multi-tenant overlay (Shape B) | §5.1 | [agentic-harness README §2](components/agentic-harness/README.md) + AH-PRD-02 §4 |
| Review-loop structural rules | §9.1 | [AH-PRD-01 §5.1 + §7](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) (already there) |
| Multi-step workflow pattern | §9.2 | [`review-loop-implementation-plan.md` §3.3 + §Phase 4](review-loop-implementation-plan.md) (already there) |
| Tool-assignment model (new) | — | agentic-harness README §2.5 |
| Specialist roadmap (new) | — | agentic-harness README §2.6 |

### What was deleted without preservation

- §1 Current agent tree, §2 Agent registry, §3 Dispatch trampoline pattern, §4 InstructionProvider code, §5 current Firestore config loading — all describe an implementation being dismantled.
- §6 ToolRegistry / `tool_filter` theory — mechanism retired per Notion 2.2.4.
- §7 Specialist catalog (Analytics / Content / Execution / Automation) — superseded by the narrow-per-platform roadmap in README §2.6.

### Documents updated

- **Deleted:** `docs/design/agent-hierarchy.md`
- **Modified (content additions):** `docs/design/components/agentic-harness/README.md` (added §2.5 Tool-assignment model, §2.6 Specialist roadmap; removed `tool_filter` and `tool_filter_state` references; updated §2 diagram, §2.1 Key Directories, §2.2 Data Flow, §2.4 Key Abstractions, §3.1 Depends On, §6 Global Document References, §7 Conventions); `docs/design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md` (added §5.2–§5.5 covering config mapping, header provider, dynamic-agent analysis, limitations; replaced `tool_filter` scope with curated roster model; updated AC #5 and dependencies)
- **Modified (cross-reference updates):** `CLAUDE.md`, `docs/product-roadmap.md`, `docs/KEN-E-System-Architecture.md`, `docs/design/review-loop-implementation-plan.md`, `docs/design/data-visualization.md`, `docs/design/api-gateway-multi-channel.md`, `docs/design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md`, `docs/design/components/agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md`, `docs/design/components/project-tasks/README.md`, `docs/design/components/automations/README.md`, `docs/design/components/knowledge-graph/README.md`, `docs/design/components/skills/README.md`, `docs/design/components/skills/skills-implementation-plan.md`, `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md`, `docs/design/components/skills/projects/SK-PRD-04-agent-builder-controls.md`

Historical entries in this log and the changelog in the harness design doc retain their original `agent-hierarchy.md` references as part of the historical record.

### Notion Design Decision

No new decision required — this review acts on three already-made decisions (Notion 2.2.4 tool-assignment model, narrow-specialist roadmap, component-docs-as-source-of-truth). The entry itself serves as the changelog.

---

## Review 18: Relocate `data-visualization.md` Under Agentic-Harness Component

**Date:** April 20, 2026
**Scope:** Move the data-visualization design doc into the component it belongs to, and sweep all inbound references to point at the new location.

### Summary

`data-visualization.md` documents the Vega-Lite artifact model, `create_visualization()` tool, `ChatResponse` extension, review-loop artifact evaluation, and frontend rendering. All of that capability is delivered by the Agentic Harness component (agent-factory-attached tool, review-loop reviewer template extension, `ChatResponse` field owned by the harness dispatch path). Keeping the doc at `docs/design/data-visualization.md` while every other component-scoped design now lives under `docs/design/components/<component>/` was a pre-migration artefact. This review relocates the doc and repairs inbound links.

The new PRD [AH-PRD-04 — Data Visualization](components/agentic-harness/projects/AH-PRD-04-data-visualization.md) (added under Sprint 11 → Project migration) now sits next to its canonical design doc in the same component folder — one directory level above the `projects/` folder — matching the pattern used by `skills/` and other components that ship a component-scoped long-form design alongside their README.

### Documents updated

- **Moved:** `docs/design/data-visualization.md` → `docs/design/components/agentic-harness/data-visualization.md` (via `git mv`; history preserved).
- **Internal links fixed (inside the moved file):** `../product-roadmap.md` → `../../../product-roadmap.md`; sibling `mcp-architecture.md` / `review-loop-implementation-plan.md` / `api-gateway-multi-channel.md` → `../../<file>`; `components/agentic-harness/README.md` → `./README.md`.
- **Inbound-link sweep:** `CLAUDE.md`, `docs/product-roadmap.md` (3 refs), `docs/KEN-E-System-Architecture.md` (§3.6.2 session-state table, §4.4 blockquote, §4.6 review-loop section, §12.3 roadmap, Appendix D glossary), `docs/design/review-loop-implementation-plan.md` §3.1, `docs/design/api-gateway-multi-channel.md` §6, `docs/design/mcp-architecture.md` §4, and `docs/design/components/agentic-harness/projects/AH-PRD-04-data-visualization.md` all repoint to the new path.

Historical entries in this log (Review 12) and the changelog in the harness design doc (v2.8 entry) retain their original `docs/design/data-visualization.md` references as part of the historical record, consistent with the convention established in Review 17.

### Notion Design Decision

No new decision required — this is a documentation-organization change that follows the component-docs-as-source-of-truth convention set in Review 17. The entry itself serves as the changelog.

---

## Review 19: `mcp-architecture.md` — v1.4 → v2.0 rewrite + move into agentic-harness component

**Date:** 2026-04-20
**Scope:** Align `mcp-architecture.md` with the clarified tool-assignment model from Review 17 and co-locate it with the agentic-harness component it primarily serves.

### Why

Review 17 retired both the per-turn `tool_filter` mechanism and the broad Analytics / Content / Execution / Automation specialist catalog. `mcp-architecture.md` still carried ~100 lines of now-superseded §5a (`tool_filter` + ToolRegistry runtime driver, Experiment #4 Option 4 decision, execution-order diagram, anti-patterns) plus wrong specialist names in §5 and §8. Remaining content (ADK internals, platform integration decisions, Firestore config schema, MCPServerManager disposition, infrastructure) is MCP-specific reference that's primarily consumed by the agentic-harness factory PRD.

### What changed in the file itself (v1.4 → v2.0)

- **Deleted former §5a** (~100 lines) — the `tool_filter` + ToolRegistry-as-runtime-driver design. The mechanism is retired; specialists now receive a fixed ≤30-tool roster at construction.
- **Rewrote §5** — dropped level-2 per-turn filtering; replaced the Analytics / Content / Execution / Automation tree with the narrow-per-platform diagram (GA in R1; Google Ads / Meta Ads / Mailchimp in R5; HubSpot and n8n noted as platform-decided but not yet mapped to specialists). Added cross-references to README §2.5 and §2.6.
- **Rewrote §4** platform-integration table — added `Specialist` column mapping each platform to its target specialist. Dropped the Analytics / Content / Execution framing.
- **Rewrote §8** — updated specialist names, replaced the "tool_filter controls subsets of facebook-business SDK" framing with the current "each specialist owns its own curated set of SDK function tools" framing.
- **Updated §2 tail** — removed the "this is where `tool_filter` and the ToolRegistry become critical (see Section 5a)" claim; replaced with a pointer to README §2.5.
- **Updated §7** — added a note that ADK's `MCPSessionManager` already handles pooling natively (why the `MCPServerManager` pooling is deprecated).
- **Updated §10** — removed the resolved Q #5 (which pointed at the now-deleted §5a) and added it as a historical note; kept the open questions (n8n, Google Ads writes, ADK version bump, dynamic MCP server connection); added Q #4 about HubSpot specialist scoping.
- **Updated roadmap refs throughout** — dropped `Feature 3.1 Content Specialist` / `Feature 3.2 Execution Specialist` / `Sprint 5-6` references; pointed at AH-PRD-02 and AH-PRD-03 instead.
- **Removed stale `tool_filter` evaluated per turn` row** from §2 (ADK-behavior table) since it's no longer architecturally relevant — §2 now focuses on the ADK behaviors we rely on.

### File moved

- **From:** `docs/design/mcp-architecture.md`
- **To:** `docs/design/components/agentic-harness/mcp-architecture.md`

Rationale: the doc is MCP-specific reference consumed primarily by AH-PRD-02 (agent factory) and future specialist PRDs. Co-locating with the agentic-harness component matches the pattern established for `data-visualization.md`. It is not a candidate for merge into the README — ~200 lines of platform-integration minutiae would bury component-level architecture.

### Inbound-link sweep

Repointed all live references from `docs/design/mcp-architecture.md` → `docs/design/components/agentic-harness/mcp-architecture.md`:

- `CLAUDE.md` (design-docs table)
- `docs/product-roadmap.md` (design-docs table + 6 Design refs blockquotes)
- `docs/KEN-E-System-Architecture.md` (6 live references — §4.3 ToolRegistry role, §4.4 platform rationale pointer, §5 roadmap pointer, §5.1 lazy-loading constraint, §7 multi-tenancy pointer, §4.4 integration rationale pointer)
- `docs/design/design-docs-roadmap-integration-plan.md` (illustrative example — updated to point at README §2.5 + mcp-architecture §4/§6)
- `docs/design/components/project-tasks/README.md` (design references table)
- `docs/design/components/agentic-harness/README.md` (§6 Global Document References)
- `docs/design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md` (dependencies + references)
- `docs/design/components/agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md` (design-docs footer)
- `docs/design/components/agentic-harness/data-visualization.md` (3 refs — sibling file, now uses `./mcp-architecture.md`)

Historical entries in this log and the harness-doc changelog row retain their original `docs/design/mcp-architecture.md` references as part of the historical record.

### Harness-doc §4.3 ToolRegistry role

`docs/KEN-E-System-Architecture.md` §4.3 previously described the ToolRegistry as the `tool_filter` driver via `before_agent_callback`. Rewrote that bullet to describe the ToolRegistry as a **build-time metadata catalog** that the factory reads to assemble each specialist's roster — not a runtime router or filter. Also updated the sentence beneath about "which *tools* are visible is dynamic per-turn" to reflect that both server connections and tool rosters are fixed at deploy time, and root-agent routing is description-based.

### Notion Design Decision

No new decision required — Review 19 acts on the decisions already captured in Review 17 (retired `tool_filter` mechanism, narrow-per-platform specialist roadmap, tool-assignment & routing model). This entry is the document-level changelog.

---

## Review 20: Frontend-migration scope lock-in — drop legacy pages, add UI-PRD-08

**Date:** 2026-04-24
**Scope:** Close the open questions carried by UI-PRD-02 and UI-PRD-05, and lock in which existing `frontend/src/pages/*` routes get redesigned versus dropped before the frontend migration kicks off.

### Why

Pre-migration gap audit against `docs/figma-export/src/app/pages/*` surfaced 11 existing routes with no plan: four admin pages, `AnalysisReport`, `OrganizationSelection`, `Recommendations`, `Campaigns`, `Reports`, `Index` (`/measurement-plan`), and `Home`. UI-PRD-02 and UI-PRD-05 had deferred three of them ("follow-up PRD"); seven had no mention anywhere. Rather than carry the ambiguity into implementation, we closed each with a disposition: drop, or redesign under a specific PRD.

### Dispositions

| Old page | Route | Disposition | PRD |
|----------|-------|-------------|-----|
| `Home.tsx` | `/` | Replaced by `ChatPage` at `/` | UI-PRD-02 §11 Cleanup |
| `Settings.tsx` | `/settings` | Dropped — superseded by `LayoutSettings` sub-nav | UI-PRD-02 §11 |
| `AdminSettings.tsx`, `AdminIndustryKeywords.tsx`, `AgentConfigManagement.tsx`, `ToolUsageDashboard.tsx` | `/settings/admin/*` | **Dropped** — admin surface removed from the product | UI-PRD-02 §11 |
| `OrganizationSelection.tsx` | `/organization-selection` | Replaced by new `/select-organization` page | **UI-PRD-08 (new)** |
| `AnalysisReport.tsx` | `/analysis-report/:reportId` | Dropped — report viewing now lives in Performance Analysis tab | UI-PRD-05 §11 (absorbed by PE-PRD-02) |
| `Recommendations.tsx` | `/recommendations` | Dropped — absorbed by Performance Analysis tab | UI-PRD-07 §11 (absorbed by PE-PRD-02) |
| `Campaigns.tsx` | `/campaigns` | Dropped — absorbed by Calendar + Campaign Management | UI-PRD-07 §11 (absorbed by PR-PRD-08) |
| `Reports.tsx` | `/reports` | Dropped — absorbed by Dashboards | UI-PRD-07 §11 (absorbed by DB-PRD-*) |
| `Simulations.tsx` | `/simulations` | Dropped — absorbed by Performance Simulations tab | UI-PRD-07 §11 (absorbed by PE-PRD-03) |
| `Index.tsx` | `/measurement-plan` | Dropped — no replacement | UI-PRD-07 §11 |

### Documents updated

- **New:** `docs/design/components/ui/projects/UI-PRD-08-organization-selection-page.md` — full 10-section PRD for the redesigned post-auth org-picker (standalone, no shell; preserves agency / super-admin / auto-select logic).
- `docs/design/components/ui/README.md` — §2 architecture diagram adds the standalone-page bucket; §5.1 dependency graph adds UI-PRD-08; §5.2 projects table adds a UI-PRD-08 row and annotates UI-PRD-07 as potentially retired in favor of PE-PRD-01…08; project count updated 7 → 8.
- `docs/design/components/ui/projects/UI-PRD-02-core-shell-pages.md` — closed the Home/Chat open question (decision: Chat replaces Home at `/`); removed the "OrganizationSelection deferred" out-of-scope line (now owned by UI-PRD-08); added **§11 Cleanup** enumerating file deletes for Home, Settings hub, four admin pages, and the legacy org-selection page.
- `docs/design/components/ui/projects/UI-PRD-05-knowledge-section.md` — closed the AnalysisReport open question (decision: dropped, not redesigned); added **§11 Cleanup** for `AnalysisReport.tsx`.
- `docs/design/components/ui/projects/UI-PRD-07-performance-page.md` — §1 flags the subsumption risk vs. PE-PRD-01…08; moved Recommendations / Campaigns / Reports out of "Out of scope" and into a new "Pages dropped from the product" subsection; added **§11 Cleanup** for `Recommendations.tsx`, `Campaigns.tsx`, `Reports.tsx`, `Index.tsx` (`/measurement-plan`), `Simulations.tsx`.
- `docs/design/components/PROJECT-PLANNER.md` — added UI-PRD-08 row at Release 1: Foundation; annotated UI-PRD-07 "may be subsumed".

### Follow-ups

- At PE-PRD-01 kickoff, decide whether to retire UI-PRD-07 and move its Cleanup table into PE-PRD-01. No action needed now — the Cleanup lives in one place in the meantime.
- Figma has no exported node for the new org-select page; UI-PRD-08 §5 carries the visual spec inline until Figma catches up.

### Notion Design Decision

Add a Design Decision entry for "Frontend migration — drop legacy routes" linking to this review. (To be filed by the design-doc maintainer.)

---

## Review 21: Release assignments — full dependency-driven sequencing across all 15 components

**Date:** 2026-04-24
**Scope:** Fill the `release` column for every PRD row in `PROJECT-PLANNER.md` (91 rows across 15 components) based on the full `blocked_by` dependency graph, and reconcile the Release overview table in `KEN-E-System-Architecture.md` §12.

### Why

Six components (Data Pipeline, Integrations, SAR-E, Performance, Billing, Chat) had `release` unset in `PROJECT-PLANNER.md`, and the pre-existing assignments contained a circular impossibility: `DM-PRD-07` (Approval Workflow & Audit) was slotted to Release 1, but depends on `PR-PRD-01` (Project Tasks data model), which was Release 2. `System-Architecture §12` carried a `TBD` row acknowledging the gap but with no resolution. With component design complete across the landscape, release sequencing was the last missing piece before implementation could be parallelized across teams.

### Method

1. Walked every `blocked_by` edge in the PRD graph (91 rows) to identify the topological earliest possible release per project.
2. Grouped projects into release themes matching product coherence (Foundation → Task Automation → Expertise + Monetization → Measurement → Multi-Channel + Extensions → Voice).
3. Resolved four judgment calls with the user before writing: billing placement (R3, not R4, to turn on revenue before the analytical layer ships); R2 width (kept wide — PR + A + DB + IN + DP + CH-04 + DM-07 as one connected graph); chat split (CH-01/02/03/05 in R1; CH-04 in R2 because its AuthStatusCard needs IN-PRD-03); DP-05 placement (R5 with the additional specialists it pairs with).

### Release structure (final)

| Release | Theme | PRD count | Content |
|---------|-------|-----------|---------|
| **1** | Foundation | 20 | DM-00..06, AH-01..03, UI-01/02/08, FF-01..03, CH-01/02/03/05 |
| **2** | Task Automation | 35 | DM-07, PR-01..08, A-01..07, DB-01..04, UI-03/04, IN-01..07, DP-01..04 + 06, CH-04 |
| **3** | Expertise + Monetization | 18 | KG-01..05, SK-00..04, UI-05, AH-04, BL-01..06 |
| **4** | Measurement | 15 | SE-01..07, PE-01..08 |
| **5** | Multi-Channel + Extensions | 2 | UI-06, DP-05 (plus Slack + additional specialists — no PRDs yet) |
| **6** | Voice | 0 | Voice channel (no PRDs yet) |
| **Subsumed** | — | 1 | UI-PRD-07 folded into PE-PRD-01 |

### Dependency observations that drove placement

- **DM-PRD-07 → R2** (not R1): depends on PR-PRD-01. Cascades to IN-PRD-01, BL-PRD-01, SE-PRD-01, DB-PRD-01 which all need DM-07 and therefore sit at R2 or later.
- **Integrations + Data Pipeline → R2** alongside PR + A + DB: IN-03 needs UI-01 + IN-02; DP-03 needs PR-04 + A-03 + A-04. They form one connected subgraph.
- **SAR-E → R4**: SE-02 (Weekly KPI Ingestion) depends on DP-01/02/03. Data Pipeline's first production consumer is SAR-E; SAR-E can't ship until Data Pipeline ships.
- **Performance → R4**: PE-05 (Setup Wizard) depends on IN-PRD-03; PE-07 (Diagnostics) depends on DP-PRD-01. Thematically pairs with SAR-E.
- **Billing → R3**: unblocked after R2 (DM-07 + FF-01 + UI-02 all in R1/R2). Placed with Expertise rather than with Measurement (R4) so revenue is turned on before the analytical layer.
- **Chat split at CH-04**: CH-04 (Session Status View) depends on IN-PRD-03 for its AuthStatusCard. CH-01/02/03/05 have no Integrations dep and ship in R1. The chat redesign is user-visible from R1 but the status view completes in R2.
- **UI-PRD-07 subsumed**: its own PRD acknowledged "May be subsumed by PE-PRD-01…08." PE-PRD-01 delivers the same `/performance` shell on `LayoutC`. UI-07 is marked subsumed rather than released.

### Documents updated

- `docs/design/components/PROJECT-PLANNER.md` — filled the `release` column on every previously-blank row (Chat 01/02/03/04/05, Integrations 01..07, Data Pipeline 01..06, SAR-E 01..07, Performance 01..08, Billing 01..06, UI-07); moved DM-PRD-07 from R1 → R2; normalized theme casing (`2: task automation` → `2: Task Automation`; `3: Expertise` → `3: Expertise + Monetization`; `5: integrations` → `5: Multi-Channel + Extensions`); added a **Release Strategy** section above the project table with per-release theme + rationale.
- `docs/KEN-E-System-Architecture.md` — rewrote the §12 Release overview table: R1 loses DM-07 (now lists DM-00..06) and gains Chat; R2 gains DM-07, IN, DP, and CH-04; R3 renamed to "Expertise + Monetization" and gains Billing; R4 "Measurement" added for SAR-E + Performance; R5 renamed to "Multi-Channel + Extensions"; `TBD` row removed; UI-PRD-07 subsumption called out below the table. Updated the note on numbering to reflect that PROJECT-PLANNER now uses 1..6 (not just 1/2/3/5).

### Follow-ups

- **`docs/product-roadmap.md` reconciliation** — that doc still describes R2.0 as "Intelligent Analytics" (review loop + GA specialist + data viz) and R3.0 as "Content & Campaigns," which no longer matches the component planner's release structure. Recommendation under separate cover: retire `docs/product-roadmap.md` in favor of `PROJECT-PLANNER.md` for project sequencing and Linear for feature/sprint detail. (Followed up in Review 27 — the Notion → Linear migration.)
- **No implementation work unblocked yet** — this review only fills in the release column. Component teams continue to pull from `blocked_by` directly; the `release` column is for cross-component planning.

### Decision

This Review entry is the canonical capture. Release assignments are tracked in `docs/design/components/PROJECT-PLANNER.md`.

---

## Review 22: Backfill — Decisions 7 + 8 (Token Budget Strategy + ToolRegistry as build-time catalog)

**Date:** 2026-04-25
**Scope:** Backfill Decisions 7 + 8 from the legacy Notion Design Decisions database into this in-repo log. These are foundational tool-handling decisions that pre-date Reviews 1–20 but only had Notion records until now.

### Context

The agent system manages a large tool inventory (~400 tools across 20–40 MCP servers) per the System Architecture §1.2. The naive approach of loading every tool definition into every agent context would consume ~60,000 tokens before any conversation begins. Two architectural decisions shape how this is handled.

### Decision 7 — Token Budget Strategy

Each specialist receives a **curated ≤30-tool roster fixed at construction time**. The cap is the scope discipline — specialists that need more than 30 tools indicate a scope problem and should be split into multiple specialists. Built-in Gemini code execution (`ToolCodeExecution`) is included as a tool *type* but carries zero context overhead — no tool definition is sent to the model. The Root Agent does not get domain tools; it routes to specialists.

Per-turn `tool_filter` predicates were considered but later retired (see Review 9) in favor of fixed rosters with description-based routing.

### Decision 8 — ToolRegistry as build-time catalog

The ToolRegistry is a **build-time metadata catalog** read by the Agent Factory at deploy time, not a runtime router. The factory uses it to assemble each specialist's ≤30-tool roster. There is no runtime tool-selection layer. Routing between specialists is description-based: the root LLM reasons over each specialist's `agent_configs/{id}.description` to pick a `dispatch_to_{name}()` call.

### Where the rationale lives now

- System Architecture §1.4 (Key Design Decisions) — narrow per-platform specialists, ≤30-tool roster
- Agentic-harness README §2.5 (Tool-assignment & routing model)
- System Architecture §4.1 (Tool Type Taxonomy)
- Review 9 in this log — `tool_filter` retirement (the refinement of Decision 8)

### Decision

This Review entry is the canonical capture. The original Notion Decisions remain accessible in archive but should not be cited as the authoritative source going forward.

---

## Review 23: Backfill — Decisions 14 + 15 + 16 (Channel architecture: API gateway, Slack, Voice)

**Date:** 2026-04-25
**Scope:** Backfill the three multi-channel architecture decisions from Notion. These cover the channel-agnostic API surface (today: web chat; planned: Slack in R5; planned: Voice in R6).

### Decision 14 — Channel-Agnostic API

Single FastAPI surface in front of Vertex AI Agent Engine. Channel-specific adapters (web frontend, Slack bot, voice gateway) translate to a common `ChatRequest` / `ChatResponse` contract. Channel knowledge does not leak into the agent path; the agent does not know whether it is responding to a browser, a Slack thread, or a voice stream.

### Decision 15 — Slack Channel

Slack Bolt SDK with thread-context binding. One ADK session per user × Slack workspace. Long-running responses use Slack's deferred response pattern (initial ack, follow-up message via webhook). Visualization artifacts degrade to text-+-image attachments per the channel-considerations note in `data-visualization.md` §9.

### Decision 16 — Voice Channel

Pipecat for voice pipeline orchestration. Cartesia TTS (sub-100ms TTFB). Deepgram STT (sub-300ms). Recall.ai or Meeting BaaS for meeting-bot integration. The voice-latency gap is the open risk: Agent Engine's ~7–13s response time vs. voice's <2s end-to-end target. R5 voice feasibility spike (Story 5.5-1) is the de-risk gate before R6 planning commits.

### Where the rationale lives now

- System Architecture §7 (Frontend & Channels)
- `docs/design/components/backlog/api-gateway-multi-channel.md` (channel adapter design)
- Risk Register entry "Voice latency incompatible with Agent Engine"

### Decision

This Review entry is the canonical capture. R5 spike outcome will produce its own Review when complete.

---

## Review 24: Backfill — Decision 18 (Session Compaction — ADK native)

**Date:** 2026-04-25
**Scope:** Backfill the session compaction architectural decision from Notion.

### Context

Long-running chat sessions accumulate events that eventually exceed the model context window. Three approaches were considered: a custom `ConversationSummarizer` written in-house, manual user-triggered compaction via a UI affordance, or ADK's built-in `EventsCompactionConfig`.

### Decision

Use ADK's `EventsCompactionConfig` with a `gemini-2.5-flash` summarizer. Triggers: every 5 user invocations OR session exceeds 50K tokens. Retention: last 10 raw events un-compacted + 1 invocation of overlap with the prior summary for continuity. KEN-E owns only the config values (`token_threshold=50000`, `event_retention_size=10`); ADK owns the summarization logic, retention windowing, and budgeting.

### Alternatives rejected

- **Custom `ConversationSummarizer`** — rejected because it duplicates ADK functionality and requires us to maintain the summary-quality bar ourselves.
- **Manual user-triggered compaction** — rejected because the UX friction (asking the user to "compact now") was deemed worse than automatic compaction with conservative thresholds.
- **Larger context window** — rejected; cost + latency penalty outweighs the benefit for typical session lengths.

### Where the rationale lives now

- System Architecture §3.5 (Session Compaction — ADK Native)
- `app/adk/deploy_ken_e.py` — config values

### Decision

This Review entry is the canonical capture.

---

## Review 25: Backfill — Decision 19 (Token Usage Visibility in UI) [PROPOSED]

**Date:** 2026-04-25
**Scope:** Backfill the proposed token-usage-visibility decision from Notion. Status: proposed; not yet implemented.

### Context

Token-usage data exists at three layers — Vertex AI `usage_metadata` per response, Weave traces, and `ConversationSummarizer.token_budget_usage` — but none of it crosses the API boundary to the frontend. The current `ChatResponse` returns content + session metadata only.

### Proposed Decision

Add a `usage` field to `ChatResponse` exposing three signals:

- **Tokens sent with most-recent query** — from `usage_metadata`; rendered as a percentage of total available context
- **Session tokens used** — running total from `ConversationSummarizer.token_budget_usage`
- **Compaction proximity** — warning indicator when the session crosses 80% of the 40K compaction trigger

### Implementation surface (when scheduled)

- API: extract `usage_metadata` from Agent Engine response, populate the new field
- Response model: extend `ChatResponse` with the `usage` field (additive, backward-compatible)
- Frontend: token-display components in the chat UI

### Status

Proposed — not in any current release plan. May be folded into the Billing or Chat components if the product case develops.

### Decision

This Review entry is the canonical capture of the proposal. When implementation is scheduled, the implementing PRD becomes authoritative.

---

## Review 26: Backfill — Decision 20 (Unified Usage Tracking for Billing) [SUPERSEDED IN PART]

**Date:** 2026-04-25
**Scope:** Backfill the unified-usage-tracking architectural decision from Notion. Partly superseded by the Billing component (BL-PRD-02).

### Context

Two separate usage-tracking Firestore collections exist:

| Collection | Tracks | Has organization_id | Has session_id | Has token counts |
|------------|--------|---------------------|-----------------|------------------|
| `tool_usage_events` | Tool calls (name, duration, user) | ✅ | ❌ | ❌ |
| `usage_records` | LLM calls (tokens, model, cost) | ❌ | ❌ | ✅ (partial) |

Monthly billing requires aggregating token usage to the organization level — neither collection supports this on its own.

### Original Decision (Decision 20)

Keep the two collections separate (tool observability vs. billing) but standardize on shared keys: `organization_id` + `session_id`. Close three gaps:

1. Backfill `organization_id` + `session_id` on `usage_records` writes
2. Ensure Vertex AI `usage_metadata` token counts reach `usage_records` reliably (currently only W&B traces)
3. Build a billing aggregation Cloud Function or BigQuery view summing tokens by organization × billing period

### Current state

The Billing component (`docs/design/components/billing/`) supersedes the aggregation-layer portion of this decision. **BL-PRD-02 (Token Meter + Monthly Enforcement)** is the canonical implementation:

- `billing.meter_increment()` is the synchronous per-call meter, not a Cloud Function aggregator
- Per-account → per-org rollup uses Shape-B Firestore subcollections
- 10-shard distributed counter handles write contention

The schema decisions in Decision 20 (shared `organization_id` + `session_id` keys) remain valid for cross-referencing the two collections.

### Where the rationale lives now

- System Architecture §3.6.5 (Unified Usage Tracking for Billing) — original framing
- `docs/design/components/billing/` — current implementation
- BL-PRD-02 — token meter spec

### Decision

This Review entry is the canonical capture of the original decision. BL-PRD-02 is the canonical implementation plan going forward.

---

## Review 27: Notion → Linear migration (workflow + decision-log + roadmap retirement)

**Date:** 2026-04-25
**Scope:** Full migration of KEN-E development off Notion. Three concurrent threads: (a) replace the local-dev session-skill workflow with the Linear-driven autonomous-agent workflow imported from Fun-E, (b) collapse all live decision references in design docs to in-repo `DESIGN-REVIEW-LOG.md` anchors with backfilled Reviews for previously-Notion-only decisions, (c) retire `docs/product-roadmap.md` after salvaging its Risk Register and Sequencing Principles into the System Architecture.

### Context

KEN-E development was three-way split across docs (architecture), Notion (decisions + sprint planning), and ad-hoc state in component READMEs (release sequencing). Per-feature execution was migrating to Linear independently. The drift surface area was high — every PRD update potentially required Notion edits, and the `product-roadmap.md` numbering (1.1 / 2.0 / …) had diverged from the component planner's release themes (1 / 2 / …). Track 1 (Fun-E infrastructure) was completed in a parallel session and shipped a multi-repo dispatch system that supports KEN-E-AI/KEN-E (15 component teams) plus KEN-E-AI/FUN-E, KEN-E-AI/MER-E, KEN-E-AI/ken-e-web, and Dive-Team/diveteam_website.

### Method (seven-phase migration in KEN-E)

**Phase 1 — Local skills import.** Copied Fun-E's `product-assistant`, `update-design-docs`, `linear-sprint-ops`, and `frontend-design` skills (12 files total) into `KEN-E/.claude/skills/`. Workflow skills (`dev-team-workflow` etc.) were intentionally NOT copied — they're baked into the agent VM image in Fun-E and shouldn't drift between repos.

**Phase 2 — Obsolete skill removal.** Deleted `start-session`, `run-tests`, `end-session`, `notion-pm-workflow` skills + `session-context` agent. These were the Notion-era local-dev session lifecycle that no longer applies.

**Phase 3 — Decision link migration.** Converted ~30 outbound Notion Decision URLs across 18 files to in-repo Review anchors. Backfilled five new Reviews (22–26) for decisions that previously only had Notion records: Decisions 7+8 (Token Budget + ToolRegistry), 14+15+16 (channel architecture), 18 (session compaction), 19 (token usage visibility), 20 (unified usage tracking). Updated DESIGN-REVIEW-LOG header to mark itself canonical and the footer template to drop the Notion follow-up line.

**Phase 4 — `product-roadmap.md` retirement.** Salvaged 8 unique Risk Register rows into System Architecture §11.4. Salvaged 4 timeless Sequencing Principles into a new System Architecture §1.7. Bulk-removed 37 `> **Roadmap:**` blockquotes across 7 design docs (those references pointed at product-roadmap features and didn't add architectural value). Updated CLAUDE.md to add `dev-workflow.md` as the human-facing workflow doc. Deleted `docs/product-roadmap.md`.

**Phase 5 — CLAUDE.md updates.** Added a new "Linear Workflow Conventions" section with the 15-team mapping (KEN-E component → Linear team display name → repo + dir), project naming convention (`<PRD-ID>: <PRD title>`), and the canonical-source rule: SKILL files are canonical for autonomous-agent behavior; `dev-workflow.md` is canonical for humans. Updated the Skills table to reflect the four imported skills (product-assistant, update-design-docs, linear-sprint-ops, frontend-design) plus a note about image-baked workflow skills.

**Phase 6 — Setup guide + prose housekeeping.** Deleted `docs/claude-code-notion-setup-guide.md`. Fixed ~12 incidental Notion-prose mentions across PROJECT-PLANNER, DM-PRD-06, multi-tenant-data-model-research-brief, Release-1-Optimization-Strategy, AH-PRD-03, AH-PRD-04, and `ai-engineer.md`. Most became Review-N anchors; some became Linear pointers; a few were dropped entirely.

**Phase 7 — Verification.** Final greps confirm: zero live-doc Notion URLs (all remaining ones are explicitly marked "historical / archival" or live in DESIGN-REVIEW-LOG entries 1–20 as accurate-for-their-time history); zero `product-roadmap.md` references outside the System Architecture's own Document History changelog; zero `start-session` / `run-tests` / `end-session` / `notion-pm-workflow` skill mentions in CLAUDE.md.

### Documents updated

- **Skills imported** (12 files): `.claude/skills/operations/product-assistant/{SKILL.md,example.md}`, `.claude/skills/tools/{update-design-docs,linear-sprint-ops}/SKILL.md`, `.claude/skills/frontend-design/SKILL.md` + 7 reference files
- **Skills deleted**: `.claude/skills/{start-session,run-tests,end-session,notion-pm-workflow}/`, `.claude/agents/session-context.md`
- **Decision-link conversions** (18 files): `KEN-E-System-Architecture.md`, `knowledge-graph/README.md` + KG-PRD-03 + KG-PRD-04 + KG-PRD-05, `agentic-harness/README.md` + AH-PRD-01 + AH-PRD-03 + AH-PRD-04 + `mcp-architecture.md` + `data-visualization.md`, `data-management/README.md` + DM-PRD-00 through DM-PRD-06 + `multi-tenant-migration-plan.md`, `feature-flags/README.md` + FF-PRD-01, `skills/skills-implementation-plan.md` + SK-PRD-01 + SK-PRD-02 + SK-PRD-04, project-tasks PRDs (PR-PRD-01, PR-PRD-06), automations PRDs (A-PRD-01, A-PRD-03), `review-loop-implementation-plan.md`, `project-planning-implementation-plan.md`, `spike-otel-pydantic-findings.md`, `multi-tenant-data-model-research-brief.md`
- **Backfilled Reviews (this log)**: 22 (Decisions 7 + 8), 23 (Decisions 14 + 15 + 16), 24 (Decision 18), 25 (Decision 19), 26 (Decision 20)
- **Header / footer**: log header reframed as canonical source going forward; footer template stripped of Notion follow-up line; existing Reviews 1–20 left intact as historical record
- **System Architecture**: new §1.7 (Sequencing principles) + 8 new rows in §11.4 (Risk Assessment Matrix); §12 release table; "What this doc is not" purpose paragraph
- **CLAUDE.md**: new "Linear Workflow Conventions" section with 15-row team mapping; updated Skills table; updated Documentation Model paragraph
- **`docs/dev-workflow.md`**: cross-link header pointing at the canonical SKILL files
- **Deleted**: `docs/product-roadmap.md`, `docs/claude-code-notion-setup-guide.md`

### What's intentionally NOT in this migration

- **Fun-E repo** — Track 1 (the multi-repo dispatch infrastructure + skill parameterization) was completed separately. This migration only touched KEN-E.
- **MER-E / DiveTeam Website / KEN-E Website repos** — each follows the same pattern when its turn comes (docs standardize to KEN-E layout, Linear teams created, CLAUDE.md mapping table added). Out of scope here.
- **Linear team / project / issue creation** — one-time data entry; can be done interactively via `product-assistant` after this lands.
- **Removing Notion MCP from individual Claude Code user settings** — per-developer; not a repo change.
- **DESIGN-REVIEW-LOG entries 1–20** — left intact. Their inline "See Decision N in Notion" references and "Notion Design Decision" footers are accurate-for-their-time historical records of how decisions were captured at the time. Per the migration policy: don't rewrite history, just stop writing new Notion links.

### Decision

This Review entry is the canonical capture. Going forward, DESIGN-REVIEW-LOG is the architectural decision log and Linear is the per-feature execution tracker. No new entries should reference the legacy Notion Design Decisions database.

---

## Review 28: Sprint 6 — Firestore Config Registry Delivered (Feature 1.1.4)

**Date:** 2026-04-24
**Branch:** `feature/1.1.4-firestore-config-registry` (PR #240)
**Scope:** Feature 1.1.4 — four stories delivering the Firestore config registry end-to-end: schemas, YAML→Firestore migration with fallback, admin CRUD + audit subcollection, and 60 s hot-reload cache. Plus two code/security-review follow-ups that surfaced during the pre-ship pass.

### Key design decisions (Notion)

| Decision | Link | Impact |
|---|---|---|
| A — Firestore MCP server config schema | https://www.notion.so/34830fd653028158bb4be8b22622bcb8 | Medium |
| B — 60 s TTL cache for agent config hot-reload (instruction only; model/temperature/max_output_tokens require redeploy) | https://www.notion.so/34830fd653028107a823e73cdf27ddc8 | High |
| C — Per-config history subcollection at `{collection}/{id}/history/{ts}` | https://www.notion.so/34830fd65302815fb08fddb54d9fafb5 | Medium |

### What landed

- **Pydantic models** at `api/src/kene_api/models/agent_config_models.py` and `api/src/kene_api/models/mcp_server_models.py` (schemas, `ConfigAuditEntry`, `CREDENTIAL_KEYS`, cross-field invariants).
- **Firestore loader with YAML fallback** at `app/adk/mcp_config/firestore_loader.py`; factory in `app/adk/mcp_config/config.py` selects via `MCP_CONFIG_SOURCE` env var. Migration script at `app/adk/mcp_config/scripts/migrate_mcp_to_firestore.py` (ran against ken-e-dev, 6 docs). Bundle-fix in `deploy_ken_e.py` so YAML is copied into the Agent Engine artifact.
- **Admin CRUD routers:** `api/src/kene_api/routers/agent_configs.py` (extended with PUT audit + redeploy-warning response) and `api/src/kene_api/routers/mcp_server_configs.py` (new — GET/PUT/history/reload). Shared helpers extracted to `api/src/kene_api/services/config_versioning.py`. Audit helper `log_config_action()` in `services/audit_service.py`. Per-config history subcollection writes on every PUT.
- **Hot-reload cache** at `app/adk/agents/utils/config_cache.py` (TTL 60 s, `threading.Lock`, serve-stale-on-error, `GOOGLE_CLOUD_PROJECT_ID`-aware). `ken_e_agent.py` `_make_instruction_provider` rewired to read from cache each turn. `MCPServerManager.reload()` added for runtime toolset eviction on config change.

### Correction to AC-6.25 scope

The Sprint 6 plan originally framed hot-reload as "instruction and temperature propagate within 60 s." Pre-ship review surfaced that ADK's `Agent` constructor only accepts a callable for `instruction`; `model`, `generate_content_config` (including `temperature` and `max_output_tokens`), and tools are baked at construction. `_REDEPLOY_REQUIRED_FIELDS` in `routers/agent_configs.py` was corrected to `{"model", "temperature", "max_output_tokens"}` and the PUT response's `warnings` list now surfaces redeploy-required guidance for all three.

### Security-review follow-up: loader-layer secret resolution

The initial MCP admin implementation resolved `${VAR}` patterns at Pydantic model-construction time (via `mode="before"` field validators on `SseConnectionConfig` / `StdioConnectionConfig`). Because FastAPI constructs these models on request parsing, every PUT would have materialized resolved secrets into Firestore, the audit trail's `changes` dict, and the PUT/GET response bodies. Fix: validators removed from the connection models; resolution moved to a loader-only helper (`_resolve_env_vars_in_dict()` in `config.py`) invoked from `MCPConfigLoader.load()` and `FirestoreMCPLoader._doc_to_runtime_config`. The admin router uses `response_model=None` and returns raw Firestore dicts with literal `${VAR}` strings preserved end-to-end. Pinned by 4 regression tests asserting canary secrets never appear in writes/responses/audit.

### Code-review follow-up: cache project_id

`get_cached_config` previously called `load_config_from_firestore(doc_id)` without `project_id`, defaulting to the loader signature's hardcoded `"ken-e-dev"` in every environment. Staging/prod hot-reload reads would have silently mis-routed to dev Firestore. Fix: read `GOOGLE_CLOUD_PROJECT_ID` at call time (matches `load_and_apply_config_overrides` behavior). Pinned by a regression test.

### Documents affected

- `api/src/kene_api/models/` — new `agent_config_models.py`, `mcp_server_models.py`
- `api/src/kene_api/routers/` — extended `agent_configs.py`; new `mcp_server_configs.py`
- `api/src/kene_api/services/` — extended `audit_service.py`; new `config_versioning.py`
- `app/adk/mcp_config/` — removed env-var resolvers from connection models; added `_resolve_env_vars_in_dict`; new `firestore_loader.py`; new `scripts/migrate_mcp_to_firestore.py`; `manager.py` gained `.reload()`
- `app/adk/agents/` — `ken_e_agent.py` `_make_instruction_provider` rewired; new `utils/config_cache.py`
- Tests: 241 passing across `api/tests/` and `app/adk/**/tests/`, 14+ new, including four secret-leak regression tests
- `docs/design/components/agentic-harness/mcp-architecture.md` — Firestore schema already reflected via main's Review 19 rewrite; no further edits needed this sprint

### Follow-ups (filed, out of Sprint 6 Feature 1.1.4 scope)

- Rate limiting on admin endpoints (`POST /api/v1/mcp-server-configs/reload` DoS surface; cross-cutting concern).
- Audit-swallow observability — structured log + metric when `log_config_action` fails silently so operators see the gap.
- Migration script validation — run Pydantic validation pass over raw YAML before Firestore write.
- Cache serve-stale bound + alert — currently unbounded; a prompt-injection remediation blocked by a Firestore outage could serve the old instruction indefinitely.
- Semver rapid-update race test — needs integration-test infra.

Sprint 6 Phase 2 (stability validation stories 1.1.1-3, 1.14.5, 1.1.2-3, 1.1.5-4) remains Backlog; those stories share the proposed `tests/integration/stability/` infrastructure, not yet built.

## Review 29: Project-Tasks PRDs — Cross-Component Alignment Pass

**Date:** 2026-04-27
**Branch:** `docs/align-project-tasks-prds`
**Scope:** Pre-Linear-issue review of the eight project-tasks PRDs (PR-PRD-01 through PR-PRD-08), the project-tasks README, the System Architecture's project-tasks coverage, and cross-component dependencies (A-PRD-01, DM-PRD-07, DB-PRD-01, DP-PRD-03, KG-PRD-04, AH-PRD-02). Goal: surface contradictions, gaps, and stale references before the work hits Linear and gets dispatched to autonomous dev teams.

### What changed

**(A) Duplicate ownership of `ProjectPlan.type`.** A-PRD-01 §4 and PR-PRD-07 §4 both claimed to add `type: Literal["freeform", "dashboard"]`. Removed the field from PR-PRD-07's data contract (§4 reframed as "consumed fields, not added here"); dropped AC #11 + the `type` enum unit test. A-PRD-01 retains sole ownership.

**(B) `Failed` and `Blocked` task statuses missing from PR-PRD-01.** PR-PRD-04's §5 algorithm referenced `Failed` (revision-cap, dispatch-failure) and `Blocked` (transitively-downstream of Rejected) as if shipped, but PR-PRD-01's enum only had six values. Added both to PR-PRD-01's `TaskStatus` from v1, with a §4 "TaskStatus semantics" subsection clarifying that PRD-01 ships the enum values; PRD-04 enforces the transition policy. PR-PRD-04's §9 risk row cleaned up to drop the "coordinate with PRD-1 to add" note.

**(C) `campaign` vs `campaign_id` rename in A-PRD-01.** A-PRD-01's composite index field and list-endpoint query param still used the legacy `campaign` name. Updated both to `campaign_id` and added a sequencing note: PR-PRD-08 lands the rename + alias + backfill before A-PRD-01's index is queried in production.

**(D) Firestore config-doc path inconsistency `agents/...` vs `agent_configs/...`.** AH-PRD-02 and PR-PRD-02 use `agent_configs/{config_id}` (canonical). The project-tasks README §2.1 + §2.4 and System Architecture §8.2 line 404 still said `agents/project_planning` / `agents/*`. Fixed all three.

**(E) DM-PRD-07 ↔ PR-PRD-08 dependency mismatch.** DM-PRD-07's "Blocks" line listed PR-PRD-08, but PR-PRD-08's own dependencies, PROJECT-PLANNER, and the README workflow all assumed PR-PRD-08 ships in parallel with PR-PRD-01 (before DM-PRD-07). Resolved by removing PR-PRD-08 from DM-PRD-07's "Blocks"; PR-PRD-08 retrofits its `write_audit` calls after DM-PRD-07 ships, mirroring PR-PRD-01's interim approach.

**(F + G) System Architecture §8.2 stale.** Said "six PRDs (PR-PRD-01 through PR-PRD-06)" — out of date once PRDs 07/08 landed. Updated to nine (PRDs 01–09) and added a paragraph block covering multi-category activities (categories + sparse fields + recurrence + owner_email + unscheduled), the Campaign entity (`accounts/{account_id}/campaigns/...` + four-objective enum + per-account generic-fallback seeding), and orphan-task lifecycle.

**(H) `assignee_type="data_pipeline"` extension not acknowledged in PR-PRD-01 / PR-PRD-04.** Added forward-coordination notes in both PRDs noting DP-PRD-03 lands the third `assignee_type` value and the orchestrator's third dispatch branch as additive patches.

**(I) Planning specialist's instruction never updated for the multi-category model.** Added new project **PR-PRD-09 — Planning Agent Multi-Category Update** (Agent / ML team, 1–2 days, blocked by PR-PRD-02 + PR-PRD-07 + PR-PRD-08). Scope: instruction update on `agent_configs/project_planning`; new `resolve_or_create_campaign` tool function; eight golden-path evals exercising every category + recurrence + campaign-resolution path. Without this PRD, every plan the agent emits collapses to `category="task"` and never assigns a campaign — undercutting the value of PRDs 7 and 8.

**(J) PR-PRD-03 header + scope stale.** Header listed only PRD-1 as a blocker; data contract used pre-PRD-7 `PlanTask`; scope omitted the Unscheduled Tasks panel, Batch Activity Wizard, Group Edit drawer, and inline campaign-create flow. Refreshed: header now includes PR-PRD-07 as a hard prerequisite; §1 Context names the multi-category contract; §2 Scope adds the orphan panel + batch wizard + group edit + campaign picker + recurrence rendering; §4 Data contract publishes the full multi-category TypeScript shape; §5 Implementation outline adds the new components + services; §6 API contract enumerates every consumed endpoint (plans, orphan tasks, campaigns, schedules/preview); §7 Acceptance criteria expanded from 10 to 16; §8 Test plan updated with new component tests.

### Cross-cutting decisions taken

| Decision | Rationale | Consequence |
|---|---|---|
| `Failed` and `Blocked` ship in PR-PRD-01's enum from v1 (not as a PR-PRD-04 follow-up) | Consumers (PR-PRD-04, DP-PRD-03) already depend on the values; making PR-PRD-01 the source of truth removes the cross-PRD coordination note and avoids a schema migration mid-release. | PR-PRD-01's tests gain one assertion; PR-PRD-04 publishes the transition policy that uses them. |
| Drop PR-PRD-08 from DM-PRD-07's `Blocks` list rather than adding DM-PRD-07 to PR-PRD-08's `Blocked by` | DM-PRD-07 itself is blocked by PR-PRD-01. Adding DM-PRD-07 to PR-PRD-08's chain would push PR-PRD-08 (and the campaign rename PR-PRD-07 needs) past DM-PRD-07's ship — extending the critical path with no functional benefit, since PR-PRD-08's audit writes can be retrofitted later. | PR-PRD-08 ships its own raw audit writes (mirroring PR-PRD-01's interim pattern) and retrofits to `write_audit` once DM-PRD-07 ships. |
| Add PR-PRD-09 as a separate ninth project (not extend PR-PRD-02 or PR-PRD-07's scope) | PR-PRD-02's owner is Agent/ML; PR-PRD-07's is Backend. Splitting ownership across the agent-instruction update would muddy responsibility. PR-PRD-09 is small (1–2 days) and consistent with how PRDs 06 / 07 / 08 were added. | Component PRD count goes from 8 → 9; sequencing places PR-PRD-09 alongside PR-PRD-05 close-out so the closing sprint isn't extended. |

### Documents updated

- `docs/design/components/project-tasks/README.md` — §1 Overview, §2.1 Key Directories (path fix), §2.4 Key Abstractions (path fix + Failed/Blocked + DP-PRD-03 note), §5 Project Index (count 8→9, dependency-graph rewrite, projects table, recommended workflow rewrite)
- `docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md` — §4 TaskStatus expanded to eight values + new "TaskStatus semantics" + "Forward-coordination" subsections; §8 unit-test list extended
- `docs/design/components/project-tasks/projects/PR-PRD-03-calendar-page-frontend.md` — header (PR-PRD-07 added as blocker), §1 Context, §2 Scope, §3 Dependencies, §4 Data contract (full multi-category TypeScript shape), §5 Implementation outline, §6 API contract, §7 ACs (10→16), §8 Test plan
- `docs/design/components/project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md` — §3 Dependencies (DP-PRD-03 forward-coord), §9 risk row cleaned up
- `docs/design/components/project-tasks/projects/PR-PRD-07-calendar-activities.md` — §4 ProjectPlan-fields-added section reframed (consumes A-PRD-01's `type`); AC #11 dropped; §8 unit test for `type` removed
- `docs/design/components/project-tasks/projects/PR-PRD-09-planning-agent-multi-category-update.md` — **new file**
- `docs/design/components/automations/projects/A-PRD-01-data-model-and-api.md` — §5 composite index `campaign` → `campaign_id`; §6 query param rename; §7 AC-3 rewrite; sequencing note added
- `docs/design/components/data-management/projects/DM-PRD-07-approval-workflow-and-audit.md` — header `Blocks` line + §2 scope bullet + §3 PR-PRD-08 dependency reframed as "later consumer"
- `docs/KEN-E-System-Architecture.md` — §8.2 closing pointer (six → nine PRDs), `agents/project_planning` → `agent_configs/project_planning`, new paragraph block for multi-category activities + Campaigns + orphan tasks
- `docs/design/components/PROJECT-PLANNER.md` — PR-PRD-02 row description (path fix), new PR-PRD-09 row

### Follow-ups (filed)

- Apply the same pre-Linear alignment pass to the other component PRD sets before issues are created (Automations, Knowledge Graph, Data Pipeline, Performance, SAR-E). The pattern surfaced here — duplicate field ownership across components, stale enum-coordination notes, mismatched `Blocks` / `Blocked by` edges, planner-doc count drift — likely repeats elsewhere.

## Review 30: Feature Flags PRDs — Cross-Component Alignment Pass

**Date:** 2026-04-27
**Branch:** `docs/align-component-prds`
**Scope:** Pre-Linear-issue review of the three feature-flags PRDs (FF-PRD-01 through FF-PRD-03), the feature-flags README, the System Architecture's feature-flags coverage (§10.1, §11.7, glossary), and every cross-component caller (CH-PRD-01/02/03, BL-PRD-01/06, PE-PRD-01/03/04/05/06/07/08, IN-PRD-03, DP-PRD-04). Goal: surface contradictions, gaps, and stale references before the work hits Linear and gets dispatched to autonomous dev teams.

### What changed

**(A) Flag-key naming convention contradicted every consumer PRD.** FF-PRD-01's `FLAG_KEY_REGEX = r"^[a-z0-9][a-z0-9-]{2,63}$"` was kebab-case-only, but every consumer PRD used snake_case (`chat_v2_enabled`, `billing_enabled`, `performance_dashboards_tab`, `data_pipeline_task_assignee`, `integrations_ui_enabled`, etc. — 15+ flags across 5 components). Chat ships in Release 1 alongside FF, so this would surface day-one. Resolved by switching to **snake_case-only** (regex `^[a-z0-9][a-z0-9_]{2,63}$`); updated FF README §7.1 + §2.3, FF-PRD-01 §4 regex + §4 examples + §5.2 example, FF-PRD-03 §4 + §5.5 examples + §5.4 E2E test flag (`automations-beta` → `automations_beta`, `new-ui` → `new_ui`, `e2e-test-flag` → `e2e_test_flag`).

**(B) PE-PRD-01's "default-on, target-off" pattern was impossible with FF-PRD-01's targeting model.** PE-PRD-01 §214 said "each flag defaults to `enabled=true` in the registry with a targeting rule (FF-PRD-02) flipping it off to dark-launch a tab." But FF-PRD-01's evaluation ladder (README §7.2) is allowlist-only — rules can only flip a default-off flag **on**, never off. Setting `default_enabled=true` makes the flag unconditionally on; only `is_active=false` disables, and that disables for everyone. Rewrote §214 to describe the standard dark-launch lifecycle: create with `default_enabled=false` + populate allowlist for early-access users; flip `default_enabled=true` at GA; post-GA kill requires flipping `default_enabled=false` (since `is_active=false` falls through to `default_enabled` per the ladder).

**(C) Hook return-type misuse in CH-PRD-02 and CH-PRD-03 example code.** `useFeatureFlag(key)` returns `{ enabled, reason, isLoading }` (FF-PRD-03 §4), but two example snippets treated the return value as a bare boolean: CH-PRD-02:262 (`const chatEnabled = useFeatureFlag("chat_v2_enabled");` then `{chatEnabled && <Route ...>}` — always truthy → route always renders) and CH-PRD-03:174 (`const enabled = useFeatureFlag("chat_categories_enabled");` then passed to React Query's `enabled` option). Fixed both with destructuring (`const { enabled } = useFeatureFlag(...)`).

**(D) System Architecture §10.1 listed feature flags as a Shape B per-account collection.** The prose introduction of the Firestore bullet listed "feature flags" alongside "skills, observations metadata, and audit logs," then later in the same bullet correctly said `feature_flags/*` is a global collection. Fixed by removing "feature flags" from the per-account list; also added the missing `feature_flag_audit/*` to the global-collections list.

**(E) System Architecture §11.7 was incomplete and contradictory.** Said "percentage-based bucketing per entity (account or user)" — missing organization, which FF-PRD-01:76's `BucketingEntity` Literal explicitly supports. Said "allowlist precedence (always-on / always-off)" — but allowlists are positive-match only; "always-off" doesn't exist in the model. Updated both lines: the entity list now reads "(account, organization, or user)" and the targeting bullet now correctly describes that allowlists are positive-only and the kill switch (`is_active=false`) is the only "off" path (and even that requires `default_enabled=false` for a true global disable, since the kill switch falls through to default).

**(F) `types.ts` ownership was ambiguous between FF-PRD-02 and FF-PRD-03.** README §5.3 said "owned by whichever PRD ships first" while FF-PRD-02 §5 said "Create" and FF-PRD-03 §5 said "Create (or extend)" — three voices, no canonical owner, recipe for merge conflicts when the two parallel teams ship. Resolved by nominating **FF-PRD-02 as sole owner**: README §5.3 now explicitly assigns the file to FF-PRD-02; FF-PRD-02 §5 marks it "canonical, owned by this PRD"; FF-PRD-03 §3 + §5 now say "imports from FF-PRD-02; appends runtime-only types" (no "Create").

**(G) No observability scope on FF-PRD-01.** The component README claims a 60s kill-switch SLO but neither PRD specified instrumentation. Added to FF-PRD-01 §2 (in-scope), §5.3 (new "Observability" sub-section), §5 implementation table (modify `feature_flag_service.py` to emit per-evaluation log), AC #13, and §8 unit-test list: `FeatureFlagService.evaluate` emits exactly one INFO log per call with field shape `{flag_key, reason, cache_hit}` and **no** PII (`user_id`, `user_email`, `organization_id`, `account_id` never logged). Updated the §9 PII risk row to reference the new fixed-shape log.

**(H) No Pydantic ↔ TypeScript contract test.** `feature_flag_models.py` and `frontend/src/lib/featureFlags/types.ts` were hand-mirrored with no drift detection beyond reviewer discipline. Added a lightweight JSON-schema snapshot test to FF-PRD-01: `test_feature_flag_schema_contract.py` calls `FeatureFlag.model_json_schema()` and asserts byte-equality against `feature_flag_schema.snapshot.json` (committed). When Pydantic models change, the test fails, the dev regenerates the snapshot in the same PR, and the snapshot diff is what the reviewer compares against the matching `types.ts` change. Documented in FF-PRD-01 §5.4, AC #14, §8 test list; FF-PRD-02 §5.4 carries the matching code-review checklist.

**(I) FF-PRD-02's admin UI shipped no surface for spotting stale flags.** README §7.1 mentions an `expected_ga_release` field "for the admin UI's old-flags report" — but FF-PRD-02 §5.3 List-table columns didn't include it. Added `expected_ga_release` (sortable, blanks last) to the list table + AC #13. No automated stale-detection (the field is free-text — can't be programmatically compared to today's date); admins eyeball during routine reviews.

### Cross-cutting decisions taken

| Decision | Rationale | Consequence |
|---|---|---|
| Snake_case-only flag keys (regex `^[a-z0-9][a-z0-9_]{2,63}$`) | Every consumer PRD (Chat, Billing, Performance, Integrations, Data Pipeline) already uses snake_case. Allowing both invites drift (`chat-v2-enabled` and `chat_v2_enabled` as two distinct flags). Snake_case also matches Python identifier and Firestore field conventions. | FF-PRD-01 regex + README §7.1 + all example code in FF README, FF-PRD-01, FF-PRD-03 changed (`new-ui`/`automations-beta`/`e2e-test-flag` → snake_case equivalents). No consumer PRDs needed renames — they were already snake_case. |
| FF-PRD-02 owns `frontend/src/lib/featureFlags/types.ts` (not "whichever ships first") | Two parallel PRDs both claiming "Create" on the same file invites merge conflicts and ambiguity at code review. FF-PRD-02 owns the admin UI which uses every type field, so it's the natural owner of the schema mirror. | FF-PRD-03 changes "Create (or extend)" → "Extend"; README §5.3 + FF-PRD-02 §3 + FF-PRD-03 §3 carry the same wording. |
| Lightweight JSON-schema snapshot for Python ↔ TS contract (not codegen) | The type surface is ~50 lines and changes rarely. A snapshot test is ~30 lines, has no codegen dependencies, and produces a reviewer-friendly diff. Codegen would have been over-engineered for the surface area. | FF-PRD-01 ships the test + fixture; FF-PRD-02 ships the matching code-review checklist. No new tooling (no `datamodel-code-generator`, no `pydantic-to-typescript`). |
| Stale-flag detection stays manual (sortable column, not auto-flagging) | `expected_ga_release` is free-text in the model — auto-comparing to "today" requires either a structured date field (model migration) or fuzzy parsing (brittle). Sortable column gets 80% of the value at near-zero cost. | FF-PRD-02 §5.3 + AC #13 carry the column. Future structured stale-detection can land as FF-PRD-04 if pain emerges. |

### Documents updated

- `docs/design/components/feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md` — §2 in-scope (observability + snapshot test), §4 regex + examples, §5 implementation table (3 row changes / additions), §5.2 example, new §5.3 (Observability), new §5.4 (Schema-contract snapshot), §7 ACs (added #13 + #14, renumbered final), §8 unit-test list (added schema-contract + log-shape cases), §9 PII risk row reworded
- `docs/design/components/feature-flags/projects/FF-PRD-02-admin-api-and-ui.md` — §2 in-scope (sole-owner clarification), §5 frontend implementation row (sole-owner wording), §5.3 list-table columns (added `expected_ga_release`), new §5.4 (Schema-contract sync code-review checklist), §7 ACs (inserted #13, renumbered)
- `docs/design/components/feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md` — §3 dependencies (rephrased types.ts ownership to "imports from FF-PRD-02; appends"), §4 example renames, §5 implementation row ("Create (or extend)" → "Extend"), §5.4 E2E test flag rename, §5.5 documentation recipe renames
- `docs/design/components/feature-flags/README.md` — §2 architecture-diagram example renames, §2.2 step 3/6 renames, §2.3 added flag-key snake_case + drift-gate sentences, §5.3 Cross-PRD coordination rewritten (sole-owner + contract-test pointer), §7.1 kebab-case → snake_case
- `docs/KEN-E-System-Architecture.md` — §10.1 removed "feature flags" from Shape B per-account list + added `feature_flag_audit/*` to globals; §11.7 entity list (`account or user` → `account, organization, or user`) and targeting bullet (allowlist always-on/always-off → allowlist positive-only + kill-switch nuance)
- `docs/design/components/performance/projects/PE-PRD-01-page-shell-and-routing.md` — §214 ("Feature-flag behavior") rewritten to describe the correct dark-launch lifecycle
- `docs/design/components/chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md` — §5.6 example destructured
- `docs/design/components/chat/projects/CH-PRD-03-session-categories.md` — example destructured

### Follow-ups (filed)

- If structured stale-flag detection becomes desirable (e.g., "highlight flags whose `expected_ga_release` is more than 60 days past today"), open FF-PRD-04 to migrate `expected_ga_release` to a structured release-id enum or ISO date and add automated reporting.
- The next pre-Linear alignment pass (Automations, Knowledge Graph, Data Pipeline, Performance, SAR-E component reviews) should specifically grep for any remaining kebab-case flag keys in case any were missed by the consumer-PRD audit done here.

---

## Review 31: Sprint 6 Phase 2 — Stability validation delivered (Stories 1.1.x harness + 1.1.1-3, 1.14.5, 1.1.2-3, 1.1.5-4)

**Date:** 2026-04-27
**Stack:** PR #260 → #262 → #263 → #265 → #269 → #270 (closeout)
**Scope:** five-PR stack delivering Sprint 6 Phase 2 — the local stability harness (Story 1.1.x) and the four stability validation stories. ACs 6.10–6.24 all PASS locally. Closes the OTEL google-genai workaround probe that had been open since Sprint 5.

### What landed

- **Harness** (`tests/integration/stability/`) — `query_corpus.py` (28 prompts × 5 categories), `diverse_invocation_runner.py` (HTTP driver with JSON report + p50/p95), `memory_profiler.py` (psutil RSS sampler context manager), `weave_trace_capture.py` (in-memory weave-call capture for compliance replay), `redis_ttl_fixture.py` (TTL controller), `stream_reconnect_fixture.py` (uvicorn-subprocess fixture for mid-stream-kill tests). 19 self-tests pass green.
- **Story 1.1.1-3 (PR #262)** — `runs/run_adk_stability.py` drives `ken_e_agent` via `InMemorySessionService` + `Runner` (no HTTP, no auth-token mint). 50/50 invocations zero ADK / callback errors; config-cache hot-reload sentinel picked up; 12/12 org_context shapes (missing, empty, >10KB, malformed, unicode/emoji, deeply nested, etc.) merge cleanly. ACs 6.10–6.13.
- **Story 1.1.2-3 (PR #263)** — `runs/run_trace_compliance.py` drives 20+ corpus queries inside `TraceCapture`, validates every captured span via `app.adk.tracking.compliance.generate_compliance_report`, and emits per-op-name compliance breakdown. **85/85 spans compliant (100.0%) across 8 op_types**. Two real bugs fixed (see below). ACs 6.18–6.20.
- **Story 1.14.5 (PR #265)** — `runs/run_otel_stability.py` (probe + paired memory delta + GenAI span coverage + non-GenAI span presence). **Outcome B** confirmed — the OTEL `google-genai` Pydantic `model_dump()` crash is resolved on ADK 1.27.5; workaround line removed from `.env.development`, `.env.staging`, `.env.production`, and `app/adk/deploy_ken_e.py` in the same PR; spike doc closed. Memory delta +0.8% (well under 10%); GenAI span coverage 100% (39/39 spans carry `model_used` + `temperature`); non-GenAI DB + HTTP spans present. ACs 6.14–6.17.
- **Story 1.1.5-4 (PR #269)** — `runs/run_session_stability.py` with `--tests {1,2,3,4}`. Test 1 (2-hour sustained): 24/24 invocations, 0 errors, RSS 405 MB → 132 MB (delta_pct **-67.4%**). Test 2 (stream reconnect): live super-admin token + pre-created session → 2 chunks streamed → mid-stream kill → restart → follow-up returned HTTP 200. Test 3 (Redis TTL cycle): seed → expire → confirm absent. Test 4 (long session integrity): 25/25 invocations in single session, `_last_reasoning` set 25/25, `_previous_tool_calls` set 16/25, cache-expiry triggered. ACs 6.21–6.24.

### Real bugs fixed (uncovered by validation)

1. **Agent emitter — root span attributes never set on parent call.** `app/adk/tracking/callbacks.py:weave_before_agent_callback` was setting the `weave.attributes()` contextvar then calling `client.create_call(op="ken_e_agent")` without `attributes=`. The contextvar propagates to `@weave.op()`-decorated children, but is **not snapshotted onto a directly-created parent call**. Result: every `ken_e_agent` root span shipped without `account_id`, `session_id`, `agent_id`, `agent_version` — a permanent 0% compliance on the parent. Fix: pass `attributes=root_attrs` explicitly to `create_call(...)`.
2. **Harness — wrong patch point for span capture.** `weave_trace_capture.py` was patching `weave.trace.context.call_context.push_call`. Push happens *before* a call's attributes are materialised from the contextvar — so even though weave eventually serialises full attributes for the call, the harness was reading them too early and recording empty dicts. Children happened to have attrs at push time (different code path), masking the parent's emptiness. Fix: patch `WeaveClient.finish_call` instead.
3. **OTEL probe never closed (Sprint 5 latent inconsistency).** Sprint 5 commit `8360b02` (landed on `main`) re-enabled Agent Engine tracing AND commented out `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai` in `.env.development` + `deploy_ken_e.py` "to test if bug still triggers on ADK 1.26.0" — but the diagnostic was never run, and `.env.staging` + `.env.production` kept the workaround active. Dev was therefore inconsistent with staging/prod for ~2 months. PR #265 ran the probe (Outcome B, clean run on ADK 1.27.5) AND deleted the workaround line from all four files in the same PR, closing the inconsistency. The probe runner remains at `tests/integration/stability/runs/run_otel_stability.py` for re-validation on future ADK upgrades.
4. **OTEL stability subprocess pipe deadlock.** First Step 2 attempt used `subprocess.Popen(stdout=PIPE)` and never drained the pipe in the parent's psutil sampling loop. The OS pipe buffer (~64 KB on macOS) filled within seconds and wedged the child. Fix: per-run temp log file.
5. **Stream-reconnect fixture mismatch with KEN-E SSE contract.** `stream_reconnect_fixture.py` extracted `session_id` from an `X-Session-Id` response header. KEN-E's `/api/v1/chat/completions` streaming response is plain SSE (`data: <text>\n\n`) — no session_id is ever exposed back to the client. The fixture worked against the unit-test stub (which set the header) but failed against the real API. Fix: caller pre-creates the session via `POST /api/v1/chat/conversations` and passes the session_id into the fixture.

### Span metadata extension (callbacks.py)

`_build_chatbot_root_attrs` now surfaces `temperature` + `max_output_tokens` onto root-span attributes when the Firestore `agent_configs/ken_e_chatbot.generate_content_config` populates them. Sourced via a small extension to `get_current_config_metadata` in `config_loader.py`. The trace-spec marks these as `Required: No` for L2 spans, but Sprint 6 AC-6.15/6.16 demands 100% coverage.

### Documents affected

- `tests/integration/stability/` — five new `runs/run_*.py` driver scripts (one per validation story); `weave_trace_capture.py` rewritten; `stream_reconnect_fixture.py` API change; README updated with each driver.
- `app/adk/tracking/callbacks.py` — `attributes=root_attrs` passed to `create_call`; `temperature` + `max_output_tokens` surfaced.
- `app/adk/agents/strategy_agent/config_loader.py` — `get_current_config_metadata` returns `temperature` + `max_output_tokens`.
- `app/adk/.env.development`, `.env.staging`, `.env.production`, `app/adk/deploy_ken_e.py` — `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai` line deleted (PR #265).
- `docs/spike-otel-pydantic-findings.md` — Status → "Workaround removed"; Sprint 6 verification section added (PR #265).
- `pyproject.toml` already updated in PR #260 (psutil, redis, pytest-httpx as dev deps).

### Known gaps + follow-ups (filed for Sprint 7)

- **W&B Weave token-validation noise** — every LLM call emits `ValidationError: 2 validation errors for EndedCallSchemaForInsert` (`input_tokens=[]`/`output_tokens=[]`) as a background tracing-export error. Doesn't affect ADK/agent/span correctness; confirmed by ACs passing. Pinned around in `pyproject.toml` (`weave>=0.51.0,<0.51.57`).
- **AC-6.22 (stream reconnect) requires manual token mint** — fully validated against the live dev API but only when a super-admin Firebase Bearer is provided via `HARNESS_AUTH_TOKEN`. Not currently runnable in CI without infrastructure to mint a token from a service account.
- **Memory-delta variance at small sample sizes** — Step 2 of `run_otel_stability.py` requires `--memory-invocations 20` (or higher) to dilute Python's allocator noise. Five-invocation runs can show ±20% swings that aren't real.
- **`docs/sprint6-phase2-plan.md`** — execution notes appended in this commit; can be deleted after Sprint 6 closes per the plan's own closeout step.

---

## Review 32: AH-PRD-09 Approved — Per-Turn Dispatch Agent + Hybrid MCP (replaces AH-PRD-02's runtime model)

**Date:** 2026-05-22
**Scope:** Formal approval of [AH-PRD-09 — Per-Turn Dispatch Agent](components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) and the supporting [per-turn dispatch RFC](per-turn-dispatch-rfc.md). Replaces AH-PRD-02's deploy-time factory with a runtime resolver; introduces hybrid MCP via `McpServerKind` (`cloud_run` + `zapier`); coordinates a Skills SandboxPool addition (SK-PRD-02 scope expansion); pulls SK-PRDs 00/01/02 into Release 1.
**Participants:** Product Owner, Product Manager, Agentic Harness lead, Skills lead, Engineering review
**Status:** Approved as v2.1 of the RFC; PRD AH-PRD-09 filed; phase 0 (Zapier feasibility spike) scheduled as the immediate next step.

### Why this decision was needed

KEN-E's product requirement is that admin agent edits go live immediately — instructions, model, temperature, max output tokens, tools, and new specialists become callable in chat without an engineer in the loop. **[AH-PRD-02](components/agentic-harness/projects/AH-PRD-02-agent-factory.md) silently regressed this** when it shipped: the root-agent construction path switched from the legacy cache-backed `_make_instruction_provider` to the factory's `_make_factory_instruction_provider` (`app/adk/agents/agent_factory/builder.py:33`), which bakes the instruction text into a closure and never reads `config_cache`. The cache from Sprint 6 Decision B exists in code and is well-tested, but no caller on the live request path reads from it. The PUT endpoint at `api/src/kene_api/routers/agent_configs.py:300-310` already returns `redeploy required` warnings for `model` / `temperature` / `max_output_tokens`, but cannot warn for `instruction` because that was supposed to hot-reload — admins editing `instruction` get silent regression today.

This is recoverable, but not by a small patch: the factory is fundamentally a deploy-time builder, and even fixing the instruction path leaves `model`, `temperature`, `max_output_tokens`, `tools`, and **new specialist creation** as redeploy-bound. AH-PRD-09 ships the architectural fix.

### Decision

1. **Approved: Per-Turn Dispatch Agent (AH-PRD-09).** Deployed root becomes a thin dispatcher whose only tool is `delegate_to_specialist(name, query, acceptance_criteria=None)`. Specialists are resolved per turn from Firestore via a new `specialist_runtime` module (TTL + content-hash cache with per-key striped locking, LRU 256). `_REDEPLOY_REQUIRED_FIELDS` shrinks to the empty set for specialists; `MergedAgentConfig.warnings` marked `deprecated=true`. Admin agent edits propagate to the next chat turn within ~60 s without redeploy.

2. **Approved: Hybrid MCP via `McpServerKind`.** Open enum (`cloud_run` | `zapier`; future kinds welcome) on `mcp_servers/{server_id}.kind`. New `McpToolsetPool` (kind-specific keying, LRU + idle TTL + `aclose()`-on-eviction, 60 s background sweep). Long-tail integrations route through a single shared Zapier MCP connection per account; flagship integrations stay on owned Cloud Run servers. Existing `mcp_servers` docs default to `cloud_run` via migration.

3. **Approved: Six-phase rollout.** Phase 0 Zapier feasibility spike (hard gate for Phase 4) → Phase 1 cache-backed instruction wiring (independent, ships value first) → Phase 2 single-dispatch root + specialist runtime → Phase 3 `McpToolsetPool` + hybrid kinds → Phase 4 Zapier-backed Integrations → Phase 5 cleanup + rollout. Total scope ~7–10 engineering weeks; ~4–6 calendar weeks with two engineers from Phase 2 onward.

4. **Approved: R1/R3 release split with Phase 4 deferred to R2.** AH-PRD-09 lands in Release 1 (Foundation) — **Phases 0–3 + 5 only** (the `cloud_run`-only runtime resolver, per RFC §7.2 no-go-pivot shape). **Phase 4 (Zapier hybrid MCP) deferred to Release 2** alongside the Integrations component — cannot ship in R1 without cascading DM-PRD-07 → PR-PRD-01 → IN-PRDs 01/02/03 into Foundation. The `cloud_run`-only version of AH-PRD-09 is structurally complete and ships the product requirement; Zapier adds the long-tail integration scalability win when Integrations is live.

5. **Approved: SK-PRDs 00/01/02 moved R3 → R1.** AH-PRD-09 Phase 5 default-on is **gated on SK-PRD-02's `SandboxPool` shipping**. Without the pool, AH-PRD-09's per-turn `LlmAgent` rebuild would respawn the sandbox process every turn under the runtime resolver, dominating latency. The Skills runtime substrate (Sandbox Spike → Skills Backend → Agent Factory Skills Integration + SandboxPool) therefore lands in R1 alongside the runtime resolver. Skills authoring UI (SK-PRD-03), agent-builder controls (SK-PRD-04), and predefined-skill seed (SK-PRD-05) stay in R3 / Expertise.

6. **Approved: Skills SandboxPool option (a).** Pool by `(account_id, config_id)` (per-agent isolation; v2 escape valve to loosen to `account_id`-only if SK-PRD-00 cost findings show over-provisioning). Owned by Skills as an SK-PRD-02 scope expansion. Design pattern mirrors AH-PRD-09's `McpToolsetPool` (LRU + idle TTL + `aclose()`-on-eviction + per-key striped locks) for operational consistency. Hard coordination dep: must ship before AH-PRD-09 Phase 5 default-on. Rejected alternative (b): sandboxes pinned to `LlmAgent` instances and ride `agent_cache` reuse — simpler but couples sandbox cold-start to every config edit, a noticeable UX regression when admins iterate.

7. **Resolved (no AH-PRD-09 work needed): Strategy supervisor scope.** The 8 strategy-pipeline specialists (`business_*`, `competitive_*`, `marketing_*`, `brand_*` researcher/formatter pairs) are account-creation-only — invoked exactly once via `create_strategy_docs_supervisor.py` during onboarding, never via the runtime chatbot. [AH-PRD-07](components/agentic-harness/projects/AH-PRD-07-unify-strategy-agent-construction.md) (originally proposed to unify their construction with the factory) was **superseded by [AH-PRD-08](components/agentic-harness/projects/AH-PRD-08-hide-strategy-pipeline-specialists.md)** (shipped R1), which hides them from the chat picker via `visible_in_frontend=False` instead of rebuilding the construction path. AH-PRD-09's runtime resolver does not apply to these specialists; legacy `strategy_agent/config_loader.py` path stays unchanged. Reopen this decision only if a future "Refresh marketing strategy" UX makes them runtime-callable.

8. **Approved: Cross-component contract preservation.** Phase 2 ships **merge-blocker parity tests** for Chat (`SessionTurnAccumulator` token aggregation — CH-PRD-01 contract) and Billing (`extract_billable_tokens(event)` — BL-PRD-02 contract) — inner-Runner dispatch must preserve the event stream both consumers depend on. Phase 5 default-on is **cutover-gated on the MER-E eval suite passing** against the new trace shape (single `delegate_to_specialist` span replacing N `dispatch_to_*` spans; inner-Runner spans nested as L2 children). MER-E coordination plan: owner pairing named by end of Phase 0, contract diff document at start of Phase 2, rollback path defined.

### What this supersedes

| Prior decision / state | Disposition |
|---|---|
| AH-PRD-02 deploy-time factory model | **Superseded in the runtime path** by AH-PRD-09. AH-PRD-02 retains its narrative as "what shipped first"; it remains canonical for the deploy-time pieces AH-PRD-09 reuses (Pydantic models, `_make_header_provider`, `build_toolset_for_doc`, the agent-builder UI, the per-account overlay model). The runtime resolver is additive — AH-PRD-02 does not get deleted. Frontmatter supersession note added. |
| Sprint 6 Decision B (cache-backed instruction) regression | **Restored by Phase 1** of AH-PRD-09. `_make_factory_instruction_provider` rewired to read `config_cache.get_cached_config`; `config_cache.get_cached_config` decorated with `@safe_weave_op(name="load_config_from_firestore")` so MER-E's eval contract returns on every turn. |
| AH-PRD-07 (Unify Strategy-Agent Construction) Option A / Option B sequencing recommendation | **No-op for AH-PRD-09.** AH-PRD-07 superseded by AH-PRD-08 (per Review 31 era's planner update). Originally framed as a sequencing decision; resolved as "no coordination needed." |
| RFC §9.2 #8 default recommendation for sandbox lifecycle (option b — pin to `LlmAgent`) | **Reversed to option (a)** during review. Option (b) was the v2-conservative recommendation in the initial RFC draft; the Skills team flipped it to option (a) because sandbox cold-start on every config edit is an unacceptable UX regression. |
| `MergedAgentConfig.warnings: list[str]` API field | **Marked vestigial** in Phase 2 (always returned empty under the runtime model); scheduled for removal one release after Phase 5 rollout. |

### Documents updated

| File | Change |
|---|---|
| `docs/design/per-turn-dispatch-rfc.md` | **New** — full design RFC, drafted as v1 by Agentic Harness, revised to v2 + v2.1 during product/dev review. Captures cross-component contracts (§4.9), cache key shapes (§4.2.1), MER-E coordination plan (§9.1), Skills sandbox decision (§9.2 #8), and AH-PRD-06 PR-C interaction (§9.2 #9). |
| `docs/design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md` | **New** — 10-section PRD, ~310 lines. Captures phase-by-phase acceptance criteria (25 total), the Chat / Billing parity-test merge blockers, the SK-PRD-02 SandboxPool hard dep on Phase 5, and Phase 4's R2 deferral. RFC is the canonical design doc; PRD is the implementation contract. |
| `docs/design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md` | Added "Superseded by AH-PRD-09" frontmatter block; corrected stale `Status: Blocked` header to `Status: Shipped (R1) — superseded in the runtime path by AH-PRD-09`. AH-PRD-02 retains its narrative as "what shipped first." |
| `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md` | Amended with §4.6 `SandboxPool` design (process-wide pool, `(account_id, config_id)` key, LRU + idle TTL + `aclose()`-on-eviction + per-key striped locks), `_build_code_executor` delegated to the pool, four new acceptance criteria (#11–14), `test_sandbox_pool.py` unit + integration tests, AH-PRD-09 as downstream consumer in §3 + §10. Estimated effort bumped 5–7 → 6–9 days. |
| `docs/KEN-E-System-Architecture.md` | `[PLANNED]` forward-references added to §1.4 (Key Design Decisions row for per-turn dispatch), §4 (Agent Definitions bullet for AH-PRD-09), §5 (MCP Server Architecture bullet for hybrid kinds + runtime pooling). Per RFC §5, full rewrites ship phase-by-phase as AH-PRD-09 lands. |
| `docs/design/components/agentic-harness/README.md` | "Last Updated" → 2026-05-22; §1 Overview added `[PLANNED]` callout paragraph; §5 intro updated 7 → 9 PRDs with AH-PRD-08 (was missing) and AH-PRD-09; §5.1 dependency graph redrawn; §5.2 added AH-PRD-08 + AH-PRD-09 rows. |
| `docs/design/components/skills/README.md` | "Last Updated" → 2026-05-22; §1 Overview mentions SandboxPool + AH-PRD-09 coordination; §3.2 added AH-PRD-09 as downstream consumer; §5 intro added "Release sequencing — R1/R3 split" paragraph; §5.2 SK-PRD-02 row updated with SandboxPool + 6–9 day effort; §5.3 added fifth coordination point (SK-PRD-02 ↔ AH-PRD-09 Phase 5). |
| `docs/design/components/PROJECT-PLANNER.md` | R1 Foundation row expanded with AH-PRD-09 + SK-PRDs 00/01/02 rationale; R3 row updated (Skills 00–05 → Skills 03–05); new AH-PRD-09 project row added; SK-PRD-00/01/02 release column flipped R3 → R1 with explanatory notes; SK-PRD-02 description extended with SandboxPool and AH-PRD-09 as downstream consumer in the `wave` column. |

### Open follow-ups (filed for tracking)

1. **Phase 0 Zapier feasibility spike** — kick off immediately. Deliverables: `docs/spike-zapier-mcp-feasibility.md` with capability / auth / performance / cost / protocol findings + a go / no-go recommendation. Exit criteria documented in AH-PRD-09 §2 / RFC §7. Hard gate for Phase 4 work.
2. **MER-E lead pairing** — AH lead + MER-E lead identified by end of Phase 0 and named in the spike report alongside the Zapier go / no-go.
3. **AH-PRD-06 PR-C sequencing** — schedule to land before or alongside Phase 2 to avoid a merge conflict at `hierarchy.py:325` (per RFC §9.2 #9). PR-C ports the `default_global` function-tool injection into the runtime resolver.
4. **SK-PRD-02 SandboxPool track** — Skills team to begin work in parallel with AH-PRD-09 Phases 1–3 (SK-PRD-00 + SK-PRD-01 are prerequisites). Hard dep on AH-PRD-09 Phase 5 default-on.
5. **Phase 4 R2 commitment review** — at the start of R2 planning, re-confirm Phase 4 deferral vs. pulling Integrations sub-PRDs into R2's first wave to unblock the long-tail integration story.
6. **`MergedAgentConfig.warnings` field removal** — scheduled for one release after Phase 5 rollout (does not block Phase 5).
7. **Cache invalidation semantics — TTL vs hash invalidation** — RFC §9.2 #2 recommends TTL in v1 with hash invalidation as a fast-follow. Revisit if observed propagation latency causes admin pain.

### Risks acknowledged at approval

- **Zapier vendor risk** — Phase 0 spike is the gate; no-go pivots cleanly to `cloud_run`-only R1 (same architecture, smaller product win).
- **Cache invalidation correctness** — content-hash invalidation + integration tests covering "write then read" within the cache window. RFC §9.1.
- **ADK Runner internals under inner-Runner wiring** — ADK version pin in Phases 2–3; Runner contract documented in AH-PRD-09 §4.
- **MER-E contract drift** — concrete coordination plan in RFC §9.1 (owner pairing, contract diff, dev verification, cutover gate, rollback path). Phase 5 default-on cutover-gated on MER-E eval suite passing.
- **Chat / Billing event-topology drift** — Phase 2 parity tests as merge blockers; both consumers share `shared/token_accounting.py` per BL-PRD-02 / CH-PRD-01.

---

## Review 33: Multi-Tenant Migration Complete — Shape A → B Cutover (DM-PRD-00 through DM-PRD-06)

**Date:** 2026-05-25
**Scope:** Migration complete; all code on Shape B; staging cut over. No new code in this review entry — it captures the completion of the workstream defined in [Review 15](#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1).

### Summary

The Shape A → B multi-tenant data-model migration delivered end-to-end across six projects:

- **DM-PRD-00 (Migration Foundation)** — config-driven `migrate_to_shape_b.py` CLI, `MigrateConfig` registry, shared Firestore indexes (9 new entries), `seed_shape_b_fixtures.py`, and the Shape B convention section appended to `api/CLAUDE.md`.
- **DM-PRD-01 (Strategy Suite Migration)** — `strategy_docs`, `strategy_audit`, and `strategy_processing_state` moved from `strategy_docs_{account_id}/`, `strategy_audit_{account_id}/`, and `strategy_processing_state_{account_id}/` top-level collections to `accounts/{account_id}/strategy_docs/`, `accounts/{account_id}/strategy_audit/`, and `accounts/{account_id}/strategy_processing_state/` subcollections. Side-effect fix: the silently-broken `collection_group("strategy_audit")` query at `audit_service.py:189` works.
- **DM-PRD-02 (Analytics Suite Migration)** — `agent_analytics`, `cost_aggregations`, and `performance_profiles` moved to `accounts/{account_id}/` subcollections.
- **DM-PRD-03 (Shape D Split)** — the nested `accounts.{account_id}.account_settings.*` and `accounts.{account_id}.funnels.*` maps inside `organizations/{org_id}` docs extracted to per-account docs at `accounts/{account_id}`, eliminating the 1 MiB-per-document ceiling risk.
- **DM-PRD-04 (Shape B-like Collapse)** — `monitoring_topics/{account_id}` and `alert_configurations/{account_id}` (degenerate Shape B-like pattern) collapsed to `accounts/{account_id}/monitoring_topics/default` and `accounts/{account_id}/alert_configurations/default`.
- **DM-PRD-05 (Deletion Sweep Rewrite)** — the single-collection deletion sweep at `routers/accounts.py:968-997` replaced by `firestore.recursive_delete(db.collection("accounts").document(account_id))`; new `DELETE /api/v1/users/{user_id}` super-admin endpoint added via `user_deletion_service.delete_user_data(user_id)`.
- **DM-PRD-06 (Verification & Staging Cutover)** — Phase 6 dev verification (DM-56), codebase residue scan (DM-57), staging deploy (DM-58–DM-60), staging Phase 6 verification (DM-61), staging timing report (DM-62), and this documentation entry (DM-63).

**Net effect:** the data-shape surface area across the codebase dropped from **four distinct patterns** (Shape A top-level prefixed collections, Shape B account-scoped subcollections, Shape C global collections, Shape D nested org-doc maps) to **two** (Shape B + Shape C). `notifications` and `usage_records` are retained as Shape C per the carve-out in Review 15.

### Key outcomes

- Data-shape surface area: **four patterns → two** (Shape B account-scoped + Shape C global).
- **Latent Firestore orphan / GDPR gap closed for account-scoped subcollections** at `routers/accounts.py:968-997` — the old single-collection sweep that orphaned every per-account Firestore subcollection on deletion is replaced by `firestore.recursive_delete`, which covers the entire `accounts/{account_id}/` subtree transitively (DM-PRD-05). Shape C collections (`notifications`, `usage_records`), GCS blobs, Neo4j data, and third-party integration tokens are handled by their respective sweeps outside this migration.
- **Silently-broken cross-account audit query fixed** — `collection_group("strategy_audit")` at `audit_service.py:189` was always returning empty under Shape A. Now that `strategy_audit` lives as a subcollection under `accounts/{account_id}/`, the collection-group index fires correctly (DM-PRD-01).
- **Shape D nested-map risk eliminated** — `organizations/{org_id}` docs no longer hold a growing `accounts.{account_id}.*` nested map that would have hit the 1 MiB Firestore document limit at scale (DM-PRD-03).
- **Shape B-like degenerate pattern collapsed** — `monitoring_topics` and `alert_configurations` now follow the canonical `accounts/{account_id}/{resource}/default` path, removing the fourth ambiguous pattern (DM-PRD-04).
- **Shape C carve-out confirmed** — `notifications` and `usage_records` deliberately retained as Shape C; verified by the DM-57 residue scan and the DM-56/DM-61 checklist items.

### Consequences

- Downstream components (`Project Tasks`, `Automations`, `Skills`, `Knowledge Graph`, `Integrations`, `SAR-E`, `Data Pipeline`, `Billing`, `Chat`) may rely on the Shape B convention without conditional fallbacks.
- All **new** account-scoped Firestore resources must land directly under `accounts/{account_id}/{resource}/...` — no Shape A intermediate stop is permitted (enforced by code review and the `MigrateConfig` registry).
- The `multi-tenant-data-model-research-brief.md` and `multi-tenant-data-model-research-findings.md` docs in `docs/design/` remain in place as historical archive.
- Per-account user-deletion now follows `delete_user_data(user_id)` → collection-group `members` sweep → IN-PRD-05 `on_user_removed` hook per affected account → `recursive_delete(users/{user_id})`. The `USER_SUBCOLLECTIONS` registry in `user_deletion_service.py` is the extension point for future consumer PRDs.

### Cross-references

- **Review 15** — [Multi-Tenant Data Model Shape — Firestore Subcollections (Shape B) + GCS Prefix (G1)](#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1): the original decision that defined the target layout and kicked off this workstream.
- **Migration plan §11 — Execution checklist** — [`docs/design/components/data-management/multi-tenant-migration-plan.md` §11](components/data-management/multi-tenant-migration-plan.md#11-execution-checklist): all checkboxes will be filled once DM-64 lands (in lockstep with this entry).
- **Staging migration timing report (DM-62)** — [`docs/design/components/data-management/runs/DM-62-staging-migration-timing-report.md`](components/data-management/runs/DM-62-staging-migration-timing-report.md): 27 source docs across 3 resources (`alert_configurations` 14, `monitoring_topics` 3, `strategy_docs` 10) in the `(default)` Firestore DB; effective throughput 0.29–0.38 docs/sec, well below the 500 writes/sec batch ceiling; `analytics` DB was a structural no-op (0 source docs). Full methodology and per-resource breakdown in the report.

### Documents updated

| File | Change |
|------|--------|
| `docs/design/DESIGN-REVIEW-LOG.md` | This entry (Review 33). |
| `docs/design/components/data-management/README.md` | Status table — DM-PRD-00 through DM-PRD-06 flipped to Complete (DM-65, landing in lockstep). |
| `docs/design/components/data-management/multi-tenant-migration-plan.md` | §11 Execution checklist — all checkboxes to be filled by DM-64 (landing in lockstep). |

---

## Review 34 — AH-PRD-09 Trace Shape Change: delegate_to_specialist Span

**Date:** 2026-05-27
**Scope:** Agentic Harness — AH-67 (Phase 5, MER-E coordination + eval suite cutover gate)

### Summary

AH-PRD-09 (Per-Turn Dispatch Agent) changes the Weave trace shape observed by MER-E.
Previously, the deploy-time agent factory (AH-PRD-02) emitted N distinct
`dispatch_to_<specialist_name>` spans — one per registered specialist function called
in a turn.  The per-turn dispatch model emits a single `delegate_to_specialist` span
with a `specialist_run` child, regardless of which specialist is invoked.

This review entry captures the contract change and the decisions made in AH-67.

### Key decisions

1. **`specialist_name` and `cache_hit` on the outer span** — attributes are written to
   `delegate_to_specialist` (not `specialist_run`) so MER-E extractors can read them
   without drilling into sub-spans.  Follows the `set_pipeline_attrs` pattern in
   `review_pipeline_tracing.py`.

2. **`mcp_pool_hit` deferred to AH-62** — the attribute is documented and a `TODO(AH-62)`
   placeholder is in `set_delegate_attrs`, but the value is not yet written.  The fixture
   asserts its absence so MER-E tooling doesn't prematurely depend on it.

3. **`resolve_agent_with_hit` pre-resolution approach** — `delegate_to_specialist` calls
   `resolve_agent_with_hit` before calling `run` to observe the LRU cache hit/miss flag
   without changing `run`'s return signature.  The double-resolution cost is one
   TTL-cached dict lookup (negligible).

4. **Cutover gate** — Phase 5 default-on flip is gated on MER-E written sign-off that
   their eval suite passes against the new trace shape.  The canonical fixture at
   `app/adk/tracking/tests/fixtures/delegate_to_specialist_trace.json` is the validation
   target.

### Consequences

- MER-E extractors that match `span["name"].startswith("dispatch_to_")` will stop
  firing after the Phase 5 flag flip.  Must be updated before the flip.
- `acceptance_criteria`, `exit_reason`, `total_iterations`, `output_key_prefix`
  attributes move from `dispatch_to_<specialist>` to `specialist_run` (one level deeper).
- The `review_loop_iteration` grandchild depth increases from 2 to 3.

### Documents updated

| File | Change |
|------|--------|
| `docs/trace-structure-spec.md` | Added §14 (AH-PRD-09 Per-Turn Dispatch) + §3.1 table row for `delegate_to_specialist` |
| `docs/design/DESIGN-REVIEW-LOG.md` | This entry (Review 34) |
| `docs/design/components/agentic-harness/projects/AH-PRD-09-trace-contract-diff.md` | New contract diff doc for MER-E extractor authors |

---

*Add new review entries above this line. Each entry should include: date, scope, summary of findings, and documents updated. Decision rationale lives in the Review itself — this log is the canonical record going forward.*
