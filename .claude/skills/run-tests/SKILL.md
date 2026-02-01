---
name: run-tests
description: |
  Run the testing phase for a user story. Creates a test plan from Acceptance Criteria,
  runs all programmatic tests, determines story status, and posts a manual testing
  checklist if needed. Use after development work is complete.
user-invocable: true
---

# Run Tests

This skill implements the Testing Phase from the notion-pm-workflow skill. It creates a test plan, runs programmatic tests, and determines the recommended story status.

## What This Skill Does

When invoked, this skill will:

1. **Identify the story** - Ask which story is being tested
2. **Fetch Acceptance Criteria** - Retrieve the story's AC and Definition of Done from Notion
3. **Create a test plan** - Categorize every requirement as Programmatic or Manual
4. **Present the test plan** - Show the plan for developer review before running tests
5. **Run programmatic tests** - Execute all applicable test suites
6. **Report results** - Pass/fail counts and failure details
7. **Determine recommended status** - Done or Ready for test
8. **Update story status** - Set the story status in Notion (Done or Ready for test)
9. **Post manual testing checklist** - If manual tests are needed, post to Notion
10. **Report outcome** - Summary with recommended status

## How to Use

Run after development work is complete:

```
/run-tests
```

Or provide the story ID directly:

```
/run-tests 2.1.3
```

This skill can be run multiple times. If tests fail, fix the issues and run `/run-tests` again.

## What This Skill Does NOT Do

- Update the Session Log
- Commit or push code
- Close the session

This separation allows you to fix failures and re-run as many times as needed.

## Workflow Steps (Detailed)

### Step 1: Identify the Story

Ask the developer:
- Which story is being tested? (by ID like "2.1.3" or by title)
- If the developer provides an ID, search Notion for it

### Step 2: Fetch Acceptance Criteria and Definition of Done

Fetch the User Story from Notion using `notion-fetch`:
- Extract **Acceptance Criteria** (Given/When/Then)
- Extract **Definition of Done** (checklist items)
- Extract **Story Title** and **Story page ID** (needed for posting checklist)

Also fetch the parent Feature:
- Extract **Feature Acceptance Criteria** (any relevant to this story)

### Step 3: Create a Test Plan

Review every testable requirement from the story and categorize it:

| Category | Description | Examples |
|----------|-------------|----------|
| **Programmatic** | Can be verified by running code | Unit tests, integration tests, type checks (`mypy`), linting (`ruff`), API endpoint tests, `pytest` assertions, TypeScript compilation, ESLint, production build |
| **Manual** | Requires human judgment or interaction | UI verification, UX flow testing, visual inspection, cross-browser testing, data validation requiring domain knowledge, end-to-end workflows involving external services |

Structure the test plan as:

```
## Test Plan: [Story ID] - [Story Title]

### Programmatic Tests
- [ ] pytest — [which test files/areas]
- [ ] mypy — type checking
- [ ] ruff — linting
- [ ] black --check — formatting
- [ ] tsc --noEmit — TypeScript compilation
- [ ] ESLint — frontend linting
- [ ] npm run build — production build
- [ ] [any story-specific programmatic checks]

### Manual Tests
- [ ] [Test description tied to specific AC]
- [ ] [Test description tied to specific AC]
(or "None — all requirements are programmatically testable")
```

### Step 4: Present the Test Plan

Show the test plan to the developer and ask:
- Does this plan look correct?
- Are there any tests to add or remove?
- Should any Manual tests be reclassified as Programmatic (or vice versa)?

Wait for developer confirmation before proceeding.

### Step 5: Run All Programmatic Tests

Determine which packages were modified by checking git status:

```bash
git diff --name-only HEAD
git diff --name-only --cached
git status --short
```

**If `packages/engine/` was modified, run:**

```bash
# Tests
cd /Users/kenwilliams/Documents/github/MER-E/packages/engine && uv run pytest -v --tb=short

# Type checking
cd /Users/kenwilliams/Documents/github/MER-E/packages/engine && uv run mypy mer_e/

# Linting
cd /Users/kenwilliams/Documents/github/MER-E/packages/engine && uv run ruff check mer_e/

# Formatting
cd /Users/kenwilliams/Documents/github/MER-E/packages/engine && uv run black --check mer_e/
```

**If `packages/frontend/` was modified, run:**

```bash
# TypeScript compilation
cd /Users/kenwilliams/Documents/github/MER-E/packages/frontend && npx tsc --noEmit

# ESLint
cd /Users/kenwilliams/Documents/github/MER-E/packages/frontend && npm run lint

# Production build
cd /Users/kenwilliams/Documents/github/MER-E/packages/frontend && npm run build
```

Run all applicable test suites. Do not stop at the first failure — run everything and report all results.

### Step 6: Report Results

Present results in this format:

```
## Test Results: [Story ID]

### Backend
- pytest: ✅ 42 passed / ❌ 2 failed
  - FAILED test_foo.py::test_bar — AssertionError: expected X got Y
  - FAILED test_baz.py::test_qux — ImportError: no module named Z
- mypy: ✅ No errors
- ruff: ✅ No issues
- black: ⚠️ 3 files would be reformatted

### Frontend
- tsc: ✅ No errors
- eslint: ✅ No warnings
- build: ✅ Success

### Overall: ❌ FAIL (2 test failures, 3 formatting issues)
```

### Step 7: Determine Recommended Status

Apply this decision tree:

```
All programmatic tests pass?
├── No  → Recommend: Fix failures and re-run /run-tests
└── Yes → Are there Manual tests in the plan?
    ├── No  → Recommend status: "Done"
    └── Yes → Recommend status: "Ready for test"
```

| Recommended Status | When |
|-------------------|------|
| Fix and re-run | Any programmatic test failed |
| `Done` | All programmatic tests pass, no manual tests needed |
| `Ready for test` | All programmatic tests pass, manual tests remain |

### Step 8: Update Story Status in Notion

If the recommended status is "Done" or "Ready for test" (i.e., all programmatic tests pass), update the story status in Notion:

```
notion-update-page:
  data:
    page_id: "[Story page ID]"
    command: "update_properties"
    properties:
      Status: "[Done or Ready for test]"
```

Do NOT update the status if the recommendation is "Fix and re-run" — keep it as "In progress".

### Step 9: Create Manual Testing Guide and Post Checklist (if applicable)

If the recommended status is "Ready for test", you must do **two things**:

#### 9a: Create a Detailed Manual Testing Guide

Create a `MANUAL_TESTING_GUIDE.md` file in the most relevant test directory for the story (e.g., `packages/frontend/src/services/__tests__/` for frontend-heavy stories, or `packages/engine/tests/` for backend-heavy stories).

The guide must follow this structure and level of detail:

```markdown
# Manual Testing Guide: Story [ID] - [Title]

## Prerequisites
- List commands to start backend/frontend servers
- List any environment variables needed
- Link to the app URL

## Seed Data: [Describe what data is needed]
- Provide a **complete, copy-paste-ready script** to populate test data
- Include a **cleanup script** to remove test data after testing
- Use the project's Firestore client and settings (not raw credentials)

## Test N: [Test Name] (AC reference)

**Steps:**
1. Exact step-by-step instructions (which button to click, which URL to visit)
2. If form input is required, provide **explicit values** to enter
3. If JSON input is needed, provide the **complete JSON** to paste

**Expected Results:**
- [ ] Specific, observable outcome with exact text/values to verify
- [ ] UI element states (visible/hidden, enabled/disabled, specific text)
- [ ] Data verification steps (e.g., "Check Firestore document X has field Y = Z")

[Repeat for each test...]

## Verification Checklist Summary
| Test | What It Validates | AC |
|------|-------------------|----|
| Test 1 | ... | AC1 |
```

**Key requirements for the guide:**
- Every test must have **numbered steps** a tester can follow without prior context
- Form inputs must include **exact values** to enter (not just "fill in the form")
- Expected results must be **checkboxes** with specific, verifiable outcomes
- Include **seed data scripts** that are copy-paste ready (Python scripts using project config)
- Include **cleanup scripts** to reset state between test runs
- Reference **exact UI text** (button labels, toast messages, indicator text)
- Include **Firestore verification steps** where data persistence matters
- End with a summary table mapping tests to Acceptance Criteria

See `packages/frontend/src/services/__tests__/MANUAL_TESTING_GUIDE.md` (from Story 2.1.3) as an exemplar.

#### 9b: Post Summary Checklist to Notion

Post a comment to the User Story in Notion referencing the guide:

```
notion-create-comment:
  parent:
    page_id: "[Story page ID]"
  rich_text:
    - type: "text"
      text:
        content: "## Manual Testing Checklist\n\nStory: [Story ID] - [Story Title]\nProgrammatic Tests: ✅ All [N] passed\nDate: [YYYY-MM-DD]\n\n### Manual Tests Required\n- [ ] [Test description 1]\n- [ ] [Test description 2]\n- [ ] [Test description 3]\n\n### Detailed Testing Guide\nSee `[path/to/MANUAL_TESTING_GUIDE.md]` for step-by-step instructions, seed data scripts, and expected results.\n\n### How to Complete\n1. Run through each item above (see the guide for detailed steps)\n2. Check the box when verified\n3. Set story status to \"Done\" when all items pass\n4. If a test fails, set status to \"In progress\" and describe the failure"
```

### Step 10: Report Outcome

Present the final summary:

```
## Testing Phase Complete

**Story:** [ID] - [Title]
**Programmatic Tests:** [N] passed, [M] failed
**Manual Tests:** [K] identified (or "None")
**Recommended Status:** [Done / Ready for test / Fix and re-run]

[If Ready for test]: Manual testing checklist posted to Notion.
[If Fix and re-run]: Fix the [M] failures listed above and run /run-tests again.
[If Done]: All requirements are programmatically verified. Ready for /end-session.
```

## Session Lifecycle

This skill is part of the development session lifecycle:

1. `/start-session` — Gather context and begin development
2. **`/run-tests`** — (you are here) Test the implementation
3. `/end-session` — Close the session, update logs, commit code

## References

- [notion-schema.md](../notion-pm-workflow/references/notion-schema.md) - Database IDs
- [notion-pm-workflow](../notion-pm-workflow/SKILL.md) - Full workflow reference (Testing Phase: Steps 3a-3d)
