import { describe, test, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { AuthContextType } from "@/contexts/AuthContext";
import { AuthContext } from "@/contexts/AuthContext";
import { Sidebar } from "./Sidebar";
import {
  SUPER_ADMIN_NAV,
  registerSuperAdminNavRow,
  resetSuperAdminNavForTesting,
} from "./super-admin-nav-registry";
import type { Brand, UserId } from "@/lib/branded-types";

type NavRowId = Brand<string, "NavRowId">;

const mockAuthContext = (
  isSuperAdmin: boolean = false,
): Partial<AuthContextType> => ({
  user: {
    id: "test-user" as UserId,
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
    resetSuperAdminNavForTesting();
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

    test("sets --sidebar-width CSS variable on collapse and expand", async () => {
      const user = userEvent.setup();
      renderSidebar();

      expect(
        document.documentElement.style.getPropertyValue("--sidebar-width"),
      ).toBe("16rem");

      const collapseButton = screen.getByRole("button", {
        name: /collapse sidebar/i,
      });
      await user.click(collapseButton);

      expect(
        document.documentElement.style.getPropertyValue("--sidebar-width"),
      ).toBe("4rem");

      const expandButton = screen.getByRole("button", {
        name: /expand sidebar/i,
      });
      await user.click(expandButton);

      expect(
        document.documentElement.style.getPropertyValue("--sidebar-width"),
      ).toBe("16rem");
    });

    test("syncs collapsed state from another tab via storage event", async () => {
      renderSidebar();

      expect(
        screen.getByRole("button", { name: /collapse sidebar/i }),
      ).toBeInTheDocument();

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "sidebarCollapsed",
          newValue: "true",
          storageArea: localStorage,
        }),
      );

      expect(
        await screen.findByRole("button", { name: /expand sidebar/i }),
      ).toBeInTheDocument();

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "sidebarCollapsed",
          newValue: "false",
          storageArea: localStorage,
        }),
      );

      expect(
        await screen.findByRole("button", { name: /collapse sidebar/i }),
      ).toBeInTheDocument();
    });

    test("ignores storage events for unrelated keys", () => {
      renderSidebar();

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "someOtherKey",
          newValue: "true",
          storageArea: localStorage,
        }),
      );

      expect(
        screen.getByRole("button", { name: /collapse sidebar/i }),
      ).toBeInTheDocument();
    });
  });

  describe("Super-admin section", () => {
    test("does not render super-admin section for non-admins even with registry entries", () => {
      registerSuperAdminNavRow({
        id: "feature-flags" as NavRowId,
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
        id: "feature-flags" as NavRowId,
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

      expect(screen.queryByText(/^admin$/i)).not.toBeInTheDocument();
    });

    test("rejects registration of rows with invalid paths", () => {
      registerSuperAdminNavRow({
        id: "bad-row" as NavRowId,
        label: "Bad Row",
        path: "javascript:alert(1)",
        order: 10,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(0);
    });

    test("deduplicates rows with the same id", () => {
      registerSuperAdminNavRow({
        id: "feature-flags" as NavRowId,
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: "feature-flags" as NavRowId,
        label: "Feature Flags Duplicate",
        path: "/admin/feature-flags",
        order: 10,
      });

      expect(SUPER_ADMIN_NAV).toHaveLength(1);
    });

    test("shows/hides admin section when isSuperAdmin changes mid-session", () => {
      registerSuperAdminNavRow({
        id: "feature-flags" as NavRowId,
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });

      const { rerender } = render(
        <MemoryRouter initialEntries={["/"]}>
          <AuthContext.Provider
            value={mockAuthContext(false) as AuthContextType}
          >
            <Sidebar />
          </AuthContext.Provider>
        </MemoryRouter>,
      );

      expect(
        screen.queryByRole("link", { name: /feature flags/i }),
      ).not.toBeInTheDocument();

      rerender(
        <MemoryRouter initialEntries={["/"]}>
          <AuthContext.Provider
            value={mockAuthContext(true) as AuthContextType}
          >
            <Sidebar />
          </AuthContext.Provider>
        </MemoryRouter>,
      );

      expect(
        screen.getByRole("link", { name: /feature flags/i }),
      ).toBeInTheDocument();

      rerender(
        <MemoryRouter initialEntries={["/"]}>
          <AuthContext.Provider
            value={mockAuthContext(false) as AuthContextType}
          >
            <Sidebar />
          </AuthContext.Provider>
        </MemoryRouter>,
      );

      expect(
        screen.queryByRole("link", { name: /feature flags/i }),
      ).not.toBeInTheDocument();
    });

    test("does not render rows with isVisible: false", () => {
      registerSuperAdminNavRow({
        id: "visible-row" as NavRowId,
        label: "Visible Row",
        path: "/admin/visible",
        order: 10,
        isVisible: true,
      });
      registerSuperAdminNavRow({
        id: "hidden-row" as NavRowId,
        label: "Hidden Row",
        path: "/admin/hidden",
        order: 20,
        isVisible: false,
      });

      renderSidebar({ isSuperAdmin: true });

      expect(
        screen.getByRole("link", { name: /visible row/i }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: /hidden row/i }),
      ).not.toBeInTheDocument();
    });

    test("renders admin rows sorted by order ascending", () => {
      registerSuperAdminNavRow({
        id: "row-order-20" as NavRowId,
        label: "Row Order 20",
        path: "/admin/order-20",
        order: 20,
      });
      registerSuperAdminNavRow({
        id: "row-order-10" as NavRowId,
        label: "Row Order 10",
        path: "/admin/order-10",
        order: 10,
      });

      renderSidebar({ isSuperAdmin: true });

      const links = screen.getAllByRole("link", { name: /row order/i });
      expect(links).toHaveLength(2);
      expect(links[0]).toHaveTextContent("Row Order 10");
      expect(links[1]).toHaveTextContent("Row Order 20");
    });
  });

  describe("Keyboard navigation", () => {
    test("Tab from collapse toggle reaches the Chat nav link", async () => {
      const user = userEvent.setup();
      renderSidebar();

      const collapseToggle = screen.getByRole("button", {
        name: /collapse sidebar/i,
      });
      collapseToggle.focus();
      expect(collapseToggle).toHaveFocus();

      await user.tab();

      const chatLink = screen.getByRole("link", { name: /^chat$/i });
      expect(chatLink).toHaveFocus();
    });

    test("nav links have correct href attributes", () => {
      renderSidebar();

      expect(screen.getByRole("link", { name: /^chat$/i })).toHaveAttribute(
        "href",
        "/",
      );
      expect(
        screen.getByRole("link", { name: /performance/i }),
      ).toHaveAttribute("href", "/performance");
      expect(screen.getByRole("link", { name: /calendar/i })).toHaveAttribute(
        "href",
        "/calendar",
      );
      expect(screen.getByRole("link", { name: /workflows/i })).toHaveAttribute(
        "href",
        "/workflows",
      );
      expect(screen.getByRole("link", { name: /knowledge/i })).toHaveAttribute(
        "href",
        "/strategy",
      );
      expect(screen.getByRole("link", { name: /extensions/i })).toHaveAttribute(
        "href",
        "/extensions",
      );
      expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute(
        "href",
        "/settings/account",
      );
    });
  });
});
