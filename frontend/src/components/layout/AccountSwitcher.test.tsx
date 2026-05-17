import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { AccountSwitcher } from "./AccountSwitcher";
import { AuthContext } from "@/contexts/AuthContext";
import { useWorkspaceOptions } from "@/hooks/useWorkspaceOptions";
import type { AccountId, OrganizationId } from "@/lib/branded-types";

// The switcher fetches live workspace data via this hook; default it to
// "not yet resolved" so most tests exercise the context-snapshot fallback.
vi.mock("@/hooks/useWorkspaceOptions", () => ({
  useWorkspaceOptions: vi.fn(() => ({ data: undefined })),
}));

const mockUseWorkspaceOptions = useWorkspaceOptions as ReturnType<typeof vi.fn>;

const mockAuthContext = {
  user: {
    id: "user-1" as any,
    email: "test@test.com",
    firstName: "Test",
    lastName: "User",
  },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  currentOrganizationId: "org-1" as any,
  selectedOrgAccount: {
    orgId: "org-1" as any,
    accountId: "acct-1" as any,
    metadata: {
      organization_name: "Acme Corp",
      account_name: "Main Account",
      industry: "Tech",
      status: "active",
    },
  },
  orgMetadata: {
    "org-1": { organization_name: "Acme Corp", plan: "pro" },
  },
  accountMetadata: {
    "acct-1": {
      account_name: "Main Account",
      industry: "Tech",
      status: "active",
      organization_id: "org-1",
    },
    "acct-2": {
      account_name: "Secondary Account",
      industry: "Tech",
      status: "active",
      organization_id: "org-1",
    },
  },
  setSelectedOrgAccount: vi.fn(),
  setCurrentOrganization: vi.fn(),
  notifications: [],
  logout: vi.fn(),
  login: vi.fn(),
  updateUser: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  resetWorkspaceSelection: vi.fn(),
  setOrgMetadata: vi.fn(),
  setAccountMetadata: vi.fn(),
  setNotifications: vi.fn(),
  refreshNotifications: vi.fn(),
  notificationSettings: [],
  securitySettings: [],
  setNotificationSettings: vi.fn(),
  setSecuritySettings: vi.fn(),
  isSuperAdmin: false,
};

const renderWithProviders = (contextOverrides = {}) => {
  const contextValue = { ...mockAuthContext, ...contextOverrides };
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue as any}>
        <AccountSwitcher />
      </AuthContext.Provider>
    </BrowserRouter>,
  );
};

describe("AccountSwitcher", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWorkspaceOptions.mockReturnValue({ data: undefined });
  });

  test("renders trigger with org/account name when selectedOrgAccount is non-null", () => {
    renderWithProviders();

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Main Account")).toBeInTheDocument();
  });

  test("renders 'Select account' when selectedOrgAccount is null", () => {
    renderWithProviders({ selectedOrgAccount: null });

    expect(screen.getByText("Select account")).toBeInTheDocument();
  });

  test("calls setSelectedOrgAccount and setCurrentOrganization on selection", async () => {
    const user = userEvent.setup();
    const setSelectedOrgAccount = vi.fn();
    const setCurrentOrganization = vi.fn();

    renderWithProviders({ setSelectedOrgAccount, setCurrentOrganization });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    const secondAccount = await screen.findByText("Secondary Account");
    await user.click(secondAccount);

    expect(setSelectedOrgAccount).toHaveBeenCalledTimes(1);
    expect(setSelectedOrgAccount).toHaveBeenCalledWith(
      expect.objectContaining({
        orgId: "org-1" as OrganizationId,
        accountId: "acct-2" as AccountId,
        metadata: expect.objectContaining({
          account_name: "Secondary Account",
        }),
      }),
    );
    expect(setCurrentOrganization).toHaveBeenCalledTimes(1);
    expect(setCurrentOrganization).toHaveBeenCalledWith(
      "org-1" as OrganizationId,
    );
  });

  test("active account row has Check icon", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await screen.findByText("Secondary Account");

    const checkIcons = document.querySelectorAll("svg.lucide-check");
    expect(checkIcons.length).toBeGreaterThan(0);
  });

  test("renders orgs/accounts from useWorkspaceOptions, not the stale context snapshot", async () => {
    // Context holds only a single stale org; the live fetch resolves the full
    // accessible set (the super-admin case from the bug report).
    mockUseWorkspaceOptions.mockReturnValue({
      data: {
        orgMetadata: {
          "org-1": { organization_name: "Acme Corp", plan: "pro" },
          "org-2": { organization_name: "Globex Inc", plan: "pro" },
        },
        accountMetadata: {
          "acct-1": {
            account_name: "Main Account",
            industry: "Tech",
            organization_id: "org-1",
          },
          "acct-9": {
            account_name: "Globex Account",
            industry: "Energy",
            organization_id: "org-2",
          },
        },
      },
    });

    const user = userEvent.setup();
    renderWithProviders();

    await user.click(screen.getByRole("button"));

    // org-2 / acct-9 exist only in the fetched data, never in context.
    expect(await screen.findByText("Globex Inc")).toBeInTheDocument();
    expect(screen.getByText("Globex Account")).toBeInTheDocument();
  });

  test("renders a 'Switch workspace' link to the workspace picker", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(screen.getByRole("button"));

    // DropdownMenuItem `asChild` applies role="menuitem" onto the <Link>.
    const link = await screen.findByRole("menuitem", {
      name: /switch workspace/i,
    });
    expect(link).toHaveAttribute("href", "/select-organization?switch=true");
  });

  test("syncs fetched workspace data back into AuthContext", () => {
    const setOrgMetadata = vi.fn();
    const setAccountMetadata = vi.fn();
    const data = {
      orgMetadata: { "org-1": { organization_name: "Acme Corp" } },
      accountMetadata: {
        "acct-1": { account_name: "Main Account", organization_id: "org-1" },
      },
    };
    mockUseWorkspaceOptions.mockReturnValue({ data });

    renderWithProviders({ setOrgMetadata, setAccountMetadata });

    expect(setOrgMetadata).toHaveBeenCalledWith(data.orgMetadata);
    expect(setAccountMetadata).toHaveBeenCalledWith(data.accountMetadata);
  });
});
