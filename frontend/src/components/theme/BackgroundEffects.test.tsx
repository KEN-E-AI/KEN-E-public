import { render, screen } from "@testing-library/react";
import { vi, afterEach } from "vitest";
import { BackgroundEffects } from "./BackgroundEffects";

describe("BackgroundEffects", () => {
  it("renders four animated blob elements when motion is allowed", () => {
    render(<BackgroundEffects />);
    const blobsContainer = screen.getByTestId("bg-blobs");
    const blobs = blobsContainer.querySelectorAll(".blur-\\[80px\\]");
    expect(blobs.length).toBeGreaterThanOrEqual(4);
  });

  describe("when prefers-reduced-motion: reduce is set", () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    it("renders static gradient and no animated blobs", () => {
      vi.spyOn(window, "matchMedia").mockImplementation((query: string) => ({
        matches: true,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn().mockReturnValue(false),
      }));

      render(<BackgroundEffects />);

      expect(screen.getByTestId("bg-static")).toBeInTheDocument();
      expect(screen.queryByTestId("bg-blobs")).not.toBeInTheDocument();
    });
  });
});
