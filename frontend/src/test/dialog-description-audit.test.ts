import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join, relative } from "node:path";

// Every <DialogContent> and <SheetContent> usage must have either:
//   (a) a <DialogDescription> / <SheetDescription> sibling inside the content block, or
//   (b) aria-describedby={...} on the opening tag (Radix-sanctioned opt-out).
//
// Without this, Radix logs "Missing `Description` or `aria-describedby`" on every
// open and screen-reader users get titled-but-undescribed dialogs. This static scan
// enforces the contract so CI catches regressions.
//
// Files that declare the primitives (not consume them) are pre-seeded in ALLOWED_FILES.
// For intentional opt-outs in consumer files, add:
//   // allow-dialog-no-description: <reason>
// on the line of the <DialogContent>/<SheetContent> opening tag, or the line before it.

const FRONTEND_SRC = resolve(__dirname, "..");
const AUDITED_DIRS = [
  resolve(FRONTEND_SRC, "components"),
  resolve(FRONTEND_SRC, "pages"),
];

// File-level allowlist. Path is relative to frontend/src (POSIX separators).
// Tag in the comment is a short rationale category.
const ALLOWED_FILES = new Set<string>([
  // shadcn/ui primitive definitions — declare the component, don't consume it
  "components/ui/dialog.tsx", // primitive
  "components/ui/sheet.tsx", // primitive
  "components/ui/alert-dialog.tsx", // primitive

  // dev preview — renders every primitive intentionally for design-system showcase
  "pages/__dev__/DesignSystemPreview.tsx", // showcase
]);

const PER_LINE_ANNOTATION = "allow-dialog-no-description";
// Match opening tags for DialogContent and SheetContent.
// The trailing alternation also matches end-of-line so multi-line tag
// declarations (`<SheetContent\n  side="right"`) are detected correctly.
const OPENING_TAG_PATTERNS = [
  /(?:^|\s)<DialogContent(?:\s|>|\/|$)/, // DialogContent opening
  /(?:^|\s)<SheetContent(?:\s|>|\/|$)/, // SheetContent opening
];
// Match description presence — DialogDescription, SheetDescription, or aria-describedby
const DESCRIPTION_PATTERNS = [
  /DialogDescription/, // <DialogDescription ...>
  /SheetDescription/, // <SheetDescription ...>
  /aria-describedby=/, // explicit ARIA attribute (Radix opt-out)
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

function lineHasAllowAnnotation(line: string, prevLine: string): boolean {
  return (
    line.includes(PER_LINE_ANNOTATION) || prevLine.includes(PER_LINE_ANNOTATION)
  );
}

// Find each <DialogContent>/<SheetContent> opening tag occurrence in a file,
// then scan forward up to LOOKAHEAD_LINES lines to see whether a Description
// or aria-describedby appears before the matching </DialogContent> or
// </SheetContent>. Returns an array of line numbers (1-based) where a content
// element lacks a description.
const LOOKAHEAD_LINES = 200;

function findMissingDescriptions(
  lines: string[],
): { lineNum: number; tag: string }[] {
  const violations: { lineNum: number; tag: string }[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const prev = i > 0 ? lines[i - 1] : "";

    let matchedTag: string | null = null;
    for (const pattern of OPENING_TAG_PATTERNS) {
      if (pattern.test(line)) {
        matchedTag = line.includes("DialogContent")
          ? "DialogContent"
          : "SheetContent";
        break;
      }
    }
    if (!matchedTag) continue;

    // Skip if the line (or previous line) carries an explicit allow annotation
    if (lineHasAllowAnnotation(line, prev)) continue;

    // Scan forward for a matching closing tag or description
    const closingTag = `</${matchedTag}>`;
    let foundDescription = false;

    const windowEnd = Math.min(i + LOOKAHEAD_LINES, lines.length);
    for (let j = i; j < windowEnd; j++) {
      const lookahead = lines[j];
      if (DESCRIPTION_PATTERNS.some((re) => re.test(lookahead))) {
        foundDescription = true;
        break;
      }
      // Stop scan at closing tag (but still check the closing tag line itself)
      if (j > i && lookahead.includes(closingTag)) break;
    }

    if (!foundDescription) {
      violations.push({ lineNum: i + 1, tag: matchedTag });
    }
  }

  return violations;
}

describe("dialog-description audit", () => {
  const allFiles = AUDITED_DIRS.flatMap(getAllSourceFiles);

  it("audited directories contain source files (guards against directory rename)", () => {
    expect(allFiles.length).toBeGreaterThan(200);
  });

  const violations: { file: string; lineNum: number; tag: string }[] = [];

  for (const file of allFiles) {
    const rel = relative(FRONTEND_SRC, file).replace(/\\/g, "/");
    if (ALLOWED_FILES.has(rel)) continue;

    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");

    const fileViolations = findMissingDescriptions(lines);
    for (const v of fileViolations) {
      violations.push({ file: rel, ...v });
    }
  }

  it("every DialogContent/SheetContent has a description or aria-describedby (without per-line annotation)", () => {
    expect(violations, formatViolationReport(violations)).toHaveLength(0);
  });
});

function formatViolationReport(
  violations: { file: string; lineNum: number; tag: string }[],
): string {
  if (violations.length === 0) return "";

  const byFile = new Map<string, { lineNum: number; tag: string }[]>();
  for (const v of violations) {
    const arr = byFile.get(v.file) ?? [];
    arr.push({ lineNum: v.lineNum, tag: v.tag });
    byFile.set(v.file, arr);
  }

  const blocks = Array.from(byFile.entries()).map(([file, items]) => {
    const lineNums = items.map((x) => x.lineNum);
    const linesStr =
      lineNums.length === 1
        ? `line ${lineNums[0]}`
        : `lines ${lineNums.join(", ")}`;
    return [
      `${file} (${items.length} occurrence(s) at ${linesStr})`,
      `  Fix A — add a sibling <DialogDescription className="sr-only">…</DialogDescription>`,
      `           (or <SheetDescription className="sr-only">…</SheetDescription>) inside the content block.`,
      `  Fix B — add aria-describedby={undefined} to the opening tag (Radix opt-out for content-free dialogs).`,
      `  Fix C — add to ALLOWED_FILES in frontend/src/test/dialog-description-audit.test.ts:`,
      `    "${file}",  // <one-word rationale>`,
      `  Fix D — annotate the opening tag line with:`,
      `    <${items[0].tag} …>  // ${PER_LINE_ANNOTATION}: <reason>`,
    ].join("\n");
  });

  return [
    "",
    `dialog-description audit found ${violations.length} violation(s) across ${byFile.size} file(s).`,
    "",
    "Radix requires every DialogContent/SheetContent to have a Description or aria-describedby.",
    "Without it, screen readers get titled-but-undescribed dialogs and Radix logs a warning.",
    "See: https://www.radix-ui.com/primitives/docs/components/dialog#description",
    "",
    "Fix one of four ways per file:",
    "",
    blocks.join("\n\n"),
    "",
  ].join("\n");
}
