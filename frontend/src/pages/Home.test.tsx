import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthContext } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import type { OrganizationId, AccountId } from "@/lib/branded-types";
import Home from "./Home";

vi.mock("@/components/home/HomeChatArea", () => ({
  default: () => <div data-testid="home-chat-area">Chat Area</div>,
}));

const mockOrgAccount: SelectedOrgAccount = {
  orgId: "org-1" as OrganizationId,
  accountId: "acc-1" as AccountId,
  metadata: {
    organization_name: "Test Org",
    account_name: "Test Account",
    industry: "Technology",
    status: "active",
  },
};

function renderHome(
  selectedOrgAccount: SelectedOrgAccount | null = mockOrgAccount,
) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider
        value={
          {
            selectedOrgAccount,
            user: null,
            isAuthenticated: true,
            isAuthLoading: false,
            hasSelectedWorkspace: true,
            currentOrganizationId: null,
            login: vi.fn(),
            logout: vi.fn(),
            updateUser: vi.fn(),
            completeWorkspaceSelection: vi.fn(),
            resetWorkspaceSelection: vi.fn(),
            setCurrentOrganization: vi.fn(),
            setSelectedOrgAccount: vi.fn(),
            orgMetadata: {},
            accountMetadata: {},
            setOrgMetadata: vi.fn(),
            setAccountMetadata: vi.fn(),
            notifications: [],
            setNotifications: vi.fn(),
            refreshNotifications: vi.fn(),
            notificationSettings: [],
            securitySettings: [],
            setNotificationSettings: vi.fn(),
            setSecuritySettings: vi.fn(),
            isSuperAdmin: false,
          } as any
        }
      >
        <Home />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("Home", () => {
  test("renders HomeChatArea directly without legacy chrome", () => {
    renderHome();
    expect(screen.getByTestId("home-chat-area")).toBeInTheDocument();
  });

  // Regression guard: Home must NOT render IconNavigation or ContextSidebar.
  // This test failed before Home.tsx was migrated off HomeLayout.
  // If HomeLayout is reintroduced into Home's render tree, these assertions will fail.
  test("does not render legacy chrome (IconNavigation, ContextSidebar)", () => {
    renderHome();
    expect(
      document.querySelector('[data-testid="icon-navigation"]'),
    ).not.toBeInTheDocument();
    expect(
      document.querySelector('[data-testid="context-sidebar"]'),
    ).not.toBeInTheDocument();
  });
});
