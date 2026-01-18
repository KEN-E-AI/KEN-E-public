---
name: notion-pm-workflow
description: |
  KEN-E product management workflow integration with Notion for tracking Releases,
  Features, User Stories, Sprints, and Session Logs. Use this skill when: (1) Starting
  a coding session to retrieve feature context and user stories, (2) Updating story
  status during development, (3) Logging progress or notes to Notion, (4) Breaking
  down stories that are too large, (5) Ending a session to record progress for
  continuity. Always read references/notion-schema.md for database IDs and valid values.
---

# KEN-E Notion PM Workflow

This skill enables Claude Code to interact with the KEN-E Product Development Notion workspace.

## Required References

**Before any Notion operation, read these files:**

1. [references/notion-schema.md](references/notion-schema.md) - Database IDs, sprint schedule, property names, valid values
2. [docs/KEN-E-Agentic-Harness-Design.md](/Users/kenwilliams/Documents/github/ken-e/docs/KEN-E-Agentic-Harness-Design.md) - Architecture decisions and technical context (read Section 12: Prioritized Feature Roadmap for story context)

## Current Sprint Context

Check `references/notion-schema.md` for the current sprint schedule. When starting a session:
- Identify which sprint the story belongs to
- Understand the sprint goal
- Note dependencies on other stories in the sprint

## Session Start Protocol

### Step 1: Check Session Continuity
Search for recent Session Logs to understand prior work:
```
notion-search:
  query: "Session"
  data_source_url: "collection://9a4b21b6-36fe-46b4-980d-2628261411e3"
```
Review the most recent session's:
- **Work Completed**: What was done
- **Next Steps**: What was planned for continuation
- **Blockers**: Any outstanding issues

### Step 2: Determine Current Sprint
Check today's date against the sprint schedule in `references/notion-schema.md`.
Fetch the current sprint to see assigned stories:
```
notion-fetch:
  id: "[Current Sprint Page ID]"
```

### Step 3: Select Work Item
Either:
- Continue work from previous session's "Next Steps"
- Ask which Feature or User Story to work on
- Suggest stories from the current sprint that are in `Backlog` status

### Step 4: Load Full Context
1. Search Notion for the story: `notion-search` with story title or ID
2. Fetch full context: `notion-fetch` on the story page
3. **Fetch the parent Feature** to understand how this story fits into the larger picture
4. Read acceptance criteria, definition of done, and related feature
5. **Read the relevant section of the architecture doc** (`docs/KEN-E-Agentic-Harness-Design.md`) for technical context

### Step 5: Create Session Log
Create a Session Log entry with:
- Today's date
- The User Story being worked on
- Sprint context (which sprint, sprint goal)
- Continuation context (if following up from previous session)
- Initial plan (bullet points)
- Repository being worked in
- Status: "In Progress"

## During Development

- Update story status to `In progress` when work begins
- If scope is too large, create child stories (see "Breaking Down Stories" below)
- Update Session Log with progress periodically
- Add blockers to Session Log if encountered

## Session End Protocol (REQUIRED)

Before ending ANY session:

1. **Update the Session Log:**
   - Work Completed: specific items finished
   - Next Steps: actionable items for next session
   - Blockers: any open questions or blockers
   - Status: "Completed" or "Blocked"

2. **Update User Story status** if appropriate:
   - `Ready for test` - code complete, needs testing
   - `Blocked` - cannot proceed
   - `Done` - fully complete and tested

3. **Add comments** to the story with any important context

## Breaking Down Large Stories

When a story is too complex for a single session:

1. Create new User Stories in Notion with titles like "X.X.X - [Child Story Name]"
2. Link them to the same parent Feature
3. Set Status to `Backlog`
4. Add Story Points estimate
5. Update parent story with note about decomposition

## Status Workflows

**User Stories:**
```
Backlog → In progress → Ready for test → Done
              ↓
           Blocked
```

**Session Logs:**
```
In Progress → Completed
     ↓
  Blocked
```

## Sprint Management

### Determining Current Sprint
Use today's date to identify the active sprint from the schedule in `references/notion-schema.md`.

### Sprint Transition
At the end of a sprint:
1. Update sprint status to `Completed`
2. Move incomplete stories to next sprint (update their Sprint relation)
3. Update next sprint status to `In progress`

### Fetching Sprint Stories
To see all stories in a sprint:
```
notion-fetch:
  id: "[Sprint Page ID from references/notion-schema.md]"
```
The response includes the User Stories relation with all assigned stories.

## Architecture Context

For technical implementation decisions, always reference:
- **docs/KEN-E-Agentic-Harness-Design.md** - Overall architecture, agent design, MCP server structure
- Section 3: Context Management Strategy - For stories related to context loading
- Section 4: Agent Definitions - For stories related to agents
- Section 5: MCP Server Architecture - For stories related to tool integration
- Section 12: Prioritized Feature Roadmap - Complete feature and story definitions

## Key Operations Reference

See [references/notion-schema.md](references/notion-schema.md) for:
- All database IDs
- Current release roadmap and page IDs
- Sprint schedule with page IDs
- Feature list with page IDs
- Property names and valid values
- Example MCP tool calls
- Data validation rules
