/**
 * AH-151: Phase-2 build-speed safe set — static verification tests.
 *
 * All test cases verify the CI configuration files directly.  No browser,
 * running app server, Cloud Build access, or PR-merge precondition is needed
 * — every check is pure file inspection.
 *
 * TC-Static  All 16 ACs pass (consolidated sweep).
 * TC-1       e2e path-filter: git fetch --depth=500, fail-open on merge-base
 *            error (AC-4).
 * TC-2       @playwright/test pinned to 1.49.0 (image version); no
 *            playwright install command in e2e step (AC-1, AC-2, AC-3).
 * TC-3       api-install step; api-integration and api-unit run in parallel
 *            on distinct emulator ports (AC-5, AC-6, AC-7).
 * TC-4       frontend-install shared step; a11y waits only on
 *            frontend-install (not e2e tail); no duplicate npm ci; e2e is
 *            isolated + fully parallel (AC-8, AC-9, AC-10, AC-15).
 * TC-5       SKIP — post-merge loop validation is a human protocol (5–10+
 *            CI builds required; cannot be automated in a single run).
 * TC-6       Lever 3 mypy-cache SAVE lives in the push-to-main staging.yaml
 *            (not the PR-only pr_checks.yaml, where it is dead code), and its
 *            mypy scope matches the pr_checks lint step (AC-16).
 */

import { test, expect } from "@playwright/test"
import * as fs from "fs"
import * as path from "path"
import { fileURLToPath } from "url"

// Paths are relative to repo root (two levels up from frontend/e2e/).
// Use import.meta.url instead of __dirname (ESM package).
const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../.."
)

function readFile(relPath: string): string {
  return fs.readFileSync(path.join(REPO_ROOT, relPath), "utf8")
}

/**
 * Extract the Cloud Build YAML block for a given step id.
 *
 * A step block starts at the `  - name:` line that precedes the `id:` line
 * and ends at the next `  - name:` line (or end of file).  Returns an empty
 * string if the step is not found.
 */
function extractStep(yaml: string, stepId: string): string {
  const idMarker = `\n    id: ${stepId}\n`
  const idPos = yaml.indexOf(idMarker)
  if (idPos === -1) return ""
  // Walk back to find the opening `  - name:` for this step.
  const stepStart = yaml.lastIndexOf("\n  - name:", idPos)
  if (stepStart === -1) return yaml.slice(idPos)
  const block = yaml.slice(stepStart)
  // The next step starts at the next `  - name:` occurrence.
  const nextStep = block.indexOf("\n  - name:", 1)
  return nextStep === -1 ? block : block.slice(0, nextStep)
}

// ─── Shared state loaded once ─────────────────────────────────────────────────

let yaml: string
let stagingYaml: string
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let pkg: { devDependencies?: Record<string, string> }
let lock: string
let pyproject: string
let terraform: string

test.beforeAll(() => {
  yaml = readFile("deployment/ci/pr_checks.yaml")
  stagingYaml = readFile("deployment/cd/staging.yaml")
  pkg = JSON.parse(readFile("frontend/package.json"))
  lock = readFile("frontend/package-lock.json")
  pyproject = readFile("pyproject.toml")
  terraform = readFile("deployment/terraform/storage.tf")
})

// Extract the mypy dir/flag args from a step body (the lines between
// `uv run --no-sync mypy` / `uv run … mypy` and the next non-continuation line).
// Used to assert the staging `mypy-warm` scope matches the pr_checks `lint` scope.
function mypyArgs(step: string): string[] {
  const m = step.match(/mypy\s*\\\n([\s\S]*?--ignore-missing-imports)/)
  if (!m) return []
  return m[1]
    .split("\n")
    .map((l) => l.replace(/\\$/, "").trim())
    .filter((l) => l.length > 0)
}

// ─── TC-Static ────────────────────────────────────────────────────────────────

test("TC-Static: All 14 ACs pass static file inspection", () => {
  // AC-1: package.json exact pin — no caret or tilde.
  expect(pkg.devDependencies?.["@playwright/test"]).toBe("1.49.0")

  // AC-2: package-lock.json resolves @playwright/test to exactly 1.49.0.
  // Match "node_modules/@playwright/test" block with version 1.49.0.
  expect(lock).toMatch(
    /"node_modules\/@playwright\/test"[\s\S]{0,200}"version":\s*"1\.49\.0"/
  )

  // AC-3: No playwright install COMMAND in the frontend-e2e-tests step.
  // The step may contain "playwright install" in YAML comments explaining the
  // image-pin contract — that is expected documentation.  Only shell command
  // invocations (`npx playwright install …`) are prohibited.
  const e2eStep = extractStep(yaml, "frontend-e2e-tests")
  expect(e2eStep).not.toMatch(/^\s+npx playwright install/m)
  expect(e2eStep).not.toMatch(/^\s+playwright install\b/m)

  // AC-4: git fetch --depth=500 in e2e path-filter.
  expect(e2eStep).toContain("--depth=500")

  // AC-5: api-install step exists, waitFor: ['-'], runs uv sync --frozen.
  const apiInstallStep = extractStep(yaml, "api-install")
  expect(apiInstallStep).toContain("id: api-install")
  expect(apiInstallStep).toContain("waitFor: ['-']")
  expect(apiInstallStep).toContain("uv sync --frozen")

  // AC-6: api-integration-tests waitFor: ['api-install'], --no-sync, port 8090.
  const apiIntStep = extractStep(yaml, "api-integration-tests")
  expect(apiIntStep).toContain("waitFor: ['api-install']")
  expect(apiIntStep).toContain("uv run --no-sync")
  expect(apiIntStep).toContain("EMULATOR_HOST_PORT=127.0.0.1:8090")
  expect(apiIntStep).not.toContain("uv sync --frozen")

  // AC-7: api-unit-tests waitFor: ['api-install'] (NOT api-integration), port 8091.
  const apiUnitStep = extractStep(yaml, "api-unit-tests")
  expect(apiUnitStep).toContain("waitFor: ['api-install']")
  // Check the waitFor line specifically — not any comment that may reference
  // api-integration-tests for documentation purposes.
  expect(apiUnitStep).not.toContain("waitFor: ['api-integration-tests']")
  expect(apiUnitStep).toContain("EMULATOR_HOST_PORT=127.0.0.1:8091")
  expect(apiUnitStep).not.toContain("EMULATOR_HOST_PORT=127.0.0.1:8090")
  expect(apiUnitStep).toContain("uv run --no-sync")
  expect(apiUnitStep).not.toContain("uv sync --frozen")

  // AC-8: frontend-install step exists, waitFor: ['-'], npm ci --prefer-offline.
  const feInstallStep = extractStep(yaml, "frontend-install")
  expect(feInstallStep).toContain("id: frontend-install")
  expect(feInstallStep).toContain("waitFor: ['-']")
  expect(feInstallStep).toContain("npm ci --prefer-offline")

  // AC-9: frontend-typecheck waitFor: ['frontend-install']; no npm ci.
  const typecheckStep = extractStep(yaml, "frontend-typecheck")
  expect(typecheckStep).toContain("waitFor: ['frontend-install']")
  expect(typecheckStep).not.toContain("npm ci")

  // AC-10: frontend-a11y-tests waitFor: ['frontend-install']; no npm ci.
  const a11yStep = extractStep(yaml, "frontend-a11y-tests")
  expect(a11yStep).toContain("waitFor: ['frontend-install']")
  expect(a11yStep).not.toContain("npm ci")

  // AC-11: GCS bucket resource for ci-mypy-cache exists in Terraform with 30-day lifecycle.
  expect(terraform).toContain("ci_mypy_cache")
  expect(terraform).toContain("age = 30")

  // AC-12: lint step waitFor includes both install-dependencies and mypy-cache-restore;
  //        mypy-cache-restore step has fail-open rsync (|| echo).
  const lintStep = extractStep(yaml, "lint")
  expect(lintStep).toContain("'install-dependencies'")
  expect(lintStep).toContain("'mypy-cache-restore'")
  const mypyRestoreStep = extractStep(yaml, "mypy-cache-restore")
  expect(mypyRestoreStep).toContain("|| echo")

  // AC-13: slow pytest marker registered in root pyproject.toml.
  expect(pyproject).toContain("slow:")

  // AC-14: -m "not slow" in app-adk-tests step.
  const appAdkStep = extractStep(yaml, "app-adk-tests")
  expect(appAdkStep).toContain('-m "not slow"')

  // AC-15: frontend-e2e-tests installs into an ISOLATED node_modules (a copy of
  // the frontend tree under /workspace/frontend-e2e) and is fully parallel
  // (waitFor: ['-']). It must NOT `cd frontend` + `npm ci` into the shared dir —
  // that was the structural source of the TS6053 race.
  expect(e2eStep).toContain("waitFor: ['-']")
  expect(e2eStep).toContain("cd /workspace/frontend-e2e")
  expect(e2eStep).toContain("tar --exclude=node_modules")
  expect(e2eStep).not.toMatch(/cd frontend\s*\n\s*npm ci/)

  // AC-16: the dead PR-only mypy-cache-save is gone from pr_checks.yaml; the
  // real SAVE lives in the push-to-main staging.yaml (verified in TC-6).
  expect(extractStep(yaml, "mypy-cache-save")).toBe("")
  expect(extractStep(stagingYaml, "mypy-cache-save")).not.toBe("")
})

// ─── TC-1: e2e path-filter depth + fail-open ──────────────────────────────────

test("TC-1: e2e path-filter uses --depth=500 and fails open on merge-base error", () => {
  const e2eStep = extractStep(yaml, "frontend-e2e-tests")

  // --depth=500 covers ~3 months of commit history without the cost of
  // --unshallow; --depth=50 (the previous value) could miss the merge-base
  // on long-lived feature branches.
  expect(e2eStep).toContain("--depth=500")

  // Fail-open: if BASE is empty (merge-base failed), run the full E2E suite
  // rather than silently skipping the gate.
  expect(e2eStep).toMatch(/\[ -z .+BASE.+ \]/)
  expect(e2eStep).toContain("running full E2E suite")
})

// ─── TC-2: Playwright package pin ────────────────────────────────────────────

test("TC-2: @playwright/test pinned to 1.49.0 exactly; no playwright install command in e2e step", () => {
  // AC-1: exact pin in package.json — no range operator.
  const playwrightPin = pkg.devDependencies?.["@playwright/test"] ?? ""
  expect(playwrightPin).toBe("1.49.0")
  expect(playwrightPin).not.toMatch(/^\^|^~|^>/)

  // AC-3: no playwright install COMMAND in the e2e Cloud Build step.
  // Comments that explain the image-pin contract are expected; only shell
  // command invocations are prohibited.
  const e2eStep = extractStep(yaml, "frontend-e2e-tests")
  expect(e2eStep).not.toMatch(/^\s+npx playwright install/m)
  expect(e2eStep).not.toMatch(/^\s+playwright install\b/m)

  // Image-pin contract comment is present (documents that image + package
  // must be bumped together).
  expect(e2eStep).toContain("Image-pin contract")
})

// ─── TC-3: api steps run in parallel after api-install ───────────────────────

test("TC-3: api-install step pre-builds venv; api-integration and api-unit run in parallel on distinct ports", () => {
  // api-install starts immediately (parallel with all other waitFor:['-'] steps).
  const apiInstallStep = extractStep(yaml, "api-install")
  expect(apiInstallStep).toContain("waitFor: ['-']")
  // It is the sole venv builder; consumers use --no-sync.
  expect(apiInstallStep).toContain("uv sync --frozen")

  // api-integration-tests: waits on api-install.
  const apiIntStep = extractStep(yaml, "api-integration-tests")
  expect(apiIntStep).toContain("waitFor: ['api-install']")
  // Consumes pre-built venv read-only.
  expect(apiIntStep).toContain("uv run --no-sync")
  expect(apiIntStep).not.toContain("uv sync --frozen")
  // Uses port 8090 (unchanged for backward compat).
  expect(apiIntStep).toContain("EMULATOR_HOST_PORT=127.0.0.1:8090")
  expect(apiIntStep).not.toContain("EMULATOR_HOST_PORT=127.0.0.1:8091")

  // api-unit-tests: waits on api-install (NOT api-integration), distinct port.
  const apiUnitStep = extractStep(yaml, "api-unit-tests")
  expect(apiUnitStep).toContain("waitFor: ['api-install']")
  // Must NOT chain on api-integration-tests — that would re-serialize the steps.
  // Check the waitFor line only; comments may reference api-integration-tests.
  expect(apiUnitStep).not.toContain("waitFor: ['api-integration-tests']")
  expect(apiUnitStep).toContain("uv run --no-sync")
  expect(apiUnitStep).not.toContain("uv sync --frozen")
  // Uses port 8091 (distinct from integration's 8090).
  expect(apiUnitStep).toContain("EMULATOR_HOST_PORT=127.0.0.1:8091")
  expect(apiUnitStep).not.toContain("EMULATOR_HOST_PORT=127.0.0.1:8090")
})

// ─── TC-4: shared frontend-install step ──────────────────────────────────────

test("TC-4: frontend-install shared step; a11y-tests no longer tails e2e; no redundant npm ci", () => {
  // frontend-install runs immediately, builds node_modules once.
  const feInstallStep = extractStep(yaml, "frontend-install")
  expect(feInstallStep).toContain("waitFor: ['-']")
  expect(feInstallStep).toContain("npm ci --prefer-offline")

  // frontend-typecheck waits only on frontend-install and has no npm ci.
  const typecheckStep = extractStep(yaml, "frontend-typecheck")
  expect(typecheckStep).toContain("waitFor: ['frontend-install']")
  expect(typecheckStep).not.toContain("npm ci")

  // frontend-a11y-tests waits only on frontend-install (not e2e or typecheck).
  const a11yStep = extractStep(yaml, "frontend-a11y-tests")
  expect(a11yStep).toContain("waitFor: ['frontend-install']")
  // Removing the e2e dependency was the key change that cuts ~31s from the
  // a11y critical path.
  expect(a11yStep).not.toContain("waitFor: ['frontend-e2e-tests")
  expect(a11yStep).not.toContain("waitFor: ['frontend-typecheck")
  expect(a11yStep).not.toContain("npm ci")

  // e2e installs into an isolated copy and is fully parallel — so there is no
  // writer of the shared frontend/node_modules other than frontend-install, and
  // both readers (typecheck, a11y) wait on it. Race is structural, not timed.
  const e2eStep = extractStep(yaml, "frontend-e2e-tests")
  expect(e2eStep).toContain("waitFor: ['-']")
  expect(e2eStep).toContain("cd /workspace/frontend-e2e")
  expect(e2eStep).not.toMatch(/cd frontend\s*\n\s*npm ci/)
})

// ─── TC-6: Lever 3 mypy-cache save relocated to push-to-main ──────────────────

test("TC-6: mypy-cache SAVE lives in staging.yaml (not PR-only pr_checks); scope matches lint", () => {
  // The save is dead code in pr_checks.yaml ($BRANCH_NAME is never 'main' on a PR
  // build), so it must NOT be there; restore stays (PRs consume the warm cache).
  expect(extractStep(yaml, "mypy-cache-save")).toBe("")
  expect(extractStep(yaml, "mypy-cache-restore")).not.toBe("")

  // staging.yaml (push-to-main) produces and uploads the cache.
  const warm = extractStep(stagingYaml, "mypy-warm")
  const save = extractStep(stagingYaml, "mypy-cache-save")
  const restore = extractStep(stagingYaml, "mypy-cache-restore")
  expect(warm).not.toBe("")
  expect(save).not.toBe("")
  expect(restore).not.toBe("")

  // Save uploads to the same bucket pr_checks restores from; fail-open.
  expect(save).toContain('.mypy_cache "gs://${PROJECT_ID}-ci-mypy-cache"')
  expect(save).toContain("|| echo")
  // Producer is fail-open so a type error never blocks the staging deploy.
  expect(warm).toContain("|| true")

  // Scope-coupling guard: the mypy dirs+flags warmed on main MUST equal the
  // pr_checks lint scope, or the cache restored on PRs is useless.
  expect(mypyArgs(warm)).toEqual(mypyArgs(extractStep(yaml, "lint")))
})

// ─── TC-5: Post-merge loop validation (human protocol) ────────────────────────

test.skip(
  "TC-5: Loop validation — post-merge human protocol (5–10+ CI builds required)",
  () => {
    // This test case documents the loop-validation contract required by AH-151
    // but CANNOT be automated in a single test run.
    //
    // Protocol (after PR merges):
    //   Lever 2 (e2e pin + path-filter): trigger 5+ no-op docs PRs; confirm
    //     zero flakes and e2e step skips for backend-only changes.
    //   Lever 1 (api parallelism): trigger 10+ no-op backend PRs; watch for
    //     api step variance (contention canary on the 8-vCPU machine).
    //   Lever 4 (frontend-install): trigger 5+ frontend PRs; confirm a11y +
    //     typecheck pass without e2e tail.
    //   Lever 3 (mypy cache): trigger 5+ docs PRs; confirm warm mypy (<30s)
    //     after first warm-up run; no rsync-related flakes.
    //
    // Targets: frontend PR ~3.5 min wall-clock; backend/docs PR ~2 min.
    //
    // See AH-151 Test Instructions TC-5 for the full validation protocol.
  }
)
