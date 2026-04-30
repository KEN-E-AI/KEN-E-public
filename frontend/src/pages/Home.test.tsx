import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthContext } from "@/contexts/AuthContext";
import type {
  AuthContextType,
  SelectedOrgAccount,
} from "@/contexts/AuthContext";
import type { OrganizationId, AccountId, UserId } from "@/lib/branded-types";
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
  const ctx: Partial<AuthContextType> = {
    selectedOrgAccount,
    user: {
      id: "test-user" as UserId,
      email: "test@example.com",
      firstName: "Test",
      lastName: "User",
    },
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
  };
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={ctx as AuthContextType}>
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
  // If HomeLayout is reintroduced into Home's render tree, those components
  // will render with their data-testid attributes and these assertions will fail.
  test("does not render legacy chrome (IconNavigation, ContextSidebar)", () => {
    renderHome();
    expect(screen.queryByTestId("icon-navigation")).not.toBeInTheDocument();
    expect(screen.queryByTestId("context-sidebar")).not.toBeInTheDocument();
  });
});
