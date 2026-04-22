# Fun-E Diagnostics Page — Figma Design Requirements

> **Scope:** Model Diagnostics tab only (first tab of the Diagnostics page)
> **Design System:** Fun-E "Analytical Warmth" (child of KEN-E "Soft Maximalism" v2.0)
> **Purpose:** Recreate the existing Model Diagnostics tab in a new Figma design, with the addition of a "Re-estimate Model" button relocated from the Configuration tab.

---

## Page Structure (Top to Bottom)

The Model Diagnostics tab contains these sections in order:

1. **Page Header** (with health badge + Re-estimate button)
2. **Health Issues Alert** (conditional — shown when status is Yellow or Red)
3. **Model Overview** (7 stat cards)
4. **Structural Break Alert** (conditional — shown when detected)
5. **ADF Stationarity Tests** (data table, 4 rows)
6. **Residual Diagnostics** (data table, 4 rows)

---

## 1. Page Header

### Left Side
- **Title:** "Diagnostics"
- **Health Status Badge** — displayed inline next to the title. A pill badge with a colored dot and label. Three variants:
  - **Green:** label "Healthy"
  - **Yellow:** label "Attention Needed"
  - **Red:** label "Action Required"
  - When issues exist, the badge shows a tooltip on hover listing each issue summary as a bulleted list
- **Subtitle:** "Model diagnostics — lag order, information criteria, stationarity tests, and residual checks."

### Right Side (NEW — relocated from Configuration tab)
- **"Re-estimate Model" button** — a secondary (not primary) button with these states:
  - **Default:** Label "Re-estimate Model"
  - **Loading/Pending:** Label changes to "Estimating...", button disabled
  - **Success feedback:** Message appears below: "Model re-estimated successfully." (auto-dismisses after 5 seconds)
  - **Error feedback:** Message appears below: "Model re-estimation failed. Please try again." with optional error detail list
  - **Timeout variant:** "The request timed out. The model may still be running — check back shortly."

### Mock Data for Header
- Health Status: **"Yellow"** (to show the non-green state)
- Badge label: "Attention Needed"

---

## 2. Health Issues Alert (Conditional)

Shown only when health status is Yellow or Red. Contains expandable issue cards.

### Header Text
- **Red status:** "Model Health Issues"
- **Yellow status:** "Model Health Warnings"

### Issue Cards
Each issue card displays:
1. **Icon + Summary** — warning icon for warnings, error icon for errors, followed by the summary text
2. **Recommended Action** — prefixed with "Recommended action:", followed by action text
3. **"Technical details" toggle** — a collapsible section toggled by a chevron icon + "Technical details" label
4. **Technical detail text** — shown when expanded, displayed in a monospace font

### Mock Data — Issue Cards
Use these 2 issues to populate the alert:

**Issue 1 (Warning):**
- Summary: "Brand Awareness is showing an unstable trend, which may reduce forecast reliability for this part of the funnel."
- Action: "Consider re-estimating after 4-6 more weeks of data. If the issue persists, escalate to your data science team."
- Technical detail: "Brand Awareness failed the ADF stationarity test (p=0.1247). The null hypothesis of a unit root could not be rejected at the 5% level."

**Issue 2 (Warning):**
- Summary: "The model's predictions for Consideration have patterns in their errors, suggesting the model is missing something systematic."
- Action: "This may resolve when the model is re-estimated with more data. If it persists, ask your data science team about adding events or adjusting the lag order."
- Technical detail: "Consideration has significant residual autocorrelation (Durbin-Watson = 1.3842). Values far from 2.0 indicate serial correlation."

Show Issue 1 with technical details collapsed, Issue 2 with technical details expanded.

---

## 3. Model Overview (Stat Cards)

7 stat cards, each displaying a label and a value. Each card has a distinct accent color from the funnel palette applied to its left border.

### The 7 Cards

**Card 1 — Last Estimated**
- Label: "Last Estimated"
- Value: formatted date+time string
- Mock value: **"Mar 25, 2026, 2:30 PM"**

**Card 2 — Lag Order** (has info tooltip)
- Label: "Lag Order" with info icon
- Value: integer
- Tooltip: "Number of past weekly periods used as predictors. Selected automatically by minimizing AIC."
- Mock value: **"3"**

**Card 3 — Model Frequency**
- Label: "Model Frequency"
- Value: capitalized text
- Mock value: **"Weekly"**

**Card 4 — Observations**
- Label: "Observations"
- Value: integer
- Mock value: **"104"**

**Card 5 — AIC** (with conditional annotation)
- Label: "AIC" — if AIC is the selected lag criterion, append "(selected)" as a secondary annotation
- Value: float with 2 decimal places
- Mock value: **"-14.32"** with "(selected)" annotation

**Card 6 — BIC** (with conditional annotation)
- Label: "BIC" — same annotation pattern as AIC, but only shown when BIC is the selected criterion
- Value: float with 2 decimal places
- Mock value: **"-13.87"** (no annotation — AIC is selected in this mock)

**Card 7 — Exog Columns** (has info tooltip)
- Label: "Exog Columns" with info icon
- Value: integer, followed by a secondary annotation showing the pulse column breakdown
- Tooltip: "Total exogenous variables in the model. Includes 2 pulse intensity column(s) with smoothing alpha=0.3."
- Mock value: **"5"** with **"(2 pulse)"** annotation

---

## 4. Structural Break Alert (Conditional)

An error-severity warning banner. In the mock, this should be **hidden** (structural_break_detected = false). Design it as a variant/component for completeness:

- Title: "Structural Break Detected"
- Body: "A structural break has been detected in the data. Model estimates may be less reliable. Human review is recommended before relying on forecasts."

---

## 5. ADF Stationarity Tests

### Section Header
- Title: "ADF Stationarity Tests"
- Subtitle: "These checks verify that each funnel metric follows a stable, predictable pattern over time. A stable pattern means the model can learn from it and produce reliable forecasts."

### Table Columns

| Column | Tooltip |
|--------|---------|
| **Funnel Stage** | None |
| **p-value** | "A statistical confidence measure. Values below 0.05 indicate a stable pattern." |
| **Status** | "'Stable' means the metric has a reliable pattern the model can learn from. 'Unstable' means the pattern is drifting." |

- p-value column headers have an info icon indicating the tooltip is available
- Status column headers have an info icon indicating the tooltip is available
- Status values are displayed as pill badges:
  - **"Stable"** — success variant
  - **"Unstable trend"** — error variant

### Mock Data — ADF Table

| Funnel Stage | p-value | Status |
|---|---|---|
| Problem Awareness | 0.0087 | Stable |
| Brand Awareness | 0.1247 | Unstable trend |
| Consideration | 0.0342 | Stable |
| Conversion | 0.0156 | Stable |

---

## 6. Residual Diagnostics

### Section Header
- Title: "Residual Diagnostics"
- Subtitle: "These checks verify that the model's prediction errors are random. Patterns in the errors suggest the model may be missing something important."

### Table Columns

| Column | Tooltip |
|--------|---------|
| **Funnel Stage** | None |
| **Autocorrelation** | "Checks whether prediction errors follow a pattern. 'No issues' is the ideal result." |
| **Durbin-Watson** | "Measures error patterns. Values near 2.0 are ideal. Below 1.5 or above 2.5 indicates a problem." |
| **Normality** | "Checks if errors follow a bell-curve distribution. 'Normal' means forecast confidence ranges are reliable." |

- Autocorrelation, Durbin-Watson, and Normality column headers have info icons indicating tooltips are available
- Autocorrelation values are displayed as pill badges:
  - **"No issues"** — success variant
  - **"Patterns found"** — error variant
- Normality values are displayed as pill badges:
  - **"Normal"** — success variant
  - **"Irregular"** — error variant

### Mock Data — Residual Table

| Funnel Stage | Autocorrelation | Durbin-Watson | Normality |
|---|---|---|---|
| Problem Awareness | No issues | 2.0134 | Normal |
| Brand Awareness | No issues | 1.8756 | Normal |
| Consideration | Patterns found | 1.3842 | Irregular |
| Conversion | No issues | 2.1203 | Normal |

---

## States to Design

Design these states as separate frames or variants:

### 1. Default / Loaded State (PRIMARY — use mock data above)
- Health status: Yellow ("Attention Needed")
- 2 warning issue cards in the alert
- All 7 stat cards populated
- Structural break: hidden
- Tables populated with 4 rows each

### 2. Healthy State (variant)
- Health status: Green ("Healthy")
- No alert banner
- All stat cards populated
- All ADF rows show "Stable"
- All residual rows show "No issues" and "Normal"

### 3. Critical State (variant)
- Health status: Red ("Action Required")
- Red alert banner with error + warning issues
- Structural break alert visible
- Multiple "Unstable trend" and "Patterns found" badges

### 4. Loading State
- Skeleton loading placeholder filling the content area below the header
- Header and tabs still visible

### 5. Empty State
- Title: "No diagnostics data available yet."
- Subtitle: "Diagnostics will appear here once the model has been estimated."

### 6. Error State
- Title: "Failed to load diagnostics data"
- Subtitle with error message

### 7. Re-estimate Button States
- Default, loading/pending, success feedback, error feedback (see Section 1)

---

## Data Formatting Rules

These formatting rules describe how the underlying data values should be displayed:

- **p-values:** 4 decimal places (e.g., 0.0087)
- **AIC / BIC:** 2 decimal places (e.g., -14.32)
- **Durbin-Watson:** 4 decimal places (e.g., 2.0134)
- **Integers** (Lag Order, Observations, Exog Columns): no decimal places
- **Last Estimated:** Localized date+time (e.g., "Mar 25, 2026, 2:30 PM")
- **Funnel stage order is always:** Problem Awareness, Brand Awareness, Consideration, Conversion
