import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { NotificationBell } from "./NotificationBell";
import { AuthContext } from "@/contexts/AuthContext";
import type { AccountId, OrganizationId } from "@/lib/branded-types";

vi.mock("@/components/notifications/NotificationSidebar", () => ({
  NotificationSidebar: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="notification-sidebar">Notifications</div> : null,
}));

const baseMockContext = {
  user: { id: "u1" as any, email: "a@b.com", firstName: "A", lastName: "B" },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  currentOrganizationId: "org-1" as OrganizationId,
  selectedOrgAccount: {
    orgId: "org-1" as OrganizationId,
    accountId: "acct-1" as AccountId,
    metadata: {
      organization_name: "Acme",
      account_name: "Main",
      industry: "Tech",
      status: "active",
    },
  },
  notifications: [],
  orgMetadata: {},
  accountMetadata: {},
  logout: vi.fn(),
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
  const contextValue = { ...baseMockContext, ...contextOverrides };
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue as any}>
        <NotificationBell />
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("NotificationBell", () => {
  test("renders bell button with aria-label", () => {
    renderWithProviders();
    expect(
      screen.getByRole("button", { name: "Notifications" }),
    ).toBeInTheDocument();
  });

  test("shows badge when unreadCount > 0", () => {
    renderWithProviders({
      notifications: [
        { id: "1", status: "unread", account_id: "acct-1" as any },
      ],
    });
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  test('shows "9+" for counts above 9', () => {
    const notifications = Array.from({ length: 10 }, (_, i) => ({
      id: String(i),
      status: "unread",
      account_id: "acct-1" as any,
    }));
    renderWithProviders({ notifications });
    expect(screen.getByText("9+")).toBeInTheDocument();
  });

  test('shows "9" (not "9+") for exactly 9 unread', () => {
    const notifications = Array.from({ length: 9 }, (_, i) => ({
      id: String(i),
      status: "unread",
      account_id: "acct-1" as any,
    }));
    renderWithProviders({ notifications });
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.queryByText("9+")).not.toBeInTheDocument();
  });

  test("no badge when all read", () => {
    renderWithProviders({
      notifications: [{ id: "1", status: "read", account_id: "acct-1" as any }],
    });
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });

  test("click opens NotificationSidebar", async () => {
    const user = userEvent.setup();
    renderWithProviders();
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByTestId("notification-sidebar")).toBeInTheDocument();
  });

  test("click when selectedOrgAccount is null does not open sidebar", async () => {
    const user = userEvent.setup();
    renderWithProviders({ selectedOrgAccount: null });
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    expect(
      screen.queryByTestId("notification-sidebar"),
    ).not.toBeInTheDocument();
  });
});
