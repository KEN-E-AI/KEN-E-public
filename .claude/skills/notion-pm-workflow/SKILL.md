---
name: notion-pm-workflow
description: |
  Reference documentation for the Notion PM workflow. This skill is NOT user-invocable.
  Use the three session lifecycle skills instead:
  - /start-session — Gather context and begin development
  - /run-tests — Run the testing phase
  - /end-session — Close the session, update logs, commit and push code

  This directory contains shared reference files used by all three skills.
---

# Notion PM Workflow (Reference Only)

This skill has been superseded by three dedicated session lifecycle skills. **Do not invoke this skill directly.**

## Use These Skills Instead

| Skill | When to Use |
|-------|-------------|
| `/start-session` | Beginning of a coding session — gathers context, creates plan, sets up git branch |
| `/run-tests` | After development is complete — creates test plan, runs tests, determines status |
| `/end-session` | End of session — updates logs, commits code, checks for PR creation |

## Reference Files

This directory contains shared reference files used by all three skills:

| File | Purpose |
|------|---------|
| [notion-schema.md](references/notion-schema.md) | Database IDs, property names, valid values, MCP examples |
| [design-doc-mapping.md](references/design-doc-mapping.md) | Maps Features to design document sections and line ranges |
| [design-change-workflow.md](references/design-change-workflow.md) | Design change propagation and impact classification |

## Status Workflows

**User Stories:**
```
Backlog → In progress → Testing Phase
              ↓              ├── All tests programmatic → Done
           Blocked           └── Manual tests needed → Ready for test
                                                            ↓
                                                     (Human completes)
                                                            ↓
                                                          Done
```

**Session Logs:**
```
In Progress → Completed
     ↓
  Blocked
```

## Git Branch Strategy

```
feature/{feature-id}-{feature-name-slug}
```

**Branch Lifecycle:**
```
main
  └── feature/1.1-evaluation-results-module  (created when first story starts)
        ├── commit: Story 1.1.1 work
        ├── commit: Story 1.1.2 work
        └── commit: Story 1.1.3 work
              └── PR created when all feature stories in sprint are Done
                    └── Merged to main
```

## Breaking Down Large Stories

When a story is too complex for a single session:

1. **Create new User Stories** in Notion with titles like "X.X.X.a - [Child Story Name]"
2. **Link them to the same parent Feature**
3. **Set the Product relation** to match the parent story (KEN-E or MER-E)
4. **Set Status** to `Backlog`
5. **Add Story Points** estimate
6. **Update parent story** with note about decomposition
7. **Update Session Log** to document the breakdown decision

## Quick Context Commands

### Create Design Decision

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
