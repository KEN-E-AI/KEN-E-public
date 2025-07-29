import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AuthContext } from "@/contexts/AuthContext";
import AccountsManagement from "./AccountsManagement";

// Mock the queries
vi.mock("@/queries/accounts", () => ({
  useAccounts: () => ({
    data: [
      {
        account_id: "test-account-1",
        account_name: "Test Account 1",
        industry: "technology",
        status: "Active",
      },
      {
        account_id: "test-account-2",
        account_name: "Test Account 2",
        industry: "retail",
        status: "Active",
      },
    ],
    isLoading: false,
  }),
  useCreateAccount: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDeleteAccount: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateAccount: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/queries/activities", () => ({
  useSyncHolidayActivityLogs: () => ({
    mutateAsync: vi.fn(),
  }),
}));

// Mock the toast hook
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

const mockAuthContext = {
  user: {
    id: "user123",
    email: "test@example.com",
    permissions: {
      organizations: {
        "test-org": "admin",
      },
      accounts: {
        "test-account-1": "admin",
        "test-account-2": "admin",
      },
    },
  },
  updateUser: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  currentOrganizationId: "test-org",
  setCurrentOrganization: vi.fn(),
  orgMetadata: {},
  setOrgMetadata: vi.fn(),
  accountMetadata: {},
  setAccountMetadata: vi.fn(),
  setSelectedOrgAccount: vi.fn(),
  loading: false,
  selectedOrganization: null,
  selectedAccount: null,
  signOut: vi.fn(),
  setUser: vi.fn(),
  setSelectedOrganization: vi.fn(),
  setSelectedAccount: vi.fn(),
  isSuperAdmin: false,
};

const mockOrgData = {
  organization_id: "test-org",
  organization_name: "Test Organization",
  plan: "Professional",
  website: "",
  company_size: "medium",
  agency: false,
  child_organizations: [],
};

const renderAccountsManagement = (hasAdminAccess = true) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthContext.Provider value={mockAuthContext}>
          <AccountsManagement
            orgData={mockOrgData}
            currentOrgId="test-org"
            hasAdminAccess={hasAdminAccess}
          />
        </AuthContext.Provider>
      </BrowserRouter>
    </QueryClientProvider>,
  );
};

describe("AccountsManagement - View-Only Access", () => {
  test("should hide create account button for view-only users", () => {
    renderAccountsManagement(false);

    // The card should still be visible
    expect(screen.getByText("Accounts")).toBeInTheDocument();

    // Should show the accounts
    expect(screen.getByText("Test Account 1")).toBeInTheDocument();
    expect(screen.getByText("Test Account 2")).toBeInTheDocument();

    // But should not have any buttons (no create or edit buttons)
    const buttons = screen.queryAllByRole("button");
    expect(buttons).toHaveLength(0);
  });

  test("should show create account button for admin users", () => {
    renderAccountsManagement(true);

    // The card should be visible
    expect(screen.getByText("Accounts")).toBeInTheDocument();

    // Admin users should see more buttons (including create)
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThanOrEqual(2); // At least create button and settings buttons
  });

  test("should hide edit/settings buttons for view-only users", () => {
    renderAccountsManagement(false);

    // Should show the accounts
    expect(screen.getByText("Test Account 1")).toBeInTheDocument();
    expect(screen.getByText("Test Account 2")).toBeInTheDocument();

    // But should not show any settings buttons
    const buttons = screen.queryAllByRole("button");
    expect(buttons.length).toBe(0); // No buttons for view-only users
  });

  test("should show edit/settings buttons for admin users", () => {
    renderAccountsManagement(true);

    // Should show the accounts
    expect(screen.getByText("Test Account 1")).toBeInTheDocument();
    expect(screen.getByText("Test Account 2")).toBeInTheDocument();

    // Should show settings buttons for each account plus the create button
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThanOrEqual(3); // Create button + 2 settings buttons
  });

  test("should not open create modal for view-only users even if openCreateModal is true", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthContext.Provider value={mockAuthContext}>
            <AccountsManagement
              orgData={mockOrgData}
              currentOrgId="test-org"
              hasAdminAccess={false}
              openCreateModal={true}
            />
          </AuthContext.Provider>
        </BrowserRouter>
      </QueryClientProvider>,
    );

    // Should not show the create account modal
    expect(screen.queryByText("Create New Account")).not.toBeInTheDocument();
  });

  test("should show appropriate UI for agency organizations", () => {
    const agencyOrgData = {
      ...mockOrgData,
      agency: true,
    };

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthContext.Provider value={mockAuthContext}>
            <AccountsManagement
              orgData={agencyOrgData}
              currentOrgId="test-org"
              hasAdminAccess={true}
            />
          </AuthContext.Provider>
        </BrowserRouter>
      </QueryClientProvider>,
    );

    // Should show agency-specific message
    expect(
      screen.getByText("Agency organizations cannot create accounts."),
    ).toBeInTheDocument();

    // Should not show create button even for admin users
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBe(2); // Only settings buttons, no create button
  });
});
