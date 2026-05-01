import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { ProfileMenu } from "./ProfileMenu";
import { AuthContext } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import {
  registerSuperAdminNavRow,
  resetSuperAdminNavForTesting,
} from "./super-admin-nav-registry";
import type { Brand } from "@/lib/branded-types";

type NavRowId = Brand<string, "NavRowId">;

const mockLogout = vi.fn();

const mockContext = {
  user: {
    id: "u1" as never,
    email: "jane@example.com",
    firstName: "Jane",
    lastName: "Doe",
  },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  currentOrganizationId: null,
  selectedOrgAccount: null,
  notifications: [],
  orgMetadata: {},
  accountMetadata: {},
  logout: mockLogout,
  login: vi.fn(),
  updateUser: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  resetWorkspaceSelection: vi.fn(),
  setCurrentOrganization: vi.fn(),
  setSelectedOrgAccount: vi.fn(),
  setOrgMetadata: vi.fn(),
  setAccountMetadata: vi.fn(),
  setNotifications: vi.fn(),
  refreshNotifications: vi.fn(),
  notificationSettings: [],
  securitySettings: [],
  setNotificationSettings: vi.fn(),
  setSecuritySettings: vi.fn(),
  isSuperAdmin: false,
};

function Providers({
  children,
  contextOverrides,
}: {
  children: ReactNode;
  contextOverrides: Partial<typeof mockContext>;
}) {
  const contextValue = { ...mockContext, ...contextOverrides };
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthContext.Provider value={contextValue as never}>
          {children}
        </AuthContext.Provider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

const renderWithProviders = (
  contextOverrides: Partial<typeof mockContext> = {},
) =>
  render(
    <Providers contextOverrides={contextOverrides}>
      <ProfileMenu />
    </Providers>,
  );

async function openMenu() {
  const user = userEvent.setup();
  const trigger = screen.getByRole("button", { name: /profile menu for/i });
  await user.click(trigger);
  return user;
}

describe("ProfileMenu", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    resetSuperAdminNavForTesting();
    mockLogout.mockClear();
  });

  describe("trigger and identity", () => {
    test("renders avatar trigger with aria-label containing user full name", () => {
      renderWithProviders();
      expect(
        screen.getByRole("button", { name: /profile menu for jane doe/i }),
      ).toBeInTheDocument();
    });

    test("trigger aria-label falls back to email when firstName and lastName are empty", () => {
      renderWithProviders({
        user: {
          id: "u1" as never,
          email: "x@y.com",
          firstName: "",
          lastName: "",
        },
      });
      expect(
        screen.getByRole("button", { name: /profile menu for x@y\.com/i }),
      ).toBeInTheDocument();
    });

    test("shows user initials in avatar", async () => {
      renderWithProviders();
      await openMenu();

      const initials = screen.getAllByText("JD");
      expect(initials.length).toBeGreaterThan(0);
    });

    test("shows U when user names are empty strings", () => {
      renderWithProviders({
        user: {
          id: "u1" as never,
          email: "test@example.com",
          firstName: "",
          lastName: "",
        },
      });

      const fallbacks = screen.getAllByText("U");
      expect(fallbacks.length).toBeGreaterThan(0);
    });

    test("initials: single name — firstName present, lastName empty → first initial only", () => {
      renderWithProviders({
        user: {
          id: "u1" as never,
          email: "jane@example.com",
          firstName: "Jane",
          lastName: "",
        },
      });
      const initials = screen.getAllByText("J");
      expect(initials.length).toBeGreaterThan(0);
    });

    test("initials: lowercase input is uppercased after concat — not before", () => {
      renderWithProviders({
        user: {
          id: "u1" as never,
          email: "jd@example.com",
          firstName: "jane",
          lastName: "doe",
        },
      });
      const initials = screen.getAllByText("JD");
      expect(initials.length).toBeGreaterThan(0);
    });

    test("initials: null user falls back to U via || operator", () => {
      renderWithProviders({ user: null as never });
      const fallbacks = screen.getAllByText("U");
      expect(fallbacks.length).toBeGreaterThan(0);
    });
  });

  describe("menu items", () => {
    test("calls logout on Sign Out click", async () => {
      renderWithProviders();
      const user = await openMenu();

      const signOutItem = await screen.findByRole("menuitem", {
        name: /sign out/i,
      });
      await user.click(signOutItem);

      expect(mockLogout).toHaveBeenCalledTimes(1);
    });

    test("renders User Settings link", async () => {
      renderWithProviders();
      await openMenu();

      const settingsItem = await screen.findByRole("menuitem", {
        name: /user settings/i,
      });
      expect(settingsItem).toHaveAttribute("href", "/settings/user");
    });
  });

  describe("theme toggle", () => {
    test("light mode shows Dark Mode label with Moon icon", async () => {
      renderWithProviders();
      await openMenu();
      expect(
        await screen.findByRole("menuitem", { name: /dark mode/i }),
      ).toBeInTheDocument();
    });

    test("clicking theme item toggles <html>.dark on", async () => {
      renderWithProviders();
      const user = await openMenu();

      expect(document.documentElement.classList.contains("dark")).toBe(false);

      const themeItem = await screen.findByRole("menuitem", {
        name: /dark mode/i,
      });
      await user.click(themeItem);

      expect(document.documentElement.classList.contains("dark")).toBe(true);
    });

    test("after enabling dark mode, the menu shows Light Mode label with Sun icon", async () => {
      // Pre-set dark mode so the next render shows the inverse-state label.
      localStorage.setItem("kene-theme", "dark");
      renderWithProviders();
      await openMenu();

      expect(document.documentElement.classList.contains("dark")).toBe(true);
      expect(
        await screen.findByRole("menuitem", { name: /light mode/i }),
      ).toBeInTheDocument();
    });

    test("clicking theme item again flips <html>.dark off", async () => {
      localStorage.setItem("kene-theme", "dark");
      renderWithProviders();
      const user = await openMenu();

      expect(document.documentElement.classList.contains("dark")).toBe(true);

      const themeItem = await screen.findByRole("menuitem", {
        name: /light mode/i,
      });
      await user.click(themeItem);

      expect(document.documentElement.classList.contains("dark")).toBe(false);
    });
  });

  describe("super-admin section", () => {
    test("does not render the Admin section when isSuperAdmin is false (even with rows)", async () => {
      registerSuperAdminNavRow({
        id: "feature-flags" as NavRowId,
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });
      renderWithProviders({ isSuperAdmin: false });
      await openMenu();

      expect(
        screen.queryByRole("menuitem", { name: /feature flags/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText(/^admin$/i)).not.toBeInTheDocument();
    });

    test("does not render the Admin section when isSuperAdmin is true but registry is empty", async () => {
      renderWithProviders({ isSuperAdmin: true });
      await openMenu();

      expect(screen.queryByText(/^admin$/i)).not.toBeInTheDocument();
    });

    test("renders the Admin label and registered rows when isSuperAdmin is true", async () => {
      registerSuperAdminNavRow({
        id: "feature-flags" as NavRowId,
        label: "Feature Flags",
        path: "/admin/feature-flags",
        order: 10,
      });
      renderWithProviders({ isSuperAdmin: true });
      await openMenu();

      expect(screen.getByText(/^admin$/i)).toBeInTheDocument();
      const ffItem = await screen.findByRole("menuitem", {
        name: /feature flags/i,
      });
      expect(ffItem).toHaveAttribute("href", "/admin/feature-flags");
    });

    test("filters rows with isVisible: false", async () => {
      registerSuperAdminNavRow({
        id: "visible" as NavRowId,
        label: "Visible Row",
        path: "/admin/visible",
        order: 10,
        isVisible: true,
      });
      registerSuperAdminNavRow({
        id: "hidden" as NavRowId,
        label: "Hidden Row",
        path: "/admin/hidden",
        order: 20,
        isVisible: false,
      });
      renderWithProviders({ isSuperAdmin: true });
      await openMenu();

      expect(
        await screen.findByRole("menuitem", { name: /visible row/i }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("menuitem", { name: /hidden row/i }),
      ).not.toBeInTheDocument();
    });

    test("renders rows in ascending order by `order`", async () => {
      registerSuperAdminNavRow({
        id: "row-30" as NavRowId,
        label: "Row 30",
        path: "/admin/30",
        order: 30,
      });
      registerSuperAdminNavRow({
        id: "row-10" as NavRowId,
        label: "Row 10",
        path: "/admin/10",
        order: 10,
      });
      registerSuperAdminNavRow({
        id: "row-20" as NavRowId,
        label: "Row 20",
        path: "/admin/20",
        order: 20,
      });
      renderWithProviders({ isSuperAdmin: true });
      await openMenu();

      const items = await screen.findAllByRole("menuitem", {
        name: /^row /i,
      });
      expect(items.map((el) => el.textContent)).toEqual([
        "Row 10",
        "Row 20",
        "Row 30",
      ]);
    });
  });
});
