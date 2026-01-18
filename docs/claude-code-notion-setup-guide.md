# Claude Code + Notion Integration

## Developer Setup & Usage Guide

*KEN-E Product Development Team*

---

## Overview

This guide explains how to configure Claude Code to work with our Notion workspace for product development. Once set up, Claude Code will be able to:

- **Understand sprint context** - Know which sprint is active and what stories are planned
- **Continue from prior sessions** - Review previous session logs for continuity
- **Retrieve feature and story context** - Load acceptance criteria and architecture references
- **Update story status** during development
- **Log session progress** for continuity between sessions
- **Create new user stories** when scope is too large
- **Reference architecture decisions** from the design documentation

---

## Prerequisites

- Claude Code installed and configured
- Access to the KEN-E Notion workspace
- Node.js installed (for MCP setup)

---

## Setup Instructions

### Step 1: Configure the Notion MCP Connection

Run this command in your terminal to add the Notion MCP server:

```bash
claude mcp add --transport http notion --scope project https://mcp.notion.com/mcp
```

This creates a `.mcp.json` file in your repository that configures the Notion connection for all team members.

### Step 2: Authenticate with Notion

The first time you use Claude Code in a repository with the Notion MCP configured:

1. Start Claude Code in your repository
2. Type `/mcp` and press Enter
3. Select the Notion MCP from the list
4. A browser window will open for OAuth authentication
5. Sign in with your Notion account and authorize access

You only need to do this once per machine. Your authentication persists across sessions.

### Step 3: Verify the PM Workflow Skill

The skill files should already be in your repository at:

```
.claude/skills/notion-pm-workflow/
├── skill.md                      # Workflow instructions for Claude Code
└── references/
    └── notion-schema.md          # Database IDs, sprint schedule, property definitions
```

The skill references the architecture document at `docs/KEN-E-Agentic-Harness-Design.md` for technical context.

---

## Daily Workflow

### Starting a Coding Session

When you begin work, invoke the skill or simply tell Claude Code you're starting:

```
"/notion-pm-workflow"
```

Or:

```
"I'm starting a coding session"
```

Claude Code will automatically:

1. **Check session continuity** - Search recent Session Logs to show what was worked on previously, including:
   - Work completed in the last session
   - Next steps that were planned
   - Any outstanding blockers

2. **Determine the current sprint** - Based on today's date, identify which sprint is active and fetch its stories

3. **Suggest work items** - Either:
   - Continue from the previous session's "Next Steps"
   - Suggest stories from the current sprint in `Backlog` status
   - Ask which story you want to work on

4. **Load full context** once you select a story:
   - Fetch the story details (acceptance criteria, definition of done)
   - Fetch the parent Feature for broader context
   - Reference the relevant architecture section from the design doc

5. **Create a Session Log** with sprint context and your initial plan

### Example: Starting Fresh

```
"I'm starting a new session. What should I work on?"
```

Claude Code responds with:
- Summary of last session's work and next steps
- Current sprint info (e.g., "Sprint 1: Context & Sessions, Jan 19 - Feb 1")
- Stories available in the current sprint

### Example: Continuing Previous Work

```
"Continue where I left off"
```

Claude Code will:
- Find your last Session Log
- Show what you completed and what was planned next
- Load the story context and create a new Session Log

### Example: Picking a Specific Story

```
"I'm picking up story 1.1.1 - Organization Context Loading"
```

Claude Code will:
- Fetch the story from Notion
- Show acceptance criteria and definition of done
- Load the Context Manager feature context
- Reference Section 3 of the architecture doc (Context Management Strategy)
- Create a Session Log

### During Development

You can ask Claude Code to update Notion at any time:

- `"Update the story status to Blocked - waiting on API credentials"`
- `"Add a comment to the story: Discovered we need a new endpoint"`
- `"This story is too big. Break it into smaller stories."`
- `"Update my session log: completed the Firestore integration"`

### Ending a Session

Before you stop working, tell Claude Code to log your progress:

```
"End session. Completed the authentication middleware and unit tests.
Next: integration tests and error handling. No blockers."
```

Claude Code will:
- Update the Session Log with work completed and next steps
- Update story status if appropriate (e.g., "Ready for test")
- Mark the Session Log as "Completed"

> **Important:** Always end your session properly so the next developer (or future you) can pick up where you left off.

---

## Sprint Workflow

### Current Release: 1.0 - Foundation

The Foundation release runs from **January 19 - May 10, 2026** across 8 sprints.

| Sprint | Dates | Goal |
|--------|-------|------|
| Sprint 1 | Jan 19 - Feb 1 | Context & Sessions |
| Sprint 2 | Feb 2 - Feb 15 | Context & Tool Registry |
| Sprint 3 | Feb 16 - Mar 1 | Tool Security & MCP Foundation |
| Sprint 4 | Mar 2 - Mar 15 | MCP Completion & Session Features |
| Sprint 5 | Mar 16 - Mar 29 | Web UI Foundation |
| Sprint 6 | Mar 30 - Apr 12 | Web UI Completion |
| Sprint 7 | Apr 13 - Apr 26 | Orchestrator |
| Sprint 8 | Apr 27 - May 10 | Integration & Polish |

### Sprint Transitions

At the end of a sprint, tell Claude Code:

```
"We're transitioning from Sprint 1 to Sprint 2"
```

Claude Code will:
- Update Sprint 1 status to `Completed`
- Move any incomplete stories to Sprint 2
- Update Sprint 2 status to `In progress`

---

## Reference: Status Values

### User Story Status

| Status | When to Use |
|--------|-------------|
| **Backlog** | Story is defined but work has not started |
| **In progress** | Development is actively underway |
| **Ready for test** | Code is complete and ready for QA/testing |
| **Blocked** | Cannot proceed due to external dependency |
| **Done** | Story is complete, tested, and accepted |

### Sprint Status

| Status | When to Use |
|--------|-------------|
| **Planning** | Sprint is being planned (future sprint) |
| **In progress** | Sprint is currently active |
| **Completed** | Sprint has ended |
| **Retrospective** | Sprint review in progress |

### Session Log Status

| Status | When to Use |
|--------|-------------|
| **In Progress** | Session is currently active |
| **Completed** | Session ended normally with progress logged |
| **Blocked** | Session ended due to blocker |

---

## Architecture Reference

When working on stories, Claude Code will reference the relevant sections of `docs/KEN-E-Agentic-Harness-Design.md`:

| Feature Area | Architecture Section |
|--------------|---------------------|
| Context Manager (1.1.x) | Section 3: Context Management Strategy |
| Tool Registry (1.2.x) | Section 5: MCP Server Architecture |
| MCP Manager (1.3.x) | Section 5: MCP Server Architecture |
| Session Service (1.4.x) | Section 3: Context Management Strategy |
| Web Channel (1.5.x) | Section 6: Multi-Channel Support |
| Primary Orchestrator (1.6.x) | Section 4: Agent Definitions |
| Basic Monitoring (1.7.x) | Section 8: Integration with Evaluation Framework |

---

## Example Prompts

### Finding and Starting Work

```
"What's in the current sprint?"
```

```
"Show me the stories for Sprint 1"
```

```
"What did I work on last time?"
```

```
"Continue from my last session"
```

```
"I'm picking up story 1.3.1 - Lazy Server Initialization"
```

### Understanding Context

```
"What's the sprint goal for this sprint?"
```

```
"Show me the parent feature for this story"
```

```
"What does the architecture doc say about MCP server management?"
```

### Updating Progress

```
"Update the session log: completed API endpoint, starting on tests"
```

```
"Mark story 1.2.1 as Ready for test"
```

```
"Add a comment to the story: Auth flow working, needs error handling"
```

### Handling Scope Changes

```
"This story is too large. Create two child stories: one for the API and one for the UI"
```

```
"Add a new story to feature 1.2: As a developer, I want rate limiting on tool calls"
```

### Ending Sessions

```
"End session. Completed: Firestore session persistence, unit tests.
Next steps: session recovery endpoint, integration tests.
Blocker: need Firestore emulator setup docs."
```

---

## Troubleshooting

### "Notion MCP not found"

Run `claude mcp list` to verify the Notion MCP is configured. If missing, re-run the setup command from Step 1.

### "Authentication required" or "Access denied"

Run `/mcp` in Claude Code and re-authenticate with Notion. Ensure you're using your KEN-E Notion account.

### "Database not found" or "Page not found"

Verify the database IDs in `.claude/skills/notion-pm-workflow/references/notion-schema.md` match your Notion workspace. Check that your Notion account has access to the KEN-E Product Development workspace.

### Claude Code doesn't know the current sprint

The sprint schedule is in `references/notion-schema.md`. Verify the dates are correct and that today's date falls within a sprint range.

### Claude Code doesn't show previous session context

Ensure your previous sessions created Session Log entries in Notion. Check that the Session Logs database is accessible.

### Claude Code doesn't reference the architecture doc

Ensure `docs/KEN-E-Agentic-Harness-Design.md` exists in your repository. The skill references this file for technical context.

---

## Files Reference

| File | Purpose |
|------|---------|
| `.claude/skills/notion-pm-workflow/skill.md` | Main workflow instructions |
| `.claude/skills/notion-pm-workflow/references/notion-schema.md` | Database IDs, sprint schedule, page IDs |
| `docs/KEN-E-Agentic-Harness-Design.md` | Architecture and technical context |
| `docs/claude-code-notion-setup-guide.md` | This guide |

---

*Questions? Contact the Product team or post in #dev-tooling on Slack.*
