/**
 * Helper functions for AccountsManagement component
 * Extracted for better testability and reusability
 */

import type { AccountCreationData } from "@/components/settings/AccountCreationWizard";
import type { QueryClient } from "@tanstack/react-query";
import { accountKeys } from "@/queries/accounts";

/**
 * Validates account creation data
 * @param data - The account creation data from wizard
 * @param orgId - The organization ID (can be null)
 * @returns Error message string or null if valid
 */
export const validateAccountCreation = (
  data: AccountCreationData,
  orgId: string | null,
): string | null => {
  if (!orgId) {
    return "No organization selected. Please select an organization first.";
  }
  if (!data.account_name || !data.industry) {
    return "Please fill in required fields: account name and industry.";
  }
  return null;
};

/**
 * Transforms wizard data to API format
 * @param data - The account creation data from wizard
 * @param orgId - The organization ID
 * @returns Transformed data for API call
 */
export const transformWizardData = (
  data: AccountCreationData,
  orgId: string,
) => ({
  accountName: data.account_name,
  organizationId: orgId,
  industry: data.industry,
  status: "Active" as const,
  websites: data.websites || [],
  timezone: data.timezone,
  dataRegion: data.data_region,
  region: data.region,
  estimatedAnnualAdBudget: data.estimated_annual_ad_budget || null,
  businessStrategyDocuments: data.business_strategy_documents || [],
  marketing_channels: data.marketing_channels || [],
  product_integrations: data.product_integrations || [],
});

/**
 * Updates React contexts after successful account creation
 * @param account - The newly created account
 * @param orgId - The organization ID
 * @param setAccountMetadata - Function to update account metadata context
 * @param setOrgMetadata - Function to update org metadata context
 */
export const updateContextsAfterCreation = (
  account: any,
  orgId: string,
  setAccountMetadata: (
    updater: (prev: Record<string, any>) => Record<string, any>,
  ) => void,
  setOrgMetadata: (
    updater: (prev: Record<string, any>) => Record<string, any>,
  ) => void,
) => {
  // Update account metadata for easy lookup
  setAccountMetadata((prev) => ({
    ...prev,
    [account.account_id]: account,
  }));

  // Update orgMetadata to include the new account
  setOrgMetadata((prev) => ({
    ...prev,
    [orgId]: {
      ...prev[orgId],
      accounts: [...(prev[orgId]?.accounts || []), account],
    },
  }));
};

/**
 * Refreshes account queries after operations
 * @param queryClient - React Query client
 * @param orgId - The organization ID
 */
export const refreshAccountQueries = async (
  queryClient: QueryClient,
  orgId: string,
) => {
  await queryClient.invalidateQueries({
    queryKey: accountKeys.list(orgId),
  });
  await queryClient.refetchQueries({
    queryKey: accountKeys.list(orgId),
  });
};
