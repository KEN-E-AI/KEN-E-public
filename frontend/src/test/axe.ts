import { configureAxe } from "vitest-axe";

// color-contrast is disabled in JSDOM tests: JSDOM has no layout engine, so
// getComputedStyle returns empty values — axe cannot compute contrast reliably
// here. Contrast is verified deterministically in token-contrast.test.ts.
export const axeRulesetDefault = {
  rules: { "color-contrast": { enabled: false } },
};

export const runAxe = configureAxe(axeRulesetDefault);
