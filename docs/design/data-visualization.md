# Data Visualization & Artifacts

**Version:** 1.0
**Date:** March 2026
**Status:** [PLANNED] — design complete, no implementation yet

---

## 1. Overview

> **Roadmap:** [Feature 2.4: Data Visualization](../product-roadmap.md#feature-24-data-visualization--phase-1) — Release 2.0

### Problem

KEN-E's agent system produces **text-only responses**. When a specialist agent queries Google Analytics via MCP, the tool returns structured JSON (sessions, users, pageviews by date), but the LLM converts this to prose — the structured data is lost. For a marketing analytics product where CMOs expect charts, tables, and visual dashboards, this is a significant gap.

### Solution

Introduce **Vega-Lite artifacts** as a first-class output type alongside text. Specialist agents produce chart specifications via a `create_visualization()` function tool, and the API delivers these artifacts to the frontend for rendering. The `ChatResponse` model is extended with an optional `artifacts` field — old clients that don't understand artifacts continue to work unchanged.

### Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| **Vega-Lite** as the visualization spec format | Declarative, JSON-based, well-supported ecosystem, separates data from presentation |
| **Agent suggests chart type, frontend can override** | Agent has data context to suggest appropriate chart type; frontend has UX context to override |
| **Additive `ChatResponse` extension** | `content: str` unchanged; new `artifacts: list[Artifact] \| None` field is backward-compatible |
| **Review loop evaluates visualization quality** | Reviewer evaluates artifacts alongside text draft — acceptance criteria can require specific visualizations |

---

## 2. Design Decisions

| # | Decision | Link |
|---|----------|------|
| 1 | Vega-Lite as visualization spec format | *Notion Decision TBD* |
| 2 | Agent suggests chart type, frontend can override | *Notion Decision TBD* |
| 3 | Additive ChatResponse extension (backward-compatible) | *Notion Decision TBD* |
| 4 | Review loop evaluates visualization quality | *Notion Decision TBD* |

> Decisions will be recorded in the [Design Decisions database in Notion](https://www.notion.so/2f230fd6530280d599f0ca1449111d7e) when implementation begins.

---

## 3. Artifact Model

### 3.1 Artifact Type Definition

```python
from pydantic import BaseModel

class ArtifactMetadata(BaseModel):
    chart_type_suggestion: str          # e.g., "line", "bar", "area", "scatter"
    title: str                          # Human-readable chart title
    data_source: str                    # e.g., "google_analytics", "meta_ads"
    description: str | None = None      # Optional natural-language description of what the chart shows

class Artifact(BaseModel):
    type: str                           # e.g., "visualization"
    spec: dict                          # Vega-Lite JSON specification
    metadata: ArtifactMetadata
```

### 3.2 Example Artifact

A full Vega-Lite spec for a line chart of website sessions over time:

```json
{
  "type": "visualization",
  "spec": {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
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

---

## 4. `create_visualization` Tool

### 4.1 Tool Signature

`create_visualization()` is a **Python function tool** (not MCP). It follows the SDK function tools pattern described in [`mcp-architecture.md`](mcp-architecture.md) Section 4.

```python
def create_visualization(
    chart_type: str,
    title: str,
    data: str,
    encoding: str,
    description: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    """Create a Vega-Lite visualization artifact from structured data.

    Args:
        chart_type: Vega-Lite mark type (e.g., "line", "bar", "area", "scatter", "arc").
        title: Human-readable chart title.
        data: JSON string of data values (array of objects).
        encoding: JSON string of Vega-Lite encoding specification.
        description: Optional description of what the chart shows.

    Returns:
        Confirmation message with artifact key.
    """
```

### 4.2 Implementation Pattern

The tool follows the SDK function tools pattern (`mcp-architecture.md` Section 4). It writes the artifact to a `response_artifacts` session state key:

```python
def create_visualization(
    chart_type: str,
    title: str,
    data: str,
    encoding: str,
    description: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    parsed_data = json.loads(data)
    parsed_encoding = json.loads(encoding)

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
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
            "data_source": "agent",
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

| Data Shape | Suggested Chart Type | Example |
|-----------|---------------------|---------|
| Time series (single metric) | `line` | Sessions over time |
| Time series (multiple metrics) | `line` with `color` encoding | Sessions + Users over time |
| Categorical comparison | `bar` | Top 5 campaigns by sessions |
| Part-of-whole | `arc` | Traffic by channel (pie/donut) |
| Correlation | `scatter` | Spend vs. conversions |
| Cumulative / stacked | `area` | Revenue by source over time |

The frontend can override the chart type by modifying the `mark` property in the Vega-Lite spec before rendering. The agent's suggestion is stored in `metadata.chart_type_suggestion` for reference.

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
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │ 5. Frontend                   │
    │    • Renders text content     │
    │    • Detects artifacts        │
    │    • Renders Vega-Lite charts │
    │      inline with message      │
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

> **Roadmap:** [Feature 2.1: Review Loop Framework](../product-roadmap.md#feature-21-review-loop-framework), [Feature 2.4: Data Visualization](../product-roadmap.md#feature-24-data-visualization--phase-1) — Release 2.0

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

When no artifacts are produced, the `?` suffix resolves to an empty string (consistent with the `{step_N_feedback?}` pattern in `review-loop-implementation-plan.md` Section 3.1).

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

> **Roadmap:** [Feature 2.4: Data Visualization](../product-roadmap.md#feature-24-data-visualization--phase-1), [Feature 3.4: Multi-Step Workflows](../product-roadmap.md#feature-34-multi-step-workflows--phase-1) — Releases 2.0, 3.0

### 7.1 Per-Step Artifacts

Each workflow step produces artifacts with unique keys in session state:

| Step | Session State Key | Content |
|------|------------------|---------|
| Step 1a (Analytics) | `step_1a_artifacts` | GA engagement chart |
| Step 1b (Execution) | `step_1b_artifacts` | Meta Ads spend chart |
| Synthesizer | `response_artifacts` | Combined artifacts from all steps |

The naming convention (`step_N_artifacts`) parallels the existing `step_N_draft` / `step_N_feedback` pattern from `review-loop-implementation-plan.md` Section 3.1.

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
  Step 1a: Analytics Specialist
    • Queries GA MCP for engagement by campaign UTM
    • Calls create_visualization(chart_type="bar",
        title="Website Engagement by Campaign",
        data=[{"campaign": "Spring Sale", "engagement_rate": 0.73}, ...],
        encoding={"x": {"field": "campaign"}, "y": {"field": "engagement_rate"}})
    • Writes: step_1a_draft (text) + step_1a_artifacts (bar chart)

  Step 1b: Execution Specialist
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
  Execution Specialist applies budget changes in Meta Ads
```

---

## 8. Frontend Rendering

### 8.1 Rendering Decision

The agent produces **Vega-Lite** specifications. The frontend needs a renderer:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **`react-vega` / `vega-embed`** | Render Vega-Lite specs directly | Full Vega-Lite support, no translation layer, future-proof | New dependency, different charting library from existing Recharts |
| **Translate to Recharts** | Convert Vega-Lite spec to Recharts component props | Uses existing `frontend/src/components/ui/chart.tsx` | Translation layer adds complexity, may not support all Vega-Lite features |

> **Implementation-time decision:** The frontend already has Recharts (`^2.12.7`) installed with chart components at `frontend/src/components/ui/chart.tsx`. Whether to add `react-vega`/`vega-embed` for native Vega-Lite rendering or build a Vega-Lite-to-Recharts translation layer is an implementation decision — both are viable. The Vega-Lite spec format is the contract; the renderer is an implementation detail.

### 8.2 MessageContent Extension

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

**Graceful degradation:** If the Vega-Lite renderer fails (malformed spec, missing dependency), the frontend shows the raw spec in a collapsible JSON block. The text content remains readable regardless.

---

## 9. Channel Considerations

> **Roadmap:** [Feature 5.1: Slack Channel](../product-roadmap.md#feature-51-slack-channel), [Feature 6.1: Voice Channel](../product-roadmap.md#feature-61-voice-channel) — Releases 5.0, 6.0

| Channel | Rendering Approach | Status |
|---------|--------------------|--------|
| **Web UI** | Full Vega-Lite rendering (interactive charts with hover, zoom) | Primary target |
| **Slack** `[PLANNED]` | Server-side render Vega-Lite to PNG via `vega-lite-to-png` or Vega CLI, send as image attachment | Requires server-side rendering pipeline |
| **Voice** `[PLANNED]` | No visual rendering. Agent describes the data verbally: "Sessions peaked on Thursday at 1,423" | `create_visualization()` still produces the artifact for session history; voice channel skips rendering |

See [`api-gateway-multi-channel.md`](api-gateway-multi-channel.md) Section 6 for the per-channel rendering architecture.

---

## 10. Open Questions

| # | Question | Impact | When to Resolve |
|---|----------|--------|----------------|
| 1 | **Firestore persistence** — should artifacts be persisted in Firestore alongside conversation history for later retrieval? | Medium — affects session replay and analytics | Sprint 7+ |
| 2 | **CSV export** — should the frontend offer a "Download CSV" option from artifact data? | Low — UX enhancement | Sprint 7+ |
| 3 | **Artifact size limits** — maximum size for a Vega-Lite spec with embedded data? Large datasets (>1,000 rows) could produce oversized specs. | Medium — affects token budget and API payload size | Sprint 7 |
| 4 | **Recharts coexistence** — if `react-vega` is added, should existing Recharts components (dashboard charts) be migrated? | Low — cosmetic consistency | Post-Sprint 7 |
| 5 | **Multiple artifacts per response** — how should the frontend layout multiple charts in a single message? | Low — UX design | Sprint 7 |
| 6 | **Artifact versioning** — should the Vega-Lite schema version be pinned or allow drift? | Low — maintainability | Sprint 7 |

---

## References

- Harness Design Doc — Sections 1.4 (Key Design Decisions), 2.3.2 (Request Flow), 3.6.2 (Session State), 4.4 (Specialist Agents), 4.6 (Review Loop Pattern)
- [`agent-hierarchy.md`](agent-hierarchy.md) Section 7 — Specialist Agent Layer
- [`api-gateway-multi-channel.md`](api-gateway-multi-channel.md) Section 6 — Stable Components Across Channels
- [`mcp-architecture.md`](mcp-architecture.md) Section 4 — SDK Function Tools Pattern
- [`review-loop-implementation-plan.md`](review-loop-implementation-plan.md) Section 3 — Architecture
- [Vega-Lite Specification](https://vega.github.io/vega-lite/)
- Frontend chart components: `frontend/src/components/ui/chart.tsx` (Recharts `^2.12.7`)
