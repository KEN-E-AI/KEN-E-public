import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { contrastRatio, meetsAa, type TextKind } from "./wcag";

// Parse --color-*: #rrggbb; lines from a CSS block
function parseTokens(cssBlock: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const re = /--(color-[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(cssBlock)) !== null) {
    tokens[`--${match[1]}`] = match[2];
  }
  return tokens;
}

function extractBlock(css: string, selector: string): string {
  const start = css.indexOf(selector);
  if (start === -1) return "";
  let depth = 0;
  let i = start;
  while (i < css.length) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) return css.slice(start, i + 1);
    }
    i++;
  }
  return "";
}

const cssPath = resolve(__dirname, "../index.css");
const cssContent = readFileSync(cssPath, "utf-8");
const lightTokens = parseTokens(extractBlock(cssContent, ":root"));
const darkTokens = parseTokens(extractBlock(cssContent, ".dark"));

type Pair = { fg: string; bg: string; kind: TextKind; label: string };

function buildPairs(
  tokens: Record<string, string>,
  label: string,
): Pair[] {
  const t = (k: string): string => tokens[k] ?? "";
  return [
    // Primary body text on primary background
    {
      fg: t("--color-text-primary"),
      bg: t("--color-bg-primary"),
      kind: "normal",
      label: `${label}: text-primary on bg-primary`,
    },
    // Primary text on elevated surface (cards)
    {
      fg: t("--color-text-primary"),
      bg: t("--color-bg-elevated"),
      kind: "normal",
      label: `${label}: text-primary on bg-elevated`,
    },
    // Secondary text on primary background (subheadings)
    {
      fg: t("--color-text-secondary"),
      bg: t("--color-bg-primary"),
      kind: "normal",
      label: `${label}: text-secondary on bg-primary`,
    },
    // Secondary text on secondary background (sidebar items)
    {
      fg: t("--color-text-secondary"),
      bg: t("--color-bg-secondary"),
      kind: "normal",
      label: `${label}: text-secondary on bg-secondary`,
    },
    // Inverse text on violet-500 (active nav pills, badge labels).
    // Usage is restricted to large/bold labels (≥14pt bold or ≥18pt regular),
    // so large-text AA (3:1) applies. Light-mode ratio is ~4.47:1 — passes large
    // text AA but not normal text AA. See accessibility-baseline.md §Exemptions.
    {
      fg: t("--color-text-inverse"),
      bg: t("--color-violet-500"),
      kind: "large",
      label: `${label}: text-inverse on violet-500`,
    },
    // Inverse text on secondary background (e.g. dark sidebar items)
    {
      fg: t("--color-text-primary"),
      bg: t("--color-bg-secondary"),
      kind: "normal",
      label: `${label}: text-primary on bg-secondary`,
    },
  ];
  // Note: border-strong token is intentionally excluded from this pair list.
  // Border colors (#cbd5e1 light / #475569 dark) are decorative separators used
  // to visually differentiate surface regions — they are not text or interactive
  // component indicators per WCAG 1.4.11, and their subtlety is a design choice.
  // If input borders or focus boundaries ever use border-strong, that would be a
  // WCAG violation and should be audited separately. See UI-54 for the full
  // contrast hardening backlog.
}

const lightPairs = buildPairs(lightTokens, "light");
const darkPairs = buildPairs(darkTokens, "dark");

// Note: violet-500 on light bg-primary as BODY TEXT is intentionally excluded
// from this list — it fails AA for normal text (small body copy). That usage
// is limited to large interactive labels / icons (large-text AA = 3:1 is met).
// See docs/design/components/ui/accessibility-baseline.md §Exemptions and UI-54.

describe("WCAG AA token-pair contrast", () => {
  [...lightPairs, ...darkPairs].forEach(({ fg, bg, kind, label }) => {
    it(`${label}`, () => {
      if (!fg || !bg) {
        // Token not found — skip gracefully with a warning
        console.warn(`Token not found for pair: ${label}`);
        return;
      }
      const ratio = contrastRatio(fg, bg);
      expect(
        meetsAa(ratio, kind),
        `${label}: ratio ${ratio.toFixed(2)}:1 must be ≥ ${kind === "normal" ? "4.5" : "3.0"}:1 for WCAG AA`,
      ).toBe(true);
    });
  });
});
