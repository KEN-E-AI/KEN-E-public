import { useMemo } from "react";
import { getAvailableAccounts } from "@/lib/organizationUtils";

interface UseAvailableAccountsParams {
  selectedOrganization: string;
  selectedChildOrg: string;
  localOrgMetadata: Record<string, any>;
  childOrganizations: Record<string, any>[];
  orgsFromFirestore: Record<string, string>;
  getAccountsByOrganizationIdFromLocal: (orgId: string) => any[];
}

interface UseAvailableAccountsReturn {
  availableAccounts: any[];
  hasAccounts: boolean;
  isAgencyOrganization: boolean;
  needsChildOrgSelection: boolean;
}

/**
 * Custom hook for managing available accounts logic
 */
export function useAvailableAccounts({
  selectedOrganization,
  selectedChildOrg,
  localOrgMetadata,
  childOrganizations,
  orgsFromFirestore,
  getAccountsByOrganizationIdFromLocal,
}: UseAvailableAccountsParams): UseAvailableAccountsReturn {
  const availableAccounts = useMemo(() => {
    return getAvailableAccounts(
      selectedOrganization,
      selectedChildOrg,
      localOrgMetadata,
      childOrganizations,
      orgsFromFirestore,
      getAccountsByOrganizationIdFromLocal,
    );
  }, [
    selectedOrganization,
    selectedChildOrg,
    localOrgMetadata,
    childOrganizations,
    orgsFromFirestore,
    getAccountsByOrganizationIdFromLocal,
  ]);

  const selectedOrg = localOrgMetadata[selectedOrganization];
  const isAgencyOrganization = selectedOrg && selectedOrg.agency === true;
  const needsChildOrgSelection = isAgencyOrganization && !selectedChildOrg;

  return {
    availableAccounts,
    hasAccounts: availableAccounts.length > 0,
    isAgencyOrganization,
    needsChildOrgSelection,
  };
}
