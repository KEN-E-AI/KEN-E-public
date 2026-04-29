# Workflow SKILL: Test Team

## Purpose

This SKILL defines the testing workflow for Test Team agents. The Test Team agent receives issues in "Ready for Testing" status, checks out the Dev Team's branch, builds the application, writes and executes Playwright browser tests based on the Dev Team's Test Instructions, captures screenshots as evidence, and reports results back to Linear.

**Runtime:** Claude Code CLI (`claude --print`) on ephemeral GCE VMs — same infrastructure as the Dev Team. Single-shot, non-interactive. No slash commands, plugins, or plan mode.

**Component context:** Injected directly into the prompt by the startup script. The correct component docs are resolved from the issue's Linear team and prepended to the prompt — they appear above the EVENT line. Read them for architecture, API contracts, feature index, design system references, and domain conventions.

Component docs live at `docs/design/components/{component-name}/README.md` plus all `projects/*.md` files in that directory.

The test commands, backend health-check endpoint, and frontend dev server port are typically named in these docs or in the Test Instructions posted by the Dev Team.

**No companion SKILLs required.** Test Team agents operate from the Test Instructions document posted by the Dev Team, which contains all context needed: branch name, build steps, test cases, and expected results.

**Playwright is pre-installed and MUST be used.** Headless Chromium and Playwright are installed on the GCE VM image. You MUST write and execute Playwright tests for every test case — do NOT fall back to CSS inspection, source code analysis, or any other non-browser verification method. The entire purpose of the Test Team is to verify the application in a real browser. If a test case cannot be executed via Playwright (e.g., requires third-party OAuth login), mark it as **BLOCKED** with an explanation — do not attempt to verify it through alternative means.

**Handling authentication:** The application uses Firebase Authentication (Google OAuth). Playwright cannot complete interactive OAuth flows. For test cases that require an authenticated session:
1. Check if the app has a test/development auth bypass (e.g., `VITE_AUTH_BYPASS=true` or a test login endpoint)
2. If no bypass exists, test what you can on unauthenticated pages (login page rendering, redirects, public routes)
3. Mark auth-dependent test cases as **BLOCKED — requires auth bypass for automated testing**
4. Include a note in the Test Results recommending the Dev Team add a test auth bypass if one doesn't exist

**Reading issue comments:** When querying comments on a Linear issue, always include the `isResolved` field and **skip resolved comments**. Resolved comments are stale artifacts from prior runs or superseded content. Only read unresolved comments — they represent the current, authoritative state of the issue. Example query:

```graphql
query {
  issue(id: "ISSUE_ID") {
    comments(filter: { resolved: { eq: false } }) {
      nodes { id body createdAt user { name } }
    }
  }
}
```

If the `filter` argument is not supported, fetch all comments with `isResolved` and discard those where `isResolved: true` in your own logic.

**Linear API usage:** Use curl with the `LINEAR_ACCESS_TOKEN` environment variable and the `apollo-require-preflight: true` header. Do NOT use MCP tools.

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "apollo-require-preflight: true" \
  -d '{"query": "..."}'
```

## Triggers

| Source | Event | Action |
|--------|-------|--------|
| Issue status → "Ready for Testing" | Webhook → GCE VM | Begin Test Execution flow |
| Issue returns to "Ready for Testing" (from "Resolving Test Issues") | Webhook → GCE VM | Begin Test Execution flow (same entry point; check for prior failure reports) |

---

## Flow 1: Test Execution

**Entry:** Issue status changes to "Ready for Testing." The Dev Team has posted Test Instructions as a comment on the issue. The Dev Team's draft PR is open but NOT merged.

### Step 1 — Set Status

Set the issue status to "Testing" using the Linear API.

To set status, first query the team's workflow states to find the state ID for "Testing":

```graphql
query {
  issue(id: "ISSUE_ID") {
    team {
      states { nodes { id name } }
    }
  }
}
```

Then update:

```graphql
mutation {
  issueUpdate(id: "ISSUE_ID", input: { stateId: "TESTING_STATE_ID" }) {
    success
  }
}
```

### Step 2 — Read Test Instructions

Read the issue comments (skip resolved), find the most recent comment containing `## Test Instructions`.

The document follows this schema:

```markdown
## Test Instructions

### Branch & Build Setup
- **Branch:** {branch-name}
- **PR:** #{pr-number} (draft)
- **Build steps:** (use the install/run commands the Dev Team named in the Test Instructions, which come from the component PRD)
  1. `git fetch origin && git checkout {branch-name}`
  2. Frontend: install deps, start dev server (e.g. `cd <frontend-path> && npm install && npm run dev`)
  3. Backend (if applicable): install deps, start API server (e.g. `cd <backend-path> && uv sync && uv run uvicorn <app>:app`)
  4. Open browser to the dev server URL named in the instructions (commonly `http://localhost:5173` for Vite)
- **Required accounts / test data:** [prerequisites]

### What the Dev Team Already Verified
[Summary of automated checks — unit tests, lint, type check, build]

### Test Cases
#### TC-1: [Test case name]
- **What to verify:** [UI behavior requiring browser access]
- **Precondition:** [Starting state]
- **Steps:** ...
- **Expected Result:** [What the tester should SEE]
- **Acceptance Criterion:** [Which AC this verifies]

### Edge Cases
...

### Acceptance Criteria Mapping
- AC-1 → TC-1, TC-3
- AC-2 → TC-2
```

**If this is a re-test** (a prior Test Failure Report exists in unresolved comments), check whether the Dev Team posted updated Test Instructions. If a comment notes "Test Instructions unchanged — internal fix only," use the original instructions. Otherwise, use the most recent Test Instructions.

**If the Test Instructions are missing or incomplete:**
1. Post a comment on the issue: "Test Instructions not found or missing required sections (Branch & Build Setup, Test Cases). Cannot begin testing."
2. Set the issue status to "Resolving Test Issues"
3. End the session

### Step 3 — Check Out Branch and Build

Follow the Branch & Build Setup section:

1. Check out the Dev Team's working branch:
   ```bash
   git fetch origin
   git checkout {branch-name}
   ```
2. Install dependencies and start the dev servers in the background, using the commands from the Test Instructions. The Test Instructions name the exact paths, commands, and ports to use. Typical pattern:
   ```bash
   # Paths and commands below come from the Test Instructions (which come from the component PRD).
   cd <frontend-path> && <install-cmd> && <dev-server-cmd> &
   FRONTEND_PID=$!
   cd <backend-path> && <install-cmd> && <run-cmd> &
   BACKEND_PID=$!
   ```
3. Wait for both servers to become healthy at the ports named in the Test Instructions. Poll with a hard timeout — do NOT retry indefinitely:
   ```bash
   BACKEND_READY=0
   FRONTEND_READY=0
   BACKEND_PORT=<port-from-test-instructions>   # commonly 8000
   FRONTEND_PORT=<port-from-test-instructions>  # commonly 5173

   # Backend — allow up to 90s for install + server startup
   for i in $(seq 1 90); do
     if curl -sf "http://localhost:${BACKEND_PORT}/health" > /dev/null 2>&1; then
       BACKEND_READY=1
       break
     fi
     sleep 1
   done

   # Frontend — allow up to 60s for install + dev server startup
   for i in $(seq 1 60); do
     if curl -sf "http://localhost:${FRONTEND_PORT}" > /dev/null 2>&1; then
       FRONTEND_READY=1
       break
     fi
     sleep 1
   done
   ```
4. If either server failed to become healthy within its timeout, **stop immediately** — do not retry, do not try to heal the environment. Kill both servers, post a failure comment identifying which side timed out, and transition the issue to "Resolving Test Issues":
   ```bash
   if [ "$BACKEND_READY" = "0" ] || [ "$FRONTEND_READY" = "0" ]; then
     kill $FRONTEND_PID $BACKEND_PID 2>/dev/null
     # Build the failure message identifying the unhealthy side
     # Post a Linear comment (see "If the build fails" block below)
     # Set status to "Resolving Test Issues"
     # Exit the session
   fi
   ```
   Past incidents (e.g., the uvicorn `--reload` StatReload hot loop on node_modules) showed that unbounded retries waste 25+ minutes of compute and obscure the real failure. A single bounded timeout surfaces the problem cleanly so the Dev Team can act on it.

**If the branch does not exist:**
1. Post a comment: "Branch '{branch-name}' not found in repository. Cannot begin testing."
2. Set the issue status to "Resolving Test Issues"
3. End the session

**If the build fails:**
1. Post a comment on the issue with the build error output
2. Set the issue status to "Resolving Test Issues"
3. End the session

### Step 4 — Write Playwright Tests

**This step is mandatory.** You MUST create and run Playwright tests. Do NOT skip this step or substitute with code inspection, CSS analysis, or any non-browser verification.

Install the Playwright test package in the repo's frontend path (Chromium browser is pre-installed on the VM image):
```bash
# Use the frontend path named in the Test Instructions (commonly `frontend/` for KEN-E-family repos).
cd <frontend-path> && npm install --save-dev @playwright/test
```

Create an `e2e/` directory inside the frontend path and write Playwright test files that translate the Test Instructions into executable browser tests.

For each test case (TC-N) in the Test Instructions, create a `test()` block:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Issue {ISSUE_ID} — Test Cases", () => {
  test("TC-1: {test case name}", async ({ page }) => {
    // Precondition: navigate to starting state
    await page.goto("/");

    // Step 1: ...
    await page.getByRole("button", { name: "..." }).click();

    // Capture screenshot after key action
    await page.screenshot({ path: "e2e-results/{ISSUE_ID}_TC1_step1_description.png" });

    // Expected result assertion
    await expect(page.getByText("...")).toBeVisible();

    // Final state screenshot
    await page.screenshot({ path: "e2e-results/{ISSUE_ID}_TC1_final.png" });
  });

  // TC-2, TC-3, etc.
});
```

**Test writing standards:**
- Use accessible selectors: `getByRole()`, `getByText()`, `getByLabel()`, `getByTestId()` — prefer these over CSS selectors
- Take screenshots at minimum: initial state, after key actions, final state
- Name screenshots descriptively: `{ISSUE_ID}_TC{N}_step{M}_{description}.png`
- Translate "Expected Result" from Test Instructions into Playwright `expect()` assertions
- Include edge case tests after the main test cases
- If the Test Instructions mention accessibility verification, add axe-core checks:
  ```typescript
  import AxeBuilder from "@axe-core/playwright";

  test("TC-N: Accessibility check", async ({ page }) => {
    await page.goto("/path");
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
  ```

### Step 5 — Execute Tests

Run the Playwright tests. **You MUST actually execute them** — do not skip execution or report results based on code analysis alone.

```bash
cd <frontend-path> && npx playwright test --reporter=list 2>&1
```

Capture the exit code and full output. Playwright returns exit code 0 if all tests pass, non-zero if any fail.

If Playwright fails to launch Chromium, verify the browser is available:
```bash
npx playwright install chromium --with-deps
```
Then retry the test run.

### Step 6 — Upload Screenshots

Upload all screenshots from `frontend/e2e-results/` to Linear using the `fileUpload` mutation.

For each screenshot file:

1. Get the file size in bytes
2. Request an upload URL:
   ```bash
   curl -s -X POST https://api.linear.app/graphql \
     -H "Authorization: $LINEAR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -H "apollo-require-preflight: true" \
     -d '{
       "query": "mutation($size: Int!, $filename: String!, $contentType: String!) { fileUpload(size: $size, filename: $filename, contentType: $contentType) { uploadFile { uploadUrl assetUrl headers { key value } } } }",
       "variables": {
         "size": FILE_SIZE_BYTES,
         "filename": "SCREENSHOT_NAME.png",
         "contentType": "image/png"
       }
     }'
   ```
3. Upload the file to the presigned URL:
   ```bash
   curl -X PUT "$UPLOAD_URL" \
     -H "Content-Type: image/png" \
     -H "Cache-Control: public, max-age=31536000" \
     --data-binary @"e2e-results/SCREENSHOT_NAME.png"
   ```
   Include any additional headers from the `headers` array in the response.
4. Store the `assetUrl` for embedding in the results comment.

### Step 6.5 — Thoroughness Check Before Declaring PASS

**This step only runs if all Playwright tests passed in Step 5.** If any test failed, skip to Step 7b — failures are already the signal that the implementation has issues, and the existing test suite is detecting them.

A clean Playwright run on a non-trivial change is a suspicious result, not a happy-path outcome. Well-written browser tests usually surface at least one observation — a minor visual quirk, a borderline accessibility issue, an edge case that behaves unexpectedly. Treat "all tests pass" as a reason to audit the test suite, not a reason to declare PASS immediately.

#### Audit the test suite against the Test Instructions

For each item below, answer "yes" or "add missing test and re-run before reporting":

- [ ] **Every edge case** listed in the Test Instructions §Edge Cases has a corresponding `test()` block — not implicitly covered, not deferred
- [ ] **Auth-dependent test cases** actually used the auth bypass. If the bypass was unavailable, those cases are marked **BLOCKED**, not reported as PASS
- [ ] **Form input tests** include invalid input and boundary values (empty, max length, special characters, malformed data) where the component accepts user input
- [ ] **Responsive behavior tests** run at the mobile breakpoint (375px) when the Test Instructions describe responsive UI
- [ ] **Accessibility checks** (`axe-core` via `@axe-core/playwright`) are present for any component the Test Instructions flag as accessibility-critical or that users will interact with via keyboard
- [ ] **Screenshot coverage** — 3+ screenshots per test case that exercises transitions (initial state, after key action, final state), distinct and not duplicates of each other. Single-state cases (e.g., verifying a static 404 page) may have 1 screenshot with a one-line justification in the test result entry
- [ ] **Assertions are specific** — `expect()` calls verify intended behavior, not generic page state. Prefer `expect(heading).toHaveText("Forecast")` over `expect(page).toBeTruthy()`

If any item is "no", the test suite is thin. Add the missing tests (return to Step 4), re-run (Step 5), re-upload any new screenshots (Step 6), and return to this check. Iterate until all items pass.

#### Substantive observations requirement

A clean run must still produce at least one substantive entry in the **Observations & Caveats** section of Step 7a. Empty observations on a non-trivial change indicate surface-level testing. Include one of:

- A minor visual or UX note (e.g., "tooltip appears with a slight delay on hover")
- An accessibility observation (e.g., "axe-core reported 0 violations on the main flow; manually verified keyboard navigation works on the modal")
- A performance note (e.g., "initial render completed under 200ms at the mobile viewport")
- An explicit statement of what was examined and why nothing emerged (e.g., "Audited responsive behavior at 375px, 768px, 1440px — no layout issues observed. Axe-core clean on the three most-exercised pages.")

Do NOT write an empty or perfunctory Observations section to satisfy this requirement — either find something concrete or cite what was examined specifically. "No issues observed" without a description of what was looked at is not acceptable.

Only proceed to Step 7a after all audit items pass and a substantive Observations entry is ready.

### Step 7 — Evaluate and Report

After all tests are executed, determine the overall result:

**IF all tests pass → post Test Results (Step 7a)**
**IF any tests fail → post Test Failure Report (Step 7b)**

#### Step 7a — All Tests Pass

Create and post a Test Results comment:

```markdown
## Test Results

### Summary
**Overall result: PASS**
Total test cases: X | Passed: X | Failed: 0

### Environment
- **Branch:** {branch-name}
- **Runtime:** Playwright {version}, headless Chromium
- **Date/time:** {ISO 8601 timestamp}
- **Application URL:** http://localhost:5173

### Test Case Results
#### TC-1: [Test case name] — PASS
- **Evidence:** ![TC-1 final]({assetUrl})
- **Notes:** [Any observations]

#### TC-2: [Test case name] — PASS
- **Evidence:** ![TC-2 final]({assetUrl})
- **Notes:** [Any observations]

### Acceptance Criteria Verification
- [x] AC-1: [Criterion text] — Verified by TC-1, TC-3
- [x] AC-2: [Criterion text] — Verified by TC-2
- [x] AC-3: [Criterion text] — Verified by Dev Team automated tests (no browser test needed)

### Observations & Caveats
[Anything the Product Owner should be aware of — minor UX quirks, performance
characteristics, visual polish notes, accessibility observations, known limitations]
```

**Test Results quality requirements:**
- Every test case must have a result entry with screenshot evidence
- Every acceptance criterion must be accounted for — either verified by a browser test case or noted as verified by automated tests
- The Acceptance Criteria Verification section must use checkboxes (`[x]` for verified, `[ ]` for not verified)
- Observations must include at least one substantive entry per the Step 6.5 requirement — empty or perfunctory entries ("No issues observed" without detail) are not acceptable

After posting the Test Results comment:

1. **Resolve the PO for assignment.** The PO is the issue's Project Lead; if no Lead is set (or the issue has no Project), fall back to Ken. Mirrors the rules in `linear-sprint-ops` operation 13 (`resolve-po-for-issue`).

   First, query the issue's Project Lead:

   ```graphql
   query {
     issue(id: "ISSUE_ID") {
       project {
         lead { id displayName }
       }
     }
   }
   ```

   Resolution logic:
   - If `issue.project.lead.id` is non-null → that is `PO_USER_ID`
   - Otherwise (no Project, or Project with no Lead) → run the fallback query:

     ```graphql
     query {
       users(filter: { displayName: { eq: "ken" } }) {
         nodes { id }
       }
     }
     ```

     Use `nodes[0].id` as `PO_USER_ID`. If `nodes` is empty, set `PO_USER_ID` to null.
   - If `PO_USER_ID` is null after both attempts → log a warning ("Unable to resolve PO for issue {ISSUE_ID}; skipping assignee update") and proceed without the `assigneeId` field in the next step. **Graceful degradation: never block the status transition on PO resolution failure.**

2. **Transition status and assign to the PO in a single mutation.** The `issueUpdate` mutation accepts both `stateId` and `assigneeId` in one input — submit them together so the issue never lands in "Testing Complete" with a stale assignee.

   First look up the "Testing Complete" state ID using the same pattern as Step 1 (`team { states { nodes { id name } } }`).

   When `PO_USER_ID` was resolved successfully:

   ```graphql
   mutation {
     issueUpdate(
       id: "ISSUE_ID",
       input: {
         stateId: "TESTING_COMPLETE_STATE_ID"
         assigneeId: "PO_USER_ID"
       }
     ) { success }
   }
   ```

   When `PO_USER_ID` is null (graceful degradation), submit the mutation with only `stateId`:

   ```graphql
   mutation {
     issueUpdate(
       id: "ISSUE_ID",
       input: { stateId: "TESTING_COMPLETE_STATE_ID" }
     ) { success }
   }
   ```

3. End the session.

**Important:** "Testing Complete" does NOT mean the issue is done. The PO will review the Test Results at Cycle end. The draft PR remains open and unmerged until the PO sets the issue to "Done."

#### Step 7b — Tests Failed

Create and post a Test Failure Report comment:

```markdown
## Test Failure Report

### Summary
**Overall result: FAIL**
Total test cases: X | Passed: X | Failed: X | Blocked: X

### Failed Test Cases

#### TC-{N}: [Test case name] — FAIL
- **Step where failure occurred:** Step {N}
- **Expected:** [What should have appeared on screen — from Test Instructions]
- **Actual:** [What Playwright observed — assertion error message and visual state from screenshot]
- **Evidence:** ![TC-N failure]({assetUrl})
- **Severity:** [Critical / High / Medium — impact on user experience]
- **Reproduction:** Consistently reproducible via Playwright

### Passed Test Cases
[Brief listing of passed test cases for context]

### Blocked Test Cases
[Test cases that could not be executed due to upstream failures, with explanation]

### Acceptance Criteria Impact
- [x] AC-1: [Criterion text] — Verified by TC-1
- [ ] AC-2: [Criterion text] — FAILED in TC-2: [brief reason]
- [x] AC-3: [Criterion text] — Verified by TC-4
```

**Failure reporting quality requirements:**
- Each failure must specify the exact step where the deviation occurred
- Expected vs. actual must describe the VISUAL state — what was on screen, not code internals
- Screenshots must clearly show the failure state
- Severity assessment helps the Dev Team prioritize fixes
- Do NOT attempt to diagnose the root cause in code — that is the Dev Team's responsibility. Describe WHAT failed visually, not WHY the code is wrong.

After posting the failure report:
1. Set the issue status to "Resolving Test Issues"
2. End the session (the Dev Team takes over from here)

---

## Status Transition Summary

| From | To | Trigger |
|------|----|---------|
| Ready for Testing | Testing | Test Team begins execution (Step 1) |
| Testing | Testing Complete | All Playwright tests pass — also reassigns issue to PO (Step 7a) |
| Testing | Resolving Test Issues | Any Playwright test fails (Step 7b) |
| Ready for Testing | Resolving Test Issues | Test Instructions missing or build fails (Steps 2-3) |

The Test Team does NOT set any other statuses. The transitions from "Resolving Test Issues" back to "Ready for Testing" and from "Testing Complete" to "Done" (or back to "In Progress" on PO rejection) are handled by the Dev Team and PO respectively.

---

## Error Handling

### Test Instructions Missing

If the issue reaches "Ready for Testing" but no Test Instructions comment exists:
1. Post a comment: "Test Instructions not found. Cannot begin testing."
2. Set the issue status to "Resolving Test Issues"
3. End the session — the Dev Team must provide Test Instructions

### Branch Not Found

If the branch specified in the Test Instructions does not exist:
1. Post a comment: "Branch '{branch-name}' not found in repository. Cannot begin testing."
2. Set the issue status to "Resolving Test Issues"
3. End the session

### Build Failure

If the application fails to build or start from the branch:
1. Capture the build error output
2. Post a comment with the full error: "Build failed on branch '{branch-name}'. Error: {output}"
3. Set the issue status to "Resolving Test Issues"
4. End the session — the Dev Team must fix the build

### Server Unreachable

If the application builds but localhost is unreachable after 30 seconds:
1. Post a comment: "Application started but not reachable at http://localhost:5173 after 30 seconds."
2. Set the issue status to "Resolving Test Issues"
3. End the session

### Playwright Failure

If Playwright itself fails to launch (not a test failure, but a runtime error):
1. Post a comment with the Playwright error output: "Playwright runtime error (not a test failure). Error: {output}"
2. Set the issue status to "Resolving Test Issues"
3. End the session
