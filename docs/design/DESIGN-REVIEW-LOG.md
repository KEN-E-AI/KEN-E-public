# Design Review Log

Hybrid decision log and document changelog. Tracks what changed in the design docs, when, and why. For full decision rationale, see the [Design Decisions database in Notion](https://www.notion.so/2f230fd6530280d599f0ca1449111d7e).

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
| `docs/design/components/automations/projects/01-data-model-and-api.md` | Firestore layout block rewritten; composite-index block updated to `accounts/*/project_plans` + `accounts/*/plan_runs` collection scope; Notion callout added. |
| `docs/design/components/automations/projects/03-task-artifact-system.md` | `plan_runs_{account_id}` → `accounts/{account_id}/plan_runs` in Dependencies + AC #3; Notion callout added. |
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

## Review 20: Sprint 6 — Firestore Config Registry Delivered (Feature 1.1.4)

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

Sprint 6 Phase 2 (stability validation stories 1.1.1-3, 1.14.5, 1.1.2-3, 1.1.5-4) remains Backlog; those stories share the proposed `tests/integration/sprint6_harness/` infrastructure, not yet built.

---

*Add new review entries above this line. Each entry should include: date, scope, summary of findings, documents updated, and a link to the corresponding Notion Design Decision(s).*
