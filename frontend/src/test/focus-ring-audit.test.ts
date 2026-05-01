import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join } from "node:path";

const AUDITED_DIRS = [
  resolve(__dirname, "../components/ui"),
  resolve(__dirname, "../components/layout"),
  resolve(__dirname, "../components/theme"),
];

function getAllTsxFiles(dir: string): string[] {
  const files: string[] = [];
  try {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        files.push(...getAllTsxFiles(full));
      } else if (entry.endsWith(".tsx") || entry.endsWith(".ts")) {
        files.push(full);
      }
    }
  } catch {
    // dir may not exist
  }
  return files;
}

// A className expression is a string literal or template literal that
// contains class names. We check: if it contains "outline-none", does it
// also contain a visible focus indicator? Accepted companions:
//   - focus-visible:outline / focus-visible:ring  (standard ring patterns)
//   - focus-visible:border / focus-visible:shadow  (custom border/shadow ring, e.g. Input)
//   - focus:bg-  (background-color change for Radix listbox/menu items — valid WCAG
//                 pattern for composite widgets navigated by arrow keys, not Tab)
//   - data-[state=  (Radix floating panel containers — HoverCard, Popover, etc. —
//                    not Tab-focusable; Radix sets outline-none on the panel div)
//   - [&_  (Tailwind arbitrary child selector — targets non-focusable children,
//           e.g. [&_.recharts-layer]:outline-none on SVG chart elements)
//   - select-none  (listbox/combobox role="option" items navigated by arrow keys,
//                   not Tab; outline-none correct per WCAG composite widget pattern)
function hasFocusVisibleCompanion(expr: string): boolean {
  return (
    expr.includes("focus-visible:outline") ||
    expr.includes("focus-visible:ring") ||
    expr.includes("focus-visible:border") ||
    expr.includes("focus-visible:shadow") ||
    expr.includes("focus:bg-") ||
    expr.includes("data-[state=") ||
    expr.includes("[&_") ||
    expr.includes("select-none")
  );
}

describe("outline-none focus-ring audit", () => {
  const allFiles = AUDITED_DIRS.flatMap(getAllTsxFiles).filter((f) =>
    f.endsWith(".tsx"),
  );

  // Group by file to produce readable errors
  const violations: string[] = [];

  for (const file of allFiles) {
    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");

    lines.forEach((line, idx) => {
      if (!line.includes("outline-none")) return;

      // Check if the same line (or the className prop context) also has the
      // companion. We also look ±3 lines around it for multi-line className strings.
      const window = lines.slice(Math.max(0, idx - 3), idx + 4).join("\n");
      if (!hasFocusVisibleCompanion(window)) {
        violations.push(
          `${file.replace(resolve(__dirname, ".."), "")}:${idx + 1} — outline-none without a focus-visible companion nearby`,
        );
      }
    });
  }

  it("no outline-none without a focus-visible companion in shell components", () => {
    expect(violations, violations.join("\n")).toHaveLength(0);
  });
});
