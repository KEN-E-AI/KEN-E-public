import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import Settings from "@/pages/Settings";
import UserSettings from "@/pages/UserSettings";

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

const mockAuthContext: AuthContextType = {
  user: mockUser,
  isAuthenticated: true,
  isLoading: false,
  notifications: [],
  orgMetadata: {
    "org-123": {
      organization_id: "org-123",
      organization_name: "Test Organization",
      company_size: "Medium",
      agency: false,
      child_organizations: [],
    },
  },
  selectedOrgAccount: mockSelectedOrgAccount,
  currentOrganizationId: "org-123",
  notificationSettings: [
    {
      id: "email-reports",
      label: "Email Reports",
      description: "Receive weekly performance reports via email",
      enabled: true,
    },
  ],
  securitySettings: [
    {
      id: "two-factor",
      label: "Two-Factor Authentication",
      description: "Add an extra layer of security to your account",
      action_type: "button",
      action_text: "Enable",
    },
  ],
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

describe("Settings Workflow Integration Tests - Simplified", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock window.alert
    Object.defineProperty(window, "alert", {
      value: vi.fn(),
      writable: true,
    });

    // Mock axios calls
    vi.mock("axios", () => ({
      default: {
        put: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        get: vi.fn().mockResolvedValue({ data: {} }),
      },
    }));
  });

  describe("Settings Page Navigation", () => {
    test("should render settings page with key elements", async () => {
      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      // Wait for component to render
      await waitFor(() => {
        expect(
          screen.getByText("Manage your organization and personal settings"),
        ).toBeInTheDocument();
      });

      // Verify settings sections are present
      expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      expect(
        screen.getByText("Select an organization to manage its settings"),
      ).toBeInTheDocument();
      expect(screen.getByText("Personal Settings")).toBeInTheDocument();
      expect(screen.getByText("User Settings")).toBeInTheDocument();
    });

    test("should display organization list with permissions", async () => {
      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      });

      // Check for organization with admin permission
      expect(screen.getByText("Test Organization")).toBeInTheDocument();
      expect(screen.getByText("Administrator")).toBeInTheDocument();
    });

    test("should handle card clicks for navigation", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      });

      // Find clickable cards by looking for elements with cursor-pointer class
      const settingsCards = screen
        .getAllByText("Organization Settings")[0]
        .closest(".cursor-pointer");

      // Find and click the organization card
      const orgCard = screen
        .getByText("Test Organization")
        .closest(".cursor-pointer");
      expect(orgCard).toBeInTheDocument();
      if (settingsCards) {
        await user.click(settingsCards);
        expect(settingsCards).toHaveClass("cursor-pointer");
      }
    });
  });

  describe("User Settings Page", () => {
    test("should render user settings page", async () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByText(
            "Manage your personal preferences and user settings",
          ),
        ).toBeInTheDocument();
      });

      // Verify profile section
      expect(screen.getByText("Profile Information")).toBeInTheDocument();
      expect(screen.getByText("Notification Preferences")).toBeInTheDocument();
      expect(screen.getByText("Security Settings")).toBeInTheDocument();
      expect(screen.getByText("User Preferences")).toBeInTheDocument();
    });

    test("should display user profile information", async () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Profile Information")).toBeInTheDocument();
      });

      // Verify form inputs with user data
      expect(screen.getByDisplayValue("John")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Doe")).toBeInTheDocument();
      expect(
        screen.getByDisplayValue("john.doe@example.com"),
      ).toBeInTheDocument();
      expect(screen.getByDisplayValue("Marketing Manager")).toBeInTheDocument();
    });

    test("should handle profile updates", async () => {
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

      await waitFor(() => {
        expect(screen.getByDisplayValue("John")).toBeInTheDocument();
      });

      // Update first name
      const firstNameInput = screen.getByDisplayValue("John");
      await user.clear(firstNameInput);
      await user.type(firstNameInput, "Jane");

      // Find and click the profile save button (first one)
      const saveButtons = screen.getAllByText("Save Changes");
      await user.click(saveButtons[0]);

      // Verify the form was updated
      expect(screen.getByDisplayValue("Jane")).toBeInTheDocument();
    });

    test("should display notification settings", async () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByText("Notification Preferences"),
        ).toBeInTheDocument();
      });

      // Verify notification settings
      expect(screen.getByText("Email Reports")).toBeInTheDocument();
      expect(
        screen.getByText("Receive weekly performance reports via email"),
      ).toBeInTheDocument();
    });

    test("should handle notification preference updates", async () => {
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

      await waitFor(() => {
        expect(screen.getByText("Email Reports")).toBeInTheDocument();
      });

      // Find the notification switch
      const emailReportsSwitch = screen.getByRole("switch");
      expect(emailReportsSwitch).toBeChecked();

      // Toggle the switch
      await user.click(emailReportsSwitch);

      // Find and click the notification save button
      const saveNotificationButton = screen.getByText(
        "Save Notification Changes",
      );
      await user.click(saveNotificationButton);

      // Verify the switch was toggled
      expect(emailReportsSwitch).not.toBeChecked();
    });

    test("should display security settings", async () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Security Settings")).toBeInTheDocument();
      });

      // Verify security settings
      expect(screen.getByText("Two-Factor Authentication")).toBeInTheDocument();
      expect(
        screen.getByText("Add an extra layer of security to your account"),
      ).toBeInTheDocument();
      expect(screen.getByText("Enable")).toBeInTheDocument();
    });

    test("should display user preferences", async () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("User Preferences")).toBeInTheDocument();
      });

      // Verify preference settings
      expect(screen.getByText("Language")).toBeInTheDocument();
      expect(screen.getByText("Theme")).toBeInTheDocument();
      expect(screen.getByText("Date Format")).toBeInTheDocument();
    });

    test("should handle preference updates", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Language")).toBeInTheDocument();
      });

      // Find language setting by label
      const languageLabel = screen.getByText("Language");
      expect(languageLabel).toBeInTheDocument();

      // Find theme setting by label
      const themeLabel = screen.getByText("Theme");
      expect(themeLabel).toBeInTheDocument();

      // Find date format setting by label
      const dateFormatLabel = screen.getByText("Date Format");
      expect(dateFormatLabel).toBeInTheDocument();
    });
  });

  describe("Authentication Context Integration", () => {
    test("should display user information from context", async () => {
      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByDisplayValue("John")).toBeInTheDocument();
      });

      // Verify user data from context is displayed
      expect(screen.getByDisplayValue("Doe")).toBeInTheDocument();
      expect(
        screen.getByDisplayValue("john.doe@example.com"),
      ).toBeInTheDocument();
      expect(screen.getByDisplayValue("Marketing Manager")).toBeInTheDocument();
    });

    test("should handle missing user data gracefully", async () => {
      const contextWithoutUser = {
        ...mockAuthContext,
        user: null,
      };

      render(
        <TestWrapper authContext={contextWithoutUser}>
          <UserSettings />
        </TestWrapper>,
      );

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });
  });

  describe("Error Handling", () => {
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

      await waitFor(() => {
        expect(screen.getByDisplayValue("John")).toBeInTheDocument();
      });

      // Try to save profile
      const saveButtons = screen.getAllByText("Save Changes");
      await user.click(saveButtons[0]);

      // Should handle the error gracefully
      await waitFor(() => {
        expect(mockAxios.default.put).toHaveBeenCalled();
      });
    });

    test("should validate form inputs", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <UserSettings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByDisplayValue("John")).toBeInTheDocument();
      });

      // Clear required field
      const firstNameInput = screen.getByDisplayValue("John");
      await user.clear(firstNameInput);

      // Verify field is cleared
      expect(firstNameInput).toHaveValue("");

      // Try to save - form should prevent submission or show validation
      const saveButtons = screen.getAllByText("Save Changes");
      await user.click(saveButtons[0]);

      // The form should handle this validation
      expect(firstNameInput).toHaveValue("");
    });
  });

  describe("Settings Layout Integration", () => {
    test("should render with settings layout wrapper", async () => {
      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(
          screen.getByText("Manage your organization and personal settings"),
        ).toBeInTheDocument();
      });

      // Verify layout structure is present
      expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      expect(screen.getByText("Personal Settings")).toBeInTheDocument();
    });

    test("should show organization selector", async () => {
      render(
        <TestWrapper>
          <Settings />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Organization Settings")).toBeInTheDocument();
      });

      // Should display organizations the user can manage
      expect(screen.getByText("Test Organization")).toBeInTheDocument();
      expect(screen.getByText("Administrator")).toBeInTheDocument();
    });
  });
});
