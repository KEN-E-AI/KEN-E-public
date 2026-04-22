# Fun-E Config Page — Figma Design Requirements

> **Scope:** New "Config" page that merges the contents of the existing "Events" tab and "Configuration" tab from the current Diagnostics page.
> **Design System:** Fun-E "Analytical Warmth" (child of KEN-E "Soft Maximalism" v2.0)
> **Note:** The "Re-estimate Model" button has been relocated to the Diagnostics page and should NOT appear on this page.

---

## Page Structure (Top to Bottom)

The Config page contains these sections in order:

1. **Page Header**
2. **Customer Lifetime Value (CLV)**
3. **Funnel Stage Mapping**
4. **Exogenous Events** (with Category Status panel)
5. **Auto-Detected Thresholds**
6. **Marketing Channels**

---

## 1. Page Header

- **Title:** "Configuration"
- **Subtitle:** "Manage model inputs — funnel mappings, lifetime value, exogenous events, and channel settings."

---

## 2. Customer Lifetime Value (CLV)

A single editable value representing the average customer lifetime value used for revenue estimation.

### Read Mode (default)
- **Label:** "Average Customer Lifetime Value"
- **Value:** Dollar-formatted number (e.g., "$4,200")
- **"Edit" button** next to the value
- If no value is configured, display "Not configured" instead of a dollar amount

### Edit Mode
- A numeric input field prefixed with "$", pre-populated with the current value
- **"Save" button** (primary) — label changes to "Saving..." while pending
- **"Cancel" button** (secondary)
- Keyboard: Enter to save, Escape to cancel
- Validation: value must be a positive number

### Error States
- Save failure: "Failed to update CLV. Please try again."
- Load failure: "Failed to load CLV configuration."

### Mock Data
- Value: **$4,200**

---

## 3. Funnel Stage Mapping

A table that maps each of the four funnel stages to a KPI data source. Always displays exactly 4 rows.

### Read Mode (default)
- **Section Title:** "Funnel Stage Mapping"
- **Subtitle:** "Configure which KPI is assigned to each funnel stage."
- **"Edit" button** in the section header

### Table Columns (Read Mode)

| Column | Description |
|--------|-------------|
| **Funnel Stage** | The stage name |
| **KPI** | The display name of the assigned KPI |
| **Data Source** | The raw data tab name (e.g., "raw_unbranded_search") |

### Edit Mode
- A warning banner appears above the table: "Changing KPI assignments requires model re-estimation for accurate forecasts. Use the Re-estimate Model button after saving."
- The KPI column becomes a dropdown selector populated with available KPIs
  - KPIs already assigned to another stage are disabled in the dropdown
  - KPIs with no data show "(no data)" suffix and are disabled
  - Placeholder text: "Select KPI..."
- The Data Source column auto-updates when a KPI is selected
- **"Save" button** (primary) — label changes to "Saving..." while pending
- **"Cancel" button** (secondary)

### Validation Errors
- "All stages must have a KPI assigned."
- "Each stage must have a unique KPI."
- Save failure: "Failed to update funnel mapping. Please try again."

### Mock Data — Funnel Mapping Table

| Funnel Stage | KPI | Data Source |
|---|---|---|
| Problem Awareness | Unbranded Search Volume | raw_unbranded_search |
| Brand Awareness | Branded Search Volume | raw_branded_search |
| Consideration | PDP Views | raw_pdp_views |
| Conversion | First-Time Account Opens | raw_account_opens |

---

## 4. Exogenous Events

A table of external events (competitor activity, seasonal patterns, market disruptions) that the model uses as exogenous controls. Supports full CRUD editing.

### Section Header
- **Title:** "Exogenous Events"
- **Subtitle:** "Manage competitor activity, seasonal events, and other external factors that may influence funnel metrics."
- **"Edit" button** in the section header (hidden during edit mode)

### Info Banner (always visible)
An informational callout with an info icon:
> "Events help the model separate external factors from organic trends, preventing interventions from inflating the forecast baseline. Calendar activities are included automatically. Use this page for non-campaign events like competitor launches, seasonal shifts, or market disruptions."

### Category Status Panel
Shown when categories exist. Displays each event category with its status:
- **Category name** followed by a status badge:
  - **Active:** success badge — "Active in model (N events)" with a checkmark icon
  - **Inactive:** warning badge — "Not yet active — needs N more event(s) (count/5)" with a warning icon
- The minimum threshold for activation is **5 events** per category
- If the category is "campaign", show a note below it: "Automatically included from Calendar. Events from the Calendar page are merged into this category."
- **Full coverage warning** (conditional): If an active category's events span the entire training period date range, show a warning: "This category covers the entire training period. The model needs some periods without events in this category to estimate its effect. Consider scheduling holdout periods."

### Empty State (no events, not editing)
> "No events configured. Add events to help the model account for competitor activity, seasonal patterns, and other external factors. Note: campaigns are automatically included as exogenous controls — you do not need to add them here."

### Table Columns (Read Mode)

| Column | Description |
|--------|-------------|
| **Start Date** | Formatted date (e.g., "Nov 20, 2025") |
| **End Date** | Formatted date (e.g., "Dec 2, 2025") |
| **Label** | Event name (e.g., "Black Friday") |
| **Category** | Event category (e.g., "seasonal") |
| **Expected Direction** | "Positive", "Negative", or "—" if not set. Has a tooltip on the column header: "Select 'positive' if this event type is expected to increase funnel metrics, 'negative' if expected to decrease, or leave blank if unknown. This is for documentation only and does not constrain the model." |

### Edit Mode
- Each column becomes editable:
  - **Start Date / End Date:** date picker inputs
  - **Label:** text input (placeholder: "e.g. Black Friday")
  - **Category:** text input with autocomplete from known categories (placeholder: "e.g. seasonal")
  - **Expected Direction:** dropdown with options: "None", "Positive", "Negative"
- Each row has a **delete button** (trash icon) in an additional column
- **"Add Row" button** below the table — adds a new empty row and focuses the first input
- **"Save" button** (primary) — label changes to "Saving..." while pending
- **"Cancel" button** (secondary)

### Row-Level Validation Errors
Shown below each invalid row:
- "Start date is required"
- "End date is required"
- "Label is required"
- "Category is required"
- "Start date must be on or before end date"

### Save Error Messages
- Conflict (409): "Someone else has modified the events. Please refresh and try again."
- General failure: "Failed to save events. Please try again."

### Mock Data — Category Status

| Category | Status |
|---|---|
| campaign | Active in model (8 events) — with auto-merge note |
| seasonal | Active in model (6 events) |
| competitor | Not yet active — needs 2 more events (3/5) |

### Mock Data — Events Table

| Start Date | End Date | Label | Category | Expected Direction |
|---|---|---|---|---|
| Nov 20, 2025 | Dec 2, 2025 | Black Friday | seasonal | Positive |
| Dec 20, 2025 | Jan 5, 2026 | Holiday Season | seasonal | Positive |
| Jan 15, 2026 | Jan 22, 2026 | Competitor Product Launch | competitor | Negative |
| Feb 1, 2026 | Feb 14, 2026 | Valentine's Day Promo | seasonal | Positive |
| Mar 1, 2026 | Mar 7, 2026 | Industry Conference | competitor | Positive |
| Sep 1, 2025 | Sep 30, 2025 | Back to School | seasonal | Positive |
| Oct 10, 2025 | Oct 17, 2025 | Competitor Price Drop | competitor | Negative |
| Jul 1, 2025 | Jul 7, 2025 | Summer Slowdown | seasonal | Negative |
| Aug 15, 2025 | Aug 22, 2025 | Market Disruption | competitor | — |

---

## 5. Auto-Detected Thresholds

A table of automatically computed per-channel spend thresholds used to classify pulse intensity. Supports manual overrides per row.

### Section Header
- **Title:** "Auto-Detected Thresholds"
- **Subtitle:** "Automatically computed from per-channel pulse spend data (Path C). Thresholds are recalculated at each model estimation."

### Empty State (insufficient data)
> "Insufficient pulse history for automatic threshold detection."
> "Continue entering per-channel cost data with each pulse. Detection requires at least 6 months of data per channel per funnel step."

### Table Columns

| Column | Description |
|--------|-------------|
| (expand chevron) | Chevron icon for rows with manual override enabled; otherwise blank |
| **Funnel Step** | The funnel stage name; shown only on the first row of each group |
| **Channel** | Display name + slug in monospace (e.g., "Paid Search `paid_search`") |
| **Method** | Detection method (e.g., "percentage above median", "sd bands", "iqr") |
| **Threshold %** | Percentage with 1 decimal (e.g., "35.0%") |
| **Rolling** | "Static" or rolling window duration (e.g., "12mo") |
| **Last Value** | Dollar-formatted threshold value (e.g., "$12,500") or "—" |
| **Flag0 Coverage** | Coverage percentage displayed as a status badge — success (30-40%), warning (20-30% or 40-50%), error (<20% or >50%), or "N/A" |
| **Override** | Checkbox to enable manual override. When checked, shows a "Manual" info badge |

### Row Grouping
Rows are grouped by funnel step. Groups are separated by a heavier border between them. The funnel step name appears only on the first row of each group.

### Manual Override Expansion
When a row has override enabled and is clicked, an expanded section appears below it with:
- Header: "Manual Override Values" with a "Reset to Auto" button
- Four editable fields in a row:
  - **Method:** dropdown — "% Above Median", "SD Bands", "IQR"
  - **Threshold %:** numeric input (range 1-100, step 0.5)
  - **Rolling Median:** dropdown — "Static", "Rolling"
  - **Window (months):** numeric input (range 3-36, step 1) — disabled when Rolling Median is "Static"
- **Auto-detected comparison line:** Shows the original auto-detected values for reference: "Auto-detected values: Method: percentage above median, Threshold: 35.0%, Rolling: No, Coverage: 32.5%"

### Mock Data — Auto-Detected Thresholds Table

**Problem Awareness group:**

| Channel | Method | Threshold % | Rolling | Last Value | Flag0 Coverage | Override |
|---|---|---|---|---|---|---|
| Paid Search `paid_search` | percentage above median | 35.0% | 12mo | $12,500 | 32.5% (success) | unchecked |
| Social Media `social_media` | sd bands | 28.5% | Static | $8,200 | 45.2% (warning) | unchecked |

**Brand Awareness group:**

| Channel | Method | Threshold % | Rolling | Last Value | Flag0 Coverage | Override |
|---|---|---|---|---|---|---|
| Paid Search `paid_search` | percentage above median | 40.2% | 12mo | $15,000 | 35.1% (success) | checked (Manual) |
| Display `display` | iqr | 22.0% | Static | $5,800 | 18.5% (error) | unchecked |

Show the "Paid Search / Brand Awareness" row expanded with override controls visible.

**Mock Override Controls (expanded row):**
- Method: "% Above Median" (selected)
- Threshold %: 42.0
- Rolling Median: "Rolling" (selected)
- Window (months): 12
- Auto-detected comparison: "Auto-detected values: Method: percentage above median, Threshold: 40.2%, Rolling: Yes, Coverage: 35.1%"

---

## 6. Marketing Channels

A coverage matrix showing which marketing channels have sufficient data across funnel stages, with the ability to exclude channels from the model.

### Section Header
- **Title:** "Marketing Channels"
- **Subtitle:** "Channels are automatically discovered from pulse data. Coverage across N months of training data (M monthly observations required). Excluded channels are hidden from pulse suggestions and omitted from the model."
  - N and M are derived from data. For mock: N = **24**, M = **3**

### Empty State (no channels)
> "No channel coverage data"
> "Coverage data is derived from pulses that have moved beyond the planning stage (active, completed, or validated) and have channels assigned. Channels will appear here automatically as you use them in pulses."

### Table Structure

**Columns:**
| Column | Description |
|--------|-------------|
| **Channel** | Display name + slug in monospace (e.g., "Paid Search `paid_search`") |
| **Problem Awareness** | Coverage badge: "observation_months/min_monthly_observations" (e.g., "5/3") — success if meets threshold, warning if not |
| **Brand Awareness** | Same as above |
| **Consideration** | Same as above |
| **Conversion** | Same as above |
| **Overall** | "Pass" (success badge) or "Insufficient" (warning badge) |
| **Exclude** | Checkbox — when checked, the channel is excluded from the model. The entire row appears dimmed/muted. |

The funnel step columns are dynamic (one per funnel step). Cells with no data show "—".

### Mock Data — Channel Coverage Table

Training period: 104 weeks (~24 months). Minimum monthly observations: 3.

| Channel | Problem Awareness | Brand Awareness | Consideration | Conversion | Overall | Exclude |
|---|---|---|---|---|---|---|
| Paid Search `paid_search` | 8/3 (success) | 7/3 (success) | 5/3 (success) | 4/3 (success) | Pass | unchecked |
| Social Media `social_media` | 6/3 (success) | 5/3 (success) | 3/3 (success) | 2/3 (warning) | Insufficient | unchecked |
| Display `display` | 4/3 (success) | 3/3 (success) | — | — | Insufficient | unchecked |
| Email `email` | 5/3 (success) | 4/3 (success) | 4/3 (success) | 3/3 (success) | Pass | unchecked |
| Affiliate `affiliate` | 2/3 (warning) | 1/3 (warning) | — | — | Insufficient | checked (row dimmed) |

---

## States to Design

### 1. Default / Loaded State (PRIMARY — use mock data above)
All five sections populated with their mock data. Events table in read mode. Funnel mapping in read mode. CLV showing "$4,200". One auto-threshold row expanded with override controls.

### 2. Events Edit Mode
Events section with editable rows (date pickers, text inputs, dropdowns), one row showing validation errors, "Add Row" / "Save" / "Cancel" buttons visible.

### 3. Funnel Mapping Edit Mode
Mapping table with KPI dropdown selectors, warning banner visible, "Save" / "Cancel" buttons visible.

### 4. CLV Edit Mode
Dollar input field with "$" prefix, "Save" / "Cancel" buttons inline.

### 5. Loading State
Each section can independently show a loading state with a "Loading..." message.

### 6. Error States
Each section can independently show an error with a "Retry" button:
- "Failed to load events."
- "Failed to load CLV configuration."
- "Failed to load funnel mapping configuration."
- "Failed to load channel guidelines."
- "Failed to load channel coverage."

### 7. Events Empty State
Events section with the empty state message, all other sections populated.
