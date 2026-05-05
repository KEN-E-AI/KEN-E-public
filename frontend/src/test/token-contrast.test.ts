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

function buildPairs(tokens: Record<string, string>, label: string): Pair[] {
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
    // Semantic alert text on semantic alert background
    {
      fg: t("--color-success-text"),
      bg: t("--color-success-bg"),
      kind: "normal",
      label: `${label}: success-text on success-bg`,
    },
    {
      fg: t("--color-error-text"),
      bg: t("--color-error-bg"),
      kind: "normal",
      label: `${label}: error-text on error-bg`,
    },
    {
      fg: t("--color-warning-text"),
      bg: t("--color-warning-bg"),
      kind: "normal",
      label: `${label}: warning-text on warning-bg`,
    },
    {
      fg: t("--color-info-text"),
      bg: t("--color-info-bg"),
      kind: "normal",
      label: `${label}: info-text on info-bg`,
    },
  ];
  // Note: border-strong token is intentionally excluded from this pair list.
  // Border colors (#cbd5e1 light / #475569 dark) are decorative separators used
  // to visually differentiate surface regions — they are not text or interactive
  // component indicators per WCAG 1.4.11, and their subtlety is a design choice.
  // If input borders or focus boundaries ever use border-strong, that would be a
  // WCAG violation and should be audited separately. See the contrast hardening
  // backlog in accessibility-baseline.md §Backlog.
}

const lightPairs = buildPairs(lightTokens, "light");
const darkPairs = buildPairs(darkTokens, "dark");

// accent-foreground (--color-violet-500) on accent surface.
// In light mode --accent = var(--color-violet-100) (#eef2ff);
// in dark mode  --accent = var(--color-violet-200) (#3730a3).
// The bg alias differs per mode so we build these pairs explicitly rather than
// inside buildPairs() where only a single token map is available.
// Usage is restricted to large interactive text (≥14pt bold); large-text AA (3:1)
// applies. Light ≈ 3.995:1, dark ≈ 3.330:1 — both ≥ 3:1 ✅.
// NOTE: dark margin is only +0.33 above the 3:1 floor. Do not lighten
// --color-violet-200 (or darken --color-violet-500) without re-checking this
// pair; CI will catch a drop below 3:1 but a near-miss tweak could ship.
// See docs/design/components/ui/accessibility-baseline.md §Exemptions.
const accentFgPairs: Pair[] = [
  {
    fg: lightTokens["--color-violet-500"] ?? "",
    bg: lightTokens["--color-violet-100"] ?? "",
    kind: "large",
    label: "light: accent-foreground on accent",
  },
  {
    fg: darkTokens["--color-violet-500"] ?? "",
    bg: darkTokens["--color-violet-200"] ?? "",
    kind: "large",
    label: "dark: accent-foreground on accent",
  },
];

// Note: violet-500 on light bg-primary as BODY TEXT is intentionally excluded
// from this list — it fails AA for normal text (small body copy). That usage
// is limited to large interactive labels / icons (large-text AA = 3:1 is met).
// See docs/design/components/ui/accessibility-baseline.md §Exemptions.
//
// violet-600 is the brand-preserving alternative for body text. Light = #4f46e5
// (~6.04:1 on bg-primary), dark = #a5b4fc (~8.95:1 on bg-primary). UI-54
// introduced it as the recommended replacement for `text-primary` body text.
const violetSixHundredPairs: Pair[] = [
  {
    fg: lightTokens["--color-violet-600"] ?? "",
    bg: lightTokens["--color-bg-primary"] ?? "",
    kind: "normal",
    label: "light: violet-600 on bg-primary (body text)",
  },
  {
    fg: darkTokens["--color-violet-600"] ?? "",
    bg: darkTokens["--color-bg-primary"] ?? "",
    kind: "normal",
    label: "dark: violet-600 on bg-primary (body text)",
  },
];

// text-inverse on violet-600 — default Button background (normal text).
// Button text is --text-body-md (14px bold ≈ 10.5pt), below the 14pt bold large-text
// threshold, so normal-text AA (4.5:1) applies.
// Light: #ffffff on #4f46e5 ≈ 6.28:1 ✅. Dark: #0f172a on #a5b4fc ≈ 8.96:1 ✅.
// Fixed in UI-39 Flow 3 after Test Team identified 4.46:1 on violet-500 button.
const textInverseVioletSixHundredPairs: Pair[] = [
  {
    fg: lightTokens["--color-text-inverse"] ?? "",
    bg: lightTokens["--color-violet-600"] ?? "",
    kind: "normal",
    label: "light: text-inverse on violet-600 (button background)",
  },
  {
    fg: darkTokens["--color-text-inverse"] ?? "",
    bg: darkTokens["--color-violet-600"] ?? "",
    kind: "normal",
    label: "dark: text-inverse on violet-600 (button background)",
  },
];

// Note: text-tertiary on bg-primary is intentionally excluded from this pair list.
// Light mode: #94a3b8 on #fafbfc ≈ 2.475:1 — fails both normal (4.5:1) and large
// (3:1) AA thresholds. Dark mode: #64748b on #0f172a ≈ 3.751:1 — fails normal AA.
// Usage is restricted to decorative/disabled text only (timestamps, secondary metadata
// supplementary to primary content). No testable pair exists for this token; the
// constraint is enforced by design convention and documented as a formal exemption.
// See docs/design/components/ui/accessibility-baseline.md §Exemptions.

describe("WCAG AA token-pair contrast", () => {
  it("light token set is populated (sanity check against parse failures)", () => {
    expect(Object.keys(lightTokens).length).toBeGreaterThan(10);
  });

  it("dark token set is populated (sanity check against parse failures)", () => {
    expect(Object.keys(darkTokens).length).toBeGreaterThan(10);
  });

  [
    ...lightPairs,
    ...darkPairs,
    ...accentFgPairs,
    ...violetSixHundredPairs,
    ...textInverseVioletSixHundredPairs,
  ].forEach(({ fg, bg, kind, label }) => {
    it(`${label}`, () => {
      expect(fg, `Missing foreground token for: ${label}`).not.toBe("");
      expect(bg, `Missing background token for: ${label}`).not.toBe("");
      const ratio = contrastRatio(fg, bg);
      expect(
        meetsAa(ratio, kind),
        `${label}: ratio ${ratio.toFixed(2)}:1 must be ≥ ${kind === "normal" ? "4.5" : "3.0"}:1 for WCAG AA`,
      ).toBe(true);
    });
  });
});
