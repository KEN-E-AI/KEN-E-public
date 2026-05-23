import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import AccountSettings from "../AccountSettings";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";

// Mock the organization API
vi.mock("@/data/organizationApi", () => ({
  getAccountsByOrganizationId: vi.fn().mockResolvedValue([]),
  createOrganization: vi.fn(),
  updateOrganization: vi.fn(),
  getOrganizationById: vi.fn().mockResolvedValue(null),
  getOrganizations: vi.fn().mockResolvedValue([]),
  createNewOrganization: vi.fn(),
  createNewAccount: vi.fn(),
  getChildOrganizations: vi.fn().mockResolvedValue([]),
}));

// Mock the toast hook
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock settings navigation
vi.mock("@/hooks/useSettingsNavigation", () => ({
  useSettingsNavigation: () => ({ currentSection: "organization" }),
}));

// Mock navigation
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({
      pathname: "/settings/organization",
    }),
  };
});

const mockUserWithMultipleOrgs = {
  uid: "user123",
  email: "test@example.com",
  firstName: "Test",
  lastName: "User",
  permissions: {
    organizations: {
      "org-1": "admin",
      "org-2": "admin",
      "org-3": "viewer",
    },
  },
};

const mockUserWithSingleOrg = {
  uid: "user123",
  email: "test@example.com",
  firstName: "Test",
  lastName: "User",
  permissions: {
    organizations: {
      "org-1": "admin",
    },
  },
};

const mockOrgData1 = {
  organization_id: "org-1",
  organization_name: "Organization 1",
  plan: "Professional",
  website: "https://org1.com",
  company_size: "medium",
  agency: false,
  child_organizations: [],
  subscription: {
    plan_name: "Professional Plan",
    plan_description: "Test plan",
    price: 99.0,
    currency: "USD",
    billing_cycle: "monthly",
    next_billing_date: "2024-02-15",
    features: ["Feature 1"],
    usage: { reports_generated: 10, reports_limit: 100 },
  },
  billing: {
    payment_method: { last_four: "4242", brand: "Visa", expires: "12/25" },
    address: "123 Test St",
    tax_id: "123456789",
  },
  team: { members_used: 5, members_limit: 10, pending_invitations: 0 },
};

const mockOrgData2 = {
  organization_id: "org-2",
  organization_name: "Organization 2",
  plan: "Enterprise",
  website: "https://org2.com",
  company_size: "large",
  agency: false,
  child_organizations: [],
  subscription: mockOrgData1.subscription,
  billing: mockOrgData1.billing,
  team: mockOrgData1.team,
};

const createMockAuthContext = (user: any, orgMetadata: any) =>
  ({
    user,
    updateUser: vi.fn(),
    completeWorkspaceSelection: vi.fn(),
    currentOrganizationId: "org-1",
    setCurrentOrganization: vi.fn(),
    orgMetadata,
    setOrgMetadata: vi.fn(),
    accountMetadata: {},
    setAccountMetadata: vi.fn(),
    setSelectedOrgAccount: vi.fn(),
    loading: false,
    selectedOrganization: mockOrgData1,
    selectedAccount: null,
    signOut: vi.fn(),
    setUser: vi.fn(),
    setSelectedOrganization: vi.fn(),
    setSelectedAccount: vi.fn(),
  }) as unknown as AuthContextType;

const renderAccountSettings = (user: any, orgMetadata: any) => {
  const mockAuthContext = createMockAuthContext(user, orgMetadata);
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={mockAuthContext}>
        <AccountSettings />
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("Organization Selector", () => {
  test("should show organization selector when user has multiple organizations", () => {
    const orgMetadata = {
      "org-1": mockOrgData1,
      "org-2": mockOrgData2,
    };

    renderAccountSettings(mockUserWithMultipleOrgs, orgMetadata);

    expect(screen.getByText("Organization Selection")).toBeInTheDocument();
  });

  test("should show organization selector even when user has only one organization", () => {
    const orgMetadata = {
      "org-1": mockOrgData1,
    };

    renderAccountSettings(mockUserWithSingleOrg, orgMetadata);

    // The organization selector should always be shown in the layout
    expect(screen.getByText("Organization Selection")).toBeInTheDocument();
  });

  test("should show organization selector with current organization selected", () => {
    const orgMetadata = {
      "org-1": mockOrgData1,
      "org-2": mockOrgData2,
    };

    renderAccountSettings(mockUserWithMultipleOrgs, orgMetadata);

    // The EntitySelector should show the current organization
    expect(screen.getByText("Organization 1")).toBeInTheDocument();
  });

  test("should render organization settings page with selector when multiple orgs available", () => {
    const orgMetadata = {
      "org-1": mockOrgData1,
      "org-2": mockOrgData2,
    };

    renderAccountSettings(mockUserWithMultipleOrgs, orgMetadata);

    // Verify the page structure
    expect(screen.getByText("Organization Settings")).toBeInTheDocument();
    expect(screen.getByText("Organization Selection")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create New Organization" }),
    ).toBeInTheDocument();
  });

  test("should maintain clean layout when only one organization exists", () => {
    const orgMetadata = {
      "org-1": mockOrgData1,
    };

    renderAccountSettings(mockUserWithSingleOrg, orgMetadata);

    // Verify the page structure with selector (now always shown)
    expect(screen.getByText("Organization Settings")).toBeInTheDocument();
    expect(screen.getByText("Organization Selection")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create New Organization" }),
    ).toBeInTheDocument();
  });
});
