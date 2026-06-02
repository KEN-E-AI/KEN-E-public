import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const cssPath = resolve(__dirname, "../index.css");
const cssContent = readFileSync(cssPath, "utf-8");

describe("reduced-motion CSS smoke test", () => {
  it("index.css contains a prefers-reduced-motion: reduce block", () => {
    expect(cssContent).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("the reduced-motion block minimises transition-duration and animation-duration via !important", () => {
    const rmStart = cssContent.indexOf(
      "@media (prefers-reduced-motion: reduce)",
    );
    expect(rmStart).toBeGreaterThan(-1);

    // Grab the block content up to 400 chars after the rule — enough to capture
    // the full declaration without parsing the entire CSS tree.
    const snippet = cssContent.slice(rmStart, rmStart + 400);

    // Values changed from 0.01ms → 1ms in CH-64 iteration 6 to ensure
    // animationend fires reliably in headless Chromium (sub-ms animations
    // may silently skip the event, preventing Radix Presence from unmounting).
    // 1ms is still imperceptibly fast for users with reduced-motion enabled.
    expect(snippet).toMatch(/transition-duration:\s*1ms\s*!important/);
    expect(snippet).toMatch(/animation-duration:\s*1ms\s*!important/);
  });

  it("the reduced-motion block targets * (all elements)", () => {
    const rmStart = cssContent.indexOf(
      "@media (prefers-reduced-motion: reduce)",
    );
    const snippet = cssContent.slice(rmStart, rmStart + 400);
    // Universal selector: *, *::before, *::after should be present
    expect(snippet).toMatch(/\*\s*[,{]/);
    expect(snippet).toContain("*::before");
    expect(snippet).toContain("*::after");
  });
});
