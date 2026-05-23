import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountsManagement from "./AccountsManagement";
import { AuthContext } from "@/contexts/AuthContext";
import * as organizationApi from "@/data/organizationApi";
import type { Organization, Account } from "@/data/organizationTypes";
import type { AuthContextType } from "@/contexts/AuthContext";

// Mock the organization API
vi.mock("@/data/organizationApi", () => ({
  getAccountsByOrganizationId: vi.fn(),
  createAccount: vi.fn(),
  updateAccount: vi.fn(),
  deleteAccount: vi.fn(),
  moveAccount: vi.fn(),
  getOrganizations: vi.fn(),
}));

// Mock the toast hook
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock react-router-dom
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

// Mock axios
vi.mock("axios", () => ({
  default: {
    put: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

const mockUser = {
  uid: "user123",
  email: "test@example.com",
  permissions: {
    organizations: {
      "current-org": "admin",
      "target-org-1": "admin",
      "target-org-2": "viewer",
    },
    accounts: {
      "acc-123": "admin",
    },
  },
};

const mockCurrentOrg = {
  organization_id: "current-org",
  organization_name: "Current Organization",
  plan: "Professional",
  website: "https://current.com",
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
} as unknown as Organization;

const mockAccount = {
  account_id: "acc-123",
  account_name: "Test Account",
  organization_id: "current-org",
  industry: "Technology",
  status: "Active",
  websites: ["https://test.com"],
  timezone: "America/New_York",
  data_region: "",
  region: [],
} as unknown as Account;

const mockTargetOrgs = [
  {
    organization_id: "target-org-1",
    organization_name: "Target Organization 1",
    plan: "Professional",
    website: "https://target1.com",
    company_size: "large",
    agency: false,
    child_organizations: [],
    subscription: mockCurrentOrg.subscription,
    billing: mockCurrentOrg.billing,
    team: mockCurrentOrg.team,
  },
  {
    organization_id: "target-org-2",
    organization_name: "Target Organization 2",
    plan: "Enterprise",
    website: "https://target2.com",
    company_size: "small",
    agency: true,
    child_organizations: [],
    subscription: mockCurrentOrg.subscription,
    billing: mockCurrentOrg.billing,
    team: mockCurrentOrg.team,
  },
] as unknown as Organization[];

const mockAuthContext = {
  user: mockUser,
  updateUser: vi.fn(),
  accountMetadata: {
    "acc-123": mockAccount,
  },
  setAccountMetadata: vi.fn(),
  orgMetadata: {
    "current-org": mockCurrentOrg,
  },
  setOrgMetadata: vi.fn(),
  setSelectedOrgAccount: vi.fn(),
  loading: false,
  selectedOrganization: mockCurrentOrg,
  selectedAccount: mockAccount,
  signOut: vi.fn(),
  setUser: vi.fn(),
  setSelectedOrganization: vi.fn(),
  setSelectedAccount: vi.fn(),
} as unknown as AuthContextType;

const renderAccountsManagement = () => {
  return render(
    <AuthContext.Provider value={mockAuthContext}>
      <AccountsManagement orgData={mockCurrentOrg} currentOrgId="current-org" />
    </AuthContext.Provider>,
  );
};

const openEditDialog = async (user: any) => {
  // Wait for accounts to load
  await waitFor(() => {
    expect(screen.getByText("Test Account")).toBeInTheDocument();
  });

  // Find the edit button by looking for the Settings icon
  const editButton = document
    .querySelector(".lucide-settings")
    ?.closest("button");
  expect(editButton).toBeInTheDocument();
  await user.click(editButton!);
};

describe("AccountsManagement - Move Account", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock successful account loading
    vi.mocked(organizationApi.getAccountsByOrganizationId).mockResolvedValue([
      mockAccount,
    ]);
  });

  test("should show Move Account button in edit dialog", async () => {
    renderAccountsManagement();

    await openEditDialog(userEvent);

    // Check that Move Account section exists
    expect(
      screen.getByText("Transfer to Another Organization"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Move Account" }),
    ).toBeInTheDocument();
  });

  test("should open move dialog when Move Account button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);

    renderAccountsManagement();

    await openEditDialog(user);

    // Click Move Account button
    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Check that move dialog opens
    await waitFor(() => {
      expect(
        screen.getByText(
          'Select the organization you want to move "Test Account" to',
        ),
      ).toBeInTheDocument();
    });

    // Verify getOrganizations was called
    expect(organizationApi.getOrganizations).toHaveBeenCalledTimes(1);
  });

  test("should display available target organizations in move dialog", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);

    renderAccountsManagement();

    // Open edit dialog and move dialog
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Open the select dropdown
    await waitFor(() => {
      expect(screen.getByText("Select an organization")).toBeInTheDocument();
    });

    const selectTrigger = screen.getByRole("combobox");
    await user.click(selectTrigger);

    // Check that target organizations are listed (current org should be filtered out)
    await waitFor(() => {
      expect(screen.getByText("Target Organization 1")).toBeInTheDocument();
      expect(screen.getByText("Target Organization 2")).toBeInTheDocument();
      expect(
        screen.queryByText("Current Organization"),
      ).not.toBeInTheDocument();
    });
  });

  test("should successfully move account to selected organization", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);
    vi.mocked(organizationApi.moveAccount).mockResolvedValue(undefined);

    renderAccountsManagement();

    // Open edit dialog and move dialog
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Select target organization
    await waitFor(() => {
      expect(screen.getByText("Select an organization")).toBeInTheDocument();
    });

    const selectTrigger = screen.getByRole("combobox");
    await user.click(selectTrigger);

    await waitFor(() => {
      expect(screen.getByText("Target Organization 1")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Target Organization 1"));

    // Confirm move
    const confirmButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(confirmButton);

    // Verify API call
    await waitFor(() => {
      expect(organizationApi.moveAccount).toHaveBeenCalledWith(
        "current-org",
        "acc-123",
        "target-org-1",
      );
    });

    // Verify success toast
    expect(mockToast).toHaveBeenCalledWith({
      title: "Account Moved",
      description: '"Test Account" has been moved to Target Organization 1.',
    });
  });

  test("should handle move account API error", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);
    vi.mocked(organizationApi.moveAccount).mockRejectedValue(
      new Error("Move failed"),
    );

    renderAccountsManagement();

    // Open dialogs and attempt move
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Select organization and confirm
    const selectTrigger = screen.getByRole("combobox");
    await user.click(selectTrigger);

    await waitFor(() => {
      expect(screen.getByText("Target Organization 1")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Target Organization 1"));

    const confirmButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(confirmButton);

    // Verify error toast
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith({
        title: "Error",
        description: "Error: Move failed",
        variant: "destructive",
      });
    });
  });

  test("should handle error loading organizations", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockRejectedValue(
      new Error("Failed to load organizations"),
    );

    renderAccountsManagement();

    // Open edit dialog
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    // Click Move Account button
    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Verify error toast
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith({
        title: "Error",
        description: "Failed to load organizations",
        variant: "destructive",
      });
    });
  });

  test("should disable Move Account button when no organization selected", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);

    renderAccountsManagement();

    // Open dialogs
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Move Account button should be disabled initially
    await waitFor(() => {
      const confirmButton = screen.getByRole("button", {
        name: "Move Account",
      });
      expect(confirmButton).toBeDisabled();
    });
  });

  test("should show message when no organizations available to move to", async () => {
    const user = userEvent.setup();
    // Only return current organization (others will be filtered out)
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
    ]);

    renderAccountsManagement();

    // Open dialogs
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Should show no organizations message
    await waitFor(() => {
      expect(
        screen.getByText("No other organizations available to move to."),
      ).toBeInTheDocument();
    });
  });

  test("should close move dialog when Cancel is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);

    renderAccountsManagement();

    // Open dialogs
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    // Click Cancel
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" }),
      ).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole("button", { name: "Cancel" });
    await user.click(cancelButton);

    // Dialog should close
    await waitFor(() => {
      expect(
        screen.queryByText(
          'Select the organization you want to move "Test Account" to',
        ),
      ).not.toBeInTheDocument();
    });
  });

  test("should update local state after successful move", async () => {
    const user = userEvent.setup();
    const mockSetAccountMetadata = vi.fn();
    const mockUpdateUser = vi.fn();

    const updatedMockAuthContext = {
      ...mockAuthContext,
      setAccountMetadata: mockSetAccountMetadata,
      updateUser: mockUpdateUser,
    };

    vi.mocked(organizationApi.getOrganizations).mockResolvedValue([
      mockCurrentOrg,
      ...mockTargetOrgs,
    ]);
    vi.mocked(organizationApi.moveAccount).mockResolvedValue(undefined);

    render(
      <AuthContext.Provider value={updatedMockAuthContext}>
        <AccountsManagement
          orgData={mockCurrentOrg}
          currentOrgId="current-org"
        />
      </AuthContext.Provider>,
    );

    // Perform move operation
    await waitFor(() => {
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    const editButton = document
      .querySelector(".lucide-settings")
      ?.closest("button");
    expect(editButton).toBeInTheDocument();
    await user.click(editButton!);

    const moveButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(moveButton);

    const selectTrigger = screen.getByRole("combobox");
    await user.click(selectTrigger);

    await waitFor(() => {
      expect(screen.getByText("Target Organization 1")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Target Organization 1"));

    const confirmButton = screen.getByRole("button", { name: "Move Account" });
    await user.click(confirmButton);

    // Verify state updates
    await waitFor(() => {
      expect(mockSetAccountMetadata).toHaveBeenCalled();
      expect(mockUpdateUser).toHaveBeenCalled();
    });
  });
});
