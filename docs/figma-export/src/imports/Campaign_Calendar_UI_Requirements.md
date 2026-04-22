# Campaign Calendar — UI Requirements Specification

**Project:** Campaign Calendar Application
**Document Purpose:** Frontend design requirements for Figma Make
**Date:** March 24, 2026
**Version:** 1.0

---

## 1. Page Overview

The **Calendar** page is the primary workspace for managing marketing campaign activities. It consists of two main sections stacked vertically:

1. **Approval Queue** — a collapsible panel at the top displaying activities awaiting review.
2. **Calendar / List View** — a switchable view showing all activities on a weekly grid calendar (default) or in a tabular list.

The page also provides global controls for filtering, adding new activities, and navigating through time.

---

## 2. Data Model Reference

The UI is backed by two tables. Designers should understand the fields to ensure every data point has a place in the interface.

### 2.1 config_campaigns

| Field | Description |
|---|---|
| `campaign_id` | Unique identifier (not displayed to user; used internally). |
| `objective` | Funnel step the campaign targets. Values: **Problem Awareness**, **Brand Awareness**, **Consideration**, **Conversion**. |
| `name` | Human-readable campaign name. |

### 2.2 config_activities

| Field | Required | Description |
|---|---|---|
| `activity_id` | Yes | Unique identifier (internal). |
| `objective` | Yes | Funnel step. Same value set as campaigns. Must align with the parent campaign's objective. |
| `expected_direction` | Yes | **Increase** or **Decrease** — direction the activity is expected to drive the linked KPI. |
| `campaign_id` | Yes | Foreign key to `config_campaigns`. Shown to user as the campaign name. |
| `channel` | No | Marketing channel. Values sourced from the **config_channel_guidelines** lookup list (dynamic). |
| `platform` | No | Execution platform (e.g., Google Ads, Bing Ads, Instagram, Facebook, MailChimp). |
| `cost` | No | Dollar amount spent on the activity. |
| `start_date` | Yes | First active date. |
| `end_date` | Yes | Last active date. |
| `category` | No | Free-text grouping label. |
| `tags` | No | One or more free-text tags (comma-separated or chip-style input). |
| `owner` | No | Email of the responsible user. Values sourced from the **allowed_users** lookup list (dynamic). |
| `status` | Yes | Default: **Draft**. Possible values: Draft, Awaiting Approval, Approved, Rejected, Revision Requested, Complete. |
| `created_date` | Auto | Timestamp of creation. |
| `created_by` | Auto | Email of the creator. |
| `last_updated_at` | Auto | Timestamp of last edit. |
| `last_updated_by` | Auto | Email of last editor. |

### 2.3 Dynamic Lookup Lists

These lists are maintained outside this page and populate dropdowns in the UI:

- **config_channel_guidelines** — provides the set of valid channel values.
- **allowed_users** — provides the set of valid owner values (email addresses). Display as name where possible, with email as secondary context.

---

## 3. Page Layout

```
┌──────────────────────────────────────────────────────────┐
│  Page Header: "Calendar"            [+ Add Activity] btn │
│──────────────────────────────────────────────────────────│
│  Approval Queue (collapsible)                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Activity Card  │  Activity Card  │  Activity Card │  │
│  │  [Approve] [Reject] [Revision Requested]           │  │
│  └────────────────────────────────────────────────────┘  │
│──────────────────────────────────────────────────────────│
│  Toolbar                                                 │
│  [◀ Prev] [Today] [Next ▶]   [Filters ▼]  [Calendar|List] │
│──────────────────────────────────────────────────────────│
│  Calendar Grid (default) or List View                    │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐           │
│  │ Mon │ Tue │ Wed │ Thu │ Fri │ Sat │ Sun │  ← Week 1  │
│  │     │ ███████████████████████│     │     │  (bars)    │
│  ├─────┼─────┼─────┼─────┼─────┼─────┼─────┤           │
│  │     │     │     │     │     │     │     │  ← Week 2  │
│  ├─────┼─────┼─────┼─────┼─────┼─────┼─────┤           │
│  │     │     │     │     │     │     │     │  ← Week 3  │
│  ├─────┼─────┼─────┼─────┼─────┼─────┼─────┤           │
│  │     │     │     │     │     │     │     │  ← Week 4  │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┘           │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Approval Queue

### 4.1 Placement & Visibility

- Positioned at the top of the page, directly below the page header.
- Collapsible — the user can expand or collapse the panel. Default state: **expanded** when there are items awaiting approval, **collapsed** when empty.
- Display a badge count (e.g., "Approval Queue (3)") so the user knows how many items need attention even when collapsed.

### 4.2 Content

- Show **all** activities with `status = "Awaiting Approval"` (no user-based filtering in v1).
- Each item is displayed as a **card** showing at minimum:
  - Activity name (derived from campaign name + descriptive context)
  - Campaign name
  - Platform and/or Channel (if set)
  - Owner (if set)
  - Start date → End date
  - Date submitted for approval (`last_updated_at`)

### 4.3 Actions

Each card provides three action buttons:

| Action | Behavior | Notes |
|---|---|---|
| **Approve** | Sets `status` to `Approved`. Card is removed from the queue. | Immediate action — no confirmation modal required. |
| **Reject** | Sets `status` to `Rejected`. Card is removed from the queue. | Immediate action — no confirmation modal required. |
| **Revision Requested** | Sets `status` to `Revision Requested`. Card is removed from the queue. | **Must prompt** the reviewer with a text input modal to provide a comment or reason before confirming. The comment should be stored and visible to the activity owner. |

### 4.4 Overflow Behavior

- If more than ~5 items are awaiting approval, the queue should be horizontally scrollable (card carousel) or show a "View All" link that expands to a full list.

---

## 5. Calendar View (Default)

### 5.1 Grid Structure

- **Layout:** Weekly grid — 7 columns (Mon–Sun or Sun–Sat depending on locale) × 4 visible rows.
- **Default view:** The current week plus the following 3 weeks (4 weeks total visible on load).
- Each column header shows the day of the week and the date.
- The leftmost column of each row may optionally display the week number or date range label (e.g., "Mar 23–29").

### 5.2 Navigation

- **Previous / Next buttons** — shift the visible window by one week at a time.
- **Today button** — returns the view so that the current week is the first visible row.
- The current date cell should have a subtle highlight (e.g., ring or background tint) so the user can orient quickly.

### 5.3 Activity Rendering

- **Multi-day activities** are rendered as **horizontal bars** spanning from `start_date` to `end_date`, similar to Google Calendar's multi-day event rendering or CoSchedule's activity bars.
- If an activity spans across week boundaries, the bar should wrap to the next row and continue.
- Each bar displays the activity name (truncated with ellipsis if needed).
- Clicking or hovering on a bar opens a **detail popover / tooltip** showing key fields (see Section 8).

### 5.4 Color Coding

Activities are color-coded by **Platform**:

- Each platform is assigned a distinct color.
- **Platforms that share the same Channel should use related hues** (e.g., shades of the same base color). For example:
  - Paid Search channel → Google Ads = dark orange, Bing Ads = light orange.
  - Social channel → Facebook = dark blue, Instagram = light blue.
- If the platform field is empty, use a neutral/gray default color.
- Include a small **color legend** (toggleable or as a tooltip) so users can reference the platform-to-color mapping.

### 5.5 Density & Overflow

- If multiple activities overlap on the same day(s), stack the bars vertically within the cell.
- If more activities exist than can fit in a cell's visible area, show a "+N more" indicator that expands to show all items (similar to Google Calendar's overflow behavior).

---

## 6. List View (Alternate)

### 6.1 Toggle

- A **Calendar | List** toggle in the toolbar switches between views.
- The currently active view should be visually indicated (e.g., highlighted button).

### 6.2 Table Columns

The list view displays activities in a sortable, paginated table with the following columns:

| Column | Source Field | Notes |
|---|---|---|
| Campaign | `campaign_id` → `config_campaigns.name` | Display the campaign name. |
| Objective | `objective` | |
| Platform | `platform` | Color indicator dot matching calendar colors. |
| Channel | `channel` | |
| Start Date | `start_date` | Sortable. Default sort: ascending. |
| End Date | `end_date` | Sortable. |
| Owner | `owner` | Display name if available, email otherwise. |
| Status | `status` | Styled as a badge/pill (e.g., color-coded by status). |
| Cost | `cost` | Formatted as currency. |
| Category | `category` | |
| Tags | `tags` | Displayed as chips/pills. |

### 6.3 Interactions

- Clicking a row opens the activity detail / edit view (see Section 8).
- Column headers are clickable to sort ascending/descending.
- Pagination or infinite scroll for large datasets.

---

## 7. Filters

### 7.1 Filter Bar

- Located in the toolbar area between the Approval Queue and the Calendar/List view.
- Can be presented as a **filter dropdown panel** or an **inline filter bar** — the filter icon in the toolbar toggles visibility.
- Active filters should be shown as removable chips/pills so the user can see and clear them easily.

### 7.2 Available Filters

| Filter | Type | Source |
|---|---|---|
| **Platform** | Multi-select dropdown | Distinct values from `config_activities.platform`. |
| **Channel** | Multi-select dropdown | Values from `config_channel_guidelines` lookup list. |
| **Status** | Multi-select dropdown | Draft, Awaiting Approval, Approved, Rejected, Revision Requested, Complete. |
| **Objective** | Multi-select dropdown | Problem Awareness, Brand Awareness, Consideration, Conversion. |
| **Category** | Multi-select dropdown | Distinct values from `config_activities.category`. |
| **Owner** | Multi-select dropdown | Values from `allowed_users` lookup list. |
| **Tags** | Multi-select with type-ahead | Distinct values from `config_activities.tags`. Since tags are freeform, provide type-ahead suggestions based on previously used tags. |

### 7.3 Behavior

- Filters apply to **both** the Calendar view and the List view.
- Filters are **additive within a category** (OR logic — selecting "Google Ads" and "Bing Ads" under Platform shows activities on either platform).
- Filters are **intersecting across categories** (AND logic — selecting Platform = "Google Ads" and Status = "Approved" shows only approved Google Ads activities).
- A **"Clear All Filters"** action resets to the unfiltered state.
- Filters do **not** affect the Approval Queue — the queue always shows all "Awaiting Approval" items regardless of filter state.

---

## 8. Activity Detail / Edit View

### 8.1 Trigger

- **Calendar view:** Click on an activity bar to open the detail view.
- **List view:** Click on a table row to open the detail view.
- **Suggested pattern:** A slide-out side panel (drawer) from the right, or a modal dialog. A side panel is preferred so the user retains context of the calendar behind it.

### 8.2 Detail View Content

Display all fields from `config_activities`:

- **Campaign** (read-only link or label showing the parent campaign name)
- **Objective** (read-only — inherited from campaign alignment)
- **Expected Direction** (Increase / Decrease indicator)
- **Platform**
- **Channel**
- **Cost** (formatted as currency)
- **Start Date** and **End Date** (with visual date range indicator)
- **Category**
- **Tags** (displayed as chips)
- **Owner** (name + email)
- **Status** (styled as a badge/pill)
- **Created by** and **Created date** (metadata footer)
- **Last updated by** and **Last updated date** (metadata footer)

### 8.3 Edit Mode

- An **"Edit" button** switches the panel into edit mode, converting display fields into form inputs.
- All editable fields use appropriate input controls (see Section 9 for the form specification — the edit form mirrors the add form, pre-populated with existing values).
- **Save** commits changes and returns to detail view.
- **Cancel** discards changes and returns to detail view.
- If the user has unsaved changes and attempts to close/cancel, display a confirmation dialog: *"You have unsaved changes. Discard?"*

### 8.4 Delete

- A **"Delete" button** (styled as a destructive action — red text or icon) is available in the detail view.
- Clicking Delete triggers a **confirmation dialog**: *"Are you sure you want to delete this activity? This action cannot be undone."*
- On confirmation, the activity is removed from `config_activities` and disappears from the calendar/list.

---

## 9. Add Activity Form

### 9.1 Trigger

- The **"+ Add Activity"** button in the page header opens the form.
- **Suggested pattern:** Same side panel (drawer) used for the detail/edit view, but in a blank-form state. Alternatively, a modal dialog.

### 9.2 Form Fields

| Field | Input Type | Required | Validation / Notes |
|---|---|---|---|
| **Campaign** | Dropdown (searchable) | Yes | Populated from `config_campaigns`. Selecting a campaign auto-sets the Objective field. |
| **Objective** | Read-only display | Yes | Auto-populated based on selected campaign's objective. Not directly editable. |
| **Expected Direction** | Toggle or radio (Increase / Decrease) | Yes | |
| **Platform** | Dropdown (searchable) | No | Free list of known platforms. Allow type-ahead. |
| **Channel** | Dropdown | No | Populated from `config_channel_guidelines` lookup. |
| **Cost** | Currency input | No | Numeric with currency formatting. |
| **Start Date** | Date picker | Yes | Must be ≤ End Date. |
| **End Date** | Date picker | Yes | Must be ≥ Start Date. |
| **Category** | Text input with suggestions | No | Type-ahead from existing categories. |
| **Tags** | Chip input (multi-value) | No | Freeform text. User types a tag and presses Enter to add it as a chip. Type-ahead suggests previously used tags. |
| **Owner** | Dropdown (searchable) | No | Populated from `allowed_users` lookup. Display name + email. |
| **Status** | Dropdown | Yes | Defaults to **Draft**. Options: Draft, Awaiting Approval, Approved, Rejected, Revision Requested, Complete. |

### 9.3 Form Behavior

- **Save** validates all required fields, then creates a new row in `config_activities`. The system auto-populates `activity_id`, `created_date`, `created_by`, `last_updated_at`, and `last_updated_by`.
- **Cancel** discards the form. If any field has been filled in, show a confirmation: *"Discard this new activity?"*
- After successful save, the new activity should immediately appear in the calendar/list and (if status = "Awaiting Approval") in the Approval Queue.

---

## 10. Interaction & State Summary

### 10.1 Status Lifecycle

```
Draft → Awaiting Approval → Approved → Complete
                          → Rejected
                          → Revision Requested → (user edits) → Awaiting Approval
```

### 10.2 Status Badge Styling

Each status should have a distinct visual treatment:

| Status | Suggested Style |
|---|---|
| Draft | Gray badge |
| Awaiting Approval | Yellow/amber badge |
| Approved | Green badge |
| Rejected | Red badge |
| Revision Requested | Orange badge |
| Complete | Blue or dark-green badge with checkmark icon |

---

## 11. Responsive & Accessibility Notes

- The calendar grid should be horizontally scrollable on smaller viewports if columns cannot fit.
- All interactive elements must be keyboard-navigable.
- Color coding must not be the **sole** indicator — include text labels or icons alongside colors for accessibility (e.g., platform name on activity bars, status text inside badges).
- Ensure sufficient color contrast ratios (WCAG AA minimum).
- Tooltips and popovers should be screen-reader friendly.

---

## 12. Edge Cases & Empty States

| Scenario | Behavior |
|---|---|
| No activities exist | Show an empty state illustration with a prompt: *"No activities yet. Click '+ Add Activity' to get started."* |
| No activities match active filters | Show: *"No activities match your filters."* with a "Clear Filters" button. |
| Approval Queue is empty | Collapse the queue panel automatically. Show a subtle label: *"No items awaiting approval."* |
| Activity has no platform set | Render with a neutral/gray color bar in the calendar. |
| Activity spans more than 4 weeks | The bar continues beyond the visible window; navigation reveals the rest. |

---

## 13. Out of Scope (v1)

The following features are acknowledged but explicitly deferred:

- User-specific approval queue filtering (show only items the logged-in user can approve).
- Drag-and-drop rescheduling of activities on the calendar.
- Recurring/repeating activities.
- Activity comments or discussion threads (beyond the revision-requested reason).
- Notification system for status changes.
- Bulk actions (approve/reject multiple items at once).
- Export or print functionality.

---

## 14. Design System Notes

- Figma already has access to the existing branding guidelines — all components should follow the established design system.
- Use the existing color palette as the foundation, extending it as needed for the platform color-coding system described in Section 5.4.
- Maintain consistency with any existing page layouts and navigation patterns already defined in the Figma project.
