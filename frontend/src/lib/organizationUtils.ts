/**
 * Utility functions for organization selection logic
 */

import type { Organization, Account } from "@/data/organizationTypes";

export interface OrganizationResolutionResult {
  organization: any;
  account: any;
  organizationId: string;
}

export interface WorkspaceMetadata {
  organization_name: string;
  account_name: string;
  industry: string;
  status: string;
  timezone?: string;
  plan?: string;
}

export interface AccountCreationValidation {
  isValid: boolean;
  errorMessage?: string;
}

/**
 * Resolves the correct organization and account based on agency status
 */
export function resolveOrganizationAndAccount(
  selectedOrganization: string,
  selectedAccount: string,
  selectedChildOrg: string,
  localOrgMetadata: Record<string, any>,
  childOrganizations: Record<string, any>[],
): OrganizationResolutionResult {
  const selectedOrg = localOrgMetadata[selectedOrganization];

  // For agency organizations, get data from child organization
  if (selectedOrg && selectedOrg.agency && selectedChildOrg) {
    const org = childOrganizations.find(
      (co) => co.organization_id === selectedChildOrg,
    );
    const account = org?.accounts?.find(
      (a: any) => a.account_id === selectedAccount,
    );

    return {
      organization: org,
      account,
      organizationId: selectedChildOrg,
    };
  }

  // For regular organizations
  const org = selectedOrg;
  const account = org?.accounts?.find(
    (a: any) => a.account_id === selectedAccount,
  );

  return {
    organization: org,
    account,
    organizationId: selectedOrganization,
  };
}

/**
 * Gets the target organization ID for account creation
 */
export function getTargetOrganizationId(
  selectedOrganization: string,
  selectedChildOrg: string,
  localOrgMetadata: Record<string, any>,
): string {
  const selectedOrg = localOrgMetadata[selectedOrganization];
  return selectedOrg && selectedOrg.agency && selectedChildOrg
    ? selectedChildOrg
    : selectedOrganization;
}

/**
 * Validates account creation requirements
 */
export function validateAccountCreationRequirements(
  selectedOrganization: string,
  selectedChildOrg: string,
  localOrgMetadata: Record<string, any>,
  accountName: string,
  accountType: string,
): AccountCreationValidation {
  if (!selectedOrganization) {
    return {
      isValid: false,
      errorMessage: "Please select an organization first.",
    };
  }

  const selectedOrg = localOrgMetadata[selectedOrganization];
  if (selectedOrg && selectedOrg.agency && !selectedChildOrg) {
    return {
      isValid: false,
      errorMessage: "Please select a client organization first.",
    };
  }

  if (!accountName || !accountType) {
    return {
      isValid: false,
      errorMessage: "Please fill in all required fields",
    };
  }

  return { isValid: true };
}

/**
 * Formats workspace metadata for consistent use
 */
export function formatWorkspaceMetadata(
  organizationName: string,
  accountName: string,
  industry: string,
  status: string,
  timezone?: string,
  plan?: string,
): WorkspaceMetadata {
  return {
    organization_name: organizationName,
    account_name: accountName,
    industry: industry || "Unknown",
    status: status || "Active",
    timezone,
    plan,
  };
}

/**
 * Processes accounts for display in the UI
 */
export function processAccountsForDisplay(
  accounts: any[],
  organizationPermission: string,
): any[] {
  return accounts.map((account: any) => ({
    account_id: account.account_id,
    account_name: account.account_name || account.account_id.replace(/-/g, " "),
    industry: account.industry || "Unknown",
    status: account.status || "Active",
    permission: organizationPermission,
  }));
}

/**
 * Checks if an organization is an agency organization
 */
export function isAgencyOrganization(organization: any): boolean {
  return Boolean(organization && organization.agency === true);
}

/**
 * Gets available accounts based on organization type and selection
 */
export function getAvailableAccounts(
  selectedOrganization: string,
  selectedChildOrg: string,
  localOrgMetadata: Record<string, any>,
  childOrganizations: Record<string, any>[],
  orgsFromFirestore: Record<string, string>,
  getAccountsByOrganizationIdFromLocal: (orgId: string) => any[],
): any[] {
  if (!selectedOrganization) return [];

  const selectedOrg = localOrgMetadata[selectedOrganization];
  if (isAgencyOrganization(selectedOrg)) {
    if (!selectedChildOrg) return [];
    const childOrg = childOrganizations.find(
      (co) => co.organization_id === selectedChildOrg,
    );
    return processAccountsForDisplay(
      childOrg?.accounts || [],
      orgsFromFirestore[selectedOrganization],
    );
  }

  return getAccountsByOrganizationIdFromLocal(selectedOrganization);
}
