import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { runAxe } from "./axe";

import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { AppErrorBoundary } from "@/components/layout/AppErrorBoundary";

vi.mock("@/utils/authRecovery", () => ({
  forceCleanLogout: vi.fn(),
}));

describe("axe sweep — shell components", () => {
  describe("ThemeToggle", () => {
    it("has no axe violations", async () => {
      const { container } = render(
        <ThemeProvider>
          <ThemeToggle />
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    });
  });

  describe("AppErrorBoundary fallback", () => {
    let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      consoleErrorSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => undefined);
    });

    it("fallback UI has no axe violations", async () => {
      const ThrowOnMount = () => {
        throw new Error("test");
      };
      const { container } = render(
        <MemoryRouter>
          <AppErrorBoundary>
            <ThrowOnMount />
          </AppErrorBoundary>
        </MemoryRouter>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
      consoleErrorSpy.mockRestore();
    });
  });
});
