# AH-PRD-04 — Data Visualization

**Status:** Blocked
**Owner team:** Core AI / Agent Platform
**Blocked by:** AH-PRD-01 (review-loop framework), AH-PRD-02 (agent factory), AH-PRD-03 (Google Analytics Specialist — E2E target)
**Parallel with:** UI-PRD-01/02 (design-system shell reused by the chart component), Automations / Project-Tasks / Knowledge-Graph projects (no overlap)
**Blocks:** Any future specialist PRD that produces charts (Google Ads, Meta Ads, HubSpot, Content Specialist) — they inherit `create_visualization()` through the factory's default function-tool roster
**Estimated effort:** 6 stories (originally Sprint 11, ≈ 50 story points). ≈ 5–7 days.

---

## 1. Context

Today KEN-E's agent system produces **text-only responses**. When the Google Analytics Specialist (AH-PRD-03) queries GA via MCP, the tool returns structured JSON (sessions, users, pageviews by date), but the LLM converts that JSON to prose — the structured data is lost before it reaches the user. For a marketing analytics product whose users expect charts, tables, and visual dashboards, this is a material gap.

This project introduces **Vega-Lite artifacts** as a first-class output type alongside text. Specialist agents produce chart specifications via a new `create_visualization()` function tool; the ADK session writes those artifacts to `response_artifacts`; the API extracts them and extends `ChatResponse` with an optional `artifacts` field; the frontend renders them inline in chat messages using the same `ArtifactRenderer` used on the Performance → Dashboards canvas, with a graceful-degradation fallback; and the review loop (AH-PRD-01) evaluates visualization quality alongside the text draft so that chart type, axis labels, and narrative consistency become verifiable acceptance criteria. After this project, a user asking "Show me traffic trends for the past week" receives an accurate chart-enhanced response verified by the review loop — the core analytics-with-visual-output capability.

The full design is captured in [`docs/design/data-visualization.md`](../data-visualization.md) (v1.1, April 2026). This PRD is the **execution plan** for that design: it maps each story to a concrete set of files, tests, and acceptance criteria, and stitches the capability onto the factory + review-loop foundation delivered by AH-PRD-01/02/03. The design doc remains the source of truth for the Vega-Lite schema, data-flow diagrams, and channel considerations; this PRD does not restate them.

## 2. Scope

This project covers Sprint 11's six stories (2.4-1 … 2.4-6) organized into two phases that match the sprint's own phasing.

### Phase 1 — Artifact pipeline (stories 2.4-1 … 2.4-4)

Ship the end-to-end artifact path without review-loop integration: agent can produce a chart, API can serialize it, frontend can render it.

- **2.4-1 Artifact model.** Pydantic `Artifact` + `ArtifactMetadata` models in a location importable from both `app/` and `api/`. Wraps a **Vega-Lite v6** spec with `chart_type_suggestion`, `title`, `data_source`, `description`. The `type` field is a `Literal["visualization"]` for this project; the frontend's artifact union also supports `"text" | "table" | "file"` (used by the dashboards surface) and is the authoritative enum.
- **2.4-2 `create_visualization()` function tool.** SDK function tool (not MCP) that parses the `data` / `encoding` JSON-string arguments, constructs a Vega-Lite v6 spec, wraps it in `Artifact`, and **appends** to `tool_context.state["response_artifacts"]` (multiple calls per turn accumulate). Returns a confirmation string including the title, chart type, and data-point count. Invalid JSON surfaces a clear error message — no unhandled exceptions. Factory attaches the tool to every specialist via the default function-tool roster established by AH-PRD-02. **Tool MUST NOT** set a `config` block on the spec or hardcode a `mark.color` — theme colors, typography, and gridline styling are applied by the frontend at render time so dark mode and user color overrides work.
- **2.4-3 `ChatResponse` extension.** Add `artifacts: list[Artifact] | None = None` (default `None`, not `[]`). The chat endpoint reads `session.state.get("response_artifacts")` after the agent run, populates the response, and clears the key so artifacts don't leak into the next turn. For SSE streaming, artifacts ship as a single atomic `artifacts` event after text streaming completes.
- **2.4-4 Frontend Vega-Lite rendering.** Already implemented on `main`: `src/app/components/dashboard/ArtifactRenderer.tsx` (react-vega 8 / Vega-Lite 6.4.2) is used by both the dashboards canvas and the chat `ChatArtifact` wrapper. Story 2.4-4 reduces to (a) threading `response.artifacts` into the chat message state, (b) rendering them via the existing `ArtifactRenderer`. Malformed specs already fall back to a collapsible raw-JSON block via `SpecFallback`; text content always renders regardless of chart rendering.

### Phase 2 — Review-loop integration & E2E (stories 2.4-5, 2.4-6)

Connect artifacts to the AH-PRD-01 review loop and validate the full chain.

- **2.4-5 Review loop artifact evaluation.** Extend the reviewer instruction template to include `{step_N_artifacts?}` (optional-suffix, parallel to the existing `{step_N_feedback?}` pattern — see `review-loop-implementation-plan.md` §3.1). Reviewer checks three aspects: (a) chart type matches data shape, (b) axes are labeled and title is meaningful, (c) text narrative references the chart accurately. Acceptance criteria may explicitly require visualizations (e.g., "Include a line chart showing daily sessions with labeled axes"); the reviewer rejects with feedback requesting a missing chart when required. Large Vega-Lite specs (> 1,000 embedded data rows) are summarized to metadata + sample points before entering the reviewer context, to cap token usage.
- **2.4-6 E2E tests.** End-to-end coverage of the full pipeline against the AH-PRD-03 Google Analytics Specialist. Scenarios: happy path ("Show me traffic trends" → line chart rendered inline), multiple artifacts in a single response, SSE streaming delivery order (text events then `artifacts` event), review-loop artifact approve / reject, malformed-spec graceful degradation, invalid-JSON input error handling.

### Out of scope

- **Firestore persistence of artifacts** — artifacts live in session state only; replay / history is deferred (see `data-visualization.md` §10 Q1).
- **CSV export from artifact data** — deferred (§10 Q2).
- **Slack / Voice channel rendering** — Web UI only. Slack server-side PNG rendering and voice verbal description are tracked by Release 5/6 (§9 channel-considerations table).
- **Migration of existing Recharts dashboard charts to the new renderer** — cosmetic, deferred (§10 Q4).
- **Changes to the GA MCP server or to any specialist's tool roster beyond adding `create_visualization()`** — the factory attaches the tool; specialist instructions include chart-type-selection guidance, but no specialist code changes.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | Reviewer instruction-template mechanism (the `{…?}` optional-suffix pattern) and `build_review_pipeline()` wrapping. Story 2.4-5 extends the reviewer template with `{step_N_artifacts?}`. | This component |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | Factory attaches `create_visualization()` to every specialist's function-tool roster. The tool lives alongside other SDK function tools in the factory's default set. | This component |
| **[AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md)** | GA Specialist is the E2E subject for story 2.4-6. The specialist's instruction is extended with chart-type-selection guidance (time series → line, categorical → bar, part-of-whole → arc, correlation → **point** [Vega-Lite mark; scatter in prose], cumulative → area — per `data-visualization.md` §4.3). | This component |
| `docs/design/components/agentic-harness/data-visualization.md` | Canonical design: artifact model (§3), tool signature and implementation (§4), data-flow diagram (§5), review-loop integration (§6), frontend rendering (§8). This PRD does not restate the design — it references sections. | `../data-visualization.md` |
| `docs/design/review-loop-implementation-plan.md` | §3.1 Building Block — reviewer template `{step_N_…?}` optional-suffix pattern that story 2.4-5 extends. | `../../../review-loop-implementation-plan.md` |
| Existing `ChatResponse` model | Extended additively in story 2.4-3. Current shape at `api/src/kene_api/models/` (exact path to be confirmed during implementation). | — |
| Frontend chart stack | Ships `react-vega` 8 (Vega-Lite 6.4.2) rendered by `src/app/components/dashboard/ArtifactRenderer.tsx`. Shared by dashboards and chat via `src/app/components/dashboard/TileSettingsPopover.tsx` (chart-type / color / data-labels). | `frontend/CLAUDE.md` |
| W&B Weave tracing | Reviewer artifact evaluation emits spans into the existing review-loop sub-span hierarchy; no new span types required. | `docs/trace-structure-spec.md` |

## 4. Data contract

No new Firestore collections or GCS buckets. All artifact state is in-memory session state plus the additive `ChatResponse` field.

### 4.1 Pydantic models (story 2.4-1)

```python
from typing import Literal

ChartType = Literal["bar", "line", "area", "point", "arc"]
# Note: Vega-Lite mark vocabulary. Use "point" (not "scatter"); "text" is
# reserved for the frontend's data-label layering transform.

ArtifactType = Literal["visualization", "text", "table", "file"]
# Chat backend only emits "visualization". Other types are produced by the
# workflow automation path (dashboards surface) and share the same renderer.

class ArtifactMetadata(BaseModel):
    chart_type_suggestion: ChartType
    title: str
    data_source: str                    # e.g., "google_analytics"; required
    description: str | None = None

class Artifact(BaseModel):
    type: ArtifactType = "visualization"
    spec: dict                          # Vega-Lite v6 JSON spec, data inline
    metadata: ArtifactMetadata
```

Models live in a shared location importable from both `app/` and `api/`. The Vega-Lite spec structure follows `data-visualization.md` §3.2 (`$schema`, `title`, `data.values` **inline — no data URLs**, `mark`, `encoding`). **Do not emit a `config` block** — the frontend applies theme, typography, palette, and gridline styling centrally.

### 4.2 `ChatResponse` extension (story 2.4-3)

```python
class ChatResponse(BaseModel):
    role: str
    content: str
    session_id: str | None = None
    artifacts: list[Artifact] | None = None   # NEW — default None, not []
```

`artifacts` defaults to `None` so old clients that don't parse the field continue to work unchanged.

### 4.3 Session state keys

| Key | Shape | Written by | Read by | Lifetime |
|-----|-------|-----------|---------|----------|
| `response_artifacts` | `list[Artifact]` | `create_visualization()` tool (append) | API chat endpoint (then cleared) | One turn |
| `step_N_artifacts` | `list[Artifact]` | Specialist worker inside a review loop (via the same tool, pipeline-prefixed) | Reviewer agent via `{step_N_artifacts?}` template | Pipeline run |

The `step_N_artifacts` naming parallels the existing `step_N_draft` / `step_N_feedback` convention (`review-loop-implementation-plan.md` §3.1), isolating concurrent pipelines.

### 4.4 Frontend render-time transforms (informational)

The renderer applies the following transforms after receiving the spec; backends should produce plain specs and let these run:

1. **Theme merge.** `config = { ...appTheme, ...colorOverride, ...spec.config }`. Spec `config` wins per-key, so omit it unless absolutely necessary.
2. **View override.** If the user picks a different chart type, `spec.mark` is swapped before embedding.
3. **Data labels.** If the user toggles labels on, the spec is wrapped in `{ layer: [<original>, { mark: "text", encoding: { ...encoding, text: encoding.y } }] }`. Skipped if the spec already has `layer`.
4. **Color override.** User-selected palette token is applied to `config.mark.color`, `config.bar.color`, etc.

## 5. Implementation outline

| Action | File | Story |
|--------|------|-------|
| Create | Shared-location `Artifact` + `ArtifactMetadata` + `ChartType`/`ArtifactType` Pydantic models (likely `app/utils/artifact_models.py` re-exported by `api/src/kene_api/models/`, to be confirmed during implementation) | 2.4-1 |
| Create | `app/adk/tools/function_tools/create_visualization.py` — SDK function tool; pure-function structure; **emits Vega-Lite v6 `$schema`; no `config` block; no hardcoded mark colors**; unit-tested | 2.4-2 |
| Modify | Agent-factory default function-tool roster (AH-PRD-02) — append `create_visualization()` so every specialist receives it | 2.4-2 |
| Modify | `api/src/kene_api/models/` — extend `ChatResponse` with `artifacts: list[Artifact] \| None = None` | 2.4-3 |
| Modify | `api/src/kene_api/routers/chat.py` — pop `response_artifacts` from session state after agent run; populate `ChatResponse.artifacts`; clear the key; emit atomic `artifacts` SSE event after text streaming completes | 2.4-3 |
| Modify | `frontend/src/app/components/ChatInterface.tsx` — thread `response.artifacts` into `Message.artifacts` and delegate to existing `ChatArtifact` / `ArtifactRenderer` (renderer + settings popover already exist on `main`) | 2.4-4 |
| Modify | `app/adk/agents/utils/review_pipeline.py` — reviewer instruction template gains `{step_N_artifacts?}` block; `build_review_pipeline()` plumbs `step_N_artifacts` from session state | 2.4-5 |
| Modify | Reviewer summarization helper — if a Vega-Lite spec contains > 1,000 rows in `data.values`, replace with metadata + first-N sample points before template injection | 2.4-5 |
| Modify | Google Analytics Specialist instruction (from AH-PRD-03) — add chart-type-selection guidance and instruct the specialist to call `create_visualization()` when the user asks for charts or when ACs require a visualization | 2.4-5 / 2.4-6 |
| Create | `app/adk/tools/function_tools/test_create_visualization.py` — unit tests (append behaviour, multi-call, invalid-JSON error, confirmation string shape, **$schema is v6, no config block emitted, chart_type in Vega-Lite mark vocabulary**) | 2.4-2 |
| Create | `app/adk/agents/utils/test_review_pipeline_artifacts.py` (or extension to existing test file) — reviewer template correctness, large-spec summarization threshold | 2.4-5 |
| Create | `api/tests/integration/test_chat_artifacts.py` — ChatResponse serialization with and without artifacts; SSE event ordering | 2.4-3 |
| Create | `app/adk/agents/tests/test_data_visualization_e2e.py` — end-to-end against the GA specialist; marked `@pytest.mark.llm` for live-model runs | 2.4-6 |

## 6. API contract

No new HTTP endpoints. Existing chat endpoint gains an additive response field and one new SSE event type.

### 6.1 Non-streaming response (existing `POST /api/v1/accounts/{account_id}/chat`)

```json
{
  "role": "assistant",
  "content": "Traffic increased 12% week-over-week. Here's the trend:",
  "session_id": "…",
  "artifacts": [
    {
      "type": "visualization",
      "spec": { "$schema": "https://vega.github.io/schema/vega-lite/v6.json", "...": "..." },
      "metadata": {
        "chart_type_suggestion": "line",
        "title": "Website Sessions — Last 7 Days",
        "data_source": "google_analytics",
        "description": "Daily session count from GA4"
      }
    }
  ]
}
```

`artifacts` is omitted (or `null`) when the agent produced no charts — old clients reading only `content` continue to work.

### 6.2 SSE streaming (atomic artifacts event)

```
event: message
data: {"content": "Traffic increased 12% week-over-week..."}

event: message
data: {"content": " Here's the trend:"}

event: artifacts
data: {"artifacts": [{"type": "visualization", "spec": {...}, "metadata": {...}}]}

event: done
data: {}
```

Vega-Lite specs must be complete to render, so artifacts are **not** streamed incrementally. The frontend begins rendering as soon as the `artifacts` event arrives.

## 7. Acceptance criteria

Mapped 1:1 to the nine sprint-level ACs from the original Sprint 11 plan (historical Notion page; archived).

1. **Artifact model.** `Artifact` and `ArtifactMetadata` Pydantic models are defined in a shared location importable from both `app/` and `api/`. `type` and `chart_type_suggestion` are `Literal` enums. The Vega-Lite spec structure (`$schema` = v6, `data.values` inline, `mark`, `encoding`) round-trips through JSON serialization.
2. **`create_visualization()` tool.** `create_visualization()` constructs valid Vega-Lite v6 specs, **appends** to `response_artifacts` (multiple calls accumulate; never overwrites), returns a human-readable confirmation string (title + chart type + data-point count), and handles invalid JSON input for `data` / `encoding` with a clear error message rather than an unhandled exception. Specs do not include a `config` block or hardcoded mark colors.
3. **`ChatResponse` artifacts.** `ChatResponse` includes an optional `artifacts: list[Artifact] | None` field (default `None`). The API extracts `response_artifacts` from session state after the agent run, populates the response, and clears the session-state key. Old clients that don't parse `artifacts` continue to work using only `content`.
4. **Frontend chart rendering.** Vega-Lite chart artifacts render inline below chat-message text through the existing `ArtifactRenderer`, with theme palette applied and the hover-reveal settings toolbar (chart type / color / data labels) available. Multiple artifacts render in list order. The text content always renders regardless of chart rendering outcome.
5. **Artifact evaluation.** When a specialist calls `create_visualization()` during a review loop, the reviewer instruction includes the artifact data via `{step_N_artifacts?}` and evaluates chart type, axis labels, title, and narrative consistency.
6. **Missing-visualization detection.** When acceptance criteria require a chart but the specialist produces text only, the reviewer rejects the draft with feedback requesting the missing visualization.
7. **Large-spec handling.** A Vega-Lite spec with more than 1,000 embedded `data.values` rows is summarized to metadata + sample data points in the reviewer context to cap token usage.
8. **End-to-end.** The full pipeline works against the GA specialist: agent calls `create_visualization()` → artifact in session state → API includes it in `ChatResponse` → SSE streams an atomic `artifacts` event → frontend renders the chart inline.
9. **Frontend graceful degradation.** Given a malformed Vega-Lite spec, the frontend's `SpecFallback` shows the raw JSON in a collapsible block with an error message; text content always renders regardless of chart rendering success.

## 8. Test plan

### Unit

- `create_visualization()` — happy path produces a Vega-Lite v6 spec matching the expected shape with no `config` block and no hardcoded mark color; two calls in one turn append (final `response_artifacts` length == 2); invalid `data` JSON returns an error string (no exception); confirmation string contains title, chart type, and `len(parsed_data)`; chart type is validated against the `ChartType` literal.
- `Artifact` / `ArtifactMetadata` — Pydantic round-trip; `artifacts=None` default on `ChatResponse`; serialization omits `artifacts` cleanly when unset (or emits `null`, matching existing Pydantic conventions); unknown `type` or `chart_type_suggestion` rejected.
- Reviewer template — `{step_N_artifacts?}` resolves to the injected artifact data when present and to an empty string when absent (parallel to `{step_N_feedback?}`).
- Large-spec summarization — spec with 1,001 rows is reduced to metadata + first-N sample points; spec with 999 rows is passed through unchanged (boundary test).

### Integration

- API — `ChatResponse` with and without artifacts serializes correctly; `response_artifacts` is cleared from session state after extraction (next turn sees no stale artifacts).
- SSE — event ordering is `message` (× N) → `artifacts` (× 1) → `done`; `artifacts` event payload is a complete, parseable JSON object.
- Review loop — specialist stub that emits a line-chart artifact passes when ACs require a line chart; same stub without the artifact is rejected with feedback requesting the missing visualization.

### Frontend component

- `ArtifactRenderer` / `ChatArtifact` — renders a valid v6 spec to a chart with theme palette applied; malformed spec falls back to a collapsible JSON block with an error; multiple artifacts render in list order; hover toolbar chart-type / color / data-label changes re-render without remounting.

### End-to-end (`@pytest.mark.llm`)

- "Show me traffic trends for the past week" against the GA specialist — specialist queries GA MCP, calls `create_visualization(chart_type="line", ...)`, `ChatResponse` contains the artifact, frontend renders the chart.
- Multiple artifacts per turn — prompt that elicits sessions chart + engagement chart; both appear in order.
- Review-loop approve / reject — AC requires a chart; specialist omits it → reviewer rejects; specialist adds it → reviewer approves.
- Malformed spec path — specialist is prompted to produce a spec with a bad `encoding`; frontend renders the collapsible fallback and the text still displays.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Vega-Lite specs with large embedded `data.values` blow the reviewer's token budget | Large-spec summarization threshold (> 1,000 rows) in story 2.4-5; metadata + sample points injected into the reviewer context. |
| Vega-Lite version drift (backend v5 / frontend v6) produces render warnings or breaks on removed features | Pin backend to v6 `$schema` (AC 1); CI test that emitted `$schema` matches the frontend's bundled `vega-lite` version. |
| Backend-provided `config` or hardcoded `mark.color` silently defeats app theme and user color overrides | Tool MUST NOT emit `config`; unit test asserts absence (AC 2). |
| Old clients fail when they encounter the new `artifacts` field | `artifacts` is optional with default `None`; SSE `artifacts` is a new event name — legacy clients listening only to `message` / `done` ignore it. Explicit regression test. |
| `response_artifacts` leaks across turns (stale chart shown on the next message) | API clears the session-state key after extraction (story 2.4-3). Integration test asserts the clear. |
| Specialist hallucinates data values in the `create_visualization()` call instead of using GA tool output | Review loop is the backstop; reviewer compares artifact data to the text narrative and rejects mismatches (AC 5, 6). |
| Token-cost inflation from artifact evaluation on every review iteration | Summarize large specs (AC 7); reviewer remains on `gemini-2.0-flash`; monitor via Weave (pattern established by AH-PRD-01). |

### Open questions

Carried over from `data-visualization.md` §10; resolve during implementation or deferred to a follow-up per the column:

- **Firestore persistence of artifacts** — needed for session replay / MER-E? Impact: medium. Resolve: follow-up project if replay becomes load-bearing.
- **CSV export from artifact data** — UX enhancement; defer.
- **Multiple artifacts per response — layout** — UX decision for story 2.4-4. Default to vertical stack in list order; revisit after first user feedback.
- **Artifact versioning** — pin Vega-Lite `$schema` to v6 (matches bundled `vega-lite` 6.4.2); revisit when `react-vega` upgrades.

## 10. Reference

- Canonical design: [`data-visualization.md`](../data-visualization.md) — §3 (Artifact model), §4 (`create_visualization`), §5 (data flow + `ChatResponse`), §6 (review-loop integration), §8 (frontend rendering), §10 (open questions).
- Parent plan: [`../../../review-loop-implementation-plan.md`](../../../review-loop-implementation-plan.md) §3.1 — reviewer template `{step_N_…?}` optional-suffix pattern that story 2.4-5 extends.
- Harness design: [`../../../KEN-E-System-Architecture.md`](../../../KEN-E-System-Architecture.md) §2.3.2 (Request flow), §4.4 (Specialist agents), §4.6 (Review loop pattern).
- Trace spec: [`../../../trace-structure-spec.md`](../../../trace-structure-spec.md) — no new span types; artifact evaluation rides the existing review-loop sub-span hierarchy.
- Upstream projects: [AH-PRD-01](./AH-PRD-01-review-loop-framework.md), [AH-PRD-02](./AH-PRD-02-agent-factory.md), [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md).
- Frontend renderer: `src/app/components/dashboard/ArtifactRenderer.tsx`, `src/app/components/dashboard/TileSettingsPopover.tsx`, `src/app/components/dashboard/artifactTypes.ts`.
- Notion (archival): [Sprint 11 — Data Visualization Tool](https://www.notion.so/KEN-E-Sprint-11-Data-Visualization-Tool-32930fd6530281cca478fa23ca3abae2) — original sprint plan with the six user stories (2.4-1 … 2.4-6).
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7; C-2, C-4, C-5, C-6, C-7; T-1, T-2, T-3, T-4, T-6; D-2.
