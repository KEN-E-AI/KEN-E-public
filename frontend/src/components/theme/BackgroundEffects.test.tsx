import { render, screen, act } from "@testing-library/react";
import { vi, afterEach } from "vitest";
import { BackgroundEffects } from "./BackgroundEffects";

describe("BackgroundEffects", () => {
  it("renders four animated blob elements when motion is allowed", () => {
    render(<BackgroundEffects />);
    const blobsContainer = screen.getByTestId("bg-blobs");
    expect(blobsContainer.children.length).toBe(4);
  });

  describe("when prefers-reduced-motion: reduce is set", () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    it("renders static gradient and no animated blobs", () => {
      vi.spyOn(window, "matchMedia").mockImplementation(((query: string) => ({
        matches: true,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn().mockReturnValue(false),
      })) as unknown as (query: string) => MediaQueryList);

      render(<BackgroundEffects />);

      expect(screen.getByTestId("bg-static")).toBeInTheDocument();
      expect(screen.queryByTestId("bg-blobs")).not.toBeInTheDocument();
    });

    it("swaps blobs for static gradient when change listener fires", () => {
      let capturedHandler: ((e: MediaQueryListEvent) => void) | null = null;

      vi.spyOn(window, "matchMedia").mockImplementation(((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(
          (_type: string, handler: (e: MediaQueryListEvent) => void) => {
            capturedHandler = handler;
          },
        ),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn().mockReturnValue(false),
      })) as unknown as (query: string) => MediaQueryList);

      render(<BackgroundEffects />);

      // Initial state: blobs visible
      expect(screen.getByTestId("bg-blobs")).toBeInTheDocument();
      expect(screen.queryByTestId("bg-static")).not.toBeInTheDocument();

      // Fire the change event simulating OS reduced-motion toggle
      act(() => {
        capturedHandler!({ matches: true } as MediaQueryListEvent);
      });

      // After toggle: static gradient visible, blobs gone
      expect(screen.getByTestId("bg-static")).toBeInTheDocument();
      expect(screen.queryByTestId("bg-blobs")).not.toBeInTheDocument();
    });
  });
});
