import { describe, test, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
} from "firebase/auth";
import api from "@/lib/api";
import Authentication from "./Authentication";
import { AuthContext } from "@/contexts/AuthContext";
import type { ReactNode } from "react";

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("@/lib/firebase", () => ({
  auth: {
    signOut: vi.fn().mockResolvedValue(undefined),
    currentUser: null,
  },
  googleProvider: {},
  authInitialized: true,
  authBypassEnabled: false,
}));

vi.mock("firebase/auth", () => ({
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  getRedirectResult: vi.fn().mockResolvedValue(null),
  sendEmailVerification: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("@/components/auth/ReCaptchaProvider", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

// Calls onVerify(true) on the next tick so captcha is auto-verified in tests.
vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: ({ onVerify }: { onVerify: (verified: boolean) => void }) => {
    setTimeout(() => onVerify(true), 0);
    return null;
  },
}));

vi.mock("@/data/teamApi", () => ({
  verifyInvitationToken: vi
    .fn()
    .mockRejectedValue({ response: { status: 404 } }),
}));

// ─── Shared helpers ───────────────────────────────────────────────────────────

const mockedApi = vi.mocked(api);

const makeAuthValue = () => ({
  user: null,
  login: vi.fn(),
  signOut: vi.fn(),
  updateUser: vi.fn(),
  setNotificationSettings: vi.fn(),
  setSecuritySettings: vi.fn(),
  selectedOrganization: null,
  setSelectedOrganization: vi.fn(),
  selectedAccount: null,
  setSelectedAccount: vi.fn(),
});

const renderAt = (
  path: string,
  authValue = makeAuthValue(),
  onAuthenticated = vi.fn(),
) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthContext.Provider value={authValue}>
        <Authentication onAuthenticated={onAuthenticated} />
      </AuthContext.Provider>
    </MemoryRouter>,
  );

// ─── Sign In view ─────────────────────────────────────────────────────────────

describe("Authentication — Sign In view", () => {
  test("renders heading, email input, password input, and Google button", () => {
    renderAt("/sign-in");
    expect(
      screen.getByRole("heading", { name: /welcome to ken-e/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /google/i })).toBeInTheDocument();
  });

  test("renders a link to create account", () => {
    renderAt("/sign-in");
    expect(
      screen.getByRole("link", { name: /create account/i }),
    ).toBeInTheDocument();
  });

  test("shows error on invalid credentials", async () => {
    const user = userEvent.setup();
    vi.mocked(signInWithEmailAndPassword).mockRejectedValueOnce({
      code: "auth/invalid-credential",
    });

    renderAt("/sign-in");

    await user.type(screen.getByLabelText(/^email/i), "bad@example.com");
    await user.type(screen.getByLabelText(/^password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/invalid email or password/i),
      ).toBeInTheDocument();
    });
  });

  // ─── Google Sign-In scenarios ─────────────────────────────────────────────

  test("Google button is enabled by default", () => {
    renderAt("/sign-in");
    expect(screen.getByRole("button", { name: /google/i })).not.toBeDisabled();
  });

  test("successful Google sign-in for existing user", async () => {
    const user = userEvent.setup();
    const authValue = makeAuthValue();
    const onAuthenticated = vi.fn();

    const firebaseUser = {
      uid: "test-uid",
      email: "test@example.com",
      displayName: "Test User",
    };
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: firebaseUser,
    } as any);

    mockedApi.get.mockResolvedValueOnce({
      data: {
        data: {
          profile: {
            email: "test@example.com",
            first_name: "Test",
            last_name: "User",
            job_title: "Developer",
          },
          permissions: { organizations: {}, accounts: {} },
          preferences: {},
        },
      },
    });
    mockedApi.post.mockResolvedValueOnce({
      data: { documents: [{ data: { emailNotifications: true } }] },
    });
    mockedApi.post.mockResolvedValueOnce({
      data: { documents: [{ data: { twoFactorEnabled: false } }] },
    });

    renderAt("/sign-in", authValue, onAuthenticated);
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(signInWithPopup).toHaveBeenCalledWith(
        expect.anything(),
        expect.anything(),
      );
    });

    await waitFor(() => {
      expect(authValue.login).toHaveBeenCalledWith({
        id: "test-uid",
        email: "test@example.com",
        firstName: "Test",
        lastName: "User",
        jobTitle: "Developer",
        permissions: { organizations: {}, accounts: {} },
        preferences: {},
      });
    });

    expect(authValue.setNotificationSettings).toHaveBeenCalledWith([
      { emailNotifications: true, id: "default" },
    ]);
    expect(authValue.setSecuritySettings).toHaveBeenCalledWith([
      { twoFactorEnabled: false, id: "default" },
    ]);
    expect(onAuthenticated).toHaveBeenCalled();
  });

  test("successful Google sign-in for new user", async () => {
    const user = userEvent.setup();
    const authValue = makeAuthValue();
    const onAuthenticated = vi.fn();

    const firebaseUser = {
      uid: "new-user-uid",
      email: "newuser@example.com",
      displayName: "New User",
    };
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: firebaseUser,
    } as any);

    mockedApi.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });
    mockedApi.post.mockImplementation((url: string) => {
      if (url === "/api/v1/firestore/documents") {
        return Promise.resolve({ data: { success: true } });
      }
      return Promise.resolve({ data: { documents: [] } });
    });

    renderAt("/sign-in", authValue, onAuthenticated);
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/api/v1/firestore/documents",
        expect.objectContaining({
          account_id: "new-user-uid",
          collection: "users",
          document_id: "new-user-uid",
          data: expect.objectContaining({
            profile: expect.objectContaining({
              email: "newuser@example.com",
              first_name: "New",
              last_name: "User",
            }),
          }),
        }),
      );
    });

    await waitFor(() => {
      expect(authValue.login).toHaveBeenCalledWith({
        id: "new-user-uid",
        email: "newuser@example.com",
        firstName: "New",
        lastName: "User",
        jobTitle: "",
        permissions: { organizations: {}, accounts: {} },
        preferences: {},
      });
    });
    expect(onAuthenticated).toHaveBeenCalled();
  });

  test("handles Google sign-in cancellation", async () => {
    const user = userEvent.setup();
    const authValue = makeAuthValue();
    vi.mocked(signInWithPopup).mockRejectedValueOnce({
      code: "auth/popup-closed-by-user",
    });

    renderAt("/sign-in", authValue);
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Sign-in cancelled. Please try again."),
      ).toBeInTheDocument();
    });
    expect(authValue.login).not.toHaveBeenCalled();
  });

  test("handles popup blocked error", async () => {
    const user = userEvent.setup();
    vi.mocked(signInWithPopup).mockRejectedValueOnce({
      code: "auth/popup-blocked",
    });

    renderAt("/sign-in");
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Pop-up blocked. Please allow pop-ups for this site."),
      ).toBeInTheDocument();
    });
  });

  test("handles API server error during Google sign-in", async () => {
    const user = userEvent.setup();
    const firebaseUser = {
      uid: "test-uid",
      email: "test@example.com",
      displayName: "Test User",
    };
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: firebaseUser,
    } as any);
    mockedApi.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 500 },
    });

    renderAt("/sign-in");
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Server error. Please try again later."),
      ).toBeInTheDocument();
    });
  });

  test("handles network error during Google sign-in", async () => {
    const user = userEvent.setup();
    vi.mocked(signInWithPopup).mockRejectedValueOnce({
      code: "auth/network-request-failed",
    });

    renderAt("/sign-in");
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please check your connection."),
      ).toBeInTheDocument();
    });
  });

  test("disables Google button while loading", async () => {
    const user = userEvent.setup();
    vi.mocked(signInWithPopup).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000)),
    );

    renderAt("/sign-in");
    const googleButton = screen.getByRole("button", { name: /google/i });
    expect(googleButton).not.toBeDisabled();

    await user.click(googleButton);
    expect(googleButton).toBeDisabled();
  });

  test("handles single-name Google users correctly", async () => {
    const user = userEvent.setup();
    const authValue = makeAuthValue();
    const firebaseUser = {
      uid: "single-name-uid",
      email: "prince@example.com",
      displayName: "Prince",
    };
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: firebaseUser,
    } as any);
    mockedApi.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });
    mockedApi.post.mockImplementation((url: string) => {
      if (url === "/api/v1/firestore/documents") {
        return Promise.resolve({ data: { success: true } });
      }
      return Promise.resolve({ data: { documents: [] } });
    });

    renderAt("/sign-in", authValue);
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/api/v1/firestore/documents",
        expect.objectContaining({
          data: expect.objectContaining({
            profile: expect.objectContaining({
              first_name: "Prince",
              last_name: "",
            }),
          }),
        }),
      );
    });
  });

  test("handles Google users with no display name", async () => {
    const user = userEvent.setup();
    const authValue = makeAuthValue();
    const firebaseUser = {
      uid: "no-name-uid",
      email: "noname@example.com",
      displayName: null,
    };
    vi.mocked(signInWithPopup).mockResolvedValueOnce({
      user: firebaseUser,
    } as any);
    mockedApi.get.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404 },
    });
    mockedApi.post.mockImplementation((url: string) => {
      if (url === "/api/v1/firestore/documents") {
        return Promise.resolve({ data: { success: true } });
      }
      return Promise.resolve({ data: { documents: [] } });
    });

    renderAt("/sign-in", authValue);
    await user.click(screen.getByRole("button", { name: /google/i }));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/api/v1/firestore/documents",
        expect.objectContaining({
          data: expect.objectContaining({
            profile: expect.objectContaining({
              first_name: "",
              last_name: "",
            }),
          }),
        }),
      );
    });
  });
});

// ─── Create Account view ──────────────────────────────────────────────────────

describe("Authentication — Create Account view", () => {
  test("renders heading and all form fields", () => {
    renderAt("/create-account");
    expect(
      screen.getByRole("heading", { name: /create your account/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /google/i })).toBeInTheDocument();
  });

  test("shows password strength indicator when typing", async () => {
    const user = userEvent.setup();
    renderAt("/create-account");

    await user.type(screen.getByLabelText(/^password/i), "pass");
    expect(screen.getByText(/weak/i)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^password/i));
    await user.type(screen.getByLabelText(/^password/i), "Password1234X");
    expect(screen.getByText(/strong/i)).toBeInTheDocument();
  });

  test("shows field error when passwords do not match", async () => {
    const user = userEvent.setup();
    renderAt("/create-account");

    await user.type(screen.getByLabelText(/full name/i), "Jane Smith");
    await user.type(screen.getByLabelText(/^email/i), "jane@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "different123");
    // Password mismatch is validated before terms — no need to check terms box
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  test("shows error when email is already registered", async () => {
    const user = userEvent.setup();
    vi.mocked(createUserWithEmailAndPassword).mockRejectedValueOnce({
      code: "auth/email-already-in-use",
    });

    renderAt("/create-account");

    await user.type(screen.getByLabelText(/full name/i), "Jane Smith");
    await user.type(screen.getByLabelText(/^email/i), "existing@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    // Use fireEvent for Radix Checkbox — userEvent pointer events don't trigger onCheckedChange in jsdom
    fireEvent.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/this email is already registered/i),
      ).toBeInTheDocument();
    });
  });

  test("shows field error when terms checkbox is not checked", async () => {
    const user = userEvent.setup();
    renderAt("/create-account");

    await user.type(screen.getByLabelText(/full name/i), "Jane Smith");
    await user.type(screen.getByLabelText(/^email/i), "jane@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    // Do NOT check the terms checkbox
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/you must agree to the terms of service/i),
      ).toBeInTheDocument();
    });
  });

  test("transitions to email-verification view after successful sign-up", async () => {
    const user = userEvent.setup();
    vi.mocked(createUserWithEmailAndPassword).mockResolvedValueOnce({
      user: {
        uid: "new-uid",
        email: "new@example.com",
        emailVerified: false,
      },
    } as any);
    mockedApi.post.mockResolvedValue({ data: { success: true } });

    renderAt("/create-account");

    await user.type(screen.getByLabelText(/full name/i), "New User");
    await user.type(screen.getByLabelText(/^email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    // Use fireEvent for Radix Checkbox — userEvent pointer events don't trigger onCheckedChange in jsdom
    fireEvent.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /check your email/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("new@example.com")).toBeInTheDocument();
  });
});

// ─── Email Verification view ──────────────────────────────────────────────────

describe("Authentication — Email Verification view", () => {
  test("renders heading and resend button at /verify-email route", () => {
    renderAt("/verify-email");
    expect(
      screen.getByRole("heading", { name: /check your email/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /resend verification email/i }),
    ).toBeInTheDocument();
  });

  test("resend button is enabled by default", () => {
    renderAt("/verify-email");
    expect(
      screen.getByRole("button", { name: /resend verification email/i }),
    ).not.toBeDisabled();
  });

  test("shows sign-in link for already-verified users", () => {
    renderAt("/verify-email");
    expect(screen.getByRole("link", { name: /sign in/i })).toBeInTheDocument();
  });
});
