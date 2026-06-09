import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { CreateOrganization } from "./CreateOrganization";
import { EARLY_RELEASE_CODE_STORAGE_KEY } from "@/data/earlyReleaseApi";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

const mockCreateOrganization = vi.fn();
vi.mock("@/data/organizationApi", () => ({
  createOrganization: (...args: unknown[]) => mockCreateOrganization(...args),
}));

vi.mock("@/data/subscriptionPlansApi", () => ({
  getDefaultPlan: vi.fn().mockResolvedValue({
    plan_name: "Free Plan",
    plan_description: "Basic features for getting started",
    price: 0,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      features: ["Basic Reports", "1 User"],
      max_reports: 10,
      max_users: 1,
    },
  }),
}));

// Mock api client for Firestore permission write
vi.mock("@/lib/api", () => ({
  default: { put: vi.fn().mockResolvedValue({ data: {} }) },
}));

// Mock branding components
vi.mock("@/components/branding/Logo", () => ({
  Logo: () => <div data-testid="logo">Logo</div>,
}));

const mockCompleteWorkspaceSelection = vi.fn();
const mockSetCurrentOrganization = vi.fn();
const mockSetSelectedOrgAccount = vi.fn();
const mockUpdateUser = vi.fn();
const mockSetOrgMetadata = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "user-123",
      uid: "user-123",
      permissions: { organizations: {} },
    },
    updateUser: mockUpdateUser,
    completeWorkspaceSelection: mockCompleteWorkspaceSelection,
    setCurrentOrganization: mockSetCurrentOrganization,
    setSelectedOrgAccount: mockSetSelectedOrgAccount,
    orgMetadata: {},
    setOrgMetadata: mockSetOrgMetadata,
  }),
}));

function renderPage() {
  return render(
    <BrowserRouter>
      <CreateOrganization />
    </BrowserRouter>,
  );
}

describe("CreateOrganization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  test("renders form with organization name field and submit button", () => {
    renderPage();
    expect(
      screen.getByRole("textbox", { name: /organization name/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create organization/i }),
    ).toBeInTheDocument();
  });

  test("shows agency toggle that reveals child org field when enabled", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(
      screen.queryByLabelText(/child organizations/i),
    ).not.toBeInTheDocument();

    const agencyToggle = screen.getByRole("switch", {
      name: /this is an agency/i,
    });
    await user.click(agencyToggle);

    expect(screen.getByLabelText(/child organizations/i)).toBeInTheDocument();
  });

  test("shows validation toast when submitting without organization name", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Missing required fields",
          variant: "destructive",
        }),
      );
    });
    expect(mockCreateOrganization).not.toHaveBeenCalled();
  });

  test("success path: calls createOrganization and navigates to settings", async () => {
    const newOrg = {
      organization_id: "org-new-123",
      organization_name: "Acme Corp",
      plan: "Free Plan",
      accounts: [],
    };
    mockCreateOrganization.mockResolvedValue(newOrg);

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockCreateOrganization).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(mockCompleteWorkspaceSelection).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/settings/organization");
    });

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Organization created successfully!",
      }),
    );
  });
});

describe("Early Release code forwarding", () => {
  const newOrg = {
    organization_id: "org-new-123",
    organization_name: "Acme Corp",
    plan: "Free Plan",
    accounts: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  test("forwards the stashed access_code in the org-create payload", async () => {
    sessionStorage.setItem(EARLY_RELEASE_CODE_STORAGE_KEY, "code-123");
    mockCreateOrganization.mockResolvedValue(newOrg);

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockCreateOrganization).toHaveBeenCalledWith(
        expect.objectContaining({ access_code: "code-123" }),
      );
    });
  });

  test("omits access_code entirely when no code is stashed", async () => {
    // No sessionStorage.setItem — ordinary (non-Early-Release) signup. The
    // field must be absent, not access_code: null, so the server gate is only
    // exercised for code-bearing users. Guards the High review finding.
    mockCreateOrganization.mockResolvedValue(newOrg);

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockCreateOrganization).toHaveBeenCalled();
    });

    expect(mockCreateOrganization.mock.calls[0][0]).not.toHaveProperty(
      "access_code",
    );
  });

  test("clears the stashed code after a successful create", async () => {
    sessionStorage.setItem(EARLY_RELEASE_CODE_STORAGE_KEY, "code-123");
    mockCreateOrganization.mockResolvedValue(newOrg);

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockCompleteWorkspaceSelection).toHaveBeenCalled();
    });

    expect(sessionStorage.getItem(EARLY_RELEASE_CODE_STORAGE_KEY)).toBeNull();
  });

  test("renders the friendly Early Access Required banner on 403 early_access_required", async () => {
    sessionStorage.setItem(EARLY_RELEASE_CODE_STORAGE_KEY, "expired-code");
    mockCreateOrganization.mockRejectedValue(
      new Error("early_access_required"),
    );

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("early-access-banner")).toBeInTheDocument();
    });

    expect(mockToast).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
    // Stash IS cleared on 403 — the banner offers no retry path and clearing
    // prevents the dead code from bleeding to a different user in the same tab.
    expect(sessionStorage.getItem(EARLY_RELEASE_CODE_STORAGE_KEY)).toBeNull();
  });

  test("survives the SelectOrganizationPage redirect hop: code stashed by signup reaches the payload", async () => {
    // Pre-seed sessionStorage exactly as Authentication.tsx would after
    // validateAccessCode returns { valid: true } (UI-60 contract).
    sessionStorage.setItem(EARLY_RELEASE_CODE_STORAGE_KEY, "hop-code-abc");
    mockCreateOrganization.mockResolvedValue(newOrg);

    const user = userEvent.setup();
    // Mount CreateOrganization directly — same as when SelectOrganizationPage
    // does navigate("/create-organization", { replace: true }), which keeps
    // sessionStorage intact because it is an in-tab navigation.
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: /organization name/i }),
      "Acme Corp",
    );
    await user.click(
      screen.getByRole("button", { name: /create organization/i }),
    );

    await waitFor(() => {
      expect(mockCreateOrganization).toHaveBeenCalledWith(
        expect.objectContaining({ access_code: "hop-code-abc" }),
      );
    });
  });
});

// Layout mirrors the SignInPage centered-card shell (no dedicated figma-export page).
describe("CreateOrganization — Responsive class structure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  test("outer wrapper carries min-h-screen flex items-center justify-center p-4", () => {
    const { container } = renderPage();
    const outer = container.firstElementChild;
    expect(outer).toHaveClass("min-h-screen");
    expect(outer).toHaveClass("flex");
    expect(outer).toHaveClass("items-center");
    expect(outer).toHaveClass("justify-center");
    expect(outer).toHaveClass("p-4");
  });

  test("inner container carries w-full max-w-md", () => {
    const { container } = renderPage();
    const inner = container.querySelector(".max-w-md");
    expect(inner).toBeInTheDocument();
    expect(inner).toHaveClass("w-full");
  });

  test("background gradient uses -50 shade tokens matching sign-in shell pattern", () => {
    const { container } = renderPage();
    const outer = container.firstElementChild;
    // className.toContain (not toHaveClass) because toHaveClass cannot match
    // arbitrary-value Tailwind tokens that contain square brackets.
    expect(outer?.className).toContain("from-[var(--color-violet-50)]");
    expect(outer?.className).toContain("via-[var(--color-bg-default)]");
    expect(outer?.className).toContain("to-[var(--color-blue-50)]");
  });
});
