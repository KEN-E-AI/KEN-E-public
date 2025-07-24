import { describe, test, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useSettingsContext } from "./useSettingsContext";

// Mock the AuthContext
let mockAuthContext = {
  user: {
    id: "user-1",
    firstName: "John",
    lastName: "Doe",
    email: "john.doe@example.com",
    permissions: {
      organizations: {
        "org-1": "admin",
        "org-2": "user",
      },
    },
  },
  selectedOrgAccount: {
    orgId: "org-1",
    accountId: "account-1",
    metadata: {
      organization_name: "Test Organization",
      account_name: "Test Account",
    },
  },
  currentOrganizationId: "org-1",
  orgMetadata: {
    "org-1": {
      organization_name: "Test Organization",
      plan: "Pro",
    },
  },
  accountMetadata: {
    "account-1": {
      account_name: "Test Account",
      industry: "Technology",
    },
  },
  hasSelectedWorkspace: true,
  isAuthenticated: true,
};

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => mockAuthContext,
}));

describe("useSettingsContext", () => {
  test("returns correct organization context", () => {
    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.currentOrganization).toEqual({
      id: "org-1",
      name: "Test Organization",
      metadata: {
        organization_name: "Test Organization",
        plan: "Pro",
      },
    });
  });

  test("returns correct account context", () => {
    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.currentAccount).toEqual({
      id: "account-1",
      name: "Test Account",
      metadata: {
        account_name: "Test Account",
        industry: "Technology",
      },
    });
  });

  test("returns correct user context", () => {
    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.currentUser).toEqual({
      id: "user-1",
      name: "John Doe",
      firstName: "John",
      lastName: "Doe",
      email: "john.doe@example.com",
    });
  });

  test("returns correct permissions for admin user", () => {
    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.permissions).toEqual({
      canManageOrganization: true,
      canManageAccounts: true,
      canManageUsers: true,
      organizationRole: "admin",
    });
  });

  test("returns correct permissions for regular user", () => {
    // Update the mock to use org-2 where user has "user" role
    mockAuthContext = {
      ...mockAuthContext,
      selectedOrgAccount: {
        ...mockAuthContext.selectedOrgAccount,
        orgId: "org-2",
      },
      currentOrganizationId: "org-2",
    };

    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.permissions).toEqual({
      canManageOrganization: false,
      canManageAccounts: false,
      canManageUsers: false,
      organizationRole: "user",
    });

    // Reset mock for other tests
    mockAuthContext.currentOrganizationId = "org-1";
    mockAuthContext.selectedOrgAccount.orgId = "org-1";
  });

  test("returns correct authentication status", () => {
    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.hasSelectedWorkspace).toBe(true);
    expect(result.current.isAuthenticated).toBe(true);
  });

  test("handles null user gracefully", () => {
    // Save original mock
    const originalMock = { ...mockAuthContext };

    // Update mock to null user
    mockAuthContext = {
      ...mockAuthContext,
      user: null,
      selectedOrgAccount: null,
      currentOrganizationId: null,
      hasSelectedWorkspace: false,
      isAuthenticated: false,
    };

    const { result } = renderHook(() => useSettingsContext());

    expect(result.current.currentUser).toEqual({
      id: null,
      name: "User",
      firstName: "",
      lastName: "",
      email: "",
    });

    expect(result.current.permissions).toEqual({
      canManageOrganization: false,
      canManageAccounts: false,
      canManageUsers: false,
      organizationRole: null,
    });

    // Restore original mock
    mockAuthContext = originalMock;
  });
});
