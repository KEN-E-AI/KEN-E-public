# KEN-E Notion Database Schema Reference

## Database IDs

| Database | Database ID | Data Source ID |
|----------|-------------|----------------|
| Releases | `1c130fd653028078b55ecfef294a0c5c` | `1c130fd6-5302-80b9-9ea5-000b8b9b655f` |
| Features | `1ba30fd6530280f98ff2f9b91bf8d588` | `1ba30fd6-5302-8093-877f-000b545e5e3f` |
| User Stories | `1ba30fd6530280c8be86fbe0b85f09ca` | `1ba30fd6-5302-8000-9407-000b4fe01ba7` |
| Sprints | `1ba30fd653028072b0edcd90ee8748be` | `1ba30fd6-5302-80ed-9373-000bee60c1b9` |
| Session Logs | `d83fc5bae1db403ea1294a87ea71dff0` | `9a4b21b6-36fe-46b4-980d-2628261411e3` |

---

## Current Release Roadmap

| Release | Page ID | Description |
|---------|---------|-------------|
| 1.0 - Foundation | `2ec30fd6-5302-813e-a35d-f3614c2c24a2` | Core infrastructure (Context Manager, Tool Registry, MCP Manager, Session Service, Web Channel, Primary Orchestrator, Basic Monitoring) |
| 2.0 - Prepare MVP | `2ec30fd6-5302-81b6-87b7-c03f818a5b1b` | Production readiness with billing and subscription management |
| 3.0 - Core Agents | `2ec30fd6-5302-81d0-9bd7-c2a7dfb688db` | Specialist AI agents, Slack integration, Workflow Manager |
| 4.0 - Automation | `2ec30fd6-5302-81f6-8774-fd0151eb5183` | n8n Integration, Scheduled Workflows, Content Calendar |
| 5.0 - Advanced | `2ec30fd6-5302-81cc-ab41-e11fbeabd404` | Voice Channel, A/B Testing, Self-Optimization |

## Release 1 Sprint Schedule

| Sprint | Page ID | Dates | Goal | Points |
|--------|---------|-------|------|--------|
| Sprint 1 | `2ec30fd6-5302-81ce-95e3-c2c82a63f6a3` | Jan 19 - Feb 1, 2026 | Context & Sessions | 13 |
| Sprint 2 | `2ec30fd6-5302-8175-9b8b-de0abfe23732` | Feb 2 - Feb 15, 2026 | Context & Tool Registry | 14 |
| Sprint 3 | `2ec30fd6-5302-8199-af55-d3f0c2c5fa06` | Feb 16 - Mar 1, 2026 | Tool Security & MCP Foundation | 13 |
| Sprint 4 | `2ec30fd6-5302-81e5-97fe-c4fa8118a147` | Mar 2 - Mar 15, 2026 | MCP Completion & Session Features | 14 |
| Sprint 5 | `2ec30fd6-5302-8131-8402-e651a60f2dfd` | Mar 16 - Mar 29, 2026 | Web UI Foundation | 13 |
| Sprint 6 | `2ec30fd6-5302-8151-971e-fb64b9c60cef` | Mar 30 - Apr 12, 2026 | Web UI Completion | 14 |
| Sprint 7 | `2ec30fd6-5302-8138-be00-f964011ecf87` | Apr 13 - Apr 26, 2026 | Orchestrator | 15 |
| Sprint 8 | `2ec30fd6-5302-8128-b302-ca19fc2aaada` | Apr 27 - May 10, 2026 | Integration & Polish | 6 |

## Release 1 Features

| Feature | Page ID | Stories |
|---------|---------|---------|
| 1.1 - Context Manager | `2ec30fd6-5302-81a4-93a9-e8a6da8229a0` | 4 |
| 1.2 - Tool Registry | `2ec30fd6-5302-81bc-97de-ed7e565540ce` | 4 |
| 1.3 - MCP Manager | `2ec30fd6-5302-810a-ae7a-e6a4f0dfdb25` | 4 |
| 1.4 - Session Service | `2ec30fd6-5302-812e-8996-d335892cbe98` | 4 |
| 1.5 - Web Channel | `2ec30fd6-5302-8162-a294-dff9119b64fa` | 4 |
| 1.6 - Primary Orchestrator | `2ec30fd6-5302-81b3-b3fb-e216982890f7` | 4 |
| 1.7 - Basic Monitoring | `2ec30fd6-5302-817a-9a2c-df7a4061e829` | 4 |

---

## Database Relationships

```
Releases (1) ────> (many) Features
Features (1) ────> (many) User Stories
Features (many) <───> (many) Sprints
User Stories (many) <───> (many) Sprints
Session Logs (many) ───> (1) User Story
```

---

## 1. Releases Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | e.g., "1.0 - MVP", "2.0 - The Report Builder" |
| Description | rich_text | - |
| Release Date | date | ISO-8601 format |
| Features | relation | Links to Features |

---

## 2. Features Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | e.g., "1.1. Create Strategy Docs" |
| Description | rich_text | - |
| Status | select | `In development`, `Planned`, `Backlog` |
| Priority | select | `🔴 High`, (empty = normal) |
| User Stories | relation | Links to User Stories |
| Sprints | relation | Links to Sprints |
| Owner | person | - |
| Release Date | date | ISO-8601 format |
| Releases | relation | Links to Releases |

---

## 3. User Stories Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Title | title | e.g., "1.1.1 - Automated Strategy Generation" |
| User Story | rich_text | "As a [persona], I want [action], So that [benefit]" |
| Status | status | `Backlog`, `In progress`, `Ready for test`, `Blocked`, `Done` |
| Priority | select | `🟢 Low`, `🟡 Medium`, `🔴 High` |
| Story Points | number | - |
| Assigned To | person | - |
| Acceptance Criteria | rich_text | Given/When/Then format |
| Definition of Done | rich_text | Verification checklist |
| Features | relation | Links to parent Feature |
| Sprints | relation | Links to Sprint(s) |
| Repository | select | GitHub repository name |

---

## 4. Sprints Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Sprint Name | title | e.g., "Sprint 1" |
| Sprint Number | number | - |
| Start Date | date | ISO-8601 format |
| End Date | date | ISO-8601 format |
| Status | select | `In progress` |
| User Stories | relation | Links to User Stories |
| Sprint Goal | rich_text | - |
| Velocity (Story Points) | number | - |
| Team Members | person | - |
| Retrospective Notes | rich_text | - |

---

## 5. Session Logs Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | Session identifier |
| Session Date | date | ISO-8601 datetime |
| Developer | person | - |
| User Story | relation | Links to User Story being worked on |
| Plan | rich_text | What was planned for this session |
| Work Completed | rich_text | What was actually completed |
| Next Steps | rich_text | Actionable items for next session |
| Blockers | rich_text | Any blockers or open questions |
| Status | select | `In Progress`, `Completed`, `Blocked` |
| Repository | rich_text | GitHub repository being worked on |

---

## MCP Tool Operations

### Search for a User Story

```
notion-search:
  query: "1.1.1" (or story title)
  query_type: "internal"
```

### Fetch Story Details

```
notion-fetch:
  id: "[page_id or URL]"
```

### Update Story Status

```
notion-update-page:
  data:
    page_id: "[User Story page ID]"
    command: "update_properties"
    properties:
      Status: "In progress"  # or "Ready for test", "Blocked", "Done"
```

### Create Session Log

```
notion-create-pages:
  parent:
    data_source_id: "9a4b21b6-36fe-46b4-980d-2628261411e3"
  pages:
    - properties:
        Name: "Session - [Story Title] - [Date]"
        date:Session Date:start: "2025-01-15"
        date:Session Date:is_datetime: 1
        Plan: "1. [First task]\n2. [Second task]"
        Status: "In Progress"
        Repository: "[repo-name]"
```

### Update Session Log

```
notion-update-page:
  data:
    page_id: "[Session Log page ID]"
    command: "update_properties"
    properties:
      Work Completed: "- Completed X\n- Completed Y"
      Next Steps: "- Do A\n- Do B"
      Status: "Completed"
```

### Create New User Story

```
notion-create-pages:
  parent:
    data_source_id: "1ba30fd6-5302-8000-9407-000b4fe01ba7"
  pages:
    - properties:
        Title: "1.X.X - [Story Name]"
        User Story: "As a [persona], I want [action], So that [benefit]."
        Status: "Backlog"
        Acceptance Criteria: "1. Given [context], When [action], Then [result]."
        Definition of Done: "• Verify that..."
        Repository: "[repo-name]"
```

### Add Comment to Story

```
notion-create-comment:
  parent:
    page_id: "[User Story page ID]"
  rich_text:
    - type: "text"
      text:
        content: "Session completed. Ready for testing."
```

### Add Testing Notes to Story

```
notion-update-page:
  data:
    page_id: "[User Story page ID]"
    command: "insert_content_after"
    selection_with_ellipsis: "Definition of Done..."
    new_str: "\n\n## Testing Notes\n- [Note 1]\n- [Note 2]"
```

---

## Data Validation Rules

1. **Status values must match exactly** (case-sensitive)
2. **Priority uses emoji prefix:** `🟢 Low`, `🟡 Medium`, `🔴 High`
3. **Dates use ISO-8601 format:** `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`
4. **Date properties require expanded format:**
   - `date:Session Date:start`: The date value
   - `date:Session Date:end`: Optional end date for ranges
   - `date:Session Date:is_datetime`: 1 for datetime, 0 for date only
5. **Relations use page IDs**, not names
6. **Title/Name properties are required** for all new pages
