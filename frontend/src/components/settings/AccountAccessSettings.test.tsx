import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AccountAccessSettings } from "./AccountAccessSettings";
import * as teamApi from "@/data/teamApi";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";

// Mock dependencies
vi.mock("@/contexts/AuthContext");
vi.mock("@/hooks/use-toast");
vi.mock("@/data/teamApi");

const mockUseAuth = useAuth as vi.MockedFunction<typeof useAuth>;
const mockUseToast = useToast as vi.MockedFunction<typeof useToast>;
const mockTeamApi = teamApi as vi.Mocked<typeof teamApi>;

describe("AccountAccessSettings", () => {
  let queryClient: QueryClient;
  const mockToast = vi.fn();

  const mockUser = {
    id: "user123",
    email: "admin@example.com",
    permissions: {
      organizations: {
        org456: "admin",
      },
    },
  };

  const mockSelectedOrgAccount = {
    orgId: "org456",
    accountId: "acc123",
  };

  const mockPermissions = [
    {
      user_id: "user1",
      email: "user1@example.com",
      access_level: "edit",
      first_name: "User",
      last_name: "One",
    },
    {
      user_id: "user2",
      email: "user2@example.com",
      access_level: "view",
      first_name: "User",
      last_name: "Two",
    },
  ];

  const mockOrgMembers = [
    ...mockPermissions,
    {
      user_id: "user3",
      email: "user3@example.com",
      access_level: "view",
      first_name: "User",
      last_name: "Three",
    },
  ];

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    mockUseAuth.mockReturnValue({
      user: mockUser,
      selectedOrgAccount: mockSelectedOrgAccount,
    } as any);

    mockUseToast.mockReturnValue({ toast: mockToast } as any);

    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <AccountAccessSettings accountId="acc123" />
      </QueryClientProvider>,
    );
  };

  test("renders loading state initially", () => {
    mockTeamApi.getAccountPermissions.mockImplementation(
      () => new Promise(() => {}),
    );
    mockTeamApi.getOrganizationMembers.mockImplementation(
      () => new Promise(() => {}),
    );

    renderComponent();

    expect(
      screen.getByText("Loading access permissions..."),
    ).toBeInTheDocument();
  });

  test("renders permissions list", async () => {
    mockTeamApi.getAccountPermissions.mockResolvedValue({
      account_id: "acc123",
      permissions: mockPermissions,
      total: 2,
    });
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockOrgMembers,
      total: 3,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("user1@example.com")).toBeInTheDocument();
      expect(screen.getByText("user2@example.com")).toBeInTheDocument();
      expect(screen.getByText("edit")).toBeInTheDocument();
      expect(screen.getByText("view")).toBeInTheDocument();
    });
  });

  test("shows grant access button for admin users", async () => {
    mockTeamApi.getAccountPermissions.mockResolvedValue({
      account_id: "acc123",
      permissions: mockPermissions,
      total: 2,
    });
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockOrgMembers,
      total: 3,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("Grant Access")).toBeInTheDocument();
    });
  });

  test("hides grant access button for view-role users", async () => {
    mockUseAuth.mockReturnValue({
      user: {
        ...mockUser,
        permissions: {
          organizations: {
            org456: "view",
          },
        },
      },
      selectedOrgAccount: mockSelectedOrgAccount,
    } as any);

    mockTeamApi.getAccountPermissions.mockResolvedValue({
      account_id: "acc123",
      permissions: mockPermissions,
      total: 2,
    });
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockOrgMembers,
      total: 3,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.queryByText("Grant Access")).not.toBeInTheDocument();
      expect(
        screen.getByText(
          "You need organization admin permissions to manage account access",
        ),
      ).toBeInTheDocument();
    });
  });

  test("grants account access", async () => {
    const user = userEvent.setup();

    mockTeamApi.getAccountPermissions.mockResolvedValue({
      account_id: "acc123",
      permissions: [],
      total: 0,
    });
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [mockOrgMembers[2]], // Only user3 available
      total: 1,
    });
    mockTeamApi.grantAccountAccess.mockResolvedValue({
      success: true,
      message: "Access granted",
    });

    renderComponent();

    // Open modal
    await waitFor(() => {
      expect(screen.getByText("Grant Access")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Grant Access"));

    // Select user
    await user.click(screen.getByText("Choose a user"));
    await user.click(screen.getByText("user3@example.com"));

    // Select access level
    await user.click(screen.getByText("View - Can view account data"));
    await user.click(screen.getByText("Edit - Can modify account settings"));

    // Submit
    await user.click(screen.getByRole("button", { name: "Grant Access" }));

    await waitFor(() => {
      expect(mockTeamApi.grantAccountAccess).toHaveBeenCalledWith(
        "acc123",
        "user3",
        "edit",
      );
      expect(mockToast).toHaveBeenCalledWith({
        title: "Success",
        description: "Access granted successfully",
      });
    });
  });

  test("revokes account access", async () => {
    const user = userEvent.setup();

    mockTeamApi.getAccountPermissions.mockResolvedValue({
      account_id: "acc123",
      permissions: mockPermissions,
      total: 2,
    });
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: mockOrgMembers,
      total: 3,
    });
    mockTeamApi.revokeAccountAccess.mockResolvedValue({
      success: true,
      message: "Access revoked",
    });

    renderComponent();

    // Click revoke button for first user
    await waitFor(() => {
      expect(screen.getAllByRole("button")[1]).toBeInTheDocument(); // Skip grant button
    });

    const revokeButtons = screen
      .getAllByRole("button")
      .filter((button) => button.querySelector("svg"));
    await user.click(revokeButtons[0]);

    // Confirm in toast
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Revoke Access",
          description: expect.stringContaining("user1@example.com"),
        }),
      );
    });

    // Click confirm in toast action
    const toastCall = mockToast.mock.calls[0][0];
    const confirmButton = toastCall.action.props.children.props.children[1];
    await confirmButton.props.onClick();

    await waitFor(() => {
      expect(mockTeamApi.revokeAccountAccess).toHaveBeenCalledWith(
        "acc123",
        "user1",
      );
    });
  });

  test("shows empty state when no permissions", async () => {
    mockTeamApi.getAccountPermissions.mockResolvedValue({
      account_id: "acc123",
      permissions: [],
      total: 0,
    });
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByText("No specific account permissions granted"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Organization admins have automatic access to all accounts",
        ),
      ).toBeInTheDocument();
    });
  });

  test("handles API errors gracefully", async () => {
    mockTeamApi.getAccountPermissions.mockRejectedValue(new Error("API Error"));
    mockTeamApi.getOrganizationMembers.mockResolvedValue({
      members: [],
      total: 0,
    });

    renderComponent();

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith({
        title: "Error",
        description: "Failed to load access permissions",
        variant: "destructive",
      });
    });
  });
});
