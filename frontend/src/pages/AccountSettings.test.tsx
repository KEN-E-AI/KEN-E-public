import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { vi } from "vitest";
import AccountSettings from "./AccountSettings";
import { useAuth } from "@/contexts/AuthContext";
import {
  getOrganizationById,
  getAccountsByOrganizationId,
} from "@/data/organizationApi";

// Mock the hooks and API calls
vi.mock("@/contexts/AuthContext");
vi.mock("@/data/organizationApi");
vi.mock("@/hooks/useSettingsNavigation", () => ({
  useSettingsNavigation: () => ({ currentSection: "organization" }),
}));
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
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

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;
const mockGetOrganizationById = getOrganizationById as ReturnType<typeof vi.fn>;
const mockGetAccountsByOrganizationId =
  getAccountsByOrganizationId as ReturnType<typeof vi.fn>;

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

  it("should load organization metadata when not already loaded", async () => {
    // Mock user with organization permissions
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

    // Mock organization data
    const mockOrganization = {
      organization_id: "ej-enterprises-2",
      organization_name: "EJ Enterprises 2",
      plan: "Free",
      company_size: "11-50",
      agency: false,
      child_organizations: [],
    };

    // Mock accounts data
    const mockAccounts = [
      {
        account_id: "acc_123",
        account_name: "EJ Cafe",
        organization_id: "ej-enterprises-2",
        industry: "Retail",
        status: "Active",
      },
    ];

    // Setup mocks
    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: "ej-enterprises-2",
      orgMetadata: {}, // Initially empty
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
    });

    mockGetOrganizationById.mockResolvedValue(mockOrganization);
    mockGetAccountsByOrganizationId.mockResolvedValue(mockAccounts);

    renderAccountSettings();

    // Should show loading state initially
    expect(
      screen.getByText("Loading organization data..."),
    ).toBeInTheDocument();

    // Wait for organization data to load
    await waitFor(() => {
      expect(mockGetOrganizationById).toHaveBeenCalledWith("ej-enterprises-2");
      expect(mockGetAccountsByOrganizationId).toHaveBeenCalledWith(
        "ej-enterprises-2",
      );
    });
  });

  it("should show organization form when organization data is loaded", async () => {
    // Mock user with organization permissions
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

    // Mock organization data already loaded
    const mockOrganization = {
      organization_id: "ej-enterprises-2",
      organization_name: "EJ Enterprises 2",
      plan: "Free",
      company_size: "11-50",
      agency: false,
      child_organizations: [],
      accounts: [],
    };

    // Setup mocks
    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: "ej-enterprises-2",
      orgMetadata: {
        "ej-enterprises-2": mockOrganization,
      },
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
    });

    renderAccountSettings();

    // Should show organization form with data
    await waitFor(() => {
      expect(
        screen.getByText("Organization Form - EJ Enterprises 2"),
      ).toBeInTheDocument();
    });

    // Should show all the organization sections
    expect(screen.getByTestId("subscription-card")).toBeInTheDocument();
    expect(screen.getByTestId("accounts-management")).toBeInTheDocument();
    expect(screen.getByTestId("billing-section")).toBeInTheDocument();
    expect(screen.getByTestId("team-management")).toBeInTheDocument();
    expect(screen.getByTestId("danger-zone")).toBeInTheDocument();
  });

  it("should show no organization access when user has no organization permissions", () => {
    // Mock user without organization permissions
    const mockUser = {
      id: "test-user-123",
      email: "test@example.com",
      firstName: "Test",
      lastName: "User",
      permissions: {
        organizations: {},
      },
    };

    // Setup mocks
    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      currentOrganizationId: null,
      orgMetadata: {},
      setOrgMetadata: vi.fn(),
      setCurrentOrganization: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      updateUser: vi.fn(),
      setAccountMetadata: vi.fn(),
    });

    renderAccountSettings();

    // Should show no organization access message
    expect(
      screen.getByText("No organization access found"),
    ).toBeInTheDocument();
  });
});
