import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { runAxe } from "./axe";

import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { AppErrorBoundary } from "@/components/layout/AppErrorBoundary";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar, SidebarProvider, SidebarRail } from "@/components/ui/sidebar";

vi.mock("@/utils/authRecovery", () => ({
  forceCleanLogout: vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/components/notifications/NotificationSidebar", () => ({
  NotificationSidebar: () => null,
}));

beforeEach(() => {
  // Default: no notifications, no selected account. Individual tests override
  // via mockReturnValueOnce when they need different state.
  vi.mocked(useAuth).mockReturnValue({
    notifications: [],
    selectedOrgAccount: null,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any);
});

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

  describe("NotificationBell", () => {
    it("has no axe violations (no unread notifications)", async () => {
      const { container } = render(<NotificationBell />);
      expect(await runAxe(container)).toHaveNoViolations();
    });

    it("has no axe violations with unread badge visible", async () => {
      vi.mocked(useAuth).mockReturnValueOnce({
        notifications: [
          {
            id: "n1",
            status: "unread",
            title: "Test 1",
            message: "Body 1",
          },
          {
            id: "n2",
            status: "unread",
            title: "Test 2",
            message: "Body 2",
          },
        ],
        selectedOrgAccount: { accountId: "acct-1" },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any);
      const { container } = render(<NotificationBell />);
      expect(await runAxe(container)).toHaveNoViolations();
    });
  });

  describe("SidebarRail", () => {
    // SidebarRail's visibility/styling depends on data-side selectors set by
    // the parent <Sidebar>. Rendering bare under SidebarProvider would axe-sweep
    // a stripped element that doesn't match the production tree.
    it("has no axe violations inside a Sidebar parent (left side)", async () => {
      const { container } = render(
        <SidebarProvider>
          <Sidebar side="left">
            <SidebarRail />
          </Sidebar>
        </SidebarProvider>,
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
