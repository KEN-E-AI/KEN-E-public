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

**Before any Notion operation:** Read [references/notion-schema.md](references/notion-schema.md) for database IDs, property names, and valid values.

## Session Start Protocol

1. Ask which Feature or User Story to work on
2. Search Notion for the story: `notion-search` with story title or ID
3. Fetch full context: `notion-fetch` on the story page
4. Read acceptance criteria, definition of done, and related feature
5. Create a Session Log entry with:
   - Today's date
   - The User Story being worked on
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

## Key Operations Reference

See [references/notion-schema.md](references/notion-schema.md) for:
- All database IDs
- Property names and valid values
- Example MCP tool calls
- Data validation rules
