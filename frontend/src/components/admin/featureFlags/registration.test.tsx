import { describe, test, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import type { ReactNode } from "react";
import "./registration";
import { ProfileMenu } from "@/components/layout/ProfileMenu";
import { AuthContext } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import {
  resetSuperAdminNavForTesting,
  registerSuperAdminNavRow,
} from "@/components/layout/super-admin-nav-registry";
import type { NavRowId } from "@/components/layout/super-admin-nav-registry";

const mockContext = {
  user: {
    id: "u1" as never,
    email: "admin@ken-e.ai",
    firstName: "Admin",
    lastName: "User",
  },
  isAuthenticated: true,
  isAuthLoading: false,
  hasSelectedWorkspace: true,
  currentOrganizationId: null,
  selectedOrgAccount: null,
  notifications: [],
  orgMetadata: {},
  accountMetadata: {},
  logout: () => {},
  login: () => {},
  updateUser: () => {},
  completeWorkspaceSelection: () => {},
  resetWorkspaceSelection: () => {},
  setCurrentOrganization: () => {},
  setSelectedOrgAccount: () => {},
  setOrgMetadata: () => {},
  setAccountMetadata: () => {},
  setNotifications: () => {},
  refreshNotifications: () => {},
  notificationSettings: [],
  securitySettings: [],
  setNotificationSettings: () => {},
  setSecuritySettings: () => {},
  isSuperAdmin: false,
  isSuperAdminLoading: false,
};

function Providers({
  children,
  contextOverrides,
}: {
  children: ReactNode;
  contextOverrides: Partial<typeof mockContext>;
}) {
  const contextValue = { ...mockContext, ...contextOverrides };
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthContext.Provider value={contextValue as never}>
          {children}
        </AuthContext.Provider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

async function openMenu() {
  const user = userEvent.setup();
  const trigger = screen.getByRole("button", { name: /profile menu for/i });
  await user.click(trigger);
  return user;
}

describe("feature-flags registration", () => {
  beforeEach(() => {
    resetSuperAdminNavForTesting();
    // Static module imports are cached, so the registration.ts side effect only fires
    // once. Re-register manually here with the same values so each test starts with
    // the expected registry state after the reset.
    registerSuperAdminNavRow({
      id: "feature-flags" as NavRowId,
      label: "Feature Flags",
      path: "/admin/feature-flags",
      order: 20,
    });
  });

  test("AC-8: admin section is absent from the DOM when isSuperAdmin is false", async () => {
    render(
      <Providers contextOverrides={{ isSuperAdmin: false }}>
        <ProfileMenu />
      </Providers>,
    );
    await openMenu();

    expect(
      screen.queryByRole("menuitem", { name: /feature flags/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/^admin$/i)).not.toBeInTheDocument();
  });

  test("Feature Flags link renders with correct href when isSuperAdmin is true", async () => {
    render(
      <Providers contextOverrides={{ isSuperAdmin: true }}>
        <ProfileMenu />
      </Providers>,
    );
    await openMenu();

    const ffItem = await screen.findByRole("menuitem", {
      name: /feature flags/i,
    });
    expect(ffItem).toHaveAttribute("href", "/admin/feature-flags");
    expect(screen.getByText(/^admin$/i)).toBeInTheDocument();
  });
});
