# Claude Code + Notion Integration

## Developer Setup & Usage Guide

*KEN-E Product Development Team*

---

## Overview

This guide explains how to configure Claude Code to work with our Notion workspace for product development. Once set up, Claude Code will be able to:

- Retrieve feature descriptions and user stories from Notion
- Update story status during development
- Log session progress for continuity between sessions
- Create new user stories when scope is too large
- Add notes when features are ready for testing

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

### Step 3: Install the PM Workflow Skill

The skill files should already be in your repository at:

```
.claude/skills/notion-pm-workflow/
```

If not present, create the directory and add the skill files from the team shared drive.

The skill contains:
- `SKILL.md` - Workflow instructions for Claude Code
- `references/notion-schema.md` - Database IDs and property definitions

---

## Daily Workflow

### Starting a Coding Session

When you begin work, tell Claude Code which story you're working on:

```
"I'm starting work on story 1.2.3 - API Authentication in the ken-e-api repo"
```

Claude Code will:
- Search Notion for the story
- Display the acceptance criteria and definition of done
- Create a Session Log entry to track progress
- Update the story status to "In progress"

### During Development

You can ask Claude Code to update Notion at any time:

- `"Update the story status to Blocked - waiting on API credentials"`
- `"Add a comment to the story: Discovered we need a new endpoint"`
- `"This story is too big. Break it into smaller stories."`

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

## Reference: Status Values

### User Story Status

| Status | When to Use |
|--------|-------------|
| **Backlog** | Story is defined but work has not started |
| **In progress** | Development is actively underway |
| **Ready for test** | Code is complete and ready for QA/testing |
| **Blocked** | Cannot proceed due to external dependency |
| **Done** | Story is complete, tested, and accepted |

### Session Log Status

| Status | When to Use |
|--------|-------------|
| **In Progress** | Session is currently active |
| **Completed** | Session ended normally with progress logged |
| **Blocked** | Session ended due to blocker |

---

## Example Prompts

Here are examples of how to interact with Claude Code for common tasks:

### Finding and Starting Work

```
"What stories are ready for development in the MVP release?"
```

```
"Show me the details for story 1.1.2"
```

```
"I'm picking up story 1.3.1 in the ken-e-web repo. Create a session log."
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
"Add a new story to feature 1.2: As a user, I want to reset my password"
```

### Ending Sessions

```
"End session. Completed: user auth API, unit tests. Next steps: integration tests, error messages. Blocker: need test credentials from DevOps."
```

---

## Troubleshooting

### "Notion MCP not found"

Run `claude mcp list` to verify the Notion MCP is configured. If missing, re-run the setup command from Step 1.

### "Authentication required" or "Access denied"

Run `/mcp` in Claude Code and re-authenticate with Notion. Ensure you're using your KEN-E Notion account.

### "Database not found" or "Page not found"

Verify the database IDs in `references/notion-schema.md` match your Notion workspace. Check that your Notion account has access to the KEN-E Product Development workspace.

### Claude Code doesn't follow the workflow

Ensure the skill is installed at `.claude/skills/notion-pm-workflow/` and contains both `SKILL.md` and `references/notion-schema.md`.

---

*Questions? Contact the Product team or post in #dev-tooling on Slack.*
