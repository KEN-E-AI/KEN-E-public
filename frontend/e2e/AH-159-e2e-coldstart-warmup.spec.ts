/**
 * AH-159: e2e cold-start warm-up — static verification tests.
 *
 * Locks the contract that prevents the fleet-wide "first signInAs exceeds the
 * per-test ceiling" failure (AH-159): a CI-only Playwright globalSetup pays the
 * first-sign-in cold-start once, before any test counts, and the Cloud Build e2e
 * step exports CI=true so that warm-up (and retries) actually engage.
 *
 * Every check is pure file inspection — no browser, app server, or Cloud Build
 * access is needed.
 */

import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);

function readFile(relPath: string): string {
  return fs.readFileSync(path.join(REPO_ROOT, relPath), "utf8");
}

// Extract the Cloud Build YAML block for a given step id (same convention as
// AH-151-ci-build-speed.spec.ts): from the `  - name:` preceding the `id:` line
// to the next `  - name:`.
function extractStep(yaml: string, stepId: string): string {
  const idMarker = `\n    id: ${stepId}\n`;
  const idPos = yaml.indexOf(idMarker);
  if (idPos === -1) return "";
  const stepStart = yaml.lastIndexOf("\n  - name:", idPos);
  if (stepStart === -1) return yaml.slice(idPos);
  const block = yaml.slice(stepStart);
  const nextStep = block.indexOf("\n  - name:", 1);
  return nextStep === -1 ? block : block.slice(0, nextStep);
}

let config: string;
let globalSetupSrc: string;
let helpers: string;
let prChecks: string;

test.beforeAll(() => {
  config = readFile("frontend/playwright.config.ts");
  globalSetupSrc = readFile("frontend/e2e/global-setup.ts");
  helpers = readFile("frontend/e2e/helpers.ts");
  prChecks = readFile("deployment/ci/pr_checks.yaml");
});

test("TC-1: playwright.config registers the global-setup warm-up", () => {
  expect(config).toMatch(/globalSetup:\s*["']\.\/e2e\/global-setup(\.ts)?["']/);
});

test("TC-2: global-setup gates on CI and warms via a wide-budget signInAs", () => {
  // No-op outside CI so local runs (hot dev server) are unaffected.
  expect(globalSetupSrc).toContain("process.env.CI");
  // Warms the stack by driving a real sign-in...
  expect(globalSetupSrc).toMatch(/signInAs\(/);
  // ...with a redirect budget wider than the 45s per-test ceiling.
  expect(globalSetupSrc).toContain("redirectTimeoutMs");
});

test("TC-3: signInAs accepts a redirect-timeout override (default 45s)", () => {
  expect(helpers).toContain("redirectTimeoutMs");
  expect(helpers).toMatch(/redirectTimeoutMs\s*=\s*45_000/);
  expect(helpers).toMatch(/timeout:\s*redirectTimeoutMs/);
});

test("TC-4: the e2e Cloud Build step exports CI=true", () => {
  const e2eStep = extractStep(prChecks, "frontend-e2e-tests");
  expect(e2eStep).not.toBe("");
  expect(e2eStep).toMatch(/^\s+- 'CI=true'/m);
});
