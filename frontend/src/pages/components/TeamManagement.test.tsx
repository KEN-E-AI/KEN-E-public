import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TeamManagement from "./TeamManagement";
import * as teamApi from "@/data/teamApi";
import * as accountsQuery from "@/queries/accounts";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";

// Mock dependencies
vi.mock("@/contexts/AuthContext");
vi.mock("@/hooks/use-toast");
vi.mock("@/data/teamApi");
vi.mock("@/queries/accounts");

const mockUseAuth = useAuth as vi.MockedFunction<typeof useAuth>;
const mockUseToast = useToast as vi.MockedFunction<typeof useToast>;
const mockTeamApi = teamApi as vi.Mocked<typeof teamApi>;
const mockAccountsQuery = accountsQuery as vi.Mocked<typeof accountsQuery>;

describe("TeamManagement", () => {
  let queryClient: QueryClient;
  const mockToast = vi.fn();

  const mockUser = {
    id: "user123",
    email: "admin@example.com",
    firstName: "Admin",
    lastName: "User",
    permissions: {
      organizations: {
        org456: "admin",
      },
    },
  };

  const mockOrgData = {
    organization_id: "org456",
    organization_name: "Test Organization",
    team: {
      members_limit: 10,
    },
  };

  const mockMembers = [
    {
      user_id: "user1",
      email: "user1@example.com",
      first_name: "User",
      last_name: "One",
      access_level: "admin",
    },
    {
      user_id: "user2",
      email: "user2@example.com",
      first_name: "User",
      last_name: "Two",
      access_level: "view",
      account_permissions: {
        acc123: "edit",
        acc456: "view",
      },
    },
    {
      user_id: "super1",
      email: "support@ken-e.ai",
      first_name: "Support",
      last_name: "Admin",
      access_level: "view",
      is_super_admin: true,
    },
  ];

  const mockAccounts = [
    { account_id: "acc123", account_name: "Account 1" },
    { account_id: "acc456", account_name: "Account 2" },
    { account_id: "acc789", account_name: "Account 3" },
  ];

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    mockUseAuth.mockReturnValue({
      user: mockUser,
    } as any);

    mockUseToast.mockReturnValue({ toast: mockToast } as any);

    mockAccountsQuery.useAccounts.mockReturnValue({
      data: mockAccounts,
      isLoading: false,
    } as any);

    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <TeamManagement orgData={mockOrgData} />
        </QueryClientProvider>
      </MemoryRouter>,
    );
  };

  test("renders team members list", async () => {
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockMembers,
      total: 3,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("user1@example.com")).toBeInTheDocument();
      expect(screen.getByText("user2@example.com")).toBeInTheDocument();
      expect(screen.getByText("support@ken-e.ai")).toBeInTheDocument();
    });
  });

  test("does not display Super Admin badge for @ken-e.ai users (badge removed)", async () => {
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockMembers,
      total: 3,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("support@ken-e.ai")).toBeInTheDocument();
    });

    expect(screen.queryByText("Super Admin")).not.toBeInTheDocument();
  });

  test("displays account permissions for view-role users", async () => {
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockMembers,
      total: 3,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      // Check for account permission badges
      expect(screen.getByText("Account 123: edit")).toBeInTheDocument();
      expect(screen.getByText("Account 456: view")).toBeInTheDocument();
    });
  });

  test("shows action menu for @ken-e.ai members (no longer special-cased)", async () => {
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockMembers,
      total: 3,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    // Current user is admin (mockUser has org admin permission)
    mockUseAuth.mockReturnValue({ user: mockUser } as any);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("support@ken-e.ai")).toBeInTheDocument();
    });

    // The @ken-e.ai member has access_level "view" and is not the current user,
    // so the action menu should now be rendered (no longer suppressed by email domain).
    const dropdownButtons = screen
      .getAllByRole("button")
      .filter((button) => button.querySelector("svg"));

    // user1 (admin), user2 (view), and super1 (view/@ken-e.ai) all get menus
    // (owners and self are excluded; none of the mockMembers are owners or self)
    expect(dropdownButtons.length).toBeGreaterThanOrEqual(mockMembers.length - 1);
  });

  test("shows account permissions in invite modal for view-role", async () => {
    const user = userEvent.setup();

    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [],
      total: 0,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    // Open invite modal
    await waitFor(() => {
      expect(screen.getByText("Invite Member")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Invite Member"));

    // Enter email
    await user.type(
      screen.getByPlaceholderText("member@example.com"),
      "newuser@example.com",
    );

    // Select view role
    await user.click(screen.getByText("View - Can view data only"));

    // Account permissions should appear
    await waitFor(() => {
      expect(screen.getByText("Account Permissions")).toBeInTheDocument();
      expect(screen.getByText("Account 1")).toBeInTheDocument();
      expect(screen.getByText("Account 2")).toBeInTheDocument();
      expect(screen.getByText("Account 3")).toBeInTheDocument();
    });
  });

  test("invites member with account permissions", async () => {
    const user = userEvent.setup();

    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [],
      total: 0,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });
    mockTeamApi.inviteMemberToOrganization.mockResolvedValue({
      success: true,
      message: "Invitation sent",
    });

    renderComponent();

    // Open invite modal
    await user.click(screen.getByText("Invite Member"));

    // Enter email
    await user.type(
      screen.getByPlaceholderText("member@example.com"),
      "newuser@example.com",
    );

    // Select view role to show account permissions
    await user.click(screen.getByText("View - Can view data only"));

    // Select account permissions
    await waitFor(() => {
      expect(screen.getByLabelText("account-acc123")).toBeInTheDocument();
    });
    await user.click(screen.getByLabelText("account-acc123"));

    // Change permission level to edit
    await user.click(screen.getAllByText("View")[1]); // Second "View" is in the dropdown
    await user.click(screen.getByText("Edit"));

    // Send invitation
    await user.click(screen.getByRole("button", { name: "Send Invitation" }));

    await waitFor(() => {
      expect(mockTeamApi.inviteMemberToOrganization).toHaveBeenCalledWith(
        "org456",
        {
          email: "newuser@example.com",
          access_level: "view",
          account_permissions: {
            acc123: "edit",
          },
        },
        "user123",
        "Admin User",
        "Test Organization",
      );
    });
  });

  test("does not show account permissions for admin role", async () => {
    const user = userEvent.setup();

    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [],
      total: 0,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    // Open invite modal
    await user.click(screen.getByText("Invite Member"));

    // Select admin role
    await user.click(screen.getByText("View - Can view data only"));
    await user.click(screen.getByText("Admin - Can manage settings"));

    // Account permissions should NOT appear
    await waitFor(() => {
      expect(screen.queryByText("Account Permissions")).not.toBeInTheDocument();
    });
  });
});

describe("TeamManagement - @ken-e.ai members are no longer special-cased", () => {
  let queryClient: QueryClient;
  const mockToast = vi.fn();

  const mockUser = {
    id: "user123",
    email: "admin@example.com",
    firstName: "Admin",
    lastName: "User",
    permissions: {
      organizations: {
        org456: "admin",
      },
    },
  };

  const mockOrgData = {
    organization_id: "org456",
    organization_name: "Test Organization",
    team: {
      members_limit: 10,
    },
  };

  const kenEMember = {
    user_id: "kene-user",
    email: "support@ken-e.ai",
    first_name: "Support",
    last_name: "Admin",
    access_level: "view" as const,
    is_super_admin: true,
  };

  const mockAccounts = [
    { account_id: "acc123", account_name: "Account 1" },
  ];

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    mockUseAuth.mockReturnValue({ user: mockUser } as any);
    mockUseToast.mockReturnValue({ toast: mockToast } as any);
    mockAccountsQuery.useAccounts.mockReturnValue({
      data: mockAccounts,
      isLoading: false,
    } as any);

    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <TeamManagement orgData={mockOrgData} />
        </QueryClientProvider>
      </MemoryRouter>,
    );

  test("a @ken-e.ai member shows their actual access_level badge, not a Super Admin badge", async () => {
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [kenEMember],
      total: 1,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("support@ken-e.ai")).toBeInTheDocument();
    });

    expect(screen.queryByText("Super Admin")).not.toBeInTheDocument();
    expect(screen.getByText("view")).toBeInTheDocument();
  });

  test("a non-owner, non-self @ken-e.ai member renders the action menu", async () => {
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [kenEMember],
      total: 1,
    });
    mockTeamApi.getOrganizationInvitations.mockResolvedValue({
      invitations: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("support@ken-e.ai")).toBeInTheDocument();
    });

    // The action menu button (MoreVertical) should be present
    const menuButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.querySelector("svg"));

    expect(menuButtons.length).toBeGreaterThan(0);
  });
});
