import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AcceptInvitation from "./AcceptInvitation";
import * as teamApi from "@/data/teamApi";
import { useAuth } from "@/contexts/AuthContext";

// Mock dependencies
vi.mock("@/contexts/AuthContext");
vi.mock("@/data/teamApi");
vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ token: "test-token-123" }),
    useNavigate: () => mockNavigate,
  };
});

const mockUseAuth = useAuth as unknown as ReturnType<typeof vi.fn>;
const mockVerifyInvitationToken =
  teamApi.verifyInvitationToken as unknown as ReturnType<typeof vi.fn>;
const mockAcceptInvitation = teamApi.acceptInvitation as unknown as ReturnType<
  typeof vi.fn
>;

const authenticatedUser = {
  id: "user-123",
  email: "test@example.com",
  firstName: "Test",
  lastName: "User",
};

const validInvitation = {
  id: "invite-id",
  email: "test@example.com",
  organization_id: "org-id",
  organization_name: "Test Org",
  invited_by: "inviter-id",
  inviter_name: "John Doe",
  access_level: "admin" as const,
  status: "pending" as const,
  invited_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86_400_000).toISOString(),
};

function renderComponent() {
  return render(
    <MemoryRouter initialEntries={["/invite/test-token-123"]}>
      <AcceptInvitation />
    </MemoryRouter>,
  );
}

describe("AcceptInvitation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: authenticatedUser,
      selectedOrganization: null,
      selectedAccount: null,
      signOut: vi.fn(),
      logout: vi.fn(),
    });
  });

  describe("Token from route param is used in API call", () => {
    test("calls verifyInvitationToken with the token from route params", async () => {
      mockVerifyInvitationToken.mockResolvedValue(validInvitation);

      renderComponent();

      await waitFor(() => {
        expect(mockVerifyInvitationToken).toHaveBeenCalledWith(
          "test-token-123",
        );
      });
    });

    test("shows loading state while verifying", () => {
      mockVerifyInvitationToken.mockReturnValue(new Promise(() => {}));

      renderComponent();

      expect(
        screen.getByText("Verifying your invitation..."),
      ).toBeInTheDocument();
    });
  });

  describe("Valid invitation — authenticated user", () => {
    test("renders invitation details after successful verification", async () => {
      mockVerifyInvitationToken.mockResolvedValue(validInvitation);

      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
          "You're invited!",
        );
      });
      expect(screen.getByText("Test Org")).toBeInTheDocument();
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /accept invitation/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /decline/i }),
      ).toBeInTheDocument();
    });

    test("calls acceptInvitation with correct arguments on accept", async () => {
      mockVerifyInvitationToken.mockResolvedValue(validInvitation);
      mockAcceptInvitation.mockResolvedValue({});

      const api = (await import("@/lib/api")).default;
      (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({});

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /accept invitation/i }),
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getByRole("button", { name: /accept invitation/i }),
      );

      await waitFor(() => {
        expect(mockAcceptInvitation).toHaveBeenCalledWith("test-token-123", {
          user_id: "user-123",
          user_email: "test@example.com",
          user_name: "Test User",
        });
      });
    });
  });

  describe("Success path — navigation after accept", () => {
    test("shows accepted state and navigates to / when Get Started is clicked", async () => {
      mockVerifyInvitationToken.mockResolvedValue(validInvitation);
      mockAcceptInvitation.mockResolvedValue({});

      const api = (await import("@/lib/api")).default;
      (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({});

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /accept invitation/i }),
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getByRole("button", { name: /accept invitation/i }),
      );

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
          "Welcome aboard! 🎉",
        );
      });

      await userEvent.click(
        screen.getByRole("button", { name: /get started/i }),
      );

      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
  });

  describe("Error states", () => {
    test("displays error UI when invitation has expired (400 + 'expired')", async () => {
      mockVerifyInvitationToken.mockRejectedValue({
        response: {
          status: 400,
          data: { detail: "This invitation has expired" },
        },
      });

      renderComponent();

      expect(
        screen.getByText("Verifying your invitation..."),
      ).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
        expect(
          screen.getByText("This invitation has expired"),
        ).toBeInTheDocument();
      });

      expect(
        screen.getByRole("button", { name: /go to dashboard/i }),
      ).toBeInTheDocument();
    });

    test("displays error UI when invitation has already been accepted (400 + 'already been accepted')", async () => {
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
          data: { detail: "This invitation has already been accepted" },
        },
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
        expect(
          screen.getByText("This invitation has already been accepted"),
        ).toBeInTheDocument();
      });

      expect(
        screen.getByRole("button", { name: /go to login/i }),
      ).toBeInTheDocument();
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
          data: { detail: "Some other validation error" },
        },
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
        expect(
          screen.getByText("Some other validation error"),
        ).toBeInTheDocument();
      });
    });

    test("displays error UI when invitation is not found (404)", async () => {
      mockUseAuth.mockReturnValue({
        user: null,
        selectedOrganization: null,
        selectedAccount: null,
        signOut: vi.fn(),
        logout: vi.fn(),
      });

      mockVerifyInvitationToken.mockRejectedValue({
        response: { status: 404, data: { detail: "Invitation not found" } },
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
        expect(screen.getByText("Invalid invitation link")).toBeInTheDocument();
      });
    });

    test("displays generic error for network / server errors (5xx)", async () => {
      mockUseAuth.mockReturnValue({
        user: null,
        selectedOrganization: null,
        selectedAccount: null,
        signOut: vi.fn(),
        logout: vi.fn(),
      });

      mockVerifyInvitationToken.mockRejectedValue({
        response: { status: 500, data: { detail: "Internal server error" } },
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
        expect(
          screen.getByText(
            "Failed to verify invitation. Please try again later.",
          ),
        ).toBeInTheDocument();
      });
    });

    test("displays error when API resolves with null (unexpected backend state)", async () => {
      mockVerifyInvitationToken.mockResolvedValue(null);

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Invalid Invitation")).toBeInTheDocument();
        expect(screen.getByText("Invalid invitation link")).toBeInTheDocument();
      });
    });
  });

  describe("Unauthenticated redirect", () => {
    test("redirects to sign-in when user is not authenticated and verification succeeds", async () => {
      mockUseAuth.mockReturnValue({
        user: null,
        selectedOrganization: null,
        selectedAccount: null,
        signOut: vi.fn(),
        logout: vi.fn(),
      });

      mockVerifyInvitationToken.mockResolvedValue(validInvitation);

      renderComponent();

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith(
          "/auth/signin?invitation=test-token-123",
          { replace: true },
        );
      });
    });
  });

  describe("Email mismatch", () => {
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
        ...validInvitation,
        email: "correct@example.com",
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Email Mismatch")).toBeInTheDocument();
      });

      expect(
        screen.getByText(/This invitation was sent to correct@example.com/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/you're signed in as wrong@example.com/),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /sign in with different account/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /go to dashboard/i }),
      ).toBeInTheDocument();
    });
  });
});
