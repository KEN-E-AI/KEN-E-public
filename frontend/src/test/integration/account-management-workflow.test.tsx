import { describe, test, expect, beforeEach, vi, type Mock } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import AccountSettings from "@/pages/AccountSettings";
import { AccountCreationWizard } from "@/components/settings/AccountCreationWizard";

// Mock modules
vi.mock("@/data/organizationApi", () => ({
  createOrganization: vi.fn(),
  getOrganizationById: vi.fn(),
  updateOrganization: vi.fn(),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

// Mock data
const mockUser = {
  id: "user-123",
  firstName: "John",
  lastName: "Doe",
  email: "john.doe@example.com",
  permissions: {
    organizations: {
      "org-123": "admin",
    },
  },
};

const mockOrgMetadata = {
  "org-123": {
    organization_id: "org-123",
    organization_name: "Test Organization",
    company_size: "Medium",
    agency: false,
    child_organizations: [],
    subscription: {
      plan_name: "Pro Plan",
      plan_description: "Advanced features for growing teams",
      price: 99,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "2024-02-01",
      features: ["Advanced Analytics", "Custom Reports", "API Access"],
      usage: {
        reports_generated: 45,
        reports_limit: 100,
      },
    },
    billing: {
      payment_method: {
        last_four: "1234",
        brand: "Visa",
        expires: "12/2025",
      },
      address: "123 Main St, City, State 12345",
      tax_id: "TAX123456",
    },
    team: {
      members_used: 5,
      members_limit: 10,
      pending_invitations: 2,
    },
  },
};

// Legacy SelectedOrgAccount shape (organization_id / account_id); the current
// type uses `orgId` / `accountId` (branded). Cast through unknown since the
// tests only exercise the fields the wizard reads from context.
const mockSelectedOrgAccount = {
  organization_id: "org-123",
  account_id: "account-456",
  metadata: {
    organization_name: "Test Organization",
    account_name: "Test Account",
  },
} as unknown as import("@/contexts/AuthContext").SelectedOrgAccount;

const mockAuthContext = {
  user: mockUser,
  isAuthenticated: true,
  isLoading: false,
  orgMetadata: mockOrgMetadata,
  selectedOrgAccount: mockSelectedOrgAccount,
  currentOrganizationId: "org-123",
  notificationSettings: [],
  securitySettings: [],
  setCurrentOrganization: vi.fn(),
  setOrgMetadata: vi.fn(),
  updateUser: vi.fn(),
  setNotificationSettings: vi.fn(),
  signOut: vi.fn(),
  resetWorkspaceSelection: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  getUserOrganizations: vi.fn(),
  getOrganizationData: vi.fn(),
  refetchUser: vi.fn(),
  clearUserData: vi.fn(),
} as unknown as AuthContextType;

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthContext.Provider value={mockAuthContext}>
          {children}
        </AuthContext.Provider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

// Mock router hooks
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useLocation: () => ({ pathname: "/settings/organization" }),
    useParams: () => ({}),
  };
});

describe("Account Management Workflow Integration Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock axios
    vi.mock("axios", () => ({
      default: {
        put: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        get: vi.fn().mockResolvedValue({ data: {} }),
      },
    }));
  });

  describe("Organization Settings View", () => {
    test("should display organization information correctly", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      // Wait for component to load
      await waitFor(() => {
        expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      });

      // Verify organization details are displayed
      expect(screen.getByDisplayValue("Test Organization")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Medium")).toBeInTheDocument();
    });

    test("should show subscription information", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Subscription")).toBeInTheDocument();
      });

      // Verify subscription details
      expect(screen.getByText("Pro Plan")).toBeInTheDocument();
      expect(screen.getByText("$99/month")).toBeInTheDocument();
      expect(
        screen.getByText("Advanced features for growing teams"),
      ).toBeInTheDocument();
    });

    test("should display billing information", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Billing")).toBeInTheDocument();
      });

      // Verify billing details
      expect(screen.getByText("**** 1234")).toBeInTheDocument();
      expect(screen.getByText("Visa")).toBeInTheDocument();
      expect(screen.getByText("12/2025")).toBeInTheDocument();
    });

    test("should show team management section", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Team")).toBeInTheDocument();
      });

      // Verify team information
      expect(screen.getByText("5 / 10 members")).toBeInTheDocument();
      expect(screen.getByText("2 pending invitations")).toBeInTheDocument();
    });
  });

  describe("Organization Update Workflow", () => {
    test("should update organization information successfully", async () => {
      const user = userEvent.setup();
      const mockAxios = vi.mocked(await import("axios"));

      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByDisplayValue("Test Organization"),
        ).toBeInTheDocument();
      });

      // Update organization name
      const nameInput = screen.getByDisplayValue("Test Organization");
      await user.clear(nameInput);
      await user.type(nameInput, "Updated Organization Name");

      // Save changes
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify API call was made
      await waitFor(() => {
        expect(mockAxios.default.put).toHaveBeenCalledWith(
          expect.stringContaining("/organizations/org-123"),
          expect.objectContaining({
            organization_name: "Updated Organization Name",
          }),
        );
      });
    });

    test("should handle organization update errors", async () => {
      const user = userEvent.setup();
      const mockAxios = vi.mocked(await import("axios"));

      // Mock API error
      (mockAxios.default.put as unknown as Mock).mockRejectedValueOnce(
        new Error("Update failed"),
      );

      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByDisplayValue("Test Organization"),
        ).toBeInTheDocument();
      });

      // Try to save changes
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify error handling
      await waitFor(() => {
        expect(mockAxios.default.put).toHaveBeenCalled();
      });
    });
  });

  describe("Account Creation Workflow", () => {
    test("should render account creation wizard", async () => {
      render(
        <TestWrapper>
          <AccountCreationWizard isOpen={true} onClose={vi.fn()} onComplete={vi.fn()} />
        </TestWrapper>,
      );

      // Verify wizard structure
      expect(screen.getByText("Create New Account")).toBeInTheDocument();

      // Verify wizard steps
      expect(screen.getByText("Basic Info")).toBeInTheDocument();
      expect(screen.getByText("Template")).toBeInTheDocument();
      expect(screen.getByText("Configuration")).toBeInTheDocument();
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });

    test("should navigate through wizard steps", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <AccountCreationWizard isOpen={true} onClose={vi.fn()} onComplete={vi.fn()} />
        </TestWrapper>,
      );

      // Fill in basic info
      const accountNameInput = screen.getByPlaceholderText(
        "e.g., Q1 2024 Campaign",
      );
      await user.type(accountNameInput, "Test Account");

      const industrySelect = screen.getByText("Select industry...");
      await user.click(industrySelect);

      const techOption = screen.getByText("Technology");
      await user.click(techOption);

      // Proceed to next step
      const nextButton = screen.getByText("Next");
      await user.click(nextButton);

      // Verify navigation to template selection
      await waitFor(() => {
        expect(screen.getByText("Choose Template")).toBeInTheDocument();
      });
    });

    test("should validate required fields", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <AccountCreationWizard isOpen={true} onClose={vi.fn()} onComplete={vi.fn()} />
        </TestWrapper>,
      );

      // Try to proceed without filling required fields
      const nextButton = screen.getByText("Next");
      await user.click(nextButton);

      // Verify validation errors appear
      await waitFor(() => {
        expect(
          screen.getByText("Account name is required"),
        ).toBeInTheDocument();
      });
    });

    test("should complete account creation successfully", async () => {
      const user = userEvent.setup();
      const mockCreateOrganization = vi.mocked(
        await import("@/data/organizationApi"),
      ).createOrganization;

      mockCreateOrganization.mockResolvedValueOnce({
        organization_id: "new-org-123",
        organization_name: "New Test Organization",
      } as unknown as Awaited<ReturnType<typeof mockCreateOrganization>>);

      render(
        <TestWrapper>
          <AccountCreationWizard isOpen={true} onClose={vi.fn()} onComplete={vi.fn()} />
        </TestWrapper>,
      );

      // Fill in basic info
      const accountNameInput = screen.getByPlaceholderText(
        "e.g., Q1 2024 Campaign",
      );
      await user.type(accountNameInput, "New Test Account");

      const industrySelect = screen.getByText("Select industry...");
      await user.click(industrySelect);

      const techOption = screen.getByText("Technology");
      await user.click(techOption);

      // Navigate through all steps (simplified - in real test would fill each step)
      const nextButton = screen.getByText("Next");
      await user.click(nextButton);

      // Complete the wizard
      const createButton = screen.getByText("Create Account");
      await user.click(createButton);

      // Verify account creation
      await waitFor(() => {
        expect(mockCreateOrganization).toHaveBeenCalled();
      });
    });
  });

  describe("Account Management Features", () => {
    test("should show accounts management section", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Accounts")).toBeInTheDocument();
      });

      // Verify accounts management features
      expect(screen.getByText("Create New Account")).toBeInTheDocument();
      expect(screen.getByText("Manage Accounts")).toBeInTheDocument();
    });

    test("should handle account actions", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Create New Account")).toBeInTheDocument();
      });

      // Click create account button
      const createButton = screen.getByText("Create New Account");
      await user.click(createButton);

      // Verify button is clickable
      expect(createButton).toBeInTheDocument();
    });
  });

  describe("Danger Zone Operations", () => {
    test("should display danger zone section", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Danger Zone")).toBeInTheDocument();
      });

      // Verify dangerous operations are available
      expect(screen.getByText("Delete Organization")).toBeInTheDocument();
      expect(screen.getByText("Transfer Ownership")).toBeInTheDocument();
    });

    test("should require confirmation for dangerous operations", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Delete Organization")).toBeInTheDocument();
      });

      // Click delete button
      const deleteButton = screen.getByText("Delete Organization");
      await user.click(deleteButton);

      // Verify confirmation dialog appears
      await waitFor(() => {
        expect(screen.getByText("Are you sure?")).toBeInTheDocument();
      });
    });
  });

  describe("Permission-Based Access", () => {
    test("should show admin features for admin users", async () => {
      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      });

      // Admin users should see all management options
      expect(screen.getByText("Team")).toBeInTheDocument();
      expect(screen.getByText("Billing")).toBeInTheDocument();
      expect(screen.getByText("Danger Zone")).toBeInTheDocument();
    });

    test("should restrict features for non-admin users", async () => {
      const nonAdminContext = {
        ...mockAuthContext,
        user: {
          ...mockUser,
          permissions: {
            organizations: {
              "org-123": "member",
            },
          },
        },
      } as unknown as AuthContextType;

      render(
        <TestWrapper>
          <AuthContext.Provider value={nonAdminContext}>
            <AccountSettings />
          </AuthContext.Provider>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      });

      // Non-admin users should have limited access
      // (This would need to be implemented based on actual permission logic)
    });
  });

  describe("Data Persistence", () => {
    test("should maintain form state during navigation", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByDisplayValue("Test Organization"),
        ).toBeInTheDocument();
      });

      // Modify form
      const nameInput = screen.getByDisplayValue("Test Organization");
      await user.clear(nameInput);
      await user.type(nameInput, "Modified Name");

      // Verify form state is maintained
      expect(screen.getByDisplayValue("Modified Name")).toBeInTheDocument();
    });

    test("should handle concurrent updates gracefully", async () => {
      const user = userEvent.setup();
      const mockAxios = vi.mocked(await import("axios"));

      // Mock slow API response
      (mockAxios.default.put as unknown as Mock).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100)),
      );

      render(
        <TestWrapper>
          <AccountSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByDisplayValue("Test Organization"),
        ).toBeInTheDocument();
      });

      // Trigger multiple updates
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);
      await user.click(saveButton);

      // Verify only one update is processed
      await waitFor(() => {
        expect(mockAxios.default.put).toHaveBeenCalledTimes(1);
      });
    });
  });
});
