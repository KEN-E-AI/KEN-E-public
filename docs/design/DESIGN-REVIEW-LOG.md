# Design Review Log

This file tracks design review discussions, findings, decisions, and open questions as we iterate on the KEN-E agentic harness architecture. Each entry captures the context, analysis, and outcome so future sessions can build on prior work.

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
| `docs/KEN-E-Agentic-Harness-Design.md` | 912 | Root design doc — rewritten from 3,771 lines, fictional classes removed |
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

### 4. ADK Internals — Deep Dive

This was the most consequential part of the review. We traced the ADK source code on the latest `main` branch to verify claims about `McpToolset` behavior.

#### 4a. `get_tools()` Per-Turn Resolution

**Original doc claim:** "`McpToolset.get_tools()` called every LLM turn — tools are re-resolved fresh."

**What we found:** This is true and **intentional**. The ADK team explicitly confirmed on [issue #3237](https://github.com/google/adk-python/issues/3237) that `get_tools(readonly_context)` is designed for per-user permissions — different users should see different tools. Naive caching at the toolset level would break this security model.

**The bug (fixed in v1.26.0):** In ADK v1.16.0, a grounding metadata check in `base_llm_flow.py` called `agent.canonical_tools()` 3-4 times per LLM response (for `google_search_agent` detection). This caused `get_tools()` to fire 4-5x per response instead of 1x. The fix ([PR #3299](https://github.com/google/adk-python/pull/3299), [commit 8f3c3bf](https://github.com/google/adk-python/commit/8f3c3bfda5e14f6a37979ad3030d3f2bbc0ae1a8)) caches resolved tools on `invocation_context.canonical_tools_cache` — so `get_tools()` is called once per turn, not once per token.

**Our ADK version:** `google-adk==1.23.0` (floor `>=1.23.0`). The fix is in `1.26.0`. We're hitting the redundant calls bug.

**Action taken:** Added ADK version note and upgrade recommendation to `mcp-architecture.md`. Added open question about bumping to `>=1.26.0`.

#### 4b. Dynamic Tool Discovery — The Gap

**The question:** The v1.0 design had a `ToolDiscoveryAgent` that could search ~400 tools and load MCP servers on-demand mid-conversation. The v2.0 design replaced this with specialist routing (fixed tool sets per specialist, assembled at deploy time). Does this lose important capability?

**What we found:**

`get_tools()` re-queries *already-connected* MCP servers each turn. This means:
- **New tools on connected servers** — automatically visible next turn (no redeploy needed)
- **New MCP server connections mid-conversation** — NOT supported. `McpToolset` instances are set on the agent at construction time.
- **Cataloged-but-not-loaded tools** — NOT discoverable. The ToolRegistry has metadata for ~400 tools, but there's no mechanism for an agent to connect to a new MCP server based on ToolRegistry search results.

**Discussion:** We debated whether this is acceptable. The conclusion was that we cannot defer dynamic tool selection — a CMO's cross-domain queries ("compare Google Ads spend with HubSpot conversions") and the growing tool inventory make static per-specialist assignment insufficient.

#### 4c. The Solution: `tool_filter` + ToolRegistry

**What we found in ADK source:** `BaseToolset` (parent of `McpToolset`) accepts a `tool_filter` parameter that can be a callable `(tool, ctx) -> bool`. It's evaluated on every `get_tools()` call with the current `ReadonlyContext`. This is the ADK-native mechanism for dynamic, per-turn tool selection.

**Architecture we designed:**

```
Each LLM turn:
  1. Root agent interprets user intent, writes relevant tool categories to session state
  2. Dispatch to specialist agent
  3. Specialist's McpToolset.get_tools(ctx) fires
  4. tool_filter predicate checks ctx.state["relevant_tools"]
  5. Only matching tools exposed to LLM — others hidden from context
```

This preserves v1.0 capabilities:
- Semantic search across ~400 tools via ToolRegistry
- Per-turn tool selection (only relevant tools in context)
- Token budget awareness (fewer tools = fewer context tokens)

Does NOT preserve:
- Runtime MCP server connection/disconnection
- If an entirely new MCP server is added, it requires config update + redeploy

**Action taken:** Added Section 5a to `mcp-architecture.md`, updated `agent-hierarchy.md` Section 6 (ToolRegistry role) and Section 8 (Agent Factory), updated harness doc Section 4.3.

### 5. Other Findings

#### Voice Latency Gap
Current Agent Engine response time is ~7-13s. Voice requires <2s end-to-end. The docs don't address this gap. Voice would likely need a separate, more lightweight agent path or a different serving strategy. Not fixed in this review — flagged as an existing issue.

#### Cost Model
The ~$1.20/hour per meeting estimate for voice doesn't account for Recall.ai/Meeting BaaS pricing (can be $50-100+/month per bot seat). Infrastructure cost estimates in Section 9.2 are for "moderate usage" without defining what moderate means. Not fixed — noted for future refinement.

### 6. Architecture Gaps Identified

These are structural gaps in the design docs — areas where the happy-path architecture is described but important concerns are not addressed. None were fixed in this review; they are tracked here for future design work.

#### 6a. No Error Handling / Resilience Design

The docs describe what happens when everything works but not what happens when it doesn't. Missing:
- What happens when an MCP server is unreachable mid-conversation?
- What happens when a specialist agent times out?
- What happens when Firestore config is corrupt or unavailable at startup?
- Graceful degradation strategy (e.g., fall back to a subset of tools, inform the user, retry?)

**Recommendation:** Add a resilience section to the harness doc or create `docs/design/error-handling-resilience.md`.

#### 6b. No Security Model for MCP

The docs mention `header_provider` for per-user OAuth but don't describe the full token lifecycle. Missing:
- How are per-user OAuth tokens stored? (Secret Manager? Firestore? ADK session state?)
- How are tokens rotated when they expire?
- How are tokens scoped per-user in a multi-tenant system where one MCP server instance serves all accounts?
- What happens if a token is revoked?

This is critical for a system handling CMO ad account credentials (Google Ads, Meta Ads, HubSpot).

**Recommendation:** Create `docs/design/security-and-auth.md` covering OAuth token lifecycle, per-user credential scoping, Secret Manager integration, and token rotation strategy.

#### 6c. Missing Cost Model for Scaled Usage

Section 9.2 of the harness doc estimates ~$1,170/month for "moderate usage" but doesn't define what moderate means. With ~400 tools across 20-40 MCP servers per account:
- Token consumption per request could be dramatically higher than estimated
- Multiple specialist agent calls per user query multiply LLM costs
- MCP server SSE connections have infrastructure costs that scale per-account
- Voice channel at ~$1.20/hour doesn't account for Recall.ai/Meeting BaaS pricing ($50-100+/month per bot seat)

**Recommendation:** Define usage tiers (light/moderate/heavy) with concrete assumptions (users, requests/day, tools loaded, MCP servers active) and cost projections per tier.

#### 6d. Workflow Management (Section 7) Is Too Thin

The state machine diagram is fine but the section is missing:
- Persistence model — how are workflow states stored and recovered after crashes?
- Failure recovery — what happens when a workflow step fails mid-execution?
- Idempotency — how do we prevent duplicate execution on retry?
- n8n webhook callbacks — how do webhook results map back to workflow steps?

**Recommendation:** Create `docs/design/workflow-management.md` as a standalone design doc (like the other three). This needs design work before Sprint 8+ implementation.

#### 6e. No Rate Limiting / Quota Management

Marketing platform APIs have aggressive rate limits:
- Google Ads: 15,000 operations/day (basic access), vary by endpoint
- Meta Marketing API: Rate limits per ad account, sliding window
- HubSpot: 100-200 requests/10 seconds depending on plan

The specialist agents need awareness of these limits. Missing:
- Back-pressure mechanism when approaching rate limits
- Quota tracking per account/platform
- User-facing feedback when rate limited ("I can't query Google Ads right now, the daily quota is exhausted")
- Retry-after / exponential backoff strategy

**Recommendation:** Add rate limit awareness to the specialist agent design. This could be a `before_tool_callback` that checks quota state, or metadata on the MCP server config.

#### 6f. Agent Factory Design Is Vague

The agent factory is referenced multiple times as Sprint 5-6 but the actual assembly logic is not described:
- How does Firestore config map to `Agent` constructor parameters?
- How does the factory wire `tool_filter` predicates?
- Is assembly at deploy time, startup time, or session creation time?
- How is the factory tested? (Config validation, integration tests)
- Hot-reload vs. redeploy semantics — can config changes take effect without redeployment?

**Recommendation:** Create `docs/design/agent-factory.md` before Sprint 5-6 implementation begins.

#### 6g. UsageTracker Scalability Concern

The `UsageTracker` (`app/adk/tracking/usage.py`) writes one Firestore document per tool call to `tool_usage_events`. At moderate scale (~3,000 tool calls/day = ~90K docs/month), writes are cheap. However, `get_usage_aggregation()` scans all documents in a date range — at heavy scale (450K+ docs/month) this becomes slow and expensive.

The `DailyCostAggregation` model exists in `analytics_models.py` but no rollup job is implemented. Without pre-aggregated daily rollups, every dashboard/report query triggers a full collection scan.

**Recommendation:** Implement a daily rollup Cloud Function that aggregates per-account, per-tool metrics into summary documents. Query summaries for dashboards, raw events only for drill-down. Consider TTL policy on raw events (e.g., 90-day retention, roll up to summaries before deletion).

### 7. Documents Modified in This Review

| File | Changes |
|------|---------|
| `docs/design/mcp-architecture.md` | v1.0 → v1.1: Rewrote Section 2 (ADK internals) with version-specific behavior and issue references. Added Section 5a (tool_filter + ToolRegistry). Updated MCPServerManager disposition. Added open questions 4-6. Updated references. |
| `docs/design/agent-hierarchy.md` | v1.0 → v1.1: Rewrote Section 6 (ToolRegistry role) with tool_filter driver design. Updated Section 8 (Agent Factory) with limitations note. |
| `docs/design/api-gateway-multi-channel.md` | Fixed Deepgram STT latency: sub-200ms → sub-300ms. Added TTS TTFB specs. |
| `docs/KEN-E-Agentic-Harness-Design.md` | v2.0 → v2.1: Added sprint-3b dependency note. Rewrote Section 4.3 (Tool Discovery) with tool_filter architecture. Added glossary entries. Updated document history. |
| `docs/design/DESIGN-REVIEW-LOG.md` | Created — this file. |

### 8. Open Questions (Carried Forward)

1. **ADK version bump to `>=1.26.0`** — Needed for per-invocation tool caching fix. Should be low-risk but needs testing.
2. **`tool_filter` integration pattern** — Three options identified (InstructionProvider, root agent state write, specialist self-search). Needs prototyping before Sprint 5-6.
3. **Per-account MCP server sets** — If different accounts need different server configurations, the agent factory needs to assemble at session creation time, not just deploy time. Needs separate design work.
4. **Voice latency budget** — 7-13s Agent Engine response time is incompatible with <2s voice target. Needs mitigation strategy. Now noted in harness doc Section 9.2.
5. ~~**Workflow management design**~~ — **Addressed:** Expanded harness doc Section 7 with data model, persistence/recovery design, and n8n integration contract.
6. ~~**Error handling / resilience**~~ — **Addressed:** Added harness doc Section 10.1 documenting existing patterns and identifying circuit breaker gap.
7. ~~**MCP security model**~~ — **Addressed:** Added harness doc Section 10.2 documenting full OAuth lifecycle, credential storage, and identifying gaps (proactive refresh, KMS, cross-tenant isolation).
8. ~~**Rate limiting / quota management**~~ — **Addressed:** Added harness doc Section 10.3 documenting existing rate limiting and identifying per-platform quota management gap.
9. ~~**Agent factory detailed design**~~ — **Addressed:** Expanded `agent-hierarchy.md` Section 8 with assembly flow, config-to-constructor mapping, header provider factory, and limitations.
10. ~~**Cost model refinement**~~ — **Addressed:** Added usage tier definitions and moderate tier cost breakdown to harness doc Section 9.2. Flagged UsageTracker scalability concern (6g).
11. **UsageTracker scalability** — Pre-aggregated daily rollups needed before heavy scale. `DailyCostAggregation` model exists but no rollup job. (see 6g)
12. **KMS encryption migration** — `EncryptionService` uses Fernet in dev, KMS path is TODO. Must complete before production launch.
13. **Circuit breaker pattern** — No circuit breaker for MCP servers or Agent Engine. Needs design for cascading failure protection.

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

*Add new review entries above this line. Each entry should follow the same structure: date, scope, findings, actions taken, open questions.*
