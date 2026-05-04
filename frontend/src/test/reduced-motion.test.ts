import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const cssPath = resolve(__dirname, "../index.css");
const cssContent = readFileSync(cssPath, "utf-8");

describe("reduced-motion CSS smoke test", () => {
  it("index.css contains a prefers-reduced-motion: reduce block", () => {
    expect(cssContent).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("the reduced-motion block zeros transition-duration via !important", () => {
    const rmStart = cssContent.indexOf(
      "@media (prefers-reduced-motion: reduce)",
    );
    expect(rmStart).toBeGreaterThan(-1);

    // Grab the block content up to 400 chars after the rule — enough to capture
    // the full declaration without parsing the entire CSS tree.
    const snippet = cssContent.slice(rmStart, rmStart + 400);

    expect(snippet).toMatch(/transition-duration:\s*0\.01ms\s*!important/);
    expect(snippet).toMatch(/animation-duration:\s*0\.01ms\s*!important/);
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
