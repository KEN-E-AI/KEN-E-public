import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join, relative } from "node:path";

// Guards pages/workflows/ against raw hex literals — every color must come
// from theme.css / Tailwind tokens. Per-line opt-out: append or precede with
// `// allow-hex-literal: <reason>`. File-level allowlist: ALLOWED_FILES below.

const FRONTEND_SRC = resolve(__dirname, "..");
const WORKFLOWS_PAGES_DIR = resolve(FRONTEND_SRC, "pages", "workflows");

// File-level allowlist (currently empty — no legitimate hex usages have been
// identified in the workflows pages surface area).
const ALLOWED_FILES = new Set<string>([]);

const PER_LINE_ANNOTATION = "allow-hex-literal";

// Matches bare hex literals: #rgb, #rrggbb, #rgba, #rrggbbaa.
// Does NOT match inside string literals that are JSX attribute values
// referencing CSS variable names like "var(--color-violet-500)" — those are
// token references, not hex literals.
const HEX_LITERAL_RE = /#[0-9a-fA-F]{3,8}\b/;

function getAllSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      files.push(...getAllSourceFiles(full));
    } else if (
      (entry.endsWith(".tsx") || entry.endsWith(".ts")) &&
      !entry.endsWith(".test.tsx") &&
      !entry.endsWith(".test.ts") &&
      !entry.endsWith(".spec.tsx") &&
      !entry.endsWith(".spec.ts")
    ) {
      files.push(full);
    }
  }
  return files;
}

function lineHasHexLiteral(line: string): boolean {
  // Strip line comments so comments that mention hex values (e.g. rationale
  // notes or documentation) do not falsely trigger the gate.
  // Only strip `//` preceded by whitespace or line-start to avoid eating URLs.
  const codeOnly = line.replace(/(^|\s)\/\/.*$/, "$1");
  return HEX_LITERAL_RE.test(codeOnly);
}

function lineHasAllowAnnotation(line: string, prevLine: string): boolean {
  return (
    line.includes(PER_LINE_ANNOTATION) || prevLine.includes(PER_LINE_ANNOTATION)
  );
}

describe("workflows pages — no hard-coded hex literals", () => {
  const allFiles = getAllSourceFiles(WORKFLOWS_PAGES_DIR);

  it("workflows pages directory contains source files (guards against directory rename)", () => {
    expect(allFiles.length).toBeGreaterThan(0);
  });

  const violations: string[] = [];

  for (const file of allFiles) {
    const rel = relative(FRONTEND_SRC, file).replaceAll("\\", "/");
    if (ALLOWED_FILES.has(rel)) continue;

    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");

    lines.forEach((line, idx) => {
      if (!lineHasHexLiteral(line)) return;
      const prev = idx > 0 ? lines[idx - 1] : "";
      if (lineHasAllowAnnotation(line, prev)) return;
      violations.push(
        `${rel}:${idx + 1} — hard-coded hex literal found (use a CSS token instead, or add \`// ${PER_LINE_ANNOTATION}: <reason>\`)`,
      );
    });
  }

  it("no hard-coded hex literals in pages/workflows/ source files", () => {
    expect(violations, violations.join("\n")).toHaveLength(0);
  });
});
