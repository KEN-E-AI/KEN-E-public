import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Authentication from "./Authentication";
import { AuthProvider } from "@/contexts/AuthContext";
import * as teamApi from "@/data/teamApi";

// Mock Firebase auth
vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: null,
    signOut: vi.fn(),
  },
  googleProvider: {},
}));

// Mock team API
vi.mock("@/data/teamApi", () => ({
  verifyInvitationToken: vi.fn(),
  acceptInvitation: vi.fn(),
}));

// Mock ReCaptcha components
vi.mock("@/components/auth/ReCaptchaWrapper", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: () => null,
}));

describe("Authentication with Invitation", () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const mockAuthContext = {
    user: null,
    isAuthenticated: false,
    hasSelectedWorkspace: false,
    login: vi.fn(),
    setNotificationSettings: vi.fn(),
    setSecuritySettings: vi.fn(),
    signOut: vi.fn(),
    completeWorkspaceSelection: vi.fn(),
    selectedOrganization: null,
    selectedAccount: null,
    setSelectedOrganization: vi.fn(),
    setSelectedAccount: vi.fn(),
    isLoading: false,
  };

  const renderWithRouter = (initialEntries: string[]) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider value={mockAuthContext}>
          <MemoryRouter initialEntries={initialEntries}>
            <Routes>
              <Route
                path="/auth/signin"
                element={<Authentication onAuthenticated={() => {}} />}
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("displays invitation message when valid invitation token is provided", async () => {
    const mockInvitation = {
      id: "test-id",
      email: "test@example.com",
      organization_id: "org-123",
      organization_name: "Test Organization",
      access_level: "admin",
      inviter_name: "John Doe",
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
      status: "pending" as const,
    };

    vi.mocked(teamApi.verifyInvitationToken).mockResolvedValue(mockInvitation);

    renderWithRouter(["/auth/signin?invitation=test-token"]);

    await waitFor(() => {
      expect(screen.getByText("You've been invited!")).toBeInTheDocument();
    });

    expect(screen.getByText(/Test Organization/)).toBeInTheDocument();
    expect(screen.getByText(/admin/)).toBeInTheDocument();
  });

  test("displays error message for invalid invitation token", async () => {
    vi.mocked(teamApi.verifyInvitationToken).mockRejectedValue({
      response: {
        status: 404,
        data: { detail: "Invitation not found" },
      },
    });

    renderWithRouter(["/auth/signin?invitation=invalid-token"]);

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
    });

    expect(screen.getByText("Invalid invitation link")).toBeInTheDocument();
  });

  test("displays error message for expired invitation", async () => {
    vi.mocked(teamApi.verifyInvitationToken).mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "Invitation has expired" },
      },
    });

    renderWithRouter(["/auth/signin?invitation=expired-token"]);

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
    });

    expect(screen.getByText("This invitation has expired")).toBeInTheDocument();
  });

  test("displays error message for already accepted invitation", async () => {
    vi.mocked(teamApi.verifyInvitationToken).mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "Invitation has already been accepted" },
      },
    });

    renderWithRouter(["/auth/signin?invitation=accepted-token"]);

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
    });

    expect(
      screen.getByText("This invitation has already been accepted"),
    ).toBeInTheDocument();
  });

  test("pre-fills email field when invitation is valid", async () => {
    const mockInvitation = {
      id: "test-id",
      email: "invited@example.com",
      organization_id: "org-123",
      organization_name: "Test Organization",
      access_level: "view",
      inviter_name: "Jane Doe",
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
      status: "pending" as const,
    };

    vi.mocked(teamApi.verifyInvitationToken).mockResolvedValue(mockInvitation);

    renderWithRouter(["/auth/signin?invitation=test-token"]);

    await waitFor(() => {
      const emailInput = screen.getByPlaceholderText(
        "Enter your email",
      ) as HTMLInputElement;
      expect(emailInput.value).toBe("invited@example.com");
    });
  });

  test("renders normally without invitation token", () => {
    renderWithRouter(["/auth/signin"]);

    expect(screen.queryByText("You've been invited!")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
  });
});
