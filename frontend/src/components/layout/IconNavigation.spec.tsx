import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { IconNavigation } from "./IconNavigation";
import { AuthContext } from "@/contexts/AuthContext";
import type { AuthContextType } from "@/contexts/AuthContext";

const mockAuthContext = (isSuperAdmin: boolean = false): AuthContextType => ({
  user: isSuperAdmin
    ? {
        id: "test-user" as any,
        email: "admin@ken-e.ai",
        firstName: "Admin",
        lastName: "User",
      }
    : {
        id: "test-user" as any,
        email: "user@example.com",
        firstName: "Regular",
        lastName: "User",
      },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  currentOrganizationId: "org-123" as any,
  selectedOrgAccount: null,
  notifications: [],
  login: vi.fn(),
  logout: vi.fn(),
  updateUser: vi.fn(),
  createOrganization: vi.fn(),
  setNotifications: vi.fn(),
  markNotificationAsRead: vi.fn(),
  archiveNotification: vi.fn(),
  setNotificationSettings: vi.fn(),
  setSecuritySettings: vi.fn(),
  isSuperAdmin,
});

const renderWithProviders = (
  ui: React.ReactElement,
  isSuperAdmin: boolean = false,
) => {
  const contextValue = mockAuthContext(isSuperAdmin);
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue}>{ui}</AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("IconNavigation", () => {
  test("renders all navigation items", () => {
    renderWithProviders(<IconNavigation />);

    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Performance" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Recommendations" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Campaigns" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reports" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Simulations" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Knowledge Base" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Orgs & Accounts" }),
    ).toBeInTheDocument();
  });

  test("navigates to correct route when clicking navigation items", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IconNavigation />);

    await user.click(screen.getByRole("button", { name: "Performance" }));
    expect(window.location.pathname).toBe("/performance");

    await user.click(screen.getByRole("button", { name: "Recommendations" }));
    expect(window.location.pathname).toBe("/recommendations");

    await user.click(screen.getByRole("button", { name: "Campaigns" }));
    expect(window.location.pathname).toBe("/campaigns");
  });

  test("shows active state for current route", () => {
    window.history.pushState({}, "", "/performance");
    renderWithProviders(<IconNavigation />);

    const performanceButton = screen.getByRole("button", {
      name: "Performance",
    });
    expect(performanceButton).toHaveClass("bg-brand-medium-blue", "text-white");
  });

  test("renders brand logo at the top", () => {
    renderWithProviders(<IconNavigation />);

    expect(screen.getByAltText("KEN-E Logo")).toBeInTheDocument();
  });

  test("renders user menu at the bottom", () => {
    renderWithProviders(<IconNavigation />);

    expect(
      screen.getByRole("button", { name: "User menu" }),
    ).toBeInTheDocument();
  });

  test("does not render admin settings icon for regular users", () => {
    renderWithProviders(<IconNavigation />, false);

    expect(
      screen.queryByRole("button", { name: "Admin Settings" }),
    ).not.toBeInTheDocument();
  });

  test("renders admin settings icon for super admin users", () => {
    renderWithProviders(<IconNavigation />, true);

    expect(
      screen.getByRole("button", { name: "Admin Settings" }),
    ).toBeInTheDocument();
  });

  test("navigates to admin settings when clicking admin icon", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IconNavigation />, true);

    const adminButton = screen.getByRole("button", { name: "Admin Settings" });
    await user.click(adminButton);

    expect(window.location.pathname).toBe("/settings/admin");
  });

  test("shows active state for admin settings route", () => {
    window.history.pushState({}, "", "/settings/admin/agent-configs");
    renderWithProviders(<IconNavigation />, true);

    const adminButton = screen.getByRole("button", { name: "Admin Settings" });
    expect(adminButton).toHaveClass("bg-brand-medium-blue", "text-white");
  });

  test("shows active state only on /settings/organization for gear icon", () => {
    window.history.pushState({}, "", "/settings/organization");
    renderWithProviders(<IconNavigation />);

    const settingsButton = screen.getByRole("button", {
      name: "Orgs & Accounts",
    });
    expect(settingsButton).toHaveClass("bg-brand-medium-blue", "text-white");
  });

  test("does not show active state on other settings pages for gear icon", () => {
    window.history.pushState({}, "", "/settings/user");
    renderWithProviders(<IconNavigation />);

    const settingsButton = screen.getByRole("button", {
      name: "Orgs & Accounts",
    });
    expect(settingsButton).not.toHaveClass("bg-brand-medium-blue");
    expect(settingsButton).toHaveClass("text-gray-400");
  });

  test("shows active state on /settings/user for user icon", () => {
    window.history.pushState({}, "", "/settings/user");
    renderWithProviders(<IconNavigation />);

    const userButton = screen.getByRole("button", { name: "User menu" });
    expect(userButton).toHaveClass("bg-brand-medium-blue", "text-white");
  });

  test("does not show active state on other pages for user icon", () => {
    window.history.pushState({}, "", "/settings/organization");
    renderWithProviders(<IconNavigation />);

    const userButton = screen.getByRole("button", { name: "User menu" });
    expect(userButton).not.toHaveClass("bg-brand-medium-blue");
    expect(userButton).toHaveClass("text-gray-400");
  });
});
