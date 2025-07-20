import { useMemo } from "react";
import { useAuth } from "@/contexts/AuthContext";

export interface SettingsContextData {
  // Organization context
  currentOrganization: {
    id: string | null;
    name: string;
    metadata: Record<string, any> | null;
  };

  // Account context
  currentAccount: {
    id: string | null;
    name: string;
    metadata: Record<string, any> | null;
  };

  // User context
  currentUser: {
    id: string | null;
    name: string;
    firstName: string;
    lastName: string;
    email: string;
  };

  // Permissions
  permissions: {
    canManageOrganization: boolean;
    canManageAccounts: boolean;
    canManageUsers: boolean;
    organizationRole: string | null;
  };

  // Status
  hasSelectedWorkspace: boolean;
  isAuthenticated: boolean;
}

/**
 * Custom hook for accessing settings-specific context data
 * Provides a clean interface for settings components to access
 * organization, account, and user data with proper typing
 */
export const useSettingsContext = (): SettingsContextData => {
  const {
    user,
    selectedOrgAccount,
    currentOrganizationId,
    orgMetadata,
    accountMetadata,
    hasSelectedWorkspace,
    isAuthenticated,
  } = useAuth();

  const settingsContext = useMemo((): SettingsContextData => {
    // Organization context
    const currentOrganization = {
      id: currentOrganizationId,
      name: selectedOrgAccount?.metadata?.organization_name || "Organization",
      metadata: currentOrganizationId
        ? orgMetadata[currentOrganizationId] || null
        : null,
    };

    // Account context
    const currentAccount = {
      id: selectedOrgAccount?.accountId || null,
      name: selectedOrgAccount?.metadata?.account_name || "Account",
      metadata: selectedOrgAccount?.accountId
        ? accountMetadata[selectedOrgAccount.accountId] || null
        : null,
    };

    // User context
    const currentUser = {
      id: user?.id || null,
      name: `${user?.firstName || ""} ${user?.lastName || ""}`.trim() || "User",
      firstName: user?.firstName || "",
      lastName: user?.lastName || "",
      email: user?.email || "",
    };

    // Permissions
    const organizationRole = currentOrganizationId
      ? user?.permissions?.organizations?.[currentOrganizationId] || null
      : null;

    const permissions = {
      canManageOrganization:
        organizationRole === "admin" || organizationRole === "owner",
      canManageAccounts:
        organizationRole === "admin" ||
        organizationRole === "owner" ||
        organizationRole === "manager",
      canManageUsers:
        organizationRole === "admin" || organizationRole === "owner",
      organizationRole,
    };

    return {
      currentOrganization,
      currentAccount,
      currentUser,
      permissions,
      hasSelectedWorkspace,
      isAuthenticated,
    };
  }, [
    user,
    selectedOrgAccount,
    currentOrganizationId,
    orgMetadata,
    accountMetadata,
    hasSelectedWorkspace,
    isAuthenticated,
  ]);

  return settingsContext;
};

export default useSettingsContext;
