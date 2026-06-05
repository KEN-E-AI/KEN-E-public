import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import AccountSettings from "./AccountSettings";
import { useAuth } from "@/contexts/AuthContext";

const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }));

// Mock the hooks and API calls
vi.mock("@/contexts/AuthContext");
vi.mock("@/data/organizationApi");
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: toastSpy }),
}));

// Mock the components
vi.mock("./components/OrganizationForm", () => ({
  default: ({ orgData }: { orgData: any }) => (
    <div data-testid="organization-form">
      Organization Form - {orgData ? orgData.organization_name : "No data"}
    </div>
  ),
}));

vi.mock("./components/SubscriptionCard", () => ({
  default: () => <div data-testid="subscription-card">Subscription Card</div>,
}));

vi.mock("./components/AccountsManagement", () => ({
  default: () => (
    <div data-testid="accounts-management">Accounts Management</div>
  ),
}));

vi.mock("./components/BillingSection", () => ({
  default: () => <div data-testid="billing-section">Billing Section</div>,
}));

vi.mock("./components/TeamManagement", () => ({
  default: () => <div data-testid="team-management">Team Management</div>,
}));

vi.mock("./components/DangerZone", () => ({
  default: () => <div data-testid="danger-zone">Danger Zone</div>,
}));

vi.mock("@/components/layout/SettingsLayout", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="settings-layout">{children}</div>
  ),
}));

vi.mock("@/components/integrations/GoogleAnalyticsPropertySelector", () => ({
  GoogleAnalyticsPropertySelector: () => (
    <div data-testid="ga-property-selector">GA Property Selector</div>
  ),
}));

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;

describe("AccountSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderAccountSettings = () => {
    return render(
      <BrowserRouter>
        <AccountSettings />
      </BrowserRouter>,
    );
  };

  it("should show loading state when orgMetadata is empty and user has org access", () => {
    const mockUser = {
      id: "test-user-123",
      email: "test@example.com",
      firstName: "Test",
      lastName: "User",
      permissions: {
        organizations: {
          "ej-enterprises-2": "admin",
        },
      },
    };

    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: "ej-enterprises-2",
      orgMetadata: {},
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
      isSuperAdmin: false,
    });

    renderAccountSettings();

    expect(
      screen.getByText("Loading organization data..."),
    ).toBeInTheDocument();
  });

  it("should show 6-tab org structure with General tab active when org data is loaded", async () => {
    const mockUser = {
      id: "test-user-123",
      email: "test@example.com",
      firstName: "Test",
      lastName: "User",
      permissions: {
        organizations: {
          "ej-enterprises-2": "admin",
        },
      },
    };

    const mockOrganization = {
      organization_id: "ej-enterprises-2",
      organization_name: "EJ Enterprises 2",
      plan: "Free",
      company_size: "11-50",
      agency: false,
      child_organizations: [],
      accounts: [],
    };

    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: "ej-enterprises-2",
      orgMetadata: {
        "ej-enterprises-2": mockOrganization,
      },
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
      isSuperAdmin: false,
    });

    renderAccountSettings();

    // All 6 tab triggers present
    expect(screen.getByRole("tab", { name: /General/i })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /Subscription/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Billing/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Team/i })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /Integrations/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Accounts/i })).toBeInTheDocument();

    // General tab is active by default — OrganizationForm and DangerZone render
    await waitFor(() => {
      expect(
        screen.getByText("Organization Form - EJ Enterprises 2"),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("danger-zone")).toBeInTheDocument();
  });

  it("resolves the org from selectedOrgAccount when currentOrganizationId is unset", async () => {
    // Super-admin case: the membership doc only lists the Evals org, but the
    // header switcher has Bank of America selected. The settings page must
    // follow the header, not the membership doc.
    const mockUser = {
      id: "test-user-123",
      email: "admin@ken-e.ai",
      firstName: "Super",
      lastName: "Admin",
      permissions: {
        organizations: {
          "evals-org": "view",
        },
      },
    };

    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: null,
      selectedOrgAccount: {
        orgId: "bofa-org",
        accountId: "bofa-acct",
        metadata: { organization_name: "Bank of America" },
      },
      orgMetadata: {
        "bofa-org": {
          organization_id: "bofa-org",
          organization_name: "Bank of America",
          accounts: [],
        },
        "evals-org": {
          organization_id: "evals-org",
          organization_name: "Evals 20260306",
          accounts: [],
        },
      },
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
      isSuperAdmin: true,
    });

    renderAccountSettings();

    await waitFor(() => {
      expect(
        screen.getByText("Organization Form - Bank of America"),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Organization Form - Evals 20260306"),
    ).not.toBeInTheDocument();
  });

  it("shows a destructive toast when redirected back with an oauth_error", async () => {
    const mockUser = {
      id: "test-user-123",
      email: "test@example.com",
      permissions: { organizations: {} },
    };

    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: null,
      selectedOrgAccount: undefined,
      orgMetadata: {},
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
      isSuperAdmin: false,
    });

    render(
      <MemoryRouter
        initialEntries={["/settings/account?oauth_error=token_exchange_failed"]}
      >
        <AccountSettings />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: "destructive",
          title: expect.stringMatching(/connection failed/i),
        }),
      ),
    );
  });

  it("should show org settings tabs when user has no organization permissions", () => {
    const mockUser = {
      id: "test-user-123",
      email: "test@example.com",
      firstName: "Test",
      lastName: "User",
      permissions: {
        organizations: {},
      },
    };

    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: null,
      orgMetadata: {},
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
      isSuperAdmin: false,
    });

    renderAccountSettings();

    // Tab shell always renders; no early return blocking the 6-tab structure
    expect(screen.getByRole("tab", { name: /general/i })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /subscription/i }),
    ).toBeInTheDocument();
  });
});
