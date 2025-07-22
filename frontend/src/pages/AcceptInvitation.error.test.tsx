import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import AcceptInvitation from "./AcceptInvitation";
import * as teamApi from "@/data/teamApi";
import { useAuth } from "@/contexts/AuthContext";

// Mock dependencies
vi.mock("@/contexts/AuthContext");
vi.mock("@/data/teamApi");
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ token: "test-token-123" }),
    useNavigate: vi.fn(() => vi.fn()),
  };
});

const mockUseAuth = useAuth as unknown as ReturnType<typeof vi.fn>;
const mockVerifyInvitationToken = teamApi.verifyInvitationToken as unknown as ReturnType<typeof vi.fn>;

describe("AcceptInvitation - Error Scenarios", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("displays error UI when invitation has expired (400 error)", async () => {
    // Setup: User is not authenticated
    mockUseAuth.mockReturnValue({
      user: null,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    // Mock API to return 400 error with "expired" message
    mockVerifyInvitationToken.mockRejectedValue({
      response: {
        status: 400,
        data: {
          detail: "This invitation has expired",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    // Should show loading state initially
    expect(screen.getByText("Verifying your invitation...")).toBeInTheDocument();

    // Wait for error to be displayed
    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
      expect(screen.getByText("This invitation has expired")).toBeInTheDocument();
    });

    // Should NOT show blank page
    expect(screen.getByRole("button", { name: /go to login/i })).toBeInTheDocument();
  });

  test("displays error UI when invitation has already been accepted (400 error)", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    mockVerifyInvitationToken.mockRejectedValue({
      response: {
        status: 400,
        data: {
          detail: "This invitation has already been accepted",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
      expect(screen.getByText("This invitation has already been accepted")).toBeInTheDocument();
    });
  });

  test("displays generic error for other 400 errors", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    mockVerifyInvitationToken.mockRejectedValue({
      response: {
        status: 400,
        data: {
          detail: "Some other validation error",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
      expect(screen.getByText("Some other validation error")).toBeInTheDocument();
    });
  });

  test("displays error UI when invitation is not found (404 error)", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    mockVerifyInvitationToken.mockRejectedValue({
      response: {
        status: 404,
        data: {
          detail: "Invitation not found",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
      expect(screen.getByText("Invalid invitation link")).toBeInTheDocument();
    });
  });

  test("displays generic error for network/server errors", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    mockVerifyInvitationToken.mockRejectedValue({
      response: {
        status: 500,
        data: {
          detail: "Internal server error",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
      expect(screen.getByText("Failed to verify invitation. Please try again later.")).toBeInTheDocument();
    });
  });

  test("redirects to sign-in when user is not authenticated and no error", async () => {
    const mockNavigate = vi.fn();
    const { useNavigate } = await import("react-router-dom");
    vi.mocked(useNavigate).mockReturnValue(mockNavigate);

    mockUseAuth.mockReturnValue({
      user: null,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    // Mock successful invitation verification
    mockVerifyInvitationToken.mockResolvedValue({
      id: "test-id",
      email: "test@example.com",
      organization_name: "Test Org",
      inviter_name: "John Doe",
      access_level: "member",
      expires_at: new Date(Date.now() + 86400000).toISOString(),
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    // Should show loading initially
    expect(screen.getByText("Verifying your invitation...")).toBeInTheDocument();

    // Should redirect after verification succeeds
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/auth/signin?invitation=test-token-123", { replace: true });
    });
  });

  test("displays email mismatch error when authenticated with wrong email", async () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "wrong@example.com",
        firstName: "Jane",
        lastName: "Smith",
      },
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    mockVerifyInvitationToken.mockResolvedValue({
      id: "test-id",
      email: "correct@example.com",
      organization_name: "Test Org",
      inviter_name: "John Doe",
      access_level: "member",
      expires_at: new Date(Date.now() + 86400000).toISOString(),
    });

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Email Mismatch")).toBeInTheDocument();
      expect(screen.getByText(/This invitation was sent to correct@example.com/)).toBeInTheDocument();
      expect(screen.getByText(/you're signed in as wrong@example.com/)).toBeInTheDocument();
    });

    // Should show options to switch accounts
    expect(screen.getByRole("button", { name: /sign in with different account/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /go to dashboard/i })).toBeInTheDocument();
  });

  test("renders fallback UI if no conditions match", async () => {
    // Mock console.error to verify it's called
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    mockUseAuth.mockReturnValue({
      user: {
        id: "user-123",
        email: "test@example.com",
        firstName: "Test",
        lastName: "User",
      },
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });

    // Mock API to resolve but with no data (edge case)
    mockVerifyInvitationToken.mockResolvedValue(null);

    render(
      <MemoryRouter initialEntries={["/invite/test-token-123"]}>
        <AcceptInvitation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Unexpected Error")).toBeInTheDocument();
      expect(screen.getByText("An unexpected error occurred. Please try refreshing the page.")).toBeInTheDocument();
    });

    // Verify error was logged
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "[AcceptInvitation] Unexpected state - no condition matched for rendering"
    );

    consoleErrorSpy.mockRestore();
  });
});