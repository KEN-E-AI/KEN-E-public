import { describe, it, expect } from "vitest";
import { contrastRatio, meetsAa, hexToRgb, relativeLuminance } from "./wcag";

describe("hexToRgb", () => {
  it("parses white", () => {
    expect(hexToRgb("#ffffff")).toEqual([255, 255, 255]);
  });
  it("parses black", () => {
    expect(hexToRgb("#000000")).toEqual([0, 0, 0]);
  });
  it("parses a mid-tone", () => {
    expect(hexToRgb("#3b82f6")).toEqual([59, 130, 246]);
  });
});

describe("relativeLuminance", () => {
  it("white has luminance 1", () => {
    expect(relativeLuminance("#ffffff")).toBeCloseTo(1.0, 5);
  });
  it("black has luminance 0", () => {
    expect(relativeLuminance("#000000")).toBeCloseTo(0.0, 5);
  });
});

describe("contrastRatio", () => {
  it("black on white = 21:1", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 0);
  });
  it("white on black = 21:1 (commutative)", () => {
    expect(contrastRatio("#ffffff", "#000000")).toBeCloseTo(21, 0);
  });
  it("identical colours = 1:1", () => {
    expect(contrastRatio("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
  });
});

describe("meetsAa", () => {
  it("4.5:1 meets AA for normal text", () => {
    expect(meetsAa(4.5, "normal")).toBe(true);
  });
  it("4.49:1 fails AA for normal text", () => {
    expect(meetsAa(4.49, "normal")).toBe(false);
  });
  it("3.0:1 meets AA for large text", () => {
    expect(meetsAa(3.0, "large")).toBe(true);
  });
  it("2.99:1 fails AA for large text", () => {
    expect(meetsAa(2.99, "large")).toBe(false);
  });
});
