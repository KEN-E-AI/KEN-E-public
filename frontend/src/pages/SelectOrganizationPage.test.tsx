import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import SelectOrganizationPage from "./SelectOrganizationPage";

// Mock factories must be declared before vi.mock() hoisting runs.
const mockNavigate = vi.fn();
const mockGetOrganizationsBatch = vi.fn();
const mockGetChildOrganizationsWithAccounts = vi.fn();
const mockAxiosGet = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => mockUseAuth() }));

vi.mock("@/data/organizationApi", () => ({
  getOrganizationsBatch: (...args: unknown[]) =>
    mockGetOrganizationsBatch(...args),
  getChildOrganizationsWithAccounts: (...args: unknown[]) =>
    mockGetChildOrganizationsWithAccounts(...args),
}));

vi.mock("@/lib/api", () => ({
  default: { get: (...args: unknown[]) => mockAxiosGet(...args) },
}));

vi.mock("@/lib/firebase", () => ({
  auth: { currentUser: null },
  authInitialized: true,
  authBypassEnabled: false,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockOrg1 = {
  organization_id: "org-1",
  organization_name: "Acme Corp",
  plan: "Pro",
  agency: false,
  error: false,
  accounts: [
    {
      account_id: "acc-1",
      account_name: "Main Account",
      industry: "Tech",
      status: "Active",
      timezone: "UTC",
    },
  ],
};

const mockOrg2 = {
  organization_id: "org-2",
  organization_name: "Globex Ventures",
  plan: "Starter",
  agency: false,
  error: false,
  accounts: [
    {
      account_id: "acc-2",
      account_name: "Dev Account",
      industry: "Finance",
      status: "Active",
      timezone: "UTC",
    },
  ],
};

const mockAgencyOrg = {
  organization_id: "org-agency",
  organization_name: "Big Agency",
  plan: "Agency",
  agency: true,
  error: false,
  accounts: [],
};

const mockChildOrg = {
  organization_id: "child-1",
  organization_name: "Client Alpha",
  agency: false,
  accounts: [
    {
      account_id: "child-acc-1",
      account_name: "Alpha Account",
      industry: "Retail",
      status: "Active",
      timezone: "UTC",
    },
  ],
};

const makeUserPermissionsResponse = (orgIds: string[]) => ({
  data: {
    data: {
      permissions: {
        organizations: Object.fromEntries(orgIds.map((id) => [id, "admin"])),
      },
    },
  },
});

const makeOrgBatchResponse = (
  orgs: Array<typeof mockOrg1>,
): Record<string, typeof mockOrg1> =>
  Object.fromEntries(orgs.map((o) => [o.organization_id, o]));

const defaultAuthMock = {
  user: { id: "user-1" },
  setSelectedOrgAccount: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  setCurrentOrganization: vi.fn(),
  setOrgMetadata: vi.fn(),
  setAccountMetadata: vi.fn(),
  isSuperAdmin: false,
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: false,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/select-organization"]}>
      <Routes>
        <Route path="/sign-in" element={<div>SIGNIN_SENTINEL</div>} />
        <Route path="/" element={<div>HOME_SENTINEL</div>} />
        <Route
          path="/settings/organization"
          element={<div>SETTINGS_ORG_SENTINEL</div>}
        />
        <Route
          path="/create-organization"
          element={<div>CREATE_ORG_SENTINEL</div>}
        />
        <Route
          path="/select-organization"
          element={<SelectOrganizationPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SelectOrganizationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no child orgs (safe baseline for non-agency tests)
    mockGetChildOrganizationsWithAccounts.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders loading spinner when isAuthLoading is true", () => {
    mockUseAuth.mockReturnValue({ ...defaultAuthMock, isAuthLoading: true });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse([]));
    renderPage();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("redirects to /sign-in when not authenticated", () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      isAuthenticated: false,
      isAuthLoading: false,
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse([]));
    renderPage();
    expect(screen.getByText("SIGNIN_SENTINEL")).toBeInTheDocument();
  });

  it("redirects to / when workspace is already selected", () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      hasSelectedWorkspace: true,
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse([]));
    renderPage();
    expect(screen.getByText("HOME_SENTINEL")).toBeInTheDocument();
  });

  it("continue flow: selects org + account → calls auth setters and navigates to /", async () => {
    const setSelectedOrgAccount = vi.fn();
    const completeWorkspaceSelection = vi.fn();
    const setCurrentOrganization = vi.fn();

    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setSelectedOrgAccount,
      completeWorkspaceSelection,
      setCurrentOrganization,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(
      makeUserPermissionsResponse(["org-1", "org-2"]),
    );
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1, mockOrg2]),
    );

    const user = userEvent.setup();
    renderPage();

    // Wait for org list to populate
    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );

    // Select org
    await user.click(screen.getByRole("button", { name: /acme corp/i }));
    // Wait for accounts to appear
    await waitFor(() =>
      expect(screen.getByText("Main Account")).toBeInTheDocument(),
    );
    // Select account
    await user.click(screen.getByRole("button", { name: /main account/i }));

    // Continue should now be enabled
    const continueBtn = screen.getByRole("button", { name: /^continue/i });
    expect(continueBtn).toBeEnabled();

    // Install fake timers BEFORE firing the click so the internal
    // setTimeout(fn, WORKSPACE_SELECTION_DELAY) is registered against the fake
    // clock.  We use a direct DOM click (not userEvent) here to avoid the async
    // pointer-event machinery that userEvent v14 schedules via its own
    // setTimeout(0) calls — those would also be captured by fake timers and
    // prevent the click from dispatching until we advance the clock.
    vi.useFakeTimers();
    act(() => {
      continueBtn.click();
    });

    // Advance past WORKSPACE_SELECTION_DELAY (1000 ms)
    act(() => vi.advanceTimersByTime(1001));
    vi.useRealTimers();

    expect(setSelectedOrgAccount).toHaveBeenCalledWith(
      expect.objectContaining({
        orgId: "org-1",
        accountId: "acc-1",
      }),
    );
    expect(setCurrentOrganization).toHaveBeenCalledWith("org-1");
    expect(completeWorkspaceSelection).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("gear icon navigates to /settings/organization without selecting the org row", async () => {
    const user = userEvent.setup();
    const setSelectedOrgAccount = vi.fn();
    const completeWorkspaceSelection = vi.fn();
    const setCurrentOrganization = vi.fn();

    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setSelectedOrgAccount,
      completeWorkspaceSelection,
      setCurrentOrganization,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );

    // Click the gear icon — the outer org-row div also has role="button" and
    // its accessible name includes the sr-only "Organization settings" text, so
    // there are two matches.  We want the real <button> element, not the div.
    const gearBtn = screen
      .getAllByRole("button", { name: /organization settings/i })
      .find((el) => el.tagName === "BUTTON")!;
    await user.click(gearBtn);

    expect(setSelectedOrgAccount).toHaveBeenCalledWith(
      expect.objectContaining({ orgId: "org-1" }),
    );
    expect(setCurrentOrganization).toHaveBeenCalledWith("org-1");
    expect(completeWorkspaceSelection).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/settings/organization");
    // The org row should NOT be "pressed" (gear click stops propagation)
    expect(screen.getByRole("button", { name: /acme corp/i })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("create new organization button navigates to /create-organization", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );

    await user.click(
      screen.getByRole("button", { name: /create new organization/i }),
    );
    expect(mockNavigate).toHaveBeenCalledWith("/create-organization");
  });

  it("create new account button calls setCurrentOrganization, completeWorkspaceSelection, and navigates", async () => {
    const user = userEvent.setup();
    const completeWorkspaceSelection = vi.fn();
    const setCurrentOrganization = vi.fn();

    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      completeWorkspaceSelection,
      setCurrentOrganization,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );
    // Select org first (button is disabled without selection)
    await user.click(screen.getByRole("button", { name: /acme corp/i }));

    await user.click(
      screen.getByRole("button", { name: /create new account/i }),
    );
    expect(setCurrentOrganization).toHaveBeenCalledWith("org-1");
    expect(completeWorkspaceSelection).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith(
      "/settings/organization?openCreateAccount=true",
    );
  });

  it("does NOT render search input when org count is ≤5", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    // 2 orgs
    mockAxiosGet.mockResolvedValue(
      makeUserPermissionsResponse(["org-1", "org-2"]),
    );
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1, mockOrg2]),
    );
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );
    expect(
      screen.queryByPlaceholderText(/search organizations/i),
    ).not.toBeInTheDocument();
  });

  it("renders search input when org count is >5", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    const sixOrgs = Array.from({ length: 6 }, (_, i) => ({
      organization_id: `org-${i}`,
      organization_name: `Org ${i}`,
      plan: "Pro",
      agency: false,
      error: false,
      accounts: [],
    }));
    mockAxiosGet.mockResolvedValue(
      makeUserPermissionsResponse(sixOrgs.map((o) => o.organization_id)),
    );
    mockGetOrganizationsBatch.mockResolvedValue(makeOrgBatchResponse(sixOrgs));
    renderPage();
    await waitFor(() => expect(screen.getByText("Org 0")).toBeInTheDocument());
    expect(
      screen.getByPlaceholderText(/search organizations/i),
    ).toBeInTheDocument();
  });

  it("filters org list based on search input", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    const sixOrgs = [
      {
        organization_id: "org-a",
        organization_name: "Alpha Co",
        plan: "Pro",
        agency: false,
        error: false,
        accounts: [],
      },
      {
        organization_id: "org-b",
        organization_name: "Beta Inc",
        plan: "Pro",
        agency: false,
        error: false,
        accounts: [],
      },
      {
        organization_id: "org-c",
        organization_name: "Gamma LLC",
        plan: "Pro",
        agency: false,
        error: false,
        accounts: [],
      },
      {
        organization_id: "org-d",
        organization_name: "Delta Corp",
        plan: "Pro",
        agency: false,
        error: false,
        accounts: [],
      },
      {
        organization_id: "org-e",
        organization_name: "Epsilon Ltd",
        plan: "Pro",
        agency: false,
        error: false,
        accounts: [],
      },
      {
        organization_id: "org-f",
        organization_name: "Zeta Group",
        plan: "Pro",
        agency: false,
        error: false,
        accounts: [],
      },
    ];
    mockAxiosGet.mockResolvedValue(
      makeUserPermissionsResponse(sixOrgs.map((o) => o.organization_id)),
    );
    mockGetOrganizationsBatch.mockResolvedValue(makeOrgBatchResponse(sixOrgs));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Alpha Co")).toBeInTheDocument(),
    );

    const searchInput = screen.getByPlaceholderText(/search organizations/i);
    await user.type(searchInput, "alpha");

    expect(screen.getByText("Alpha Co")).toBeInTheDocument();
    expect(screen.queryByText("Beta Inc")).not.toBeInTheDocument();
    expect(screen.queryByText("Gamma LLC")).not.toBeInTheDocument();

    // Clear search restores all orgs
    await user.clear(searchInput);
    expect(screen.getByText("Alpha Co")).toBeInTheDocument();
    expect(screen.getByText("Beta Inc")).toBeInTheDocument();
  });

  it("renders Error Loading badge on orgs with metadata.error=true but keeps them clickable", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
      setSelectedOrgAccount: vi.fn(),
    });
    const errorOrg = {
      ...mockOrg1,
      organization_id: "org-err",
      organization_name: "Broken Org",
      error: true,
    };
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-err"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([errorOrg]),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Broken Org")).toBeInTheDocument(),
    );
    expect(screen.getByText("Error Loading")).toBeInTheDocument();

    // Still clickable — selecting it should set aria-pressed to true
    const orgRow = screen.getByRole("button", { name: /broken org/i });
    await user.click(orgRow);
    expect(orgRow).toHaveAttribute("aria-pressed", "true");
  });

  it("Continue is disabled initially and enabled after org + account selection", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );

    const continueBtn = screen.getByRole("button", { name: /^continue/i });
    expect(continueBtn).toBeDisabled();

    // Select org only → still disabled
    await user.click(screen.getByRole("button", { name: /acme corp/i }));
    expect(continueBtn).toBeDisabled();

    // Select account → enabled
    await waitFor(() =>
      expect(screen.getByText("Main Account")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /main account/i }));
    expect(continueBtn).toBeEnabled();
  });

  it("does not render BackgroundEffects inside the page", () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse([]));
    renderPage();
    expect(screen.queryAllByTestId("bg-blobs").length).toBe(0);
    expect(screen.queryAllByTestId("bg-static").length).toBe(0);
  });

  it("redirects to /create-organization when non-super-admin has no org permissions", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse([]));

    renderPage();

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/create-organization", {
        replace: true,
      });
    });
  });

  it("does not redirect to /create-organization when non-super-admin has at least one org", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    expect(mockNavigate).not.toHaveBeenCalledWith(
      "/create-organization",
      expect.anything(),
    );
  });

  it("does not redirect to /create-organization for super-admin with empty Firestore permissions", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      isSuperAdmin: true,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse([]));

    renderPage();

    // After loading resolves, super-admin should NOT be redirected
    await waitFor(() => {
      expect(mockNavigate).not.toHaveBeenCalledWith(
        "/create-organization",
        expect.anything(),
      );
    });
  });

  // Regression guard for the original Critical #1: a transient API failure
  // must NOT bounce a multi-org user to /create-organization. The redirect
  // can only fire after a successful fetch confirms the user genuinely has
  // zero orgs.
  it("renders Retry UI and does NOT redirect when user-data fetch rejects", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockRejectedValue(new Error("network failure"));

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("We couldn't load your workspaces. Please try again."),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalledWith(
      "/create-organization",
      expect.anything(),
    );
  });

  it("renders Retry UI and does NOT redirect when user-data response is missing permissions shape", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    // Malformed payload: no `permissions.organizations` field
    mockAxiosGet.mockResolvedValue({ data: { data: {} } });

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /retry/i }),
      ).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalledWith(
      "/create-organization",
      expect.anything(),
    );
  });

  it("clicking Retry re-fires the user-data fetch and recovers on success", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet
      .mockRejectedValueOnce(new Error("first attempt fails"))
      .mockResolvedValueOnce(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /retry/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });
    expect(mockAxiosGet).toHaveBeenCalledTimes(2);
  });

  it("non-agency happy path: org → account → Continue still works unchanged", async () => {
    const setSelectedOrgAccount = vi.fn();
    const completeWorkspaceSelection = vi.fn();
    const setCurrentOrganization = vi.fn();

    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setSelectedOrgAccount,
      completeWorkspaceSelection,
      setCurrentOrganization,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-1"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockOrg1]),
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Acme Corp")).toBeInTheDocument(),
    );

    // Select org (non-agency) — accounts should appear directly
    await user.click(screen.getByRole("button", { name: /acme corp/i }));
    await waitFor(() =>
      expect(screen.getByText("Main Account")).toBeInTheDocument(),
    );

    // Select account → Continue enabled
    await user.click(screen.getByRole("button", { name: /main account/i }));
    const continueBtn = screen.getByRole("button", { name: /^continue/i });
    expect(continueBtn).toBeEnabled();

    // getChildOrganizationsWithAccounts must NOT have been called for non-agency org
    expect(mockGetChildOrganizationsWithAccounts).not.toHaveBeenCalled();
  });

  it("agency happy path: drill-down through child org → account → Continue", async () => {
    const setSelectedOrgAccount = vi.fn();
    const completeWorkspaceSelection = vi.fn();
    const setCurrentOrganization = vi.fn();

    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setSelectedOrgAccount,
      completeWorkspaceSelection,
      setCurrentOrganization,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-agency"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockAgencyOrg]),
    );
    mockGetChildOrganizationsWithAccounts.mockResolvedValue([mockChildOrg]);

    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Big Agency")).toBeInTheDocument(),
    );

    // Select agency org → child orgs should load
    await user.click(screen.getByRole("button", { name: /big agency/i }));

    // Agency hint banner and Client Organizations section should appear
    await waitFor(() =>
      expect(
        screen.getByText(
          /agency organizations cannot create their own accounts/i,
        ),
      ).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByText("Client Alpha")).toBeInTheDocument(),
    );

    // Continue is still disabled (no child org or account selected)
    expect(screen.getByRole("button", { name: /^continue/i })).toBeDisabled();

    // Select child org → accounts should appear
    await user.click(screen.getByRole("button", { name: /client alpha/i }));
    await waitFor(() =>
      expect(screen.getByText("Alpha Account")).toBeInTheDocument(),
    );

    // Continue is still disabled (account not selected yet)
    expect(screen.getByRole("button", { name: /^continue/i })).toBeDisabled();

    // Select account → Continue enabled
    await user.click(screen.getByRole("button", { name: /alpha account/i }));
    expect(screen.getByRole("button", { name: /^continue/i })).toBeEnabled();

    // Click Continue and verify it resolves with the child org ID
    vi.useFakeTimers();
    act(() => {
      screen.getByRole("button", { name: /^continue/i }).click();
    });
    act(() => vi.advanceTimersByTime(1001));
    vi.useRealTimers();

    expect(setSelectedOrgAccount).toHaveBeenCalledWith(
      expect.objectContaining({
        orgId: "child-1",
        accountId: "child-acc-1",
      }),
    );
    expect(completeWorkspaceSelection).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("agency Continue gating: disabled without child-org, disabled without account, enabled with full triple", async () => {
    mockUseAuth.mockReturnValue({
      ...defaultAuthMock,
      setOrgMetadata: vi.fn(),
      setAccountMetadata: vi.fn(),
    });
    mockAxiosGet.mockResolvedValue(makeUserPermissionsResponse(["org-agency"]));
    mockGetOrganizationsBatch.mockResolvedValue(
      makeOrgBatchResponse([mockAgencyOrg]),
    );
    mockGetChildOrganizationsWithAccounts.mockResolvedValue([mockChildOrg]);

    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Big Agency")).toBeInTheDocument(),
    );

    const continueBtn = screen.getByRole("button", { name: /^continue/i });

    // No org selected yet → disabled
    expect(continueBtn).toBeDisabled();

    // Agency org selected, no child org → still disabled
    await user.click(screen.getByRole("button", { name: /big agency/i }));
    await waitFor(() =>
      expect(screen.getByText("Client Alpha")).toBeInTheDocument(),
    );
    expect(continueBtn).toBeDisabled();

    // Child org selected, no account → still disabled
    await user.click(screen.getByRole("button", { name: /client alpha/i }));
    await waitFor(() =>
      expect(screen.getByText("Alpha Account")).toBeInTheDocument(),
    );
    expect(continueBtn).toBeDisabled();

    // Account selected → enabled
    await user.click(screen.getByRole("button", { name: /alpha account/i }));
    expect(continueBtn).toBeEnabled();
  });
});
