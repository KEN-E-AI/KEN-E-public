---
name: end-session
description: |
  End a development session. Checks for design changes, updates the Session Log and
  story status, commits and pushes code, checks if a PR should be created, and
  presents a session summary. Use when you are done working for the session.
user-invocable: true
---

# End Session

This skill implements the Session End Protocol from the notion-pm-workflow skill. It ensures all session artifacts are properly updated, code is committed, and the session is closed cleanly.

## What This Skill Does

When invoked, this skill will:

1. **Check test status** - Verify that `/run-tests` has been run
2. **Check for design changes** - Ask about architectural or schema changes
3. **Update the Session Log** - Record work completed, next steps, blockers
4. **Update story status** - Based on test results
5. **Check downstream dependencies** - Notify dependent stories if applicable
6. **Add comments to the story** - Key decisions and context for reviewers
7. **Clean up temporary test artifacts** - Delete MANUAL_TESTING_GUIDE.md and run cleanup scripts
8. **Git commit and push** - Stage, commit, and push to feature branch
9. **Check for feature completion** - Create a PR if all sprint stories are Done
10. **Present session summary** - Final report of everything accomplished

## How to Use

Run when you are done working for the session:

```
/end-session
```

## Prerequisites

Before running `/end-session`, you should have:
- Completed development work on the story
- Run `/run-tests` at least once with all programmatic tests passing

If `/run-tests` has not been run, this skill will prompt you to run it first.

## Workflow Steps (Detailed)

### Step 1: Check Test Status

Ask the developer:
- Has `/run-tests` been run this session?
- Did all programmatic tests pass?
- What is the recommended status from the test run? (Done / Ready for test)

If tests have NOT been run or are failing:
- Prompt the developer to run `/run-tests` first
- Do NOT proceed with closing the session until tests pass

If the developer explicitly wants to close without passing tests (e.g., work is incomplete):
- Proceed, but set story status to "In progress" (not Done or Ready for test)

### Step 2: Design Change Check

Ask the developer: **Did any design changes occur during this session?**

Design changes include:
- Data model changes (new fields, changed types, modified relationships)
- API changes (new endpoints, changed contracts, changed request/response formats)
- Behavioral changes (different processing flow, error handling)
- Technology changes (different libraries, infrastructure)
- Constraint changes (performance, security requirements)

**If NO design changes:** Skip to Step 3.

**If YES:** Follow the design change propagation workflow:

1. **Classify the change:**

   | Impact Level | Scope | Examples |
   |-------------|-------|---------|
   | Low | Current story only | Algorithm choice, library selection |
   | Medium | Current story + siblings | Adding/removing acceptance criteria |
   | High | Feature + downstream features | New API endpoint, data model change |
   | Critical | Multiple releases | Technology change, pattern change |

2. **For Medium+ impact, create a Design Decision record:**

   ```
   notion-create-pages:
     parent:
       data_source_id: "a88ce7c8-1ebb-4634-a422-2c1abcd2daf9"
     pages:
       - properties:
           Title: "[Brief decision title]"
           date:Decision Date:start: "[YYYY-MM-DD]"
           date:Decision Date:is_datetime: 0
           Context: "[Why this decision was needed]"
           Decision: "[What was decided]"
           Alternatives Considered: "[Other options]"
           Consequences: "[Impact on the system]"
           Status: "Accepted"
           Impact Level: "[Low/Medium/High/Critical]"
   ```

3. **Identify and update affected stories:**
   - Use the feature dependency table in [design-change-workflow.md](../notion-pm-workflow/references/design-change-workflow.md)
   - Add a comment to each affected story:

   ```
   notion-create-comment:
     parent:
       page_id: "[Affected Story page ID]"
     rich_text:
       - type: "text"
         text:
           content: "⚠️ DESIGN CHANGE: This story is affected by [Decision Title].\n\nImpact: [How this story needs to change]"
   ```

4. **For High/Critical changes, update the design document:**
   - Read [design-doc-mapping.md](../notion-pm-workflow/references/design-doc-mapping.md) to find affected sections
   - Update `docs/MER-E_Design.md` at the relevant line ranges

### Step 3: Update the Session Log

Fetch the Session Log created by `/start-session` (search Notion for today's session log on this story).

Update the Session Log with:

```
notion-update-page:
  data:
    page_id: "[Session Log page ID]"
    command: "update_properties"
    properties:
      Work Completed: "- Completed X\n- Completed Y\n- ⚠️ DESIGN CHANGE: [if applicable]"
      Next Steps: "- Do A\n- Do B"
      Blockers: "- [Any blockers, or 'None']"
      Status: "Completed"
```

Set Session Log Status to:
- `Completed` — Normal session end
- `Blocked` — Session ended due to a blocker

### Step 4: Update Story Status

Based on the test results from `/run-tests`:

| Condition | Status |
|-----------|--------|
| All programmatic tests pass, no manual tests | `Done` |
| All programmatic tests pass, manual tests remain | `Ready for test` |
| Development work incomplete | `In progress` |
| Cannot proceed due to external issue | `Blocked` |

```
notion-update-page:
  data:
    page_id: "[Story page ID]"
    command: "update_properties"
    properties:
      Status: "[Determined status]"
```

**Key rules:**
- NEVER set status to "Done" if manual tests remain uncompleted
- NEVER set status to "Ready for test" if programmatic tests haven't passed
- ALWAYS run `/run-tests` before setting Done or Ready for test

### Step 5: Check Downstream Dependencies

If the story status is being set to "Done":

1. Fetch the story's **Dependencies** relation (stories that depend on THIS story)
2. For each dependent story:
   - Add a comment noting what capabilities are now available:

   ```
   notion-create-comment:
     parent:
       page_id: "[Dependent Story page ID]"
     rich_text:
       - type: "text"
         text:
           content: "✅ Dependency completed: [Story ID] - [Story Title]\n\nNow available: [Brief description of what this story provides]"
   ```

   - If the dependent story was "Blocked" by this story, consider updating its status to "Backlog"

### Step 6: Add Comments to the Story

If there are important notes for the next developer or reviewer, add a comment to the story:

```
notion-create-comment:
  parent:
    page_id: "[Story page ID]"
  rich_text:
    - type: "text"
      text:
        content: "## Session Notes - [YYYY-MM-DD]\n\n### Key Decisions\n- [Decision 1]\n- [Decision 2]\n\n### Areas Needing Attention\n- [Area 1]\n\n### What's Ready for Downstream\n- [Capability 1]"
```

Skip this step if there are no noteworthy decisions or context to share.

### Step 7: Clean Up Temporary Test Artifacts

Before committing, remove any temporary files created during the testing phase:

1. **Delete the Manual Testing Guide** (created by `/run-tests`):
   ```bash
   find packages/ -name "MANUAL_TESTING_GUIDE.md" -delete
   ```

2. **Run any cleanup scripts** referenced in the guide (e.g., seed data cleanup) if they haven't been run already.

These files are session-specific artifacts that should not be committed to the repository.

### Step 8: Git Commit and Push

Check for uncommitted changes:

```bash
git status
```

If there are changes to commit:

1. **Review what's being committed:**
   ```bash
   git diff --stat
   git diff --cached --stat
   ```

2. **Stage changes:**
   ```bash
   git add [specific files]
   ```

3. **Commit with conventional commit format:**
   ```bash
   git commit -m "feat(feature-name): description of changes

   - Detail 1
   - Detail 2

   Refs: Story X.X.X

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
   ```

4. **Push to remote:**
   ```bash
   git push -u origin feature/X.X-feature-name
   ```

### Step 9: Check for Feature Completion

Determine if a Pull Request should be created:

1. **Fetch the parent Feature** from Notion
2. **Fetch the current Sprint** (if assigned)
3. **Check all stories in the Feature for the current Sprint:**
   - Are ALL of them "Done"?

4. **If ALL stories are Done, create a PR:**

   ```bash
   gh pr create \
     --title "feat: Feature X.X - Feature Name" \
     --body "## Summary
   Implements Feature X.X - [Feature Name]

   ### Completed Stories
   - [x] X.X.1 - Story 1 title
   - [x] X.X.2 - Story 2 title
   - [x] X.X.3 - Story 3 title

   ### Changes
   - [List key changes]

   ### Testing
   - All programmatic tests pass
   - [Manual testing status if applicable]

   ### Notion Links
   - Feature: [Link to Feature page]
   - Sprint: [Link to Sprint page]

   ---
   Generated with Claude Code" \
     --base main
   ```

5. **Report the PR URL** to the developer

6. **Add a comment to the Feature page:**

   ```
   notion-create-comment:
     parent:
       page_id: "[Feature page ID]"
     rich_text:
       - type: "text"
         text:
           content: "PR Created: [PR URL]\n\nAll Sprint [N] stories complete. Ready for review."
   ```

**If NOT all stories are Done:** Skip PR creation and note which stories remain.

### Step 10: Present Session Summary

Present a comprehensive summary:

```
## Session Summary

### Work Completed
- [Item 1]
- [Item 2]
- [Item 3]

### Test Results
- Programmatic: [N] passed, [M] failed
- Manual tests: [K] identified / None
- Recommended status: [Done / Ready for test]

### Story Status
**[Story ID] - [Story Title]:** [Status] → [New Status]
[Reason for status]

### Design Decisions
- [Decision title and impact, or "None"]

### Session Log
Updated: [Session Log title]
Status: [Completed / Blocked]

### Git
- Branch: `feature/X.X-feature-name`
- Commits: [N] new commits
- Pushed: Yes / No

### Pull Request
- [PR URL if created, or "Not yet — [N] stories remaining in this feature"]

### Next Steps
- [Item 1]
- [Item 2]
```

## Error Handling

- **Session Log not found:** Search by story title and today's date. If still not found, note the gap and continue.
- **Story not found in Notion:** Ask the developer for the story page ID directly.
- **Git push fails:** Report the error and suggest manual resolution.
- **PR creation fails:** Report the error and provide the `gh pr create` command for manual execution.

## Session Lifecycle

This skill is part of the development session lifecycle:

1. `/start-session` — Gather context and begin development
2. `/run-tests` — Test the implementation
3. **`/end-session`** — (you are here) Close the session

## Notion Database Reference

| Database | Data Source ID |
|----------|----------------|
| User Stories | `1ba30fd6-5302-8000-9407-000b4fe01ba7` |
| Session Logs | `2f230fd6-5302-80b3-a026-000be20a8517` |
| Design Decisions | `a88ce7c8-1ebb-4634-a422-2c1abcd2daf9` |
| Features | `1ba30fd6-5302-8093-877f-000b545e5e3f` |
| Sprints | `1ba30fd6-5302-80ed-9373-000bee60c1b9` |

## References

- [notion-schema.md](../notion-pm-workflow/references/notion-schema.md) - Database IDs and property schemas
- [design-change-workflow.md](../notion-pm-workflow/references/design-change-workflow.md) - Design change propagation
- [design-doc-mapping.md](../notion-pm-workflow/references/design-doc-mapping.md) - Feature to design doc section mapping
- [notion-pm-workflow](../notion-pm-workflow/SKILL.md) - Full workflow reference
