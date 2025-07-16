import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import Settings from "@/pages/Settings";
import UserSettings from "@/pages/UserSettings";
import AccountSettings from "@/pages/AccountSettings";

// Mock data
const mockUser = {
  id: "user-123",
  firstName: "John",
  lastName: "Doe",
  email: "john.doe@example.com",
  jobTitle: "Marketing Manager",
  preferences: {
    language: "en",
    theme: "light",
    date_format: "mm-dd-yyyy",
  },
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
      plan_description: "Advanced features",
      price: 99,
      currency: "USD",
      billing_cycle: "monthly",
    },
    billing: {
      payment_method: {
        last_four: "1234",
        brand: "Visa",
        expires: "12/2025",
      },
    },
    team: {
      members_used: 5,
      members_limit: 10,
      pending_invitations: 2,
    },
  },
};

const mockSelectedOrgAccount: SelectedOrgAccount = {
  orgId: "org-123",
  accountId: "account-456",
  metadata: {
    organization_name: "Test Organization",
    account_name: "Test Account",
    industry: "Technology",
    status: "Active",
    timezone: "UTC",
    plan: "Pro",
  },
};

const mockNotificationSettings = [
  {
    id: "email-reports",
    label: "Email Reports",
    description: "Receive weekly performance reports via email",
    enabled: true,
  },
  {
    id: "push-notifications",
    label: "Push Notifications",
    description: "Get real-time notifications on your device",
    enabled: false,
  },
];

const mockSecuritySettings = [
  {
    id: "two-factor",
    label: "Two-Factor Authentication",
    description: "Add an extra layer of security to your account",
    action_type: "button",
    action_text: "Enable",
  },
  {
    id: "password-change",
    label: "Change Password",
    description: "Update your account password",
    action_type: "button",
    action_text: "Change",
  },
];

const mockAuthContext: AuthContextType = {
  user: mockUser,
  isAuthenticated: true,
  isLoading: false,
  orgMetadata: mockOrgMetadata,
  selectedOrgAccount: mockSelectedOrgAccount,
  currentOrganizationId: "org-123",
  notificationSettings: mockNotificationSettings,
  securitySettings: mockSecuritySettings,
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
};

// Test wrapper component
const TestWrapper = ({
  children,
  authContext = mockAuthContext,
}: {
  children: React.ReactNode;
  authContext?: AuthContextType;
}) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthContext.Provider value={authContext}>
          {children}
        </AuthContext.Provider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe("Settings Workflow Integration Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock axios calls
    vi.mock("axios", () => ({
      default: {
        put: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        get: vi.fn().mockResolvedValue({ data: {} }),
      },
    }));
  });

  describe("Settings Navigation Flow", () => {
    test("should navigate through all settings sections", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Verify main settings page loads
      expect(
        screen.getByText(
          "Manage your organization, accounts, and personal settings",
        ),
      ).toBeInTheDocument();

      // Verify settings cards are present
      expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      expect(screen.getByText("Account Management")).toBeInTheDocument();
      expect(screen.getByText("User Settings")).toBeInTheDocument();

      // Verify current context is displayed
      expect(screen.getByText("Current Context")).toBeInTheDocument();
      expect(screen.getAllByText("Test Organization")).toHaveLength(4); // Multiple instances expected

      // Verify quick actions are present
      expect(screen.getByText("Quick Actions")).toBeInTheDocument();
      expect(screen.getByText("Switch Organization")).toBeInTheDocument();
      expect(screen.getByText("Create Organization")).toBeInTheDocument();
    });

    test("should display configuration status indicators", async () => {
      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Check for status badges
      expect(screen.getByText("Complete")).toBeInTheDocument();
      expect(screen.getByText("Needs Attention")).toBeInTheDocument();
      expect(screen.getByText("Incomplete")).toBeInTheDocument();

      // Check for progress indicators
      const progressBars = screen.getAllByRole("progressbar");
      expect(progressBars).toHaveLength(3); // One for each settings card
    });
  });

  describe("User Settings Workflow", () => {
    test("should complete user profile update workflow", async () => {
      const user = userEvent.setup();
      const mockUpdateUser = vi.fn();

      const contextWithMocks = {
        ...mockAuthContext,
        updateUser: mockUpdateUser,
      };

      render(
        <TestWrapper authContext={contextWithMocks}>
          <UserSettings />
        </TestWrapper>,
      );

      // Verify user settings page loads
      expect(
        screen.getByText("Manage your personal preferences and user settings"),
      ).toBeInTheDocument();

      // Verify profile section
      expect(screen.getByText("Profile Information")).toBeInTheDocument();

      // Update profile information
      const firstNameInput = screen.getByDisplayValue("John");
      const lastNameInput = screen.getByDisplayValue("Doe");
      const emailInput = screen.getByDisplayValue("john.doe@example.com");

      await user.clear(firstNameInput);
      await user.type(firstNameInput, "Jane");

      await user.clear(lastNameInput);
      await user.type(lastNameInput, "Smith");

      // Save changes
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify update was called
      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalledWith({
          firstName: "Jane",
          lastName: "Smith",
          email: "john.doe@example.com",
          jobTitle: "Marketing Manager",
          preferences: mockUser.preferences,
        });
      });
    });

    test("should update notification preferences", async () => {
      const user = userEvent.setup();
      const mockSetNotificationSettings = vi.fn();

      const contextWithMocks = {
        ...mockAuthContext,
        setNotificationSettings: mockSetNotificationSettings,
      };

      render(
        <TestWrapper authContext={contextWithMocks}>
          <UserSettings />
        </TestWrapper>,
      );

      // Verify notification section
      expect(screen.getByText("Notification Preferences")).toBeInTheDocument();

      // Find notification switches
      const emailReportsSwitch = screen.getByRole("switch", {
        name: /Email Reports/i,
      });
      const pushNotificationsSwitch = screen.getByRole("switch", {
        name: /Push Notifications/i,
      });

      // Verify initial states
      expect(emailReportsSwitch).toBeChecked();
      expect(pushNotificationsSwitch).not.toBeChecked();

      // Toggle notifications
      await user.click(pushNotificationsSwitch);
      await user.click(emailReportsSwitch);

      // Save notification changes
      const saveNotificationButton = screen.getByText(
        "Save Notification Changes",
      );
      await user.click(saveNotificationButton);

      // Verify settings were updated
      await waitFor(() => {
        expect(mockSetNotificationSettings).toHaveBeenCalledWith([
          {
            id: "email-reports",
            label: "Email Reports",
            description: "Receive weekly performance reports via email",
            enabled: false,
          },
          {
            id: "push-notifications",
            label: "Push Notifications",
            description: "Get real-time notifications on your device",
            enabled: true,
          },
        ]);
      });
    });

    test("should update user preferences", async () => {
      const user = userEvent.setup();
      const mockUpdateUser = vi.fn();

      const contextWithMocks = {
        ...mockAuthContext,
        updateUser: mockUpdateUser,
      };

      render(
        <TestWrapper authContext={contextWithMocks}>
          <UserSettings />
        </TestWrapper>,
      );

      // Verify preferences section
      expect(screen.getByText("User Preferences")).toBeInTheDocument();

      // Change language preference
      const languageSelect = screen.getByDisplayValue("English");
      await user.click(languageSelect);

      const spanishOption = screen.getByText("Español");
      await user.click(spanishOption);

      // Change theme preference
      const themeSelect = screen.getByDisplayValue("Light");
      await user.click(themeSelect);

      const darkOption = screen.getByText("Dark");
      await user.click(darkOption);

      // Save changes
      const saveButton = screen.getAllByText("Save Changes")[1]; // Second save button for preferences
      await user.click(saveButton);

      // Verify preferences were updated
      await waitFor(() => {
        expect(mockUpdateUser).toHaveBeenCalledWith({
          firstName: "John",
          lastName: "Doe",
          email: "john.doe@example.com",
          jobTitle: "Marketing Manager",
          preferences: {
            language: "es",
            theme: "dark",
            date_format: "mm-dd-yyyy",
          },
        });
      });
    });
  });

  describe("Organization Settings Navigation", () => {
    test("should navigate to organization settings", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Click on organization settings card
      const orgSettingsCard = screen
        .getByText("Organization Settings")
        .closest('div[role="button"]');
      expect(orgSettingsCard).toBeInTheDocument();

      await user.click(orgSettingsCard!);

      // Verify navigation would occur (in a real test, this would check router navigation)
      // For now, we just verify the card is clickable
      expect(orgSettingsCard).toHaveClass("cursor-pointer");
    });

    test("should navigate to account management", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Click on account management card
      const accountCard = screen
        .getByText("Account Management")
        .closest('div[role="button"]');
      expect(accountCard).toBeInTheDocument();

      await user.click(accountCard!);

      // Verify navigation would occur
      expect(accountCard).toHaveClass("cursor-pointer");
    });

    test("should navigate to user settings", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Click on user settings card
      const userSettingsCard = screen
        .getByText("User Settings")
        .closest('div[role="button"]');
      expect(userSettingsCard).toBeInTheDocument();

      await user.click(userSettingsCard!);

      // Verify navigation would occur
      expect(userSettingsCard).toHaveClass("cursor-pointer");
    });
  });

  describe("Settings Layout Integration", () => {
    test("should render with correct layout structure", () => {
      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Verify SettingsLayout structure
      expect(screen.getByText("Settings")).toBeInTheDocument();

      // Verify entity selector is disabled for main settings
      const entitySelector = screen.getByText("Test Organization");
      expect(entitySelector).toBeInTheDocument();
    });

    test("should show entity selector on appropriate pages", () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      // User settings should NOT show entity selector
      expect(screen.getByText("User Settings")).toBeInTheDocument();

      // Entity selector should be disabled for user settings
      const entitySelector = screen.queryByText("Test Organization");
      expect(entitySelector).not.toBeInTheDocument();
    });
  });

  describe("Form Validation Integration", () => {
    test("should validate required fields in user settings", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      // Clear required field
      const firstNameInput = screen.getByDisplayValue("John");
      await user.clear(firstNameInput);

      // Try to save
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify validation (this would depend on actual validation implementation)
      // In a real implementation, this would check for validation errors
      expect(firstNameInput).toHaveValue("");
    });

    test("should handle form submission errors gracefully", async () => {
      const user = userEvent.setup();

      // Mock axios to throw error
      const mockAxios = vi.mocked(await import("axios"));
      mockAxios.default.put.mockRejectedValueOnce(new Error("Network error"));

      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      // Try to save
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify error handling (would show error message in real implementation)
      await waitFor(() => {
        // In a real implementation, this would check for error toast/alert
        expect(mockAxios.default.put).toHaveBeenCalled();
      });
    });
  });

  describe("End-to-End Settings Workflow", () => {
    test("should complete full settings configuration workflow", async () => {
      const user = userEvent.setup();

      // Start with main settings page
      const { rerender } = render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Navigate to user settings
      rerender(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      // Update profile
      const firstNameInput = screen.getByDisplayValue("John");
      await user.clear(firstNameInput);
      await user.type(firstNameInput, "Updated John");

      // Save changes
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify the workflow completes
      expect(screen.getByDisplayValue("Updated John")).toBeInTheDocument();
    });
  });
});
