import React from "react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { signInWithPopup, createUserWithEmailAndPassword } from "firebase/auth";
import Authentication from "./Authentication";
import * as earlyReleaseApi from "@/data/earlyReleaseApi";

// ─── Module mocks ────────────────────────────────────────────────────────────

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
    post: vi.fn().mockResolvedValue({ data: { success: true } }),
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

vi.mock("@/data/teamApi", () => ({
  verifyInvitationToken: vi
    .fn()
    .mockRejectedValue({ response: { status: 404 } }),
}));

vi.mock("@/data/earlyReleaseApi", () => ({
  getSignupPolicy: vi.fn(),
  validateAccessCode: vi.fn(),
  EARLY_RELEASE_CODE_STORAGE_KEY: "kene_early_release_code",
}));

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

// ─── Helpers ─────────────────────────────────────────────────────────────────

const renderSignup = (path = "/signup") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Authentication onAuthenticated={vi.fn()} />
    </MemoryRouter>,
  );

const mockPolicy = (invite_only: boolean) =>
  vi.mocked(earlyReleaseApi.getSignupPolicy).mockResolvedValue({ invite_only });

const mockValidate = (valid: boolean) =>
  vi.mocked(earlyReleaseApi.validateAccessCode).mockResolvedValue({ valid });

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("Authentication — Early Release gate (flag OFF / open signup)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockPolicy(false);
  });

  test("does not show the early-access banner", async () => {
    renderSignup();
    await waitFor(() =>
      expect(earlyReleaseApi.getSignupPolicy).toHaveBeenCalled(),
    );
    expect(screen.queryByTestId("early-access-banner")).not.toBeInTheDocument();
  });

  test("submit button is enabled by today's rules (no code gate)", async () => {
    renderSignup();
    await waitFor(() =>
      expect(earlyReleaseApi.getSignupPolicy).toHaveBeenCalled(),
    );
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).not.toBeDisabled();
  });

  test("does not write to sessionStorage", async () => {
    renderSignup();
    await waitFor(() =>
      expect(earlyReleaseApi.getSignupPolicy).toHaveBeenCalled(),
    );
    expect(sessionStorage.getItem("kene_early_release_code")).toBeNull();
  });
});

describe("Authentication — Early Release gate (flag ON, no invitation, non-staff email)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockPolicy(true);
  });

  test("shows the early-access banner and code field", async () => {
    renderSignup();
    await waitFor(() =>
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument(),
    );
    expect(screen.getByLabelText(/early release code/i)).toBeInTheDocument();
  });

  test("submit button is disabled until code validates", async () => {
    renderSignup();
    await waitFor(() =>
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeDisabled();
  });

  test("on valid code blur: sets valid status and writes sessionStorage", async () => {
    mockValidate(true);
    renderSignup();

    await waitFor(() =>
      expect(screen.getByLabelText(/early release code/i)).toBeInTheDocument(),
    );

    const codeInput = screen.getByLabelText(/early release code/i);
    fireEvent.change(codeInput, { target: { value: "GOOD-CODE" } });
    fireEvent.blur(codeInput);

    await waitFor(() =>
      expect(earlyReleaseApi.validateAccessCode).toHaveBeenCalledWith(
        "GOOD-CODE",
      ),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).not.toBeDisabled(),
    );

    expect(sessionStorage.getItem("kene_early_release_code")).toBe("GOOD-CODE");
  });

  test("on invalid code blur: shows inline error and submit stays disabled", async () => {
    mockValidate(false);
    renderSignup();

    await waitFor(() =>
      expect(screen.getByLabelText(/early release code/i)).toBeInTheDocument(),
    );

    const codeInput = screen.getByLabelText(/early release code/i);
    fireEvent.change(codeInput, { target: { value: "BAD-CODE" } });
    fireEvent.blur(codeInput);

    await waitFor(() =>
      expect(
        screen.getByText(/invalid early release code/i),
      ).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeDisabled();
    expect(sessionStorage.getItem("kene_early_release_code")).toBeNull();
  });

  test("on 429 validate error: shows friendly error", async () => {
    vi.mocked(earlyReleaseApi.validateAccessCode).mockRejectedValueOnce(
      Object.assign(new Error("Rate limited"), { response: { status: 429 } }),
    );
    renderSignup();

    await waitFor(() =>
      expect(screen.getByLabelText(/early release code/i)).toBeInTheDocument(),
    );

    const codeInput = screen.getByLabelText(/early release code/i);
    fireEvent.change(codeInput, { target: { value: "ANY-CODE" } });
    fireEvent.blur(codeInput);

    await waitFor(() =>
      expect(screen.getByText(/couldn't validate/i)).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeDisabled();
  });

  test("getSignupPolicy rejection is treated as flag OFF (fail-open)", async () => {
    vi.mocked(earlyReleaseApi.getSignupPolicy).mockRejectedValueOnce(
      new Error("Service unavailable"),
    );

    renderSignup();

    await waitFor(() =>
      expect(earlyReleaseApi.getSignupPolicy).toHaveBeenCalled(),
    );

    expect(screen.queryByTestId("early-access-banner")).not.toBeInTheDocument();
  });
});

describe("Authentication — Early Release gate (flag ON, @ken-e.ai email: no client exemption)", () => {
  // The client no longer exempts @ken-e.ai emails: signup is pre-auth so the
  // client cannot know super_admin status, and the server gate bypasses on the
  // super_admin role only (not email domain). The code field therefore stays
  // visible regardless of email. See DM-PRD-11 §4.3 + DESIGN-REVIEW-LOG 2026-06-08.
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockPolicy(true);
  });

  test("keeps the code field visible when the user types a @ken-e.ai email", async () => {
    const user = userEvent.setup();
    renderSignup();

    await waitFor(() =>
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText(/^email/i), "alice@ken-e.ai");

    // Field remains; @ken-e.ai is no longer a client-side bypass.
    expect(screen.getByTestId("access-code-field")).toBeInTheDocument();
    // And submit stays gated until a code validates.
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeDisabled();
  });

  test("code field is identical for @ken-e.ai and public emails", async () => {
    const user = userEvent.setup();
    renderSignup();

    await waitFor(() =>
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText(/^email/i), "alice@ken-e.ai");
    expect(screen.getByTestId("access-code-field")).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^email/i));
    await user.type(screen.getByLabelText(/^email/i), "public@example.com");
    expect(screen.getByTestId("access-code-field")).toBeInTheDocument();
  });
});

describe("Authentication — Early Release gate (flag ON, invitation token present)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockPolicy(true);
  });

  test("does not show the code field when ?invitation param is present", async () => {
    renderSignup("/signup?invitation=tok-123");

    await waitFor(() =>
      expect(earlyReleaseApi.getSignupPolicy).toHaveBeenCalled(),
    );

    expect(screen.queryByTestId("access-code-field")).not.toBeInTheDocument();
  });
});

describe("Authentication — Early Release gate: Google path gating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockPolicy(true);
  });

  test("Google button is disabled when code is not yet valid", async () => {
    renderSignup();

    await waitFor(() =>
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument(),
    );

    expect(screen.getByRole("button", { name: /google/i })).toBeDisabled();
    expect(signInWithPopup).not.toHaveBeenCalled();
  });
});

describe("Authentication — Early Release gate: email/password path gating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockPolicy(true);
  });

  test("handleSignUp aborts before calling createUserWithEmailAndPassword when code not valid", async () => {
    const user = userEvent.setup();
    renderSignup();

    await waitFor(() =>
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText(/full name/i), "Test User");
    await user.type(screen.getByLabelText(/^email/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password123");
    await user.type(screen.getByLabelText(/confirm password/i), "password123");
    fireEvent.click(screen.getByRole("checkbox"));

    // Submit button is disabled by requiresAccessCode; try to submit via form directly
    const form = document.querySelector("form");
    if (form) fireEvent.submit(form);

    await waitFor(() =>
      expect(createUserWithEmailAndPassword).not.toHaveBeenCalled(),
    );
  });
});
