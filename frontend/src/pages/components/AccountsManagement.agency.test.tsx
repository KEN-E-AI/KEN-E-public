import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountsManagement from "./AccountsManagement";
import { AuthContext } from "@/contexts/AuthContext";
import * as organizationApi from "@/data/organizationApi";
import type { Organization, Account } from "@/data/organizationTypes";
import type { AuthContextType } from "@/contexts/AuthContext";

// Mock the organization API
vi.mock("@/data/organizationApi");

// Mock navigation
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

// Mock toast
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

// These fixtures use a legacy `seats`-based shape; the current Organization
// interface has shifted to `plan_name`/`price`/`features`-style billing and
// `members_used`/`members_limit`-style team. The runtime tests below only
// touch `organization_id`, `agency`, and `child_organizations`, so the cast
// through unknown is acceptable. TODO: regenerate from the current type
// when the legacy `seats` fixtures are no longer useful for any consumer.
const mockRegularOrg = {
  organization_id: "regular-org",
  organization_name: "Regular Organization",
  plan: "Growth",
  website: "https://regular.org",
  agency: false,
  child_organizations: [],
  subscription: {
    seats: 100,
    active_seats: 50,
    seats_included: 100,
    price_per_extra_seat: 15,
    trial_days_left: 0,
  },
  billing: {
    billing_email: "billing@regular.org",
    invoice_details: "Regular Org Inc.",
  },
  team: {
    users: 50,
  },
} as unknown as Organization;

const mockAgencyOrg = {
  organization_id: "agency-org",
  organization_name: "Agency Organization",
  plan: "Agency",
  website: "https://agency.org",
  agency: true,
  child_organizations: ["child-org-1", "child-org-2"],
  subscription: {
    seats: 500,
    active_seats: 250,
    seats_included: 500,
    price_per_extra_seat: 10,
    trial_days_left: 0,
  },
  billing: {
    billing_email: "billing@agency.org",
    invoice_details: "Agency Inc.",
  },
  team: {
    users: 250,
  },
} as unknown as Organization;

const mockAuthContext = {
  user: {
    uid: "test-user",
    email: "test@example.com",
    permissions: {
      organizations: {
        "regular-org": "admin",
        "agency-org": "admin",
      },
      accounts: {},
    },
  },
  accountMetadata: {},
  setAccountMetadata: vi.fn(),
  selectedOrganization: null,
  selectedAccount: null,
  setSelectedOrganization: vi.fn(),
  setSelectedAccount: vi.fn(),
  orgMetadata: {},
  setOrgMetadata: vi.fn(),
  organizations: [],
  setOrganizations: vi.fn(),
  accounts: [],
  setAccounts: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  signInWithGoogle: vi.fn(),
  loading: false,
  updateUser: vi.fn(),
  setSelectedOrgAccount: vi.fn(),
  setUser: vi.fn(),
} as unknown as AuthContextType;

describe("AccountsManagement - Agency Restrictions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock successful (empty) account loading by default
    vi.mocked(organizationApi.getAccountsByOrganizationId).mockResolvedValue(
      [],
    );
  });

  test("should show Create Account button for regular organizations", async () => {
    render(
      <AuthContext.Provider value={mockAuthContext}>
        <AccountsManagement
          orgData={mockRegularOrg}
          currentOrgId="regular-org"
        />
      </AuthContext.Provider>,
    );

    // Wait for loading to complete
    await screen.findByText("Accounts");

    // Check that the Create Account button is visible
    const createButton = screen.getByRole("button", { name: "" }); // Plus icon button
    expect(createButton).toBeInTheDocument();
    expect(createButton).toHaveClass("h-8", "w-8"); // Size classes for the icon button
  });

  test("should NOT show Create Account button for agency organizations", async () => {
    render(
      <AuthContext.Provider value={mockAuthContext}>
        <AccountsManagement orgData={mockAgencyOrg} currentOrgId="agency-org" />
      </AuthContext.Provider>,
    );

    // Wait for loading to complete
    await screen.findByText("Accounts");

    // Check that the Create Account button is NOT visible
    // Since there are no accounts and no create button, there should be no buttons at all
    const buttons = screen.queryAllByRole("button");
    expect(buttons).toHaveLength(0);
  });

  test("should show informational message for agency organizations", async () => {
    render(
      <AuthContext.Provider value={mockAuthContext}>
        <AccountsManagement orgData={mockAgencyOrg} currentOrgId="agency-org" />
      </AuthContext.Provider>,
    );

    // Wait for loading to complete
    await screen.findByText("Accounts");

    // Check that the informational message is displayed
    expect(
      screen.getByText("Agency organizations cannot create accounts."),
    ).toBeInTheDocument();
  });

  test("should NOT show informational message for regular organizations", async () => {
    render(
      <AuthContext.Provider value={mockAuthContext}>
        <AccountsManagement
          orgData={mockRegularOrg}
          currentOrgId="regular-org"
        />
      </AuthContext.Provider>,
    );

    // Wait for loading to complete
    await screen.findByText("Accounts");

    // Check that the informational message is NOT displayed
    expect(
      screen.queryByText("Agency organizations cannot create accounts."),
    ).not.toBeInTheDocument();
  });

  test("clicking Create Account button should open modal for regular organizations", async () => {
    const user = userEvent.setup();

    render(
      <AuthContext.Provider value={mockAuthContext}>
        <AccountsManagement
          orgData={mockRegularOrg}
          currentOrgId="regular-org"
        />
      </AuthContext.Provider>,
    );

    // Wait for loading to complete
    await screen.findByText("Accounts");

    // Find and click the Create Account button
    const createButton = screen.getByRole("button", { name: "" }); // Plus icon button
    await user.click(createButton);

    // Check that the modal is opened
    expect(screen.getByText("Create New Account")).toBeInTheDocument();
    expect(screen.getByLabelText("Account Name")).toBeInTheDocument();
  });
});
