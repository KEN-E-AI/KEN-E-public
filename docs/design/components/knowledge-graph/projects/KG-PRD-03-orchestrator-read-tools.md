# KG-PRD-03 — Orchestrator Read Tools (Hierarchical Context + Hybrid Search)

**Status:** Ready for development (after KG-PRDs 1 + 2 merge)
**Owner team:** Agent / ML
**Blocked by:** KG-PRD-01, KG-PRD-02
**Parallel with:** KG-PRD-05
**Estimated effort:** 4–5 days

---

## 1. Context

The KEN-E orchestrator agent today reads account context only at session start: `HierarchicalContextManager` loads a ~5k-token "executive summary" into the system prompt, then the agent is on its own. If the user asks about a topic that wasn't in the executive summary, the agent cannot drill into the KB — it must hallucinate or answer vaguely. Two previously-approved Sprint 7 stories ([1.1.6-1](https://www.notion.so/34230fd653028175bccadb3dfd3d581f), [1.1.6-2](https://www.notion.so/34230fd65302816ea2eeeec49aedd90e)) proposed on-demand section loading and per-entity drill-down tools; neither has shipped. This PRD delivers those, plus two new tools needed to support the `Observation` layer (KG-PRD-02) and semantic fallback for fuzzy queries.

Four complementary retrieval primitives; the orchestrator picks one per user question:

| Tool | Retrieval shape | Good for |
|---|---|---|
| `load_context_section(section)` | Bulk structured listing of one of 7 fixed domains | "Who are our competitors?" / "What do we sell?" |
| `load_document(entity_type, entity_id)` | Detail drill-down on one entity | "Tell me more about ProductCategory X" |
| `search_kb(query, node_types?, k=10)` | Semantic vector similarity | "Anything about usage-based pricing?" |
| `list_observations(subject?, valid_only=true)` | Long-tail conversational facts | "What did we learn about pricing last time?" |

All tools are **read-only**, account-scoped by `tool_context.state["account_id"]` (never by LLM-supplied argument), and wrapped with Weave tracing.

## 2. Scope

### In scope
- New module `app/adk/agents/shared_tools/kb_read_tools.py` with four FunctionTool wrappers.
- `load_context_section`: implement all 7 sections (products, icps, competitors, strategies, brand, performance, calendar) with account-scoped Cypher + formatted markdown output. Replaces the partial `load_section()` at `app/adk/agents/utils/context_loader.py:133` (which only handles `campaigns` with mock data).
- `load_document`: generic entity-detail loader that accepts any of the 28 registered node types + `Observation`.
- `search_kb`: query-embedding via `text-embedding-004`, Neo4j vector index lookup, result snippeting.
- `list_observations`: paginated observation filter over the Phase 2 layer.
- Tool registration on the root agent at `app/adk/agents/ken_e_agent.py:244`.
- Removal of the legacy keyword-detection path (`SECTION_KEYWORDS`, `should_load_section`) in `shared/context_utils.py` once the tools ship, per Design Decision 17.
- Unit tests per tool + an end-to-end integration test that exercises all four from a single agent invocation.

### Out of scope
- Write tools of any kind (KG-PRD-04 owns the session-end writer).
- Observation *creation* — tools only read.
- Changes to `HierarchicalContextManager` beyond decoupling `load_section` from the tool (the Level 1 executive summary still loads at session start as today).
- Artifact / screenshot search.
- Caching beyond request-scope (acceptable for v1 — revisit if latency becomes an issue).

## 3. Dependencies

- **KG-PRD-01:** `kb_vector_index`, `:KGNode` label, `kg_node_account_id` index.
- **KG-PRD-02:** `Observation` node type + `source_session_id` property (used by `list_observations`).
- **External:**
  - Google `text-embedding-004` (already used by `app/adk/agents/strategy_agent/embeddings.py`).
  - ADK `FunctionTool` + `tool_context` — pattern established by `search_company_news` at `app/adk/agents/ken_e_agent.py:210-226`.
- **Existing files to study:**
  - `app/adk/agents/ken_e_agent.py:210-244` — tool wrapping + registration pattern
  - `app/adk/agents/utils/context_loader.py` — `HierarchicalContextManager`, `ORG_CONTEXT_QUERY`, `load_section`
  - `app/adk/agents/utils/shared/context_utils.py` — `format_context_markdown`, `SECTION_KEYWORDS` (to remove)
  - `app/adk/agents/strategy_agent/embeddings.py` — embedding generation (reuse `EmbeddingGenerator`)
  - `api/src/kene_api/models/graph_models.py` — entity type / relationship mapping
  - `app/adk/tracking/callbacks.py` — Weave tracing helper (`@safe_weave_op`)

## 4. Data contract

All four tools take `tool_context: ToolContext | None = None` as the last parameter (ADK convention). `account_id` is pulled from `tool_context.state["account_id"]`. Any LLM-supplied `account_id` argument is ignored and an error emitted.

### `load_context_section`

```python
def load_context_section(
    section: Literal["products", "icps", "competitors", "strategies",
                     "brand", "performance", "calendar"],
    tool_context: ToolContext | None = None,
) -> str:
    """Load a domain section of the account knowledge graph as formatted markdown.

    Returns <= 10,000 tokens of readable markdown including entity identifiers
    that can be passed to load_document() for drill-down. Returns a concise
    error message listing valid sections if `section` is invalid."""
```

#### Section → Cypher mapping

The seven sections group related node types. The queries below are the **reference shapes** — each owning team must reconcile the relationship names against the live schema before implementing (the exploration found `BELONGS_TO`, `HAS_{PHASE}_STRATEGY`, `HAS_CAMPAIGN`, etc. — not the names in the original Sprint 7 story). Take the 7-section taxonomy as authoritative; adapt the Cypher to reality.

| Section | Node types to include | Traversal sketch |
|---|---|---|
| `products` | `ProductCategory`, `Product`, `ValueProposition` | Start from `Account`, traverse via whichever relationship currently connects Account → ProductCategory, then ProductCategory → Product, ProductCategory → ValueProposition |
| `icps` | `CustomerProfile` | Account → CustomerProfile (verify current relationship name) |
| `competitors` | `CompetitiveEnvironment`, `Competitor`, `CompetitorTactic`, `CompetitorStrength`, `CompetitorWeakness`, `SubstituteProduct` | Account → CompetitiveEnvironment → Competitor → (tactics / strengths / weaknesses / substitutes) |
| `strategies` | `Goal`, `Strength`, `Weakness`, `Opportunity`, `Risk`, `SWOTAnalysis` | Account → SWOTAnalysis → (strengths / weaknesses / opportunities / risks); Account → Goal |
| `brand` | `BrandIdentity`, `BrandPersonality`, `VoiceAndTone`, `ColorPalette`, `Typography`, `ImageStyle`, `MissionAndValues` | Account → BrandIdentity → all brand element types |
| `performance` | `Campaign`, `CampaignPerformance` (if modeled) | Account → Campaign → CampaignPerformance |
| `calendar` | `Campaign` filtered by date | Account → Campaign WHERE date range overlaps [now - 90d, now + 180d] |

Every section query MUST include `{account_id: $account_id}` in the traversal seed (the Account match). Defense-in-depth: after retrieving nodes, filter in Python to only return those where `node.account_id == account_id`.

#### Output format

Use `format_context_markdown()` (existing helper in `shared/context_utils.py`) — YAML frontmatter for metadata + markdown body with H2/H3 headings per entity type, each entity rendered as a small block:

```markdown
---
account_id: acc_abc123
section: competitors
generated_at: 2026-04-18T15:22:00Z
---

## Competitive Environment
<description from CompetitiveEnvironment hub node>

## Competitors

### Acme Corp
- **Identifier:** `competitor_acc_abc_xyz` *(use with `load_document` for details)*
- **Headquarters:** San Francisco, CA
- **Market share:** 18%

### Tactics (Acme Corp)
- **Aggressive pricing in SMB segment** (identifier: `tactic_acc_abc_aaa`)
- **Content marketing via blog** (identifier: `tactic_acc_abc_bbb`)

### ... (next competitor)
```

Token budget: **hard cap at 10,000 tokens** (measured via `tiktoken` or similar). If the raw content exceeds it, drop the lowest-priority entity types first (e.g. for `competitors`, drop `CompetitorWeakness` before `Competitor`). Never truncate mid-entity — that produces garbage identifiers.

Target latency: < 1 second per section for an account with up to 50 entities.

### `load_document`

```python
def load_document(
    entity_type: str,      # Any registered node type from NODE_TYPE_REGISTRY or "Observation"
    entity_id: str,        # The node_id
    tool_context: ToolContext | None = None,
) -> str:
    """Load the full properties + 1-hop neighbors of one entity as formatted markdown.

    Account-scoped: returns an error if the entity does not belong to the
    selected account."""
```

Cypher:
```cypher
MATCH (n {node_id: $entity_id, account_id: $account_id})
WHERE $entity_type IN labels(n)
OPTIONAL MATCH (n)-[r]-(neighbor)
  WHERE neighbor.account_id = $account_id OR 'Account' IN labels(neighbor)
RETURN n, collect({rel: type(r), dir: CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END,
                   neighbor: neighbor}) AS edges
```

Output: YAML frontmatter + markdown with the entity's properties listed, then a "Related entities" section listing each 1-hop neighbor with relationship direction + type + neighbor identifier. Cap at 8,000 tokens; truncate the neighbor list (not the entity properties) if needed.

Errors:
- Entity not found → 2-line markdown error `"No entity found: <type> <id> (may have been deleted or belong to another account)"`.
- `entity_type` not registered → error naming the valid types (up to 20 examples to keep the response small).

### `search_kb`

```python
def search_kb(
    query: str,
    node_types: list[str] | None = None,    # Filter by label; None = all :KGNode
    k: int = 10,
    tool_context: ToolContext | None = None,
) -> str:
    """Semantic similarity search over embedded KB content for the current account.

    Returns a ranked list of matches as markdown with node_id handles for
    drill-down via load_document()."""
```

Cypher:
```cypher
CALL db.index.vector.queryNodes('kb_vector_index', $k * 3, $query_embedding)
YIELD node, score
WHERE node.account_id = $account_id
  AND ($node_types IS NULL OR any(label IN labels(node) WHERE label IN $node_types))
  AND (node.valid_to IS NULL)                          // current facts only
RETURN node, score
ORDER BY score DESC
LIMIT $k
```

Why `$k * 3`: vector index returns pre-filter, so we overshoot and post-filter. If an account has many KGNodes, `k*3` is a reasonable headroom; tune if needed.

Query embedding uses `EmbeddingGenerator` (reuse from `app/adk/agents/strategy_agent/embeddings.py`) with task `"RETRIEVAL_QUERY"` (vs `"RETRIEVAL_DOCUMENT"` for stored embeddings — matching the existing writer's task is important).

Output format (markdown):
```markdown
## Search results for "usage-based pricing"

### [1] Observation · confidence=high · score=0.847
"The CMO mentioned they're pivoting to usage-based pricing next quarter."
- **Identifier:** `obs_acc_abc_aaa1` *(use with `load_document` for details)*
- **Observed in session:** `s_abc_xyz`
- **Recorded:** 2026-04-15

### [2] Product · score=0.712
Premium SaaS Tier — `prod_acc_abc_bbb2`
...
```

Cap results at 10 (even if `k > 10`); if more are requested, return 10 + a note. Include the score to help the agent judge relevance ("the top result had score 0.4 — no strong match").

### `list_observations`

```python
def list_observations(
    subject: str | None = None,
    valid_only: bool = True,
    limit: int = 20,
    tool_context: ToolContext | None = None,
) -> str:
    """List Observation nodes for the account, optionally filtered by subject
    (case-insensitive substring match). Defaults to valid (non-superseded)
    observations only."""
```

Cypher:
```cypher
MATCH (o:Observation {account_id: $account_id})
WHERE ($subject IS NULL OR toLower(o.subject) CONTAINS toLower($subject))
  AND ($valid_only = false OR o.valid_to IS NULL)
OPTIONAL MATCH (o)-[:ABOUT]->(target)
RETURN o, target
ORDER BY o.created_time DESC
LIMIT $limit
```

Output: markdown list grouped by subject, most recent first, with `node_id` handles.

### Tool registration

Register all four tools on the root agent via `FunctionTool` wrapping — same pattern as `search_company_news` at `app/adk/agents/ken_e_agent.py:210-244`. Each tool wrapped with `@safe_weave_op(name="kb.load_context_section")` etc.

Root instruction additions (small — the tools' docstrings carry most of the guidance):

```
## Knowledge base access

You have four read-only tools for the current account's knowledge graph:

- `load_context_section(section)` — bulk load one of: products, icps,
  competitors, strategies, brand, performance, calendar. Use when the user
  asks about a whole domain ("Tell me about our competitors").

- `load_document(entity_type, entity_id)` — drill into one entity. Use after
  identifying a `node_id` from one of the other tools.

- `search_kb(query, node_types?, k=10)` — semantic search. Use for fuzzy or
  cross-cutting questions where you don't know the exact node type
  ("Anything about pricing?").

- `list_observations(subject?, valid_only=true)` — long-tail facts surfaced in
  past conversations. Use when the user asks "what did we say about X?"
  or "what did we decide?".

Start with load_context_section when the question is about a whole domain.
Fall back to search_kb when the question is fuzzy or cross-domain.
Use load_document only after you have a node_id.
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `app/adk/agents/shared_tools/__init__.py` |
| Create | `app/adk/agents/shared_tools/kb_read_tools.py` |
| Create | `app/adk/agents/shared_tools/kb_formatting.py` — markdown renderers shared across tools |
| Create | `app/adk/agents/shared_tools/kb_cypher.py` — section Cypher queries, centralized for testability |
| Modify | `app/adk/agents/ken_e_agent.py` — register four new tools in the `tools=[]` list at line 244; small instruction update |
| Modify | `app/adk/agents/utils/context_loader.py` — `load_section()` delegates to `load_context_section` under the hood, or is removed if callers switch to the tool directly |
| Modify | `app/adk/agents/utils/shared/context_utils.py` — remove `SECTION_KEYWORDS` and `should_load_section()` (dead code per Design Decision 17) |
| Create | `app/adk/agents/shared_tools/test_kb_read_tools.py` (unit) |
| Create | `app/adk/agents/shared_tools/test_kb_cypher.py` (unit; query builder tests) |
| Create | `tests/integration/test_orchestrator_kb_tools.py` — end-to-end chat turns |
| Create | `tests/integration/test_kb_tools_multi_tenant.py` — cross-account isolation for all four tools |

### Embedding reuse

Import `EmbeddingGenerator` from `app/adk/agents/strategy_agent/embeddings.py`. Create one module-level instance (thread-safe per the ADK patterns); call `.generate_query_embedding(query)` inside `search_kb`. Measure p95 latency — `text-embedding-004` typically < 200ms.

### Section registry

Centralize the seven sections + their node types + their Cypher in one place:

```python
# app/adk/agents/shared_tools/kb_cypher.py
SECTION_SPECS: dict[str, SectionSpec] = {
    "products": SectionSpec(
        node_types=["ProductCategory", "Product", "ValueProposition"],
        cypher="MATCH (a:Account {account_id: $account_id}) ... RETURN ...",
        token_priority=["ProductCategory", "Product", "ValueProposition"],
        # when over budget, drop lower-priority types first
    ),
    ...
}
```

Makes it easy to test each section's Cypher in isolation and add sections later without touching the tool function.

### Multi-tenancy guard

In each tool wrapper's first line:

```python
account_id = tool_context.state.get("account_id") if tool_context else None
if not account_id:
    return "Error: no account selected in session state."
# IMPORTANT: ignore any LLM-supplied account_id argument.
```

Tool function signatures do **not** include `account_id` as a parameter — the LLM cannot pass one. Any attempt would surface as an unknown kwarg error.

## 6. API contract

No HTTP endpoints. Tools are called by the ADK runtime on the agent's behalf.

## 7. Acceptance criteria

1. Chat turn: user asks "who are our competitors?" → agent calls `load_context_section("competitors")` → response is well-formed markdown covering `CompetitiveEnvironment` + all `Competitor` entities (plus their tactics / strengths / weaknesses / substitutes) for the selected account, < 1 second, within the 10k-token budget.
2. Each of the 7 section names returns a valid markdown response against an account with representative data. An unknown section name returns an error listing the valid options.
3. `load_document("Competitor", "competitor_acc_abc_xyz")` returns full properties + 1-hop neighbors (tactics, strengths, weaknesses). Unknown `entity_type` returns a clear error. `entity_id` not found returns a clear error.
4. `search_kb("usage-based pricing")` against an account that has one matching Observation returns that Observation as the top result with score > 0.7 (qualitative — the exact score depends on the embedding model, but it should clearly lead).
5. `search_kb` filtered by `node_types=["Product"]` excludes Observations even when an Observation is semantically closer.
6. `search_kb` returns 0 results with a helpful message when the account has no embedded content (e.g. fresh account with embeddings still running).
7. `list_observations()` returns the 20 most recent valid Observations; `list_observations(subject="pricing")` filters by subject substring; `valid_only=false` includes superseded Observations.
8. **Multi-tenant isolation:** with two accounts A and B each carrying distinct content, every tool called with session state `account_id=A` returns zero rows / entities belonging to B. Verified in `test_kb_tools_multi_tenant.py` for all four tools and all combinations of filter arguments.
9. An LLM that attempts to pass `account_id="otheracc"` as a tool argument gets rejected (unknown kwarg) rather than silently honored.
10. Each tool call appears as a distinct Weave span with `account_id` attribute and the tool name.
11. Removing `SECTION_KEYWORDS` / `should_load_section` does not break any existing test.
12. End-to-end chat (`test_orchestrator_kb_tools.py`): a three-turn conversation exercising all four tools completes without errors and each tool's output surfaces back into the final response.

## 8. Test plan

**Unit tests** (`test_kb_read_tools.py`, `test_kb_cypher.py`):
- Each section's Cypher (from `SECTION_SPECS`) parses as valid Cypher (send to Neo4j with `EXPLAIN`).
- Token budget enforcement: build a mock section with enough entities to exceed 10k → verify the lowest-priority type is dropped first.
- Markdown rendering: a seeded set of 5 competitors renders with the expected structure and identifiers.
- `search_kb`: mock `EmbeddingGenerator` + mock Neo4j → verify the emitted Cypher and the post-filter logic.
- `list_observations`: filter combinations produce the right Cypher params.
- Multi-tenancy guard: tool called without `account_id` in state → returns the error message.

**Integration tests** (`test_orchestrator_kb_tools.py`, `test_kb_tools_multi_tenant.py`):
- Seed fixture account with 20 strategy nodes across types + 5 Observations (some superseded).
- Call each tool via the ADK runtime with a crafted prompt; assert expected content in the response.
- Cross-account test: seed two accounts; call every tool with account A's state; assert no account-B content ever surfaces.
- Weave tracing: assert spans are emitted with correct attributes (mock Weave or read from the test tracer).

**Performance check (smoke):**
- `load_context_section("competitors")` on a populated account: p95 < 1s.
- `search_kb`: p95 < 1.5s end-to-end (including embedding generation).

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Section queries reference relationships that don't match the live schema | The 1.1.6-1 story named relationships (`HAS_COMPETITIVE_ENVIRONMENT` etc.) that don't match current data. Owning team must spot-check a populated account and adjust each Cypher query before implementation. Budget a half-day for reconciliation. |
| Section token budget overruns on large accounts | Enforce the 10k cap with a truncation strategy that preserves completeness at the entity level (drop a whole type, not a partial entity). Document which types drop first per section. |
| Vector index returns stale results when an Observation is created without waiting for embedding generation | Acceptable for v1: if an Observation has `embedding = null`, it is not returned by `search_kb`. `list_observations` is the fallback. Document for the agent. |
| LLM attempts to call `search_kb(query, account_id="…")` | Python raises `TypeError` on unknown kwarg; ADK should surface that to the LLM as a tool error. Confirm. |
| Tool calls inflate conversation context during a long chat | Each response is <= 10k tokens; 3–4 tool calls per turn is the realistic upper bound. ADK's summarizer handles it. If it becomes a problem, cap turns-per-tool-call. |
| Ordering drift — `search_kb` score threshold not well-tuned | Return scores verbatim; let the agent decide what to trust. Do not silently drop results below a threshold. |
| Removing `SECTION_KEYWORDS` breaks a dependency we missed | Grep for imports before removal. If any live caller exists, leave the file but mark its functions as deprecated and add a pending-deletion story. |

## 10. Reference

- Notion: [Story 1.1.6-1](https://www.notion.so/34230fd653028175bccadb3dfd3d581f), [Story 1.1.6-2](https://www.notion.so/34230fd65302816ea2eeeec49aedd90e) — these cover `load_context_section` and `load_document`.
- Notion: Design Decision 17 — agent-driven context loading supersedes keyword detection.
- Harness design: `docs/KEN-E-System-Architecture.md` §3.2 (Hierarchical Context Loading).
- Parent plan: [`the-purpose-of-neo4j-clever-frost.md`](../../../../../Users/kenwilliams/.claude/plans/the-purpose-of-neo4j-clever-frost.md) §Phase 3.
- Pattern files: `app/adk/agents/ken_e_agent.py:210-244`, `app/adk/agents/utils/context_loader.py`.
- CLAUDE.md rules in scope: C-1, C-2, C-4, C-7; PY-1, PY-3, PY-7; T-1, T-3, T-4, T-6.
