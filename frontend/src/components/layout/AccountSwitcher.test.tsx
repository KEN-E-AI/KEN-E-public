import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { AccountSwitcher } from "./AccountSwitcher";
import { AuthContext } from "@/contexts/AuthContext";
import type { AccountId, OrganizationId } from "@/lib/branded-types";

const mockAuthContext = {
  user: {
    id: "user-1" as any,
    email: "test@test.com",
    firstName: "Test",
    lastName: "User",
  },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  currentOrganizationId: "org-1" as any,
  selectedOrgAccount: {
    orgId: "org-1" as any,
    accountId: "acct-1" as any,
    metadata: {
      organization_name: "Acme Corp",
      account_name: "Main Account",
      industry: "Tech",
      status: "active",
    },
  },
  orgMetadata: {
    "org-1": { organization_name: "Acme Corp", plan: "pro" },
  },
  accountMetadata: {
    "acct-1": {
      account_name: "Main Account",
      industry: "Tech",
      status: "active",
      organization_id: "org-1",
    },
    "acct-2": {
      account_name: "Secondary Account",
      industry: "Tech",
      status: "active",
      organization_id: "org-1",
    },
  },
  setSelectedOrgAccount: vi.fn(),
  setCurrentOrganization: vi.fn(),
  notifications: [],
  logout: vi.fn(),
  login: vi.fn(),
  updateUser: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  resetWorkspaceSelection: vi.fn(),
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
  const contextValue = { ...mockAuthContext, ...contextOverrides };
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue as any}>
        <AccountSwitcher />
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("AccountSwitcher", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders trigger with org/account name when selectedOrgAccount is non-null", () => {
    renderWithProviders();

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Main Account")).toBeInTheDocument();
  });

  test("renders 'Select account' when selectedOrgAccount is null", () => {
    renderWithProviders({ selectedOrgAccount: null });

    expect(screen.getByText("Select account")).toBeInTheDocument();
  });

  test("calls setSelectedOrgAccount and setCurrentOrganization on selection", async () => {
    const user = userEvent.setup();
    const setSelectedOrgAccount = vi.fn();
    const setCurrentOrganization = vi.fn();

    renderWithProviders({ setSelectedOrgAccount, setCurrentOrganization });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    const secondAccount = await screen.findByText("Secondary Account");
    await user.click(secondAccount);

    expect(setSelectedOrgAccount).toHaveBeenCalledTimes(1);
    expect(setSelectedOrgAccount).toHaveBeenCalledWith(
      expect.objectContaining({
        orgId: "org-1" as OrganizationId,
        accountId: "acct-2" as AccountId,
        metadata: expect.objectContaining({
          account_name: "Secondary Account",
        }),
      }),
    );
    expect(setCurrentOrganization).toHaveBeenCalledTimes(1);
    expect(setCurrentOrganization).toHaveBeenCalledWith(
      "org-1" as OrganizationId,
    );
  });

  test("active account row has Check icon", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await screen.findByText("Secondary Account");

    const checkIcons = document.querySelectorAll("svg.lucide-check");
    expect(checkIcons.length).toBeGreaterThan(0);
  });
});
