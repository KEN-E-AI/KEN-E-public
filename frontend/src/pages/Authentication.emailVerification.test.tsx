import React from "react";
import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Authentication from "./Authentication";
import { auth } from "@/lib/firebase";
import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signInWithEmailAndPassword,
} from "firebase/auth";
import api from "@/lib/api";

// Mock dependencies
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

// Mock ReCaptcha components
vi.mock("@/components/auth/ReCaptchaErrorBoundary", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaProvider", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: ({
    onVerify,
  }: {
    onVerify: (verified: boolean) => void;
    action: string;
  }) => {
    // Auto-verify for testing
    React.useEffect(() => {
      onVerify(true);
    }, [onVerify]);
    return null;
  },
}));

describe("Authentication - Email Verification", () => {
  const mockOnAuthenticated = vi.fn();
  const mockUser = {
    uid: "test-uid",
    email: "test@example.com",
    emailVerified: false,
  };

  // Render at /sign-up so the component shows CreateAccountView
  const renderSignUp = () =>
    render(
      <MemoryRouter initialEntries={["/sign-up"]}>
        <Authentication onAuthenticated={mockOnAuthenticated} />
      </MemoryRouter>,
    );

  // Render at /sign-in so the component shows SignInView
  const renderSignIn = () =>
    render(
      <MemoryRouter initialEntries={["/sign-in"]}>
        <Authentication onAuthenticated={mockOnAuthenticated} />
      </MemoryRouter>,
    );

  const fillAndSubmitSignUpForm = async (
    user: ReturnType<typeof userEvent.setup>,
  ) => {
    await user.type(screen.getByLabelText(/full name/i), "John Doe");
    await user.type(screen.getByLabelText(/^email/i), "john@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    await user.click(screen.getByRole("checkbox", { name: /i agree to the/i }));
    await user.click(screen.getByRole("button", { name: /create account/i }));
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.post as Mock).mockResolvedValue({ data: { data: {} } });
    (api.get as Mock).mockResolvedValue({
      data: {
        data: { profile: { email: "test@example.com", email_verified: true } },
      },
    });
    (api.put as Mock).mockResolvedValue({ data: {} });
    (api.patch as Mock).mockResolvedValue({ data: {} });
  });

  describe("Sign Up Flow", () => {
    it("should send verification email after successful signup", async () => {
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock).mockResolvedValue(undefined);

      renderSignUp();
      const user = userEvent.setup();

      await fillAndSubmitSignUpForm(user);

      await waitFor(() => {
        expect(sendEmailVerification).toHaveBeenCalledWith(mockUser);
      });
    });

    it("should show email verification message after signup", async () => {
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock).mockResolvedValue(undefined);

      renderSignUp();
      const user = userEvent.setup();

      await fillAndSubmitSignUpForm(user);

      await waitFor(() => {
        // EmailVerificationView heading and copy (redesigned from "Verify your email")
        expect(
          screen.getByRole("heading", { level: 1, name: /check your email/i }),
        ).toBeInTheDocument();
        expect(
          screen.getByText(/we've sent a verification link/i),
        ).toBeInTheDocument();
        expect(
          screen.getByRole("button", { name: /resend verification email/i }),
        ).toBeInTheDocument();
      });
    });

    it("should show resend button after signup", async () => {
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock).mockResolvedValue(undefined);

      renderSignUp();
      const user = userEvent.setup();

      await fillAndSubmitSignUpForm(user);

      await waitFor(() => {
        const resendButton = screen.getByRole("button", {
          name: /resend verification email/i,
        });
        expect(resendButton).toBeInTheDocument();
      });
    });
  });

  describe("Sign In Flow", () => {
    it("should prevent sign in if email is not verified", async () => {
      const unverifiedUser = { ...mockUser, emailVerified: false };
      (signInWithEmailAndPassword as Mock).mockResolvedValue({
        user: unverifiedUser,
      });

      renderSignIn();
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/^email/i), "test@example.com");
      await user.type(screen.getByLabelText(/^password/i), "password123");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(
          screen.getByText(/please verify your email before signing in/i),
        ).toBeInTheDocument();
        expect(auth.signOut).toHaveBeenCalled();
        expect(mockOnAuthenticated).not.toHaveBeenCalled();
      });
    });

    it("should allow sign in if email is verified", async () => {
      const verifiedUser = { ...mockUser, emailVerified: true };
      (signInWithEmailAndPassword as Mock).mockResolvedValue({
        user: verifiedUser,
      });
      (api.post as Mock).mockResolvedValue({
        data: { documents: [] },
      });

      renderSignIn();
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/^email/i), "test@example.com");
      await user.type(screen.getByLabelText(/^password/i), "password123");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(mockOnAuthenticated).toHaveBeenCalled();
      });
    });

    it("should update email verification status in Firestore on first verified sign in", async () => {
      const verifiedUser = { ...mockUser, emailVerified: true };
      (signInWithEmailAndPassword as Mock).mockResolvedValue({
        user: verifiedUser,
      });
      (api.get as Mock).mockResolvedValue({
        data: {
          data: {
            profile: { email: "test@example.com", email_verified: false },
          },
        },
      });
      (api.put as Mock).mockResolvedValue({ data: {} });

      renderSignIn();
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/^email/i), "test@example.com");
      await user.type(screen.getByLabelText(/^password/i), "password123");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(api.put).toHaveBeenCalledWith(
          "/api/v1/firestore/documents/users/test-uid?account_id=test-uid",
          expect.objectContaining({
            update: expect.objectContaining({
              field: "profile.email_verified",
              value: true,
            }),
          }),
        );
      });
    });
  });

  describe("Resend Verification Email", () => {
    it("should resend verification email when button is clicked", async () => {
      (auth as any).currentUser = { ...mockUser, emailVerified: false };
      (sendEmailVerification as Mock).mockResolvedValue(undefined);
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });

      renderSignUp();
      const user = userEvent.setup();

      await fillAndSubmitSignUpForm(user);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /resend verification email/i }),
        ).toBeInTheDocument();
      });

      await user.click(
        screen.getByRole("button", { name: /resend verification email/i }),
      );

      await waitFor(() => {
        expect(sendEmailVerification).toHaveBeenCalledTimes(2); // Once on signup, once on resend
        expect(
          screen.getByText(/verification email sent successfully/i),
        ).toBeInTheDocument();
      });
    });

    it("should handle resend error", async () => {
      (auth as any).currentUser = { ...mockUser, emailVerified: false };
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock)
        .mockResolvedValueOnce(undefined) // Success on signup
        .mockRejectedValueOnce(new Error("resend failed")); // Fail on resend

      renderSignUp();
      const user = userEvent.setup();

      await fillAndSubmitSignUpForm(user);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /resend verification email/i }),
        ).toBeInTheDocument();
      });

      await user.click(
        screen.getByRole("button", { name: /resend verification email/i }),
      );

      await waitFor(() => {
        expect(screen.getByText(/failed to resend email/i)).toBeInTheDocument();
      });
    });
  });
});
