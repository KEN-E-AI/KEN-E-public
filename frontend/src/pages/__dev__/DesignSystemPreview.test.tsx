import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { DesignSystemPreview } from "./DesignSystemPreview";

function renderWithTheme() {
  return render(
    <ThemeProvider>
      <DesignSystemPreview />
    </ThemeProvider>,
  );
}

describe("DesignSystemPreview", () => {
  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders without throwing", () => {
    expect(() => renderWithTheme()).not.toThrow();
  });

  it("ThemeToggle button is present", () => {
    renderWithTheme();
    expect(
      screen.getByRole("button", { name: /toggle theme/i }),
    ).toBeInTheDocument();
  });

  it("renders exactly 5 iframes with widths 375, 768, 1200, 1440, 1920", () => {
    renderWithTheme();
    const iframes = document.querySelectorAll("iframe");
    expect(iframes).toHaveLength(5);

    const expectedWidths = [375, 768, 1200, 1440, 1920];
    iframes.forEach((iframe, index) => {
      expect(Number(iframe.getAttribute("width"))).toBe(expectedWidths[index]);
    });
  });

  it('"Primitives" heading is present', () => {
    renderWithTheme();
    expect(
      screen.getByRole("heading", { name: /primitives/i }),
    ).toBeInTheDocument();
  });

  it('"Shell at viewport widths" heading is present', () => {
    renderWithTheme();
    expect(
      screen.getByRole("heading", { name: /shell at viewport widths/i }),
    ).toBeInTheDocument();
  });

  it("ThemeToggle toggles dark class on documentElement", () => {
    renderWithTheme();
    const toggle = screen.getByRole("button", { name: /toggle theme/i });
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
