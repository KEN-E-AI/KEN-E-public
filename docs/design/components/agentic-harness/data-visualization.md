# Data Visualization & Artifacts

**Version:** 1.1
**Date:** April 2026
**Status:** [IN PROGRESS] — design contract captured in `docs/figma-export/src/app/components/dashboard/`; production frontend renderer to be delivered by Dashboards (DB-PRD-03 `VisualizationWidget`) + Chat (CH-PRD-02) and consumed/extended by AH-PRD-04. Backend pipeline pending.

**Changes from v1.0 (March 2026):**
- Bumped Vega-Lite schema target from **v5 → v6** to match the Figma-export reference (`react-vega` 8 / `vega-lite` 6.4.2). The production frontend currently ships `recharts`; the Vega-Lite renderer is delivered by Dashboards / Chat sibling PRDs (see DB-PRD-03 / CH-PRD-02).
- Normalized `chart_type_suggestion` to the Vega-Lite mark vocabulary (`point` replaces `scatter`; `text` reserved for frontend layering).
- Formalized the artifact `type` union (`visualization | text | table | file`) — chat emits only `visualization`, the dashboards surface emits the others.
- Forbade backend-emitted `spec.config` blocks and hardcoded mark colors — theme + user color overrides are applied by the frontend.
- Required inline `spec.data.values` (no data URLs).
- Documented frontend render-time transforms (theme merge, mark swap, data-label layering, color override).
- Added dashboards surface reference (same renderer, different data source).

---

## 1. Overview


### Problem

KEN-E's agent system produces **text-only responses**. When a specialist agent queries Google Analytics via MCP, the tool returns structured JSON (sessions, users, pageviews by date), but the LLM converts this to prose — the structured data is lost. For a marketing analytics product where CMOs expect charts, tables, and visual dashboards, this is a significant gap.

### Solution

Introduce **Vega-Lite artifacts** as a first-class output type alongside text. Specialist agents **and the root coordinator (`ken_e`)** produce chart specifications via a `create_visualization()` function tool, and the API delivers these artifacts to the frontend for rendering. The `ChatResponse` model is extended with an optional `artifacts` field — old clients that don't understand artifacts continue to work unchanged.

The same `ArtifactRenderer` powers both the chat surface and the Performance → Dashboards canvas (workflow-output artifacts), so visualizations are consistent across the product.

### Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| **Vega-Lite v6** as the visualization spec format | Declarative, JSON-based, well-supported ecosystem, separates data from presentation. Version matches `react-vega` bundled in the app. |
| **Agent suggests chart type, frontend can override** | Agent has data context to suggest appropriate chart type; frontend has UX context to override (the hover settings toolbar lets users change chart type, color, and data labels per artifact). |
| **Additive `ChatResponse` extension** | `content: str` unchanged; new `artifacts: list[Artifact] \| None` field is backward-compatible |
| **Frontend owns theme and interactivity** | Backend emits plain specs with inline data; frontend applies app palette, typography, data labels, and user color overrides at render time. |
| **Review loop evaluates visualization quality** | Reviewer evaluates artifacts alongside text draft — acceptance criteria can require specific visualizations |

---

## 2. Design Decisions

| # | Decision | Link |
|---|----------|------|
| 1 | Vega-Lite **v6** as visualization spec format | *DESIGN-REVIEW-LOG entry pending — captured when AH-PRD-04 implementation begins* |
| 2 | Agent suggests chart type, frontend can override (and persist the override per-placement on the dashboards surface) | *DESIGN-REVIEW-LOG entry pending* |
| 3 | Additive ChatResponse extension (backward-compatible) | *DESIGN-REVIEW-LOG entry pending* |
| 4 | Review loop evaluates visualization quality | *DESIGN-REVIEW-LOG entry pending* |
| 5 | Backend emits plain specs; theme, color overrides, and data labels applied by the frontend | *DESIGN-REVIEW-LOG entry pending* |

> Decisions will be recorded as Review entries in [`docs/design/DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) when AH-PRD-04 implementation begins.

---

## 3. Artifact Model

### 3.1 Artifact Type Definition

```python
from typing import Literal
from pydantic import BaseModel

# Vega-Lite mark vocabulary. Use "point" (not "scatter"); "text" is reserved
# for the frontend's data-label layering transform.
ChartType = Literal["bar", "line", "area", "point", "arc"]

# Chat backend emits only "visualization". Other types are produced by the
# workflow automation path (dashboards surface) and share the same renderer.
ArtifactType = Literal["visualization", "text", "table", "file"]

class ArtifactMetadata(BaseModel):
    chart_type_suggestion: ChartType
    title: str                          # Human-readable chart title
    data_source: str                    # e.g., "google_analytics", "meta_ads"; required
    description: str | None = None      # Optional natural-language description of what the chart shows

class Artifact(BaseModel):
    type: ArtifactType = "visualization"
    spec: dict                          # Vega-Lite v6 JSON specification, data inline
    metadata: ArtifactMetadata
```

### 3.2 Example Artifact

A full Vega-Lite v6 spec for a line chart of website sessions over time:

```json
{
  "type": "visualization",
  "spec": {
    "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
    "title": "Website Sessions — Last 7 Days",
    "data": {
      "values": [
        {"date": "2026-03-11", "sessions": 1247},
        {"date": "2026-03-12", "sessions": 1389},
        {"date": "2026-03-13", "sessions": 1156},
        {"date": "2026-03-14", "sessions": 1423},
        {"date": "2026-03-15", "sessions": 982},
        {"date": "2026-03-16", "sessions": 874},
        {"date": "2026-03-17", "sessions": 1302}
      ]
    },
    "mark": "line",
    "encoding": {
      "x": {"field": "date", "type": "temporal", "title": "Date"},
      "y": {"field": "sessions", "type": "quantitative", "title": "Sessions"}
    }
  },
  "metadata": {
    "chart_type_suggestion": "line",
    "title": "Website Sessions — Last 7 Days",
    "data_source": "google_analytics",
    "description": "Daily session count from GA4, showing traffic trend over the past week"
  }
}
```

### 3.3 Spec Authoring Rules

Backends MUST follow these rules so theme, dark mode, and user interactivity work:

1. **`$schema` pinned to v6** — `https://vega.github.io/schema/vega-lite/v6.json`.
2. **Data inline** — always `spec.data.values: [...]`. The frontend has no data-URL fetcher.
3. **No `config` block** — theme, palette, axis/gridline styling are applied centrally. If the spec has a `config` key it overrides the app theme.
4. **No hardcoded `mark.color` / `config.mark.color`** — users can override color per artifact from the hover toolbar; hardcoded values silently defeat this. Use an `encoding.color` channel only when a data dimension requires it.
5. **Canonical `title`** — set on the spec (`spec.title`). `metadata.title` mirrors it for the API layer and reviewer context; the frontend reads `spec.title`.

---

## 4. `create_visualization` Tool

### 4.1 Tool Signature

`create_visualization()` is a **Python function tool** (not MCP). It follows the SDK function tools pattern described in [`mcp-architecture.md`](./mcp-architecture.md) §4.

```python
def create_visualization(
    chart_type: ChartType,              # "bar" | "line" | "area" | "point" | "arc"
    title: str,
    data: str,
    encoding: str,
    description: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    """Create a Vega-Lite v6 visualization artifact from structured data.

    Args:
        chart_type: Vega-Lite mark type. Use "point" for scatter plots.
        title: Human-readable chart title.
        data: JSON string of data values (array of objects).
        encoding: JSON string of Vega-Lite encoding specification.
        description: Optional description of what the chart shows.

    Returns:
        Confirmation message with artifact title, chart type, and data-point count.
    """
```

### 4.2 Implementation Pattern

The tool follows the SDK function tools pattern ([`mcp-architecture.md`](./mcp-architecture.md) §4). It writes the artifact to a `response_artifacts` session state key:

```python
def create_visualization(
    chart_type: ChartType,
    title: str,
    data: str,
    encoding: str,
    description: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    try:
        parsed_data = json.loads(data)
        parsed_encoding = json.loads(encoding)
    except json.JSONDecodeError as exc:
        return f"Error: invalid JSON in data or encoding: {exc}"

    # Plain spec: no `config`, no hardcoded mark color. Theme applied frontend-side.
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "title": title,
        "data": {"values": parsed_data},
        "mark": chart_type,
        "encoding": parsed_encoding,
    }

    artifact = {
        "type": "visualization",
        "spec": spec,
        "metadata": {
            "chart_type_suggestion": chart_type,
            "title": title,
            "data_source": "agent",  # specialist should override with its source id
            "description": description,
        },
    }

    if tool_context:
        artifacts = tool_context.state.get("response_artifacts", [])
        artifacts.append(artifact)
        tool_context.state["response_artifacts"] = artifacts

    return f"Visualization created: {title} ({chart_type} chart, {len(parsed_data)} data points)"
```

### 4.3 Chart Type Selection

The agent suggests a chart type based on the data shape and user's intent:

| Data Shape | Suggested `chart_type` | Example |
|-----------|------------------------|---------|
| Time series (single metric) | `line` | Sessions over time |
| Time series (multiple metrics) | `line` with `color` encoding | Sessions + Users over time |
| Categorical comparison | `bar` | Top 5 campaigns by sessions |
| Part-of-whole | `arc` | Traffic by channel (pie/donut) |
| Correlation (scatter plot) | `point` | Spend vs. conversions |
| Cumulative / stacked | `area` | Revenue by source over time |

The frontend can override the chart type at render time by swapping the `mark` property (see §8.3). The agent's suggestion is stored in `metadata.chart_type_suggestion` for reference.

### 4.4 Tool Availability & Wiring

`create_visualization` is a **`default_global: true` function tool** in the tool catalogue (`app/adk/tools/registry/config/tools.yaml`). It is attached to:

- **Every specialist** — `specialist_runtime` resolves the default-global function tools (`resolve_default_global_tools`) and passes them into `resolve_specialist_roster`.
- **The root coordinator (`ken_e`)** — so it can render a chart inline when *it* owns the final response (the common case: the coordinator presents a delegated result and decides a chart makes the answer clearer).

**Wiring gotcha (root coordinator).** The root build paths — `hierarchy.py` (deploy-time) and `root_tools_attacher.py` (per-turn hot-reload) — must feed the default-global function tools into the roster resolver as **candidates**. A `tool_ids` allowlist only *filters* candidates; it cannot *introduce* a tool. So:

- If the root build passes `function_tools=[]`, `function.create_visualization` is silently dropped even when it is listed in `ken_e_chatbot.tool_ids`, and the model improvises by emitting the call as plain text instead of invoking the tool.
- With `ken_e_chatbot.tool_ids` **unset**, all default-global function tools attach automatically (default-global semantics). With an **explicit** allowlist, it must list `function.create_visualization`.
- The `set_todo_list` / `update_todo_list` ledger tools are *also* `default_global` **and** always appended via `get_supervisor_function_tools()`, so the root tool list is **deduped by name** to avoid advertising a duplicate declaration to Gemini.

---

## 5. Data Flow: Agent to Frontend

### 5.1 Flow Diagram

```
User asks: "Show me website traffic trends for the past week"

    ┌──────────────────────────────┐
    │ 1. Specialist Agent           │
    │    • Queries GA MCP tool      │
    │    • Receives structured JSON │
    │    • Calls create_visualization() │
    │    • Writes text draft         │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │ 2. Session State              │
    │    • draft: "Traffic increased..."  │
    │    • response_artifacts: [{spec}]   │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │ 3. Review Loop (if active)    │
    │    • Reviewer evaluates draft │
    │      AND artifacts            │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │ 4. API Layer                  │
    │    • Extracts response_artifacts │
    │      from session state       │
    │    • Builds ChatResponse      │
    │      with content + artifacts │
    │    • Clears session key       │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │ 5. Frontend                   │
    │    • Renders text content     │
    │    • Detects artifacts        │
    │    • Applies app theme + user │
    │      overrides, renders chart │
    │      via ArtifactRenderer     │
    └──────────────────────────────┘
```

### 5.2 ChatResponse Extension

The `ChatResponse` model is extended with an optional `artifacts` field:

```python
class ChatResponse(BaseModel):
    role: str
    content: str
    session_id: str | None = None
    artifacts: list[Artifact] | None = None    # NEW — optional, backward-compatible
```

**Backward compatibility:** The `artifacts` field defaults to `None`. Old clients that don't parse this field continue to work unchanged — they receive `content` as before. The text in `content` is self-contained; artifacts provide supplementary visual data.

### 5.3 Streaming Considerations

In SSE streaming mode, artifacts are transmitted as a separate event after text streaming completes:

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

Artifacts are sent as a single atomic event (not streamed incrementally) because Vega-Lite specs must be complete to render. The frontend begins rendering the chart as soon as the `artifacts` event arrives.

---

## 6. Review Loop Integration


### 6.1 Reviewer Evaluates Artifacts

When a specialist calls `create_visualization()`, the artifacts are stored in session state alongside the text draft. The reviewer evaluates both:

- **Text quality** — does the prose accurately describe the data?
- **Artifact quality** — does the chart type match the data shape? Is the data complete? Are axes labeled?
- **Consistency** — does the text narrative match the visualization?

### 6.2 Reviewer Instruction Template

The reviewer's instruction template includes an optional `{step_N_artifacts?}` variable:

```
DRAFT TO REVIEW:
{step_N_draft}

ARTIFACTS (if any):
{step_N_artifacts?}

Evaluate the draft AND any artifacts against the acceptance criteria...
```

When no artifacts are produced, the `?` suffix resolves to an empty string (consistent with the `{step_N_feedback?}` pattern in [`review-loop-implementation-plan.md`](../../review-loop-implementation-plan.md) Section 3.1).

### 6.3 Acceptance Criteria for Visualizations

Acceptance criteria can explicitly require visualizations:

```
Acceptance criteria:
1. Include a line chart showing daily sessions for the past 7 days
2. Chart must have labeled axes (Date, Sessions)
3. Narrative must reference the chart and highlight the peak day
```

The reviewer checks that a visualization artifact exists, matches the specified chart type, and contains the expected data dimensions.

---

## 7. Multi-Step Workflow Integration


### 7.1 Per-Step Artifacts

Each workflow step produces artifacts with unique keys in session state:

| Step | Session State Key | Content |
|------|------------------|---------|
| Step 1a (Analytics) | `step_1a_artifacts` | GA engagement chart |
| Step 1b (Execution) | `step_1b_artifacts` | Meta Ads spend chart |
| Synthesizer | `response_artifacts` | Combined artifacts from all steps |

The naming convention (`step_N_artifacts`) parallels the existing `step_N_draft` / `step_N_feedback` pattern from [`review-loop-implementation-plan.md`](../../review-loop-implementation-plan.md) Section 3.1.

### 7.2 Synthesizer References

The synthesizer agent can reference artifacts from parallel steps when composing the final response:

```
You are given completed research from parallel analyses.

Analytics findings: {step_1a_draft}
Analytics charts: {step_1a_artifacts?}

Spend data: {step_1b_draft}
Spend charts: {step_1b_artifacts?}

Combine into a unified response. Include all relevant charts.
```

### 7.3 Extended Example: Meta Ads Optimization

A multi-step workflow for "Increase budgets for Meta Ads campaigns that result in the most engaged website visitors":

```
Phase 1 — Data Gathering (ParallelAgent):
  Step 1a: Google Analytics Specialist
    • Queries GA MCP for engagement by campaign UTM
    • Calls create_visualization(chart_type="bar",
        title="Website Engagement by Campaign",
        data=[{"campaign": "Spring Sale", "engagement_rate": 0.73}, ...],
        encoding={"x": {"field": "campaign"}, "y": {"field": "engagement_rate"}})
    • Writes: step_1a_draft (text) + step_1a_artifacts (bar chart)

  Step 1b: Meta Ads Specialist
    • Queries Meta Ads SDK for spend by campaign
    • Calls create_visualization(chart_type="bar",
        title="Meta Ads Daily Spend by Campaign",
        data=[{"campaign": "Spring Sale", "spend": 1250}, ...],
        encoding={"x": {"field": "campaign"}, "y": {"field": "spend"}})
    • Writes: step_1b_draft (text) + step_1b_artifacts (bar chart)

Phase 2 — Synthesis:
  Synthesizer combines both charts + text into optimisation plan
  → User sees engagement chart + spend chart + recommendation text

Phase 3 — Execution (after user approval):
  Meta Ads Specialist applies budget changes in Meta Ads
```

---

## 8. Frontend Rendering

### 8.1 Renderer

The chat-side renderer has shipped: `frontend/src/components/chat/ChatArtifactRenderer.tsx` (`react-vega` 8 / Vega-Lite v6), built from the Figma design contract at `docs/figma-export/src/app/components/dashboard/ArtifactRenderer.tsx`. `ChatInterface.tsx` wires `response.artifacts` into message state and renders each via `ChartArtifactItem` (chart + hover settings toolbar). The dashboards surface uses a sibling renderer over the **same Vega-Lite spec contract**:

- **Dashboards** ([DB-PRD-03](../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md)) — `frontend/src/components/dashboards/widgets/VisualizationWidget.tsx` (react-vega-backed).
- **Chat** ([CH-PRD-02](../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md)) — `ChatArtifactRenderer.tsx`, ported from the same Figma source.

The Vega-Lite spec is the contract between backend and frontend; the renderer is an implementation detail.

> **⚠️ Width contract — pass an explicit numeric `width`, never `width: "container"`.**
> Vega-Lite's responsive `width: "container"` does **not** work with `react-vega` 8: `<VegaEmbed>` embeds into a bare `<div>` whose container-width measurement resolves to **0**, so the chart paints into a **0-pixel-wide `<svg>`** — the marks exist in the DOM but are invisible, and Vega throws **no** error (so the `SpecFallback` path never triggers — it looks like a blank chart). `ChatArtifactRenderer` measures its wrapper with `useLayoutEffect` + a `ResizeObserver` and injects an explicit numeric `width` into the spec (with a fallback width for the first pre-paint frame and the jsdom test environment). **Any new react-vega 8 renderer (e.g. the dashboards `VisualizationWidget`) must do the same.** Regression-tested in `ChatArtifactRenderer.spec.tsx` ("passes an explicit numeric width"). Caught during the AH-PRD-04 root-coordinator rollout; see §10.

### 8.2 Message Layout

The chat message display component detects artifacts in the response and renders charts inline:

```
┌─────────────────────────────────────────────────────┐
│ KEN-E                                                │
│                                                      │
│ Traffic increased 12% week-over-week. Here's the     │
│ trend for the past 7 days:                           │
│                                                      │
│ ┌─────────────────────────────────────────────────┐  │
│ │         Website Sessions — Last 7 Days           │  │
│ │  1400 ┤        ●                    ●            │  │
│ │  1200 ┤   ●              ●                       │  │
│ │  1000 ┤            ●                             │  │
│ │   800 ┤                       ●                  │  │
│ │       └──┬──┬──┬──┬──┬──┬──┬                     │  │
│ │        Mon Tue Wed Thu Fri Sat Sun               │  │
│ └─────────────────────────────────────────────────┘  │
│                                                      │
│ The peak was Thursday (1,423 sessions), likely        │
│ driven by the email campaign sent that morning.       │
└─────────────────────────────────────────────────────┘
```

Each rendered artifact has a hover-revealed toolbar (top-right) with a gear button that opens the shared `TileSettingsPopover`:

- **View as** — change chart type (Auto / bar / line / area / scatter / pie / table).
- **Color** — pick from the app's palette tokens (auto / violet / blue / teal / amber / slate).
- **Data labels** — toggle value labels above marks.

On the dashboards surface these settings persist per placement; in chat they're session-local per artifact instance.

### 8.3 Render-Time Transforms

The renderer applies these transforms after receiving the spec. Backends should produce plain specs and let these run:

1. **Theme merge.** `config = { ...appTheme, ...colorOverride, ...spec.config }`. Spec `config` wins per-key — backends should omit it.
2. **View override.** `spec.mark` is swapped for the user's chart-type selection before embedding. `table` renders from `spec.data.values` via a tabular fallback.
3. **Data labels.** When enabled, the spec is wrapped: `{ layer: [<original>, { mark: { type: "text", dy: -6 }, encoding: { ...encoding, text: encoding.y } }] }`. Skipped when the spec already has `layer`.
4. **Color override.** User-selected palette token is resolved via CSS variable and applied to the `config.mark.color` / `bar.color` / `line.color` / `area.color` / `point.fill` / `arc.fill` family.

**Graceful degradation:** If the Vega-Lite renderer fails (malformed spec, missing dependency), the frontend shows the raw spec in a collapsible JSON block with an error (`SpecFallback`). The text content remains readable regardless.

---

## 9. Channel Considerations


| Channel | Rendering Approach | Status |
|---------|--------------------|--------|
| **Web UI** | Full Vega-Lite v6 rendering via `ArtifactRenderer` (interactive charts with hover, configurable chart type / color / data labels) | Primary target — production renderer to be delivered by DB-PRD-03 / CH-PRD-02 (or this PRD as fallback); see §8.1 |
| **Slack** `[PLANNED]` | Server-side render Vega-Lite to PNG via `vega-lite-to-png` or Vega CLI, send as image attachment. Apply the same app-theme config server-side for consistency. | Requires server-side rendering pipeline |
| **Voice** `[PLANNED]` | No visual rendering. Agent describes the data verbally: "Sessions peaked on Thursday at 1,423" | `create_visualization()` still produces the artifact for session history; voice channel skips rendering |

See [`api-gateway-multi-channel.md`](../backlog/api-gateway-multi-channel.md) Section 6 for the per-channel rendering architecture.

---

## 10. Open Questions

| # | Question | Impact | When to Resolve |
|---|----------|--------|----------------|
| 1 | **Firestore persistence** — should artifacts be persisted in Firestore alongside conversation history for later retrieval? | Medium — affects session replay and analytics | Sprint 7+ |
| 2 | **CSV export** — should the frontend offer a "Download CSV" option from artifact data? | Low — UX enhancement | Sprint 7+ |
| 3 | **Artifact size limits** — maximum size for a Vega-Lite spec with embedded data? Large datasets (>1,000 rows) could produce oversized specs. | Medium — affects token budget and API payload size | Sprint 7 |
| 4 | **Recharts coexistence** — existing `frontend/src/components/ui/chart.tsx` Recharts components (pre-existing dashboard cards) are retained; no migration planned. Revisit if styling drift becomes visible. | Low — cosmetic consistency | Post-Sprint 7 |
| 5 | **Multiple artifacts per response — layout** — vertical stack in list order is the current behavior; revisit once multi-artifact responses are common. | Low — UX design | Sprint 7 |
| 6 | **Schema version drift** — pinned to v6 to match `react-vega` 8 bundle. Upgrade in lockstep with the frontend dependency. | Low — maintainability | On `react-vega` upgrade |
| 7 | **Color override persistence (chat)** — on the dashboards surface, user overrides persist per placement; in chat they're session-local. Should chat persist per-message overrides? | Low — UX | Follow-up |
| 8 | **No real-browser render coverage** — `ChatArtifactRenderer.spec.tsx` mocks `react-vega` entirely, and the `chat-artifacts` e2e seeds an artifact with empty `data` and asserts only the `chart-artifact-item` wrapper, not that marks paint. The §8.1 zero-width bug therefore passed CI. Add a real-render assertion (mount the real renderer in a browser and assert a non-zero `<svg>` width / visible marks). | Medium — render regressions ship undetected | Follow-up |

---

## References

- Harness Design Doc — Sections 1.4 (Key Design Decisions), 2.3.2 (Request Flow), 3.6.2 (Session State), 4.4 (Specialist Agents), 4.6 (Review Loop Pattern)
- [`components/agentic-harness/README.md`](./README.md) §2.6 — Specialist roadmap
- [`api-gateway-multi-channel.md`](../backlog/api-gateway-multi-channel.md) Section 6 — Stable Components Across Channels
- [`mcp-architecture.md`](./mcp-architecture.md) §4 — SDK Function Tools Pattern
- [`review-loop-implementation-plan.md`](../../review-loop-implementation-plan.md) Section 3 — Architecture
- Frontend renderer (Figma export, design contract): `docs/figma-export/src/app/components/dashboard/ArtifactRenderer.tsx`
- Shared config UI (Figma export): `docs/figma-export/src/app/components/dashboard/TileSettingsPopover.tsx`
- Artifact union + adapter (Figma export): `docs/figma-export/src/app/components/dashboard/artifactTypes.ts`
- Production-tree equivalents: [DB-PRD-03](../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md) (`frontend/src/components/dashboards/widgets/VisualizationWidget.tsx`) + [CH-PRD-02](../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md) chat surface
- [Vega-Lite v6 Specification](https://vega.github.io/vega-lite/)
