# Goals Tab — Design Specification

> **Context:** This tab is the 4th tab within the Performance page, positioned between "Simulations" and "Diagnostics". The Analysis, Simulations, and Diagnostics tabs already exist in the Figma file.

---

## 1. Purpose

The Goals tab lets users review historical goal performance and set future KPI targets — all in one horizontally-scrollable table. Historic months are read-only (showing what happened vs. what was planned). Future months are editable (allowing the user to set or change targets).

---

## 2. Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Analysis]  [Simulations]  [Goals]  [Diagnostics]      │  ← Existing tab bar
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tab header area                                        │
│  ┌───────────────────────────────────┐  ┌────────────┐  │
│  │ Title + subtitle                  │  │ Save Goals  │  │
│  └───────────────────────────────────┘  └────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │                                                     ││
│  │                  Goals Table                         ││
│  │              (horizontally scrollable)               ││
│  │                                                     ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  Disclaimer footer                                      │
└─────────────────────────────────────────────────────────┘
```

### Tab Header

- **Title:** "Goals"
- **Subtitle:** "Set future KPI targets and track performance against past goals."
- **Save button:** Right-aligned, only enabled when unsaved changes exist. Uses the primary CTA style (gradient fill, violet shadow). Label: "Save Goals". Disabled state when no changes have been made.

---

## 3. Table Structure

### Dimensions

- **Rows:** 5 total — 1 header row + 4 funnel stage rows
- **Columns:** Variable — frozen label column + N time-period columns

### Column Order (left to right)

```
[Funnel Stage — FROZEN] | ...past months... | CURRENT MONTH | month+1 | month+2
                          ←── scroll left ──   ─── default visible ───────────→
```

- The **Funnel Stage column** is frozen (always visible on the left edge).
- On initial load, the table scrolls to show the **current month as the first time column**, with the next two months visible.
- The user scrolls **left** to reveal historic months, going back as far as actual data exists.
- The user scrolls **right** to see future months (current + 2 is the furthest).

### Scroll Affordance

When there is scrollable content to the left (i.e. the table is not scrolled to the beginning), show a subtle **fade/shadow gradient** on the left edge of the scrollable area — adjacent to the frozen column. This signals that more content is available to the left. A similar gradient appears on the right edge when scrollable content exists there, but this will rarely be needed since only 3 future columns exist.

---

## 4. Column Definitions

### 4A. Frozen Column — "Funnel Stage"

**Width:** ~200px (widest column — accommodates stage name + KPI name)

**Header cell content:**
```
Funnel Stage
```

**Data cell content (one per funnel stage):**
```
┌────────────────────────┐
│  ● Problem Awareness   │  ← Stage color dot + stage name (semibold)
│    Unbranded Search    │  ← Current KPI name (regular weight, muted color)
└────────────────────────┘
```

- The **color dot** uses the funnel stage's semantic color (blue, violet, amber, teal — matching the existing design system).
- **Stage name** is semibold, primary text color.
- **KPI name** is regular weight, muted/tertiary text color, smaller font size.

**Row order (top to bottom):**
1. Problem Awareness
2. Brand Awareness
3. Consideration
4. Conversion

---

### 4B. Historic Month Columns (read-only)

These columns appear for every past month that has actual data, regardless of whether goals were configured for that month.

**Width:** ~260px per column (wider than future columns to accommodate 3 data rows + KPI label)

**Header cell content:**
```
┌──────────────────────────────────────────┐
│            January 2026                  │  ← Month + year (semibold)
├────────────┬────────────┬────────────────┤
│   Goal     │  Actual    │    % Diff      │  ← Sub-headers (small, muted)
└────────────┴────────────┴────────────────┘
```

**Data cell content:**
```
┌──────────────────────────────────────────┐
│  Unbranded Search                        │  ← Historic KPI name (small label)
├────────────┬────────────┬────────────────┤
│   1,200    │   1,150    │    -4.2%       │  ← Values (tabular numerals)
└────────────┴────────────┴────────────────┘
```

**Cell layout details:**
- **KPI label** spans the full cell width, top-aligned. Small font, muted color. This tells the user which KPI was mapped to this funnel stage during this historic period.
- Below the label, **three values** sit in a row matching the sub-header columns:
  - **Goal:** The target value that was set. If no goal was configured for this month, show "—" in muted text.
  - **Actual:** The observed value for this KPI in this month. Always present for historic months (pulled from actual funnel data).
  - **% Diff:** `((Actual - Goal) / Goal) * 100`. Color-coded:
    - **Positive (goal exceeded):** Green text (e.g. `+8.3%`)
    - **Negative (goal missed):** Red text (e.g. `-4.2%`)
    - **Zero:** Neutral/muted text (`0.0%`)
    - **No goal set:** Show "—" in muted text (cannot compute diff without a goal)

**All numeric values** use tabular (monospace) numerals and thousands separators (e.g. `1,200`).

---

### 4C. Current + Future Month Columns (editable)

These columns are the current month and the next 2 months (3 columns total).

**Width:** ~140px per column (narrower — only one value per cell)

**Header cell content:**
```
┌──────────────────┐
│   March 2026     │  ← Month + year (semibold)
│   ★ Current      │  ← "Current" badge (only on the current month column)
├──────────────────┤
│     Target       │  ← Sub-header (small, muted)
└──────────────────┘
```

- The **current month** column gets a small "Current" indicator or badge to anchor the user's sense of time.
- The next two months show only the month/year and "Target" sub-header — no badge.

**Data cell content:**
```
┌──────────────────┐
│   [ 1,400     ]  │  ← Editable number input
└──────────────────┘
```

**Cell states:**
- **Has value:** The input displays the target value with thousands formatting. On focus, the raw number is shown for editing.
- **Null / no goal:** The input is empty with placeholder text "—" (dash). The input field has a slightly more muted/dashed border to indicate "not yet set."
- **Dirty (unsaved change):** A subtle highlight on the cell (e.g. a thin left accent border in violet, or a faint violet background tint) to indicate the value has been modified but not saved.

---

## 5. Visual Boundary: Past vs. Future

A clear **visual divider** separates historic columns from future/editable columns. This is one of the most important navigational cues in the table.

**Implementation:**
- A **2px vertical rule** in the primary violet color, positioned between the last historic month and the current month column.
- Optionally, a very subtle **background tint difference**: historic columns could have a faint cool-gray background (`surface-secondary`), while future columns sit on the default white/elevated surface.
- The divider should be visible in the header row as well, creating a full-height separation line.

---

## 6. Interaction Patterns

### Editing a Target Value

1. User clicks on a future-month cell.
2. The input field receives focus. The formatted number (e.g. `1,400`) switches to a raw number (`1400`) for editing.
3. User types a new value.
4. On blur or Enter, the value is formatted with thousands separators.
5. The cell shows a "dirty" visual indicator.
6. The "Save Goals" button becomes enabled (transitions from disabled to CTA style).

### Saving Goals

1. User clicks "Save Goals".
2. Button enters a loading state (spinner + "Saving..." label).
3. On success: dirty indicators are removed from all cells. A brief success toast/notification appears ("Goals saved"). Button returns to disabled state.
4. On error: toast with error message. Dirty indicators and button remain so the user can retry.

### Scrolling

- **Horizontal scroll:** The table's time-period columns scroll horizontally. The frozen column remains fixed.
- **Mouse/trackpad:** Standard horizontal scroll. On macOS, two-finger horizontal swipe on trackpad.
- **Keyboard:** When a future-month input is focused, Tab/Shift+Tab moves between cells (left-right within the same row, then wrapping to the next row).

### Cancel / Discard Changes

If the user navigates away from the Goals tab with unsaved changes, no blocking confirmation is needed (the unsaved changes are simply discarded — lightweight MVP behavior). The dirty state is visual only.

---

## 7. States

### Loading State

While goal data or actual data is being fetched, show a skeleton table with the correct row/column structure. The frozen column can show real stage names (known at render time), while time-period cells show animated placeholder bars.

### Empty State — No Actual Data Available

If the system has no actual historical data at all (brand new setup), show a centered empty state message within the tab:

> **No funnel data available yet.**
> Goals and historical performance will appear here once actual data has been collected.

### Partial State — Actuals Exist but No Goals Set

This is the normal state for months where the user hasn't configured goals. The table still renders all historic months with actual data. The "Goal" and "% Diff" values show "—" in those months. This is **not** an error state — it's expected.

---

## 8. Visual Design Notes

These notes align with the existing Fun-E "Soft Maximalism" design language already established in the Figma file:

- **Table container:** Rounded corners (`radius-lg`), subtle border (`border-ds`), elevated surface background. Consistent with the card treatment used elsewhere on the Performance page.
- **Header row:** Slightly darker surface or distinct background tint to separate from data rows. Semibold text.
- **Row hover (data rows):** Subtle background highlight on hover for the entire row (including the frozen cell). Helps the user track across a wide table.
- **Typography:** All numbers use tabular/monospace numerals for vertical alignment. KPI names and labels use the standard sans-serif.
- **Stage color dots:** 8px circles, same palette as the funnel chart (blue → violet → amber → teal).
- **Cell padding:** Generous — the cells hold dense information (especially historic cells), so sufficient internal padding is critical to readability.
- **Focus ring on inputs:** Violet focus ring, matching the input treatment used in the Simulations tab.

---

## 9. Responsive & Overflow Behavior

This is a desktop-first analytics tool. The table is designed for viewport widths of 1024px+.

- At **1280px+**, the frozen column + 3 future columns fit comfortably with room for partial display of the most recent historic column (hinting at scrollability).
- At **1024px**, the table may show only the frozen column + 2–3 time columns. The scroll affordance becomes more important at this width.
- **No mobile layout** is required for this tab.

---

## 10. Data Model — Historic Funnel Mapping

> This section proposes how to support the "which KPI was used for this funnel stage in a given month" requirement.

### Problem

The current funnel mapping (`config_funnel_mapping` sheet) stores only the **current** KPI-to-stage assignment. When the user changes a mapping (e.g. swaps "Unbranded Search" for a different awareness KPI), the previous assignment is lost. The Goals tab needs to display the historic KPI name for each stage in past months.

### Proposed Solution — New Google Sheet Tab: `history_funnel_mapping`

This tab uses a **change-event log** pattern. A new row is appended each time a funnel mapping changes, recording when it became active.

| Column | Type | Description |
|--------|------|-------------|
| `effective_date` | `YYYY-MM-DD` | First day of the month this mapping became active |
| `stage` | `string` | Funnel stage name (e.g., `Problem Awareness`) |
| `kpi_name` | `string` | KPI technical identifier (e.g., `Unbranded_Search`) |
| `display_name` | `string` | Human-readable label (e.g., `Unbranded Search`) |

**Example data:**

| effective_date | stage | kpi_name | display_name |
|---------------|-------|----------|--------------|
| 2025-01-01 | Problem Awareness | Unbranded_Search | Unbranded Search |
| 2025-01-01 | Brand Awareness | Branded_Search | Branded Search |
| 2025-01-01 | Consideration | PDP_Views | PDP Views |
| 2025-01-01 | Conversion | First_Purchases | First Purchases |
| 2025-09-01 | Problem Awareness | Organic_Impressions | Organic Impressions |

In this example, "Problem Awareness" was mapped to "Unbranded Search" from January 2025 through August 2025, then changed to "Organic Impressions" starting September 2025.

### Lookup Logic

To find which KPI was used for a given stage in a given month:

```
SELECT kpi_name, display_name
FROM history_funnel_mapping
WHERE stage = {target_stage}
  AND effective_date <= {first_day_of_target_month}
ORDER BY effective_date DESC
LIMIT 1
```

This returns the most recent mapping that was active on or before the target month.

### When to Write Records

- **On feature launch (seed):** Write one row per stage using the current `config_funnel_mapping` values with `effective_date` set to the earliest month that has actual data. This backfills history so all existing months resolve correctly.
- **On mapping change:** When the user updates `config_funnel_mapping` via the Settings page, also append new rows to `history_funnel_mapping` with `effective_date` = first day of the current month.

### Why Change-Event Log (Not Monthly Snapshots)

A monthly snapshot approach (one row per stage per month) would be simpler to query but generates 4 rows per month indefinitely. The change-event log is more compact — most deployments will have very few mapping changes. The backend service handles the "most recent before date" lookup, so the frontend receives the resolved KPI name per cell and doesn't need to implement the logic.

---

## 11. Accessibility

- **Table semantics:** Use proper `<table>`, `<thead>`, `<tbody>`, `<th>`, `<td>` elements (or their ARIA equivalents) so screen readers can navigate by row/column.
- **Frozen column:** Marked with `scope="row"` headers. Screen readers should announce the stage name when navigating across a row.
- **Editable inputs:** Each input has an accessible label derived from the stage name + month (e.g. `aria-label="Problem Awareness target for April 2026"`).
- **Color + text:** The % Diff color coding (red/green) is supplemented with the `+`/`-` sign prefix, so the information is not conveyed by color alone.
- **Focus management:** Tab key moves through editable cells in a logical order (left to right, top to bottom within the future columns).

---

## 12. Summary Table

| Aspect | Historic Months | Future Months (incl. Current) |
|--------|----------------|-------------------------------|
| **Editable?** | No | Yes |
| **Cell content** | KPI name + Goal + Actual + % Diff | Editable target input |
| **Background** | Subtle muted tint | Default surface |
| **Column width** | ~260px | ~140px |
| **Data source** | Actuals API + Goals API + Historic mapping | Goals API (user input) |
| **Empty state** | "—" for Goal/% Diff if no goal set; Actual always shown | Empty input with "—" placeholder |
