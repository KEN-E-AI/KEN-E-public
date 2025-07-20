import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DangerZone from "./DangerZone";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { deleteOrganization } from "@/data/organizationApi";

// Mock dependencies
vi.mock("@/contexts/AuthContext");
vi.mock("@/hooks/use-toast");
vi.mock("@/data/organizationApi");
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;
const mockUseToast = useToast as ReturnType<typeof vi.fn>;
const mockDeleteOrganization = deleteOrganization as ReturnType<typeof vi.fn>;

describe("DangerZone", () => {
  const mockToast = vi.fn();
  const mockUpdateUser = vi.fn();
  const mockSetOrgMetadata = vi.fn();
  const mockNavigate = vi.fn();

  const mockUser = {
    id: "user-123",
    email: "test@example.com",
    firstName: "Test",
    lastName: "User",
    permissions: {
      organizations: { "org-123": "admin" },
      accounts: {},
    },
  };

  const mockOrgData = {
    organization_id: "org-123",
    organization_name: "Test Organization",
    plan: "Professional",
    website: "https://test.com",
    company_size: "11-50",
    agency: false,
    child_organizations: [],
    subscription: {
      plan_name: "Professional Plan",
      plan_description: "Full features",
      price: 99,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "2024-02-01",
      features: ["Advanced Reports", "Multiple Users"],
      usage: { reports_generated: 5, reports_limit: 100 },
    },
    billing: {
      payment_method: { last_four: "1234", brand: "Visa", expires: "12/25" },
      address: "123 Test St",
      tax_id: "TAX123",
    },
    team: {
      members_used: 2,
      members_limit: 10,
      pending_invitations: 1,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();

    mockUseToast.mockReturnValue({ toast: mockToast });
    mockUseAuth.mockReturnValue({
      user: mockUser,
      updateUser: mockUpdateUser,
      setOrgMetadata: mockSetOrgMetadata,
      orgMetadata: { "org-123": mockOrgData },
    });

    // Mock useNavigate
    vi.doMock("react-router-dom", () => ({
      useNavigate: () => mockNavigate,
    }));
  });

  const renderDangerZone = () => {
    return render(<DangerZone orgData={mockOrgData} />);
  };

  describe("Component Rendering", () => {
    test("should render danger zone with organization deletion option", () => {
      renderDangerZone();

      expect(screen.getByText("Danger Zone")).toBeInTheDocument();
      expect(screen.getByText("Delete Organization")).toBeInTheDocument();
      expect(
        screen.getByText(
          /permanently delete your organization \(requires all accounts to be deleted first\)/i,
        ),
      ).toBeInTheDocument();
    });

    test("should render cancel subscription option", () => {
      renderDangerZone();

      expect(screen.getByText("Cancel Subscription")).toBeInTheDocument();
      expect(
        screen.getByText(
          /cancel your subscription and downgrade to free plan/i,
        ),
      ).toBeInTheDocument();
    });
  });

  describe("Organization Deletion - AlertDialog Functionality", () => {
    test("should open delete confirmation dialog when delete button is clicked", async () => {
      const user = userEvent.setup();
      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Verify confirmation dialog appears
      await waitFor(() => {
        expect(screen.getByText("Delete Organization")).toBeInTheDocument();
        expect(
          screen.getByText(/are you sure you want to delete the organization/i),
        ).toBeInTheDocument();
        expect(screen.getByText('"Test Organization"')).toBeInTheDocument();
      });
    });

    test("should show warning about deleting accounts first", async () => {
      const user = userEvent.setup();
      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      await waitFor(() => {
        expect(
          screen.getByText("📋 Required: You must delete all accounts first"),
        ).toBeInTheDocument();
        expect(
          screen.getByText(
            /before deleting this organization, please remove all accounts/i,
          ),
        ).toBeInTheDocument();
        expect(
          screen.getByText("⚠️ Warning: This action cannot be undone"),
        ).toBeInTheDocument();
      });
    });

    test("should close dialog when cancel is clicked", async () => {
      const user = userEvent.setup();
      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Click cancel in confirmation dialog
      const cancelButton = screen.getByRole("button", { name: /cancel/i });
      await user.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(
          screen.queryByText("Delete Organization"),
        ).not.toBeInTheDocument();
      });
    });

    test("should successfully delete organization when confirmed", async () => {
      const user = userEvent.setup();
      mockDeleteOrganization.mockResolvedValue(undefined);
      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      expect(confirmButton).toBeInTheDocument();
      await user.click(confirmButton!);

      // Verify API call and state updates
      await waitFor(() => {
        expect(mockDeleteOrganization).toHaveBeenCalledWith("org-123");
        expect(mockUpdateUser).toHaveBeenCalled();
        expect(mockSetOrgMetadata).toHaveBeenCalled();
        expect(mockToast).toHaveBeenCalledWith({
          title: "Organization Deleted",
          description:
            '"Test Organization" and all associated accounts have been permanently deleted.',
        });
      });
    });
  });

  describe("Organization Deletion Error Handling", () => {
    test("should handle account constraint error (400 status)", async () => {
      const user = userEvent.setup();
      const constraintError = {
        response: {
          status: 400,
          data: {
            detail:
              "Cannot delete organization with 3 associated accounts. Delete accounts first.",
          },
        },
      };
      mockDeleteOrganization.mockRejectedValue(constraintError);

      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      await user.click(confirmButton!);

      // Verify specific error message for account constraint
      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith({
          title: "Cannot Delete Organization",
          description:
            "You must delete all accounts first before deleting this organization. Please remove accounts from the Accounts section above.",
          variant: "destructive",
        });
      });
    });

    test("should handle generic API errors", async () => {
      const user = userEvent.setup();
      const genericError = {
        response: {
          status: 500,
          data: {
            detail: "Internal server error",
          },
        },
      };
      mockDeleteOrganization.mockRejectedValue(genericError);

      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      await user.click(confirmButton!);

      // Verify generic error handling
      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith({
          title: "Error",
          description: "Error: Internal server error",
          variant: "destructive",
        });
      });
    });

    test("should handle network errors without response", async () => {
      const user = userEvent.setup();
      const networkError = new Error("Network connection failed");
      mockDeleteOrganization.mockRejectedValue(networkError);

      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      await user.click(confirmButton!);

      // Verify network error handling
      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith({
          title: "Error",
          description: "Error: Network connection failed",
          variant: "destructive",
        });
      });
    });

    test("should handle edge case where error has no detail", async () => {
      const user = userEvent.setup();
      const emptyError = {
        response: {
          status: 400,
          data: {},
        },
      };
      mockDeleteOrganization.mockRejectedValue(emptyError);

      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      // Confirm deletion
      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      await user.click(confirmButton!);

      // Verify fallback error message
      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith({
          title: "Error",
          description: "Error: Failed to delete organization",
          variant: "destructive",
        });
      });
    });
  });

  describe("State Management", () => {
    test("should update user permissions after successful deletion", async () => {
      const user = userEvent.setup();
      mockDeleteOrganization.mockResolvedValue(undefined);

      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      await user.click(confirmButton!);

      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalledWith({
          permissions: {
            organizations: {},
            accounts: {},
          },
        });
      });
    });

    test("should update org metadata after successful deletion", async () => {
      const user = userEvent.setup();
      mockDeleteOrganization.mockResolvedValue(undefined);

      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      await user.click(deleteButton);

      const confirmButton = screen
        .getAllByRole("button", { name: /delete organization/i })
        .find((button) => button.className.includes("bg-red-600"));
      await user.click(confirmButton!);

      await waitFor(() => {
        expect(mockSetOrgMetadata).toHaveBeenCalledWith({});
      });
    });
  });

  describe("Accessibility", () => {
    test("should have proper ARIA labels for destructive actions", () => {
      renderDangerZone();

      const deleteButton = screen.getByRole("button", {
        name: /delete organization/i,
      });
      expect(deleteButton).toHaveAttribute(
        "class",
        expect.stringContaining("destructive"),
      );
    });

    test("should use proper heading hierarchy", () => {
      renderDangerZone();

      const dangerZoneTitle = screen.getByText("Danger Zone");
      expect(dangerZoneTitle.tagName).toBe("H3"); // CardTitle renders as h3
    });

    test("should have warning icon for visual accessibility", () => {
      renderDangerZone();

      // Check for AlertTriangle icon in the title
      const alertIcon = document.querySelector(
        '[data-lucide="alert-triangle"]',
      );
      expect(alertIcon).toBeInTheDocument();
    });
  });
});
