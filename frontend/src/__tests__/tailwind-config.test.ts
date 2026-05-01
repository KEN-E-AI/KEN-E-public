import { describe, test, expect } from "vitest";
import config from "../../tailwind.config";

describe("tailwind.config.ts", () => {
  test("xl breakpoint is redefined to 1200px (UI-PRD-01 §5 requirement)", () => {
    const screens = (
      config.theme as { extend?: { screens?: Record<string, string> } }
    )?.extend?.screens;
    expect(screens?.xl).toBe("1200px");
  });
});
