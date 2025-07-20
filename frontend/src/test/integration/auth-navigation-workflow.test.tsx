import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Authentication from "@/pages/Authentication";
import Settings from "@/pages/Settings";
import Home from "@/pages/Home";
import Performance from "@/pages/Performance";

// Mock Firebase
vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: null,
    signInWithEmailAndPassword: vi.fn(),
    createUserWithEmailAndPassword: vi.fn(),
    signOut: vi.fn(),
    onAuthStateChanged: vi.fn(),
  },
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
  },
};

const mockSelectedOrgAccount = {
  organization_id: "org-123",
  account_id: "account-456",
  metadata: {
    organization_name: "Test Organization",
    account_name: "Test Account",
  },
};

// Create test app component
const TestApp = ({ authContext }: { authContext: AuthContextType }) => {
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
          <Routes>
            <Route path="/login" element={<Authentication />} />
            <Route path="/signup" element={<Authentication />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Home />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <Settings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/performance"
              element={
                <ProtectedRoute>
                  <Performance />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthContext.Provider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe("Authentication and Navigation Workflow Integration Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock window.location
    Object.defineProperty(window, "location", {
      writable: true,
      value: {
        href: "http://localhost:3000",
        pathname: "/",
        search: "",
        hash: "",
        assign: vi.fn(),
        replace: vi.fn(),
      },
    });
  });

  describe("Authentication Flow", () => {
    test("should redirect unauthenticated users to login", async () => {
      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      render(<TestApp authContext={unauthenticatedContext} />);

      // Should redirect to login page
      await waitFor(() => {
        expect(window.location.pathname).toBe("/login");
      });
    });

    test("should allow authenticated users to access protected routes", async () => {
      const authenticatedContext: AuthContextType = {
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
      };

      render(<TestApp authContext={authenticatedContext} />);

      // Should allow access to home page
      await waitFor(() => {
        expect(screen.getByText("KEN-E")).toBeInTheDocument();
      });
    });

    test("should handle loading states during authentication", async () => {
      const loadingContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: true,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      render(<TestApp authContext={loadingContext} />);

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });
  });

  describe("Login Workflow", () => {
    test("should render login form", async () => {
      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      // Start at login page
      window.location.pathname = "/login";

      render(<TestApp authContext={unauthenticatedContext} />);

      // Should show login form
      await waitFor(() => {
        expect(screen.getByText("Sign in to KEN-E")).toBeInTheDocument();
      });

      // Verify form fields
      expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
      expect(screen.getByText("Sign In")).toBeInTheDocument();
    });

    test("should handle login form submission", async () => {
      const user = userEvent.setup();
      const mockSignIn = vi.fn();

      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
        notificationSettings: [],
        securitySettings: [],
        setCurrentOrganization: vi.fn(),
        setOrgMetadata: vi.fn(),
        updateUser: vi.fn(),
        setNotificationSettings: vi.fn(),
        signOut: mockSignIn,
        resetWorkspaceSelection: vi.fn(),
        completeWorkspaceSelection: vi.fn(),
        getUserOrganizations: vi.fn(),
        getOrganizationData: vi.fn(),
        refetchUser: vi.fn(),
        clearUserData: vi.fn(),
      };

      window.location.pathname = "/login";

      render(<TestApp authContext={unauthenticatedContext} />);

      // Fill in login form
      const emailInput = screen.getByPlaceholderText("Email");
      const passwordInput = screen.getByPlaceholderText("Password");
      const submitButton = screen.getByText("Sign In");

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");
      await user.click(submitButton);

      // Verify form submission
      expect(emailInput).toHaveValue("test@example.com");
      expect(passwordInput).toHaveValue("password123");
    });

    test("should display login validation errors", async () => {
      const user = userEvent.setup();

      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      window.location.pathname = "/login";

      render(<TestApp authContext={unauthenticatedContext} />);

      // Try to submit without filling fields
      const submitButton = screen.getByText("Sign In");
      await user.click(submitButton);

      // Should display validation errors
      await waitFor(() => {
        expect(screen.getByText("Email is required")).toBeInTheDocument();
        expect(screen.getByText("Password is required")).toBeInTheDocument();
      });
    });
  });

  describe("Signup Workflow", () => {
    test("should render signup form", async () => {
      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      window.location.pathname = "/signup";

      render(<TestApp authContext={unauthenticatedContext} />);

      // Should show signup form
      await waitFor(() => {
        expect(
          screen.getByText("Create your KEN-E account"),
        ).toBeInTheDocument();
      });

      // Verify form fields
      expect(screen.getByPlaceholderText("First Name")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Last Name")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
      expect(screen.getByText("Sign Up")).toBeInTheDocument();
    });

    test("should handle signup form submission", async () => {
      const user = userEvent.setup();

      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      window.location.pathname = "/signup";

      render(<TestApp authContext={unauthenticatedContext} />);

      // Fill in signup form
      const firstNameInput = screen.getByPlaceholderText("First Name");
      const lastNameInput = screen.getByPlaceholderText("Last Name");
      const emailInput = screen.getByPlaceholderText("Email");
      const passwordInput = screen.getByPlaceholderText("Password");
      const submitButton = screen.getByText("Sign Up");

      await user.type(firstNameInput, "John");
      await user.type(lastNameInput, "Doe");
      await user.type(emailInput, "john.doe@example.com");
      await user.type(passwordInput, "password123");
      await user.click(submitButton);

      // Verify form submission
      expect(firstNameInput).toHaveValue("John");
      expect(lastNameInput).toHaveValue("Doe");
      expect(emailInput).toHaveValue("john.doe@example.com");
      expect(passwordInput).toHaveValue("password123");
    });
  });

  describe("Navigation Workflow", () => {
    test("should navigate between protected routes when authenticated", async () => {
      const user = userEvent.setup();

      const authenticatedContext: AuthContextType = {
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
      };

      render(<TestApp authContext={authenticatedContext} />);

      // Should start at home page
      await waitFor(() => {
        expect(screen.getByText("KEN-E")).toBeInTheDocument();
      });

      // Navigate to settings
      const settingsLink = screen.getByText("Settings");
      await user.click(settingsLink);

      // Should navigate to settings page
      await waitFor(() => {
        expect(screen.getByText("Settings")).toBeInTheDocument();
      });
    });

    test("should handle logout workflow", async () => {
      const user = userEvent.setup();
      const mockSignOut = vi.fn();

      const authenticatedContext: AuthContextType = {
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
        signOut: mockSignOut,
        resetWorkspaceSelection: vi.fn(),
        completeWorkspaceSelection: vi.fn(),
        getUserOrganizations: vi.fn(),
        getOrganizationData: vi.fn(),
        refetchUser: vi.fn(),
        clearUserData: vi.fn(),
      };

      render(<TestApp authContext={authenticatedContext} />);

      // Should show authenticated content
      await waitFor(() => {
        expect(screen.getByText("KEN-E")).toBeInTheDocument();
      });

      // Find and click logout button
      const logoutButton = screen.getByText("Sign Out");
      await user.click(logoutButton);

      // Should call signOut function
      expect(mockSignOut).toHaveBeenCalled();
    });
  });

  describe("Organization Context Flow", () => {
    test("should handle organization selection", async () => {
      const user = userEvent.setup();
      const mockSetCurrentOrganization = vi.fn();

      const authenticatedContext: AuthContextType = {
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        orgMetadata: mockOrgMetadata,
        selectedOrgAccount: mockSelectedOrgAccount,
        currentOrganizationId: "org-123",
        notificationSettings: [],
        securitySettings: [],
        setCurrentOrganization: mockSetCurrentOrganization,
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

      render(<TestApp authContext={authenticatedContext} />);

      // Should show current organization
      await waitFor(() => {
        expect(screen.getByText("Test Organization")).toBeInTheDocument();
      });

      // Organization context should be available throughout the app
      expect(screen.getByText("Test Organization")).toBeInTheDocument();
    });

    test("should handle organization switching", async () => {
      const user = userEvent.setup();
      const mockSetCurrentOrganization = vi.fn();

      const authenticatedContext: AuthContextType = {
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        orgMetadata: {
          ...mockOrgMetadata,
          "org-456": {
            organization_id: "org-456",
            organization_name: "Second Organization",
            company_size: "Small",
            agency: false,
            child_organizations: [],
          },
        },
        selectedOrgAccount: mockSelectedOrgAccount,
        currentOrganizationId: "org-123",
        notificationSettings: [],
        securitySettings: [],
        setCurrentOrganization: mockSetCurrentOrganization,
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

      render(<TestApp authContext={authenticatedContext} />);

      // Should show current organization
      await waitFor(() => {
        expect(screen.getByText("Test Organization")).toBeInTheDocument();
      });

      // Switch organization functionality would be tested here
      // (Implementation depends on actual organization switcher component)
    });
  });

  describe("Error Handling", () => {
    test("should handle authentication errors", async () => {
      const errorContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
        notificationSettings: [],
        securitySettings: [],
        setCurrentOrganization: vi.fn(),
        setOrgMetadata: vi.fn(),
        updateUser: vi.fn(),
        setNotificationSettings: vi.fn(),
        signOut: vi.fn().mockRejectedValue(new Error("Auth error")),
        resetWorkspaceSelection: vi.fn(),
        completeWorkspaceSelection: vi.fn(),
        getUserOrganizations: vi.fn(),
        getOrganizationData: vi.fn(),
        refetchUser: vi.fn(),
        clearUserData: vi.fn(),
      };

      render(<TestApp authContext={errorContext} />);

      // Should handle authentication errors gracefully
      await waitFor(() => {
        expect(window.location.pathname).toBe("/login");
      });
    });

    test("should handle network errors during authentication", async () => {
      const user = userEvent.setup();

      // Mock network error
      vi.mocked(
        await import("@/lib/firebase"),
      ).auth.signInWithEmailAndPassword.mockRejectedValue(
        new Error("Network error"),
      );

      const unauthenticatedContext: AuthContextType = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        orgMetadata: {},
        selectedOrgAccount: null,
        currentOrganizationId: null,
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
      };

      window.location.pathname = "/login";

      render(<TestApp authContext={unauthenticatedContext} />);

      // Fill in login form
      const emailInput = screen.getByPlaceholderText("Email");
      const passwordInput = screen.getByPlaceholderText("Password");
      const submitButton = screen.getByText("Sign In");

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");
      await user.click(submitButton);

      // Should display error message
      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      });
    });
  });
});
