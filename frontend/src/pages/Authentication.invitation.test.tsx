import React from "react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Authentication from "./Authentication";
import * as teamApi from "@/data/teamApi";

// Mock Firebase auth module (needed by Authentication.tsx)
vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: null,
    signOut: vi.fn().mockResolvedValue(undefined),
  },
  googleProvider: {},
  authInitialized: true,
  authBypassEnabled: false,
}));

vi.mock("firebase/auth", () => ({
  createUserWithEmailAndPassword: vi.fn(),
  sendEmailVerification: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  getRedirectResult: vi.fn().mockResolvedValue(null),
}));

// Mock @/lib/api directly so axios.create() is never called during module load
vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    login: vi.fn(),
    setNotificationSettings: vi.fn(),
    setSecuritySettings: vi.fn(),
  }),
}));

// Mock team API
vi.mock("@/data/teamApi", () => ({
  verifyInvitationToken: vi.fn(),
  acceptInvitation: vi.fn(),
}));

// Mock ReCaptcha components
vi.mock("@/components/auth/ReCaptchaErrorBoundary", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaWrapper", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: ({
    onVerify,
  }: {
    onVerify: (verified: boolean) => void;
    action: string;
  }) => {
    React.useEffect(() => {
      onVerify(true);
    }, [onVerify]);
    return null;
  },
}));

describe("Authentication with Invitation", () => {
  const renderWithRouter = (initialEntries: string[]) => {
    return render(
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route
            path="/sign-in"
            element={<Authentication onAuthenticated={() => {}} />}
          />
        </Routes>
      </MemoryRouter>,
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
      invited_at: new Date().toISOString(),
      status: "pending" as const,
    };

    vi.mocked(teamApi.verifyInvitationToken).mockResolvedValue(mockInvitation);

    renderWithRouter(["/sign-in?invitation=test-token"]);

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

    renderWithRouter(["/sign-in?invitation=invalid-token"]);

    await waitFor(() => {
      expect(screen.getByText("Invalid invitation link")).toBeInTheDocument();
    });
  });

  test("displays error message for expired invitation", async () => {
    vi.mocked(teamApi.verifyInvitationToken).mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "Invitation has expired" },
      },
    });

    renderWithRouter(["/sign-in?invitation=expired-token"]);

    await waitFor(() => {
      expect(
        screen.getByText("This invitation has expired"),
      ).toBeInTheDocument();
    });
  });

  test("displays error message for already accepted invitation", async () => {
    vi.mocked(teamApi.verifyInvitationToken).mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "Invitation has already been accepted" },
      },
    });

    renderWithRouter(["/sign-in?invitation=accepted-token"]);

    await waitFor(() => {
      expect(
        screen.getByText("This invitation has already been accepted"),
      ).toBeInTheDocument();
    });
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
      invited_at: new Date().toISOString(),
      status: "pending" as const,
    };

    vi.mocked(teamApi.verifyInvitationToken).mockResolvedValue(mockInvitation);

    renderWithRouter(["/sign-in?invitation=test-token"]);

    await waitFor(() => {
      const emailInput = screen.getByPlaceholderText(
        "you@example.com",
      ) as HTMLInputElement;
      expect(emailInput.value).toBe("invited@example.com");
    });
  });

  test("renders normally without invitation token", () => {
    renderWithRouter(["/sign-in"]);

    expect(screen.queryByText("You've been invited!")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: /welcome to ken-e/i }),
    ).toBeInTheDocument();
  });
});
