import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { ProfileMenu } from "./ProfileMenu";
import { AuthContext } from "@/contexts/AuthContext";

const mockLogout = vi.fn();

const mockContext = {
  user: {
    id: "u1" as any,
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

const renderWithProviders = (contextOverrides = {}) => {
  const contextValue = { ...mockContext, ...contextOverrides };
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue as any}>
        <ProfileMenu />
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("ProfileMenu", () => {
  test("renders avatar trigger with aria-label containing user full name", () => {
    renderWithProviders();
    expect(
      screen.getByRole("button", { name: /profile menu for jane doe/i }),
    ).toBeInTheDocument();
  });

  test("trigger aria-label falls back to email when firstName and lastName are empty", () => {
    renderWithProviders({
      user: { id: "u1" as any, email: "x@y.com", firstName: "", lastName: "" },
    });
    expect(
      screen.getByRole("button", { name: /profile menu for x@y\.com/i }),
    ).toBeInTheDocument();
  });

  test("shows user initials in avatar", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    const trigger = screen.getByRole("button", {
      name: /profile menu for jane doe/i,
    });
    await user.click(trigger);

    const initials = screen.getAllByText("JD");
    expect(initials.length).toBeGreaterThan(0);
  });

  test("shows U when user names are empty strings", () => {
    renderWithProviders({
      user: {
        id: "u1" as any,
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
        id: "u1" as any,
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
        id: "u1" as any,
        email: "jd@example.com",
        firstName: "jane",
        lastName: "doe",
      },
    });
    const initials = screen.getAllByText("JD");
    expect(initials.length).toBeGreaterThan(0);
  });

  test("initials: null user falls back to U via || operator", () => {
    renderWithProviders({ user: null });
    const fallbacks = screen.getAllByText("U");
    expect(fallbacks.length).toBeGreaterThan(0);
  });

  test("calls logout on Sign Out click", async () => {
    const user = userEvent.setup();
    mockLogout.mockClear();
    renderWithProviders();

    const trigger = screen.getByRole("button", {
      name: /profile menu for jane doe/i,
    });
    await user.click(trigger);

    const signOutItem = await screen.findByText("Sign Out");
    await user.click(signOutItem);

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  test("renders User Settings link", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    const trigger = screen.getByRole("button", {
      name: /profile menu for jane doe/i,
    });
    await user.click(trigger);

    // DropdownMenuItem asChild renders the Link as role="menuitem" (Radix overrides)
    const settingsItem = await screen.findByRole("menuitem", {
      name: /user settings/i,
    });
    expect(settingsItem).toHaveAttribute("href", "/settings/user");
  });
});
