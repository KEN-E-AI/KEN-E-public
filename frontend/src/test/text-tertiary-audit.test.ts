import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join, relative } from "node:path";

// --color-text-tertiary fails AA in light mode (~2.475:1 on bg-primary) and
// is formally exempt — see accessibility-baseline.md §Exemptions. Usage is
// strictly limited to decorative or disabled text (timestamps, secondary
// metadata, placeholder/disabled states in form primitives, dim icons).
//
// This audit is the runtime enforcement of that exemption: any new file that
// applies `text-tertiary` (Tailwind class) or `text-[var(--color-text-tertiary)]`
// (arbitrary value) must be added to ALLOWED_FILES below with a one-word
// rationale tag, OR the offending line must carry `// allow-text-tertiary:
// <reason>` as a per-line escape hatch.
//
// `.test.tsx` / `.test.ts` files are excluded — tests can legitimately reference
// the class string in assertions without it appearing in shipped UI.

const FRONTEND_SRC = resolve(__dirname, "..");
const AUDITED_DIRS = [
  resolve(FRONTEND_SRC, "components"),
  resolve(FRONTEND_SRC, "pages"),
];

// File-level allowlist. Path is relative to frontend/src (POSIX separators).
// Tag in the comment is a short rationale category.
const ALLOWED_FILES = new Set<string>([
  // shadcn/ui primitives — placeholder, disabled-state, and dim-icon usage
  "components/ui/accordion.tsx",
  "components/ui/alert-dialog.tsx",
  "components/ui/breadcrumb.tsx",
  "components/ui/button.tsx",
  "components/ui/calendar.tsx",
  "components/ui/chart.tsx",
  "components/ui/command.tsx",
  "components/ui/context-menu.tsx",
  "components/ui/dialog.tsx",
  "components/ui/drawer.tsx",
  "components/ui/dropdown-menu.tsx",
  "components/ui/form.tsx",
  "components/ui/input.tsx",
  "components/ui/menubar.tsx",
  "components/ui/select.tsx",
  "components/ui/sheet.tsx",
  "components/ui/sonner.tsx",
  "components/ui/table.tsx",
  "components/ui/tabs.tsx",
  "components/ui/textarea.tsx",
  "components/ui/toggle.tsx",

  // chat — timestamps and captions per accessibility-baseline.md §Exemptions
  "components/chat/ChatInterface.tsx",
  "components/chat/SessionsSidebar.tsx",

  // layout — secondary metadata, breadcrumb separators, inactive-link tertiary state
  "components/layout/AccountSwitcher.tsx",
  "components/layout/ExtensionsNavItem.tsx",
  "components/layout/LayoutC.tsx",
  "components/layout/ProfileMenu.tsx",

  // dev preview — renders every primitive intentionally
  "pages/__dev__/DesignSystemPreview.tsx",
]);

const PER_LINE_ANNOTATION = "allow-text-tertiary";
const TARGET_PATTERNS = [
  /\btext-tertiary\b/, // tailwind shorthand
  /text-\[var\(--color-text-tertiary\)\]/, // arbitrary value
];

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

function lineMatchesTarget(line: string): boolean {
  return TARGET_PATTERNS.some((re) => re.test(line));
}

function lineHasAllowAnnotation(line: string, prevLine: string): boolean {
  return (
    line.includes(PER_LINE_ANNOTATION) || prevLine.includes(PER_LINE_ANNOTATION)
  );
}

describe("text-tertiary usage audit", () => {
  const allFiles = AUDITED_DIRS.flatMap(getAllSourceFiles);

  it("audited directories contain source files (guards against directory rename)", () => {
    expect(allFiles.length).toBeGreaterThan(50);
  });

  const violations: string[] = [];

  for (const file of allFiles) {
    const rel = relative(FRONTEND_SRC, file).replaceAll("\\", "/");
    if (ALLOWED_FILES.has(rel)) continue;

    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");

    lines.forEach((line, idx) => {
      if (!lineMatchesTarget(line)) return;
      const prev = idx > 0 ? lines[idx - 1] : "";
      if (lineHasAllowAnnotation(line, prev)) return;
      violations.push(
        `${rel}:${idx + 1} — text-tertiary used outside ALLOWED_FILES with no \`${PER_LINE_ANNOTATION}\` annotation`,
      );
    });
  }

  it("no text-tertiary in non-allowlisted files (without per-line annotation)", () => {
    expect(violations, violations.join("\n")).toHaveLength(0);
  });
});
