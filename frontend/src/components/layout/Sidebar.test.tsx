import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { AuthContextType } from "@/contexts/AuthContext";
import { AuthContext } from "@/contexts/AuthContext";
import { Sidebar, SUPER_ADMIN_NAV, registerSuperAdminNavRow } from "./Sidebar";

const mockAuthContext = (
  isSuperAdmin: boolean = false,
): Partial<AuthContextType> => ({
  user: {
    id: "test-user" as any,
    email: isSuperAdmin ? "admin@ken-e.ai" : "user@example.com",
    firstName: "Test",
    lastName: "User",
  },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  isSuperAdmin,
});

const renderSidebar = ({
  initialPath = "/",
  isSuperAdmin = false,
}: { initialPath?: string; isSuperAdmin?: boolean } = {}) => {
  const contextValue = mockAuthContext(isSuperAdmin);
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthContext.Provider value={contextValue as AuthContextType}>
        <Sidebar />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
};

describe("Sidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    // Reset SUPER_ADMIN_NAV registry between tests
    SUPER_ADMIN_NAV.length = 0;
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    SUPER_ADMIN_NAV.length = 0;
  });

  describe("Nav items render", () => {
    test("renders all seven nav items", () => {
      renderSidebar();

      expect(screen.getByRole("link", { name: /chat/i })).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /performance/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /calendar/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /workflows/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /knowledge/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /extensions/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /settings/i }),
      ).toBeInTheDocument();
    });

    test("renders inside a primary navigation landmark", () => {
      renderSidebar();
      expect(
        screen.getByRole("navigation", { name: "Primary navigation" }),
      ).toBeInTheDocument();
    });
  });

  describe("Active route highlights", () => {
    test("highlights the Performance link when at /performance", () => {
      renderSidebar({ initialPath: "/performance" });

      const performanceLink = screen.getByRole("link", {
        name: /performance/i,
      });
      expect(performanceLink).toHaveClass("bg-[var(--color-violet-500)]");
    });

    test("does not highlight other links when at /performance", () => {
      renderSidebar({ initialPath: "/performance" });

      const chatLink = screen.getByRole("link", { name: /^chat$/i });
      expect(chatLink).not.toHaveClass("bg-[var(--color-violet-500)]");
    });

    test("highlights Chat link exactly at /", () => {
      renderSidebar({ initialPath: "/" });

      const chatLink = screen.getByRole("link", { name: /^chat$/i });
      expect(chatLink).toHaveClass("bg-[var(--color-violet-500)]");
    });

    test("does not highlight Chat at /performance (startsWith / would match)", () => {
      renderSidebar({ initialPath: "/performance" });

      const chatLink = screen.getByRole("link", { name: /^chat$/i });
      expect(chatLink).not.toHaveClass("bg-[var(--color-violet-500)]");
    });
  });

  describe("Collapse/expand toggle", () => {
    test("mounts expanded when localStorage has no value", () => {
      renderSidebar();

      const toggleButton = screen.getByRole("button", {
        name: /collapse sidebar/i,
      });
      expect(toggleButton).toBeInTheDocument();
      expect(toggleButton).toHaveAttribute("aria-expanded", "true");
    });

    test("clicking collapse toggle writes true to localStorage and updates aria-label", async () => {
      const user = userEvent.setup();
      renderSidebar();

      const toggleButton = screen.getByRole("button", {
        name: /collapse sidebar/i,
      });
      await user.click(toggleButton);

      expect(localStorage.getItem("sidebarCollapsed")).toBe("true");
      expect(
        screen.getByRole("button", { name: /expand sidebar/i }),
      ).toBeInTheDocument();
    });

    test("mounts collapsed when localStorage has 'true'", () => {
      localStorage.setItem("sidebarCollapsed", "true");
      renderSidebar();

      const toggleButton = screen.getByRole("button", {
        name: /expand sidebar/i,
      });
      expect(toggleButton).toBeInTheDocument();
      expect(toggleButton).toHaveAttribute("aria-expanded", "false");
    });
  });

  describe("Super-admin section", () => {
    test("does not render super-admin section for non-admins even with registry entries", () => {
      registerSuperAdminNavRow({
        id: "feature-flags",
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });

      renderSidebar({ isSuperAdmin: false });

      expect(
        screen.queryByRole("link", { name: /feature flags/i }),
      ).not.toBeInTheDocument();
    });

    test("renders super-admin section for admins when registry has entries", () => {
      registerSuperAdminNavRow({
        id: "feature-flags",
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });

      renderSidebar({ isSuperAdmin: true });

      expect(
        screen.getByRole("link", { name: /feature flags/i }),
      ).toBeInTheDocument();
    });

    test("does not render super-admin section for admins when registry is empty", () => {
      renderSidebar({ isSuperAdmin: true });

      // No separator or admin heading should appear
      expect(screen.queryByText(/admin/i)).not.toBeInTheDocument();
    });
  });
});
