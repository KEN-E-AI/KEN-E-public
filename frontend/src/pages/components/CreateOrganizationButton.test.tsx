import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import AccountSettings from "../AccountSettings";
import { AuthContext } from "@/contexts/AuthContext";

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

const mockUser = {
  uid: "user123",
  email: "test@example.com",
  firstName: "Test",
  lastName: "User",
  permissions: {
    organizations: {
      "test-org": "admin",
    },
  },
};

const mockOrgData = {
  organization_id: "test-org",
  organization_name: "Test Organization",
  plan: "Professional",
  website: "https://test.com",
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

const mockAuthContext = {
  user: mockUser,
  updateUser: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  currentOrganizationId: "test-org",
  setCurrentOrganization: vi.fn(),
  orgMetadata: {
    "test-org": mockOrgData,
  },
  setOrgMetadata: vi.fn(),
  accountMetadata: {},
  setAccountMetadata: vi.fn(),
  setSelectedOrgAccount: vi.fn(),
  loading: false,
  selectedOrganization: mockOrgData,
  selectedAccount: null,
  signOut: vi.fn(),
  setUser: vi.fn(),
  setSelectedOrganization: vi.fn(),
  setSelectedAccount: vi.fn(),
};

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

const renderAccountSettings = () => {
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={mockAuthContext}>
        <AccountSettings />
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("Create Organization Button", () => {
  test("should show Create New Organization button on organization settings page", () => {
    renderAccountSettings();

    expect(
      screen.getByRole("button", { name: "Create New Organization" }),
    ).toBeInTheDocument();
  });

  test("should navigate to create organization page when button is clicked", async () => {
    const user = userEvent.setup();
    renderAccountSettings();

    const createButton = screen.getByRole("button", {
      name: "Create New Organization",
    });
    await user.click(createButton);

    expect(mockNavigate).toHaveBeenCalledWith("/create-organization");
  });

  test("should show page header with organization settings title", () => {
    renderAccountSettings();

    expect(screen.getByText("Organization Settings")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Manage your organization profile, subscription, and team settings",
      ),
    ).toBeInTheDocument();
  });
});
