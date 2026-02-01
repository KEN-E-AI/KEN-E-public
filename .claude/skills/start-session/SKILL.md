---
name: start-session
description: |
  Start a new development session for a MER-E or KEN-E user story. This skill automatically
  gathers all context needed to work on a user story: fetches the story hierarchy (Story →
  Feature → Release → Sprint), reads relevant design document sections, reviews previous
  session logs, explores related code, creates an implementation plan, and creates a new
  Session Log entry.

  Use this skill at the beginning of any coding session to ensure comprehensive context.
user-invocable: true
---

# Start Session

This skill automates the Session Start Protocol. It gathers comprehensive context for a user story, creates an implementation plan, and prepares you to begin development.

## Session Lifecycle

This skill is the first of three skills that manage a development session:

1. **`/start-session`** — (you are here) Gather context, plan, and begin development
2. **`/run-tests`** — Run the testing phase when development is complete
3. **`/end-session`** — Close the session, update logs, commit and push code

## What This Skill Does

When invoked, this skill will:

1. **Ask for the story** - Prompt you to identify the User Story to work on
2. **Gather all context** - Delegate to the `session-context` agent to fetch the full story hierarchy, dependencies, design doc sections, previous sessions, and related code
3. **Manage Git branch** - Create or switch to the feature branch
4. **Create implementation plan** - Build a comprehensive, ordered plan from the gathered context
5. **Validate the plan** - Analyze similar codebase patterns to ensure consistency, minimal changes, and code reuse
6. **Create a Session Log** - Document the plan for this session in Notion
7. **Update story status** - Set the User Story to "In progress"
8. **Present the summary** - Give you everything you need to start

## How to Use

Simply invoke `/start-session` and follow the prompts:

```
/start-session
```

Or provide the story ID directly:

```
/start-session 1.1.1
```

## Workflow Steps (Detailed)

### Step 1: Identify the Story

Ask the developer:
- Which product? (KEN-E or MER-E)
- Which story? (by ID like "1.1.1" or by searching for keywords)

### Step 2: Gather Context (DELEGATE to session-context agent)

**Use the `Task` tool with `subagent_type: "session-context"`** to gather all context in parallel. Pass the story identifier and product name to the agent.

The session-context agent will:
- Find the story in Notion
- Fetch the full hierarchy: Story → Feature → Release → Sprint
- Check dependencies and blockers
- Read relevant design document sections (using the design-doc-mapping)
- Review previous Session Logs for this story
- Explore the codebase for related modules, test patterns, and similar implementations
- Return a structured "Session Context Summary"

**Why delegate?** The session-context agent is a read-only research specialist that can gather all this context efficiently without consuming main conversation context with the full 285KB+ design document and multiple Notion page fetches.

**Example Task call:**
```
Task(
  subagent_type="session-context",
  prompt="Gather session context for MER-E story 1.1.1",
  description="Gather session context"
)
```

The agent returns a structured summary including:
- Story details (title, AC, DoD, points, priority)
- Feature details (benefit hypothesis, functional groups)
- Release and Sprint context
- Dependencies and their status
- Design document key details
- Previous session summaries
- Related code modules and patterns
- Suggested implementation approach
- Expected git branch name

### Step 3: Manage Git Branch

Using the Feature ID and name from the context summary:

1. **Determine branch name** from the Feature:
   - Format: `feature/{feature-id}-{feature-name-slug}`
   - Example: `feature/1.1-evaluation-results-module`

2. **Check if branch exists:**
   ```bash
   git fetch origin
   git branch -a --list "*feature/{feature-id}*"
   ```

3. **If branch exists:** Switch to it
   ```bash
   git checkout feature/X.X-feature-name
   git pull origin feature/X.X-feature-name
   ```

4. **If branch doesn't exist:** Create from main
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/X.X-feature-name
   ```

5. **Report branch status** to the developer

### Step 4: Create Implementation Plan

Using the context summary from the session-context agent, build a comprehensive implementation plan:

1. **Review the Acceptance Criteria** — each criterion maps to one or more implementation tasks
2. **Review the Definition of Done** — ensure every DoD item is addressed
3. **Review the Suggested Implementation Approach** from the session-context agent
4. **Review previous session "Next Steps"** — incorporate any carryover work
5. **Order tasks logically** — dependencies between tasks determine sequence
6. **Include test tasks** — each functional task should have associated test work

The plan should be a numbered list of concrete, actionable steps. Each step should reference the specific files to create or modify.

### Step 5: Validate the Plan Against the Codebase

Before finalizing, validate the implementation plan for quality and consistency:

1. **Analyze similar implementations** — Find existing code in the codebase that does something similar to what the plan proposes. Use the `Task` tool with `subagent_type: "Explore"` if needed to search for patterns.

2. **Check consistency** — Ensure the plan:
   - Follows the same patterns, naming conventions, and code organization as the rest of the codebase
   - Uses the same libraries, utilities, and abstractions already established
   - Follows the project's existing test patterns and structure
   - Matches the architectural style described in CLAUDE.md

3. **Minimize changes** — Ensure the plan:
   - Does not introduce unnecessary abstractions or over-engineering
   - Does not duplicate functionality that already exists
   - Makes the smallest set of changes needed to satisfy the Acceptance Criteria
   - Avoids modifying files or modules outside the story's scope

4. **Maximize code reuse** — Ensure the plan:
   - Leverages existing utility functions, base classes, and shared modules
   - Extends existing patterns rather than creating new ones
   - References specific existing implementations to use as templates

5. **Revise the plan** if any issues are found in steps 1-4. Present the final plan to the developer.

**If the design-doc-researcher agent is needed** for clarifying specific design questions during validation, use:
```
Task(
  subagent_type="design-doc-researcher",
  prompt="[Specific question about design requirements]",
  description="Research design doc"
)
```

### Step 6: Create Session Log

Create a new Session Log entry in Notion:

```
notion-create-pages:
  parent:
    data_source_id: "2f230fd6-5302-805e-8885-000c8043ddd5"
  pages:
    - properties:
        Name: "Session - [Story Title] - [YYYY-MM-DD]"
        date:Session Date:start: "[YYYY-MM-DD]"
        date:Session Date:is_datetime: 1
        User Story: "[Story Page URL]"
        Product: "[Product Page URL]"
        Plan: "[The implementation plan from Step 4]"
        Status: "In Progress"
        Repository: "MER-E"
```

### Step 7: Update Story Status

Set the User Story status to "In progress" if it was in "Backlog":

```
notion-update-page:
  data:
    page_id: "[Story page ID]"
    command: "update_properties"
    properties:
      Status: "In progress"
```

### Step 8: Present Summary

Present the complete context and plan to the developer. Use this format:

```
## Session Context Summary

### User Story: [ID] - [Title]
**Priority:** [Priority] | **Points:** [Points] | **Status:** [Status]

**User Story:**
[As a... I want... So that...]

**Acceptance Criteria:**
[Given/When/Then items]

### Feature: [ID] - [Title]
**Benefit Hypothesis:** [Text]

**Functional Groups:**
[List of functional groups]

### Release: [Number] - [Title]
**Goal:** [Release goal]

### Sprint: [Name] (if assigned)
**Goal:** [Sprint goal]
**Dates:** [Start] - [End]

### Design Document Sections
**Primary:** [Section numbers and titles]
**Supporting:** [Section numbers and titles]

### Previous Sessions
[Summary of prior work, or "No previous sessions found"]

### Dependencies
[List of dependent stories with their status, or "None"]

### Git Branch
**Branch:** `feature/[feature-id]-[feature-name-slug]`
**Status:** [Created new branch / Switched to existing branch]

### Implementation Plan
1. [Step 1 — files involved]
2. [Step 2 — files involved]
3. [Step 3 — files involved]
...

### Session Log Created
Session - [Story Title] - [YYYY-MM-DD]

### Session Lifecycle
When development is complete, run `/run-tests` to execute the testing phase.
When ready to close the session, run `/end-session` to update logs and commit.
```

## Breaking Down Large Stories

If the story is too complex for a single session:

1. **Create new User Stories** in Notion with titles like "X.X.X.a - [Child Story Name]"
2. **Link them to the same parent Feature**
3. **Set the Product relation** to match the parent story (KEN-E or MER-E)
4. **Set Status** to `Backlog`
5. **Add Story Points** estimate
6. **Update parent story** with note about decomposition
7. **Update Session Log** to document the breakdown decision

## Error Handling

If the skill encounters issues:
- **Story not found:** Prompts for clarification or alternative search terms
- **session-context agent fails:** Fall back to manual context gathering using Notion MCP tools
- **Missing Feature/Release:** Notes the gap and continues with available context
- **Design doc section not found:** Notes and suggests checking the mapping
- **No previous sessions:** Notes this is the first session for this story

## Related Skills

- `/run-tests` - Run the testing phase (test plan, programmatic tests, manual checklist)
- `/end-session` - Close the session (design changes, session log, git, PR check)

## References

- [notion-schema.md](../notion-pm-workflow/references/notion-schema.md) - Database IDs
- [design-doc-mapping.md](../notion-pm-workflow/references/design-doc-mapping.md) - Feature to section mapping
- [design-change-workflow.md](../notion-pm-workflow/references/design-change-workflow.md) - Design change process
