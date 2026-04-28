import React from "react";
import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import Authentication from "./Authentication";
import { auth } from "@/lib/firebase";
import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signInWithEmailAndPassword,
} from "firebase/auth";
import axios from "axios";

// Mock dependencies
vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: null,
    signOut: vi.fn(),
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
}));

vi.mock("axios");
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    login: vi.fn(),
    setNotificationSettings: vi.fn(),
    setSecuritySettings: vi.fn(),
  }),
}));

// Mock ReCaptcha components
vi.mock("@/components/auth/ReCaptchaWrapper", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: ({
    onVerify,
    action,
  }: {
    onVerify: (verified: boolean) => void;
    action: string;
  }) => {
    // Auto-verify for testing
    React.useEffect(() => {
      onVerify(true);
    }, [onVerify]);
    return <div data-testid={`recaptcha-${action}`} />;
  },
}));

describe("Authentication - Email Verification", () => {
  const mockOnAuthenticated = vi.fn();
  const mockUser = {
    uid: "test-uid",
    email: "test@example.com",
    emailVerified: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (axios.post as Mock).mockResolvedValue({ data: { data: {} } });
    (axios.get as Mock).mockResolvedValue({
      data: { data: { profile: { email: "test@example.com" } } },
    });
  });

  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <Authentication onAuthenticated={mockOnAuthenticated} />
      </BrowserRouter>,
    );
  };

  describe("Sign Up Flow", () => {
    it("should send verification email after successful signup", async () => {
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock).mockResolvedValue(undefined);

      renderComponent();
      const user = userEvent.setup();

      // Switch to sign up tab
      await user.click(screen.getByRole("tab", { name: /create account/i }));

      // Fill in signup form
      await user.type(screen.getByLabelText(/first name/i), "John");
      await user.type(screen.getByLabelText(/last name/i), "Doe");
      await user.type(
        screen.getByLabelText(/email address/i),
        "john@example.com",
      );
      await user.type(screen.getByLabelText(/^password$/i), "password123");
      await user.type(
        screen.getByLabelText(/confirm password/i),
        "password123",
      );
      await user.click(
        screen.getByRole("checkbox", { name: /i agree to the/i }),
      );

      // Submit form
      await user.click(screen.getByRole("button", { name: /create account/i }));

      await waitFor(() => {
        expect(sendEmailVerification).toHaveBeenCalledWith(mockUser);
      });
    });

    it("should show email verification message after signup", async () => {
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock).mockResolvedValue(undefined);

      renderComponent();
      const user = userEvent.setup();

      // Switch to sign up tab
      await user.click(screen.getByRole("tab", { name: /create account/i }));

      // Fill and submit form
      await user.type(screen.getByLabelText(/first name/i), "John");
      await user.type(screen.getByLabelText(/last name/i), "Doe");
      await user.type(
        screen.getByLabelText(/email address/i),
        "john@example.com",
      );
      await user.type(screen.getByLabelText(/^password$/i), "password123");
      await user.type(
        screen.getByLabelText(/confirm password/i),
        "password123",
      );
      await user.click(
        screen.getByRole("checkbox", { name: /i agree to the/i }),
      );

      await user.click(screen.getByRole("button", { name: /create account/i }));

      await waitFor(() => {
        expect(screen.getByText(/verify your email/i)).toBeInTheDocument();
        expect(
          screen.getByText(/we've sent a verification email/i),
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

      renderComponent();
      const user = userEvent.setup();

      // Switch to sign up tab and complete signup
      await user.click(screen.getByRole("tab", { name: /create account/i }));
      await user.type(screen.getByLabelText(/first name/i), "John");
      await user.type(screen.getByLabelText(/last name/i), "Doe");
      await user.type(
        screen.getByLabelText(/email address/i),
        "john@example.com",
      );
      await user.type(screen.getByLabelText(/^password$/i), "password123");
      await user.type(
        screen.getByLabelText(/confirm password/i),
        "password123",
      );
      await user.click(
        screen.getByRole("checkbox", { name: /i agree to the/i }),
      );

      await user.click(screen.getByRole("button", { name: /create account/i }));

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

      renderComponent();
      const user = userEvent.setup();

      // Fill in signin form
      await user.type(
        screen.getByLabelText(/email address/i),
        "test@example.com",
      );
      await user.type(screen.getByLabelText(/password/i), "password123");

      // Submit form
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
      (axios.post as Mock).mockResolvedValue({
        data: { documents: [] },
      });

      renderComponent();
      const user = userEvent.setup();

      // Fill in signin form
      await user.type(
        screen.getByLabelText(/email address/i),
        "test@example.com",
      );
      await user.type(screen.getByLabelText(/password/i), "password123");

      // Submit form
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
      (axios.get as Mock).mockResolvedValue({
        data: {
          data: {
            profile: { email: "test@example.com", email_verified: false },
          },
        },
      });
      (axios.patch as Mock).mockResolvedValue({ data: {} });

      renderComponent();
      const user = userEvent.setup();

      await user.type(
        screen.getByLabelText(/email address/i),
        "test@example.com",
      );
      await user.type(screen.getByLabelText(/password/i), "password123");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(axios.patch).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/firestore/documents/users/test-uid"),
          expect.objectContaining({
            account_id: "test-uid",
            data: expect.objectContaining({
              profile: expect.objectContaining({
                email_verified: true,
              }),
            }),
          }),
        );
      });
    });
  });

  describe("Resend Verification Email", () => {
    it("should resend verification email when button is clicked", async () => {
      // Set up auth.currentUser
      (auth as any).currentUser = { ...mockUser, emailVerified: false };
      (sendEmailVerification as Mock).mockResolvedValue(undefined);

      // First, complete signup to show the resend button
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });

      renderComponent();
      const user = userEvent.setup();

      // Complete signup
      await user.click(screen.getByRole("tab", { name: /create account/i }));
      await user.type(screen.getByLabelText(/first name/i), "John");
      await user.type(screen.getByLabelText(/last name/i), "Doe");
      await user.type(
        screen.getByLabelText(/email address/i),
        "john@example.com",
      );
      await user.type(screen.getByLabelText(/^password$/i), "password123");
      await user.type(
        screen.getByLabelText(/confirm password/i),
        "password123",
      );
      await user.click(
        screen.getByRole("checkbox", { name: /i agree to the/i }),
      );
      await user.click(screen.getByRole("button", { name: /create account/i }));

      // Wait for resend button and click it
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
          screen.getByText(/verification email sent! please check your inbox/i),
        ).toBeInTheDocument();
      });
    });

    it("should handle too many requests error", async () => {
      (auth as any).currentUser = { ...mockUser, emailVerified: false };
      (sendEmailVerification as Mock).mockRejectedValue({
        code: "auth/too-many-requests",
      });

      // First, complete signup to show the resend button
      (createUserWithEmailAndPassword as Mock).mockResolvedValue({
        user: mockUser,
      });
      (sendEmailVerification as Mock)
        .mockResolvedValueOnce(undefined) // Success on signup
        .mockRejectedValueOnce({ code: "auth/too-many-requests" }); // Fail on resend

      renderComponent();
      const user = userEvent.setup();

      // Complete signup
      await user.click(screen.getByRole("tab", { name: /create account/i }));
      await user.type(screen.getByLabelText(/first name/i), "John");
      await user.type(screen.getByLabelText(/last name/i), "Doe");
      await user.type(
        screen.getByLabelText(/email address/i),
        "john@example.com",
      );
      await user.type(screen.getByLabelText(/^password$/i), "password123");
      await user.type(
        screen.getByLabelText(/confirm password/i),
        "password123",
      );
      await user.click(
        screen.getByRole("checkbox", { name: /i agree to the/i }),
      );
      await user.click(screen.getByRole("button", { name: /create account/i }));

      // Wait for and click resend button
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /resend verification email/i }),
        ).toBeInTheDocument();
      });

      await user.click(
        screen.getByRole("button", { name: /resend verification email/i }),
      );

      await waitFor(() => {
        expect(screen.getByText(/too many requests/i)).toBeInTheDocument();
      });
    });
  });
});
