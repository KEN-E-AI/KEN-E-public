/**
 * Dark-mode parity — UI-31
 *
 * Renders every redesigned UI-PRD-02 page under both light and dark themes and
 * asserts zero axe violations. Each describe block covers one page; `it.each`
 * runs the same assertion twice (light / dark).
 *
 * Contrast is intentionally excluded from axe (JSDOM has no layout engine).
 * Token-pair contrast is verified deterministically in token-contrast.test.ts.
 *
 * The `.dark` class is applied / removed on document.documentElement directly,
 * mirroring the mechanism used by ThemeProvider in production.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { runAxe } from "./axe";
import { useAuth } from "@/contexts/AuthContext";

import Authentication from "@/pages/Authentication";
import AcceptInvitation from "@/pages/AcceptInvitation";
import AccountSettings from "@/pages/AccountSettings";
import UserSettings from "@/pages/UserSettings";
import { CreateOrganization } from "@/pages/CreateOrganization";
import EmailActionHandler from "@/components/auth/EmailActionHandler";

// ── Module-level mocks ──────────────────────────────────────────────────────

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
  AuthContext: {
    Provider: ({ children }: { children: ReactNode }) => <>{children}</>,
  },
}));

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
  applyActionCode: vi.fn().mockResolvedValue(undefined),
  checkActionCode: vi
    .fn()
    .mockResolvedValue({ data: { email: "test@example.com" } }),
  getAuth: vi.fn(() => ({})),
}));

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock("axios", () => {
  const inst = {
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  };
  return { default: { ...inst, create: vi.fn(() => inst) } };
});

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("@/components/auth/ReCaptchaProvider", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaWrapper", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/ReCaptchaV3", () => ({
  default: ({ onVerify }: { onVerify: (v: boolean) => void }) => {
    setTimeout(() => onVerify(true), 0);
    return null;
  },
}));

vi.mock("@/components/auth/ReCaptchaErrorBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/data/teamApi", () => ({
  verifyInvitationToken: vi
    .fn()
    .mockRejectedValue({ response: { status: 404 } }),
  acceptInvitation: vi.fn().mockResolvedValue({}),
}));

vi.mock("@/data/organizationApi", () => ({
  createOrganization: vi.fn().mockResolvedValue({ id: "org-1" }),
  updateOrganization: vi.fn().mockResolvedValue({}),
  getOrganizationsBatch: vi.fn().mockResolvedValue({}),
  getOrganizations: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/data/subscriptionPlansApi", () => ({
  getDefaultPlan: vi.fn().mockResolvedValue({
    plan_name: "Free Plan",
    price: 0,
    currency: "USD",
    billing_cycle: "monthly",
    features: { features: [], max_reports: 10, max_users: 1 },
  }),
}));

vi.mock("@/components/branding/Logo", () => ({
  Logo: () => <div role="img" aria-label="KEN-E logo" />,
}));

vi.mock("@/components/notifications/NotificationSidebar", () => ({
  NotificationSidebar: () => null,
}));

vi.mock("@/components/notifications/NotificationPreferences", () => ({
  NotificationPreferences: ({ onSave }: { onSave: () => void }) => (
    <div>
      <button onClick={onSave}>Save preferences</button>
    </div>
  ),
}));

// AccountSettings child component mocks — paths are relative to AccountSettings.tsx
// so from test file they resolve via the @/ alias prefix.
vi.mock("@/components/layout/SettingsLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/integrations/GoogleAnalyticsPropertySelector", () => ({
  GoogleAnalyticsPropertySelector: () => (
    <div aria-label="Google Analytics property selector" />
  ),
}));

vi.mock("@/pages/components/OrganizationForm", () => ({
  default: () => <div data-testid="org-form" />,
}));

vi.mock("@/pages/components/SubscriptionCard", () => ({
  default: () => <div data-testid="subscription-card" />,
}));

vi.mock("@/pages/components/AccountsManagement", () => ({
  default: () => <div data-testid="accounts-management" />,
}));

vi.mock("@/pages/components/BillingSection", () => ({
  default: () => <div data-testid="billing-section" />,
}));

vi.mock("@/pages/components/TeamManagement", () => ({
  default: () => <div data-testid="team-management" />,
}));

vi.mock("@/pages/components/DangerZone", () => ({
  default: () => <div data-testid="danger-zone" />,
}));

// ── Shared test state ───────────────────────────────────────────────────────

const themes = [
  { theme: "light", isDark: false },
  { theme: "dark", isDark: true },
] as const;

const baseAuthValue = {
  user: {
    id: "user-1",
    email: "test@example.com",
    firstName: "Test",
    lastName: "User",
    permissions: {
      organizations: { "org-1": "admin" },
    },
  },
  login: vi.fn(),
  logout: vi.fn(),
  signOut: vi.fn(),
  updateUser: vi.fn(),
  setNotificationSettings: vi.fn(),
  setSecuritySettings: vi.fn(),
  selectedOrganization: {
    organization_id: "org-1",
    organization_name: "Acme Corp",
  },
  setSelectedOrganization: vi.fn(),
  selectedAccount: { accountId: "acct-1", accountName: "Main Account" },
  setSelectedAccount: vi.fn(),
  selectedOrgAccount: { accountId: "acct-1" },
  notifications: [],
  isAuthenticated: true,
  completeWorkspaceSelection: vi.fn(),
  currentOrganizationId: "org-1",
  setCurrentOrganization: vi.fn(),
  setSelectedOrgAccount: vi.fn(),
  orgMetadata: {},
  setOrgMetadata: vi.fn(),
  setAccountMetadata: vi.fn(),
  isSuperAdmin: false,
} as const;

/** Apply or remove `.dark` class before running axe under a given theme. */
function applyTheme(isDark: boolean) {
  if (isDark) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

// Remove `.dark` after every test to prevent cross-test bleed.
afterEach(() => {
  document.documentElement.classList.remove("dark");
  vi.clearAllMocks();
});

// ── Authentication — sign-in view ───────────────────────────────────────────

describe("dark-mode parity — Authentication (sign-in)", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(
      baseAuthValue as ReturnType<typeof useAuth>,
    );
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/sign-in"]}>
            <Authentication onAuthenticated={vi.fn()} />
          </MemoryRouter>
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── Authentication — sign-up view ───────────────────────────────────────────

describe("dark-mode parity — Authentication (sign-up)", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(
      baseAuthValue as ReturnType<typeof useAuth>,
    );
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/sign-up"]}>
            <Authentication onAuthenticated={vi.fn()} />
          </MemoryRouter>
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── Authentication — email-verification view ─────────────────────────────────

describe("dark-mode parity — Authentication (email-verification)", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(
      baseAuthValue as ReturnType<typeof useAuth>,
    );
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/verify-email"]}>
            <Authentication onAuthenticated={vi.fn()} />
          </MemoryRouter>
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── EmailActionHandler — unsupported-mode / error state ─────────────────────
// EmailActionHandler only handles verifyEmail; any other mode sets error state
// immediately and renders the "Verification Failed" error card.

describe("dark-mode parity — EmailActionHandler (error state)", () => {
  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter
            initialEntries={[
              "/auth/action?mode=resetPassword&oobCode=test-code",
            ]}
          >
            <Routes>
              <Route path="/auth/action" element={<EmailActionHandler />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>,
      );
      // Flush the async mount effects so the component settles before axe.
      await new Promise((r) => setTimeout(r, 0));
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── EmailActionHandler — verifyEmail view ───────────────────────────────────

describe("dark-mode parity — EmailActionHandler (verifyEmail)", () => {
  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter
            initialEntries={["/auth/action?mode=verifyEmail&oobCode=test-code"]}
          >
            <Routes>
              <Route path="/auth/action" element={<EmailActionHandler />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>,
      );
      await new Promise((r) => setTimeout(r, 0));
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── AcceptInvitation ─────────────────────────────────────────────────────────

describe("dark-mode parity — AcceptInvitation", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: baseAuthValue.user,
      logout: vi.fn(),
    } as ReturnType<typeof useAuth>);
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/invite/test-token-123"]}>
            <Routes>
              <Route path="/invite/:token" element={<AcceptInvitation />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>,
      );
      await new Promise((r) => setTimeout(r, 0));
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── AccountSettings (/settings/organization) ─────────────────────────────────

describe("dark-mode parity — AccountSettings", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue(
      baseAuthValue as ReturnType<typeof useAuth>,
    );
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/settings/organization"]}>
            <AccountSettings />
          </MemoryRouter>
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── UserSettings (/settings/user) ────────────────────────────────────────────

describe("dark-mode parity — UserSettings", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: baseAuthValue.user,
      updateUser: vi.fn(),
    } as ReturnType<typeof useAuth>);
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/settings/user"]}>
            <UserSettings />
          </MemoryRouter>
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});

// ── CreateOrganization (/create-organization) ─────────────────────────────────

describe("dark-mode parity — CreateOrganization", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: baseAuthValue.user,
      updateUser: vi.fn(),
      completeWorkspaceSelection: vi.fn(),
      setCurrentOrganization: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
      orgMetadata: {},
      setOrgMetadata: vi.fn(),
    } as ReturnType<typeof useAuth>);
  });

  it.each(themes)(
    "has no axe violations in $theme mode",
    async ({ isDark }) => {
      applyTheme(isDark);
      const { container } = render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/create-organization"]}>
            <CreateOrganization />
          </MemoryRouter>
        </ThemeProvider>,
      );
      expect(await runAxe(container)).toHaveNoViolations();
    },
  );
});
