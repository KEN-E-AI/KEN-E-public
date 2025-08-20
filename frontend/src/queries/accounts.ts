import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAccountsByOrganizationId,
  deleteAccount as deleteAccountApi,
  createAccount as createAccountApi,
  updateAccount as updateAccountApi,
} from "@/data/organizationApi";
import type { Account } from "@/types/organization";

// Query keys factory
export const accountKeys = {
  all: ["accounts"] as const,
  lists: () => [...accountKeys.all, "list"] as const,
  list: (orgId: string) => [...accountKeys.lists(), orgId] as const,
  details: () => [...accountKeys.all, "detail"] as const,
  detail: (id: string) => [...accountKeys.details(), id] as const,
};

// Queries
export const useAccounts = (organizationId: string | null) => {
  return useQuery({
    queryKey: accountKeys.list(organizationId || ""),
    queryFn: async () => {
      if (!organizationId) return [];
      return getAccountsByOrganizationId(organizationId);
    },
    enabled: !!organizationId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

// Mutations
export const useDeleteAccount = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      orgId,
      accountId,
    }: {
      orgId: string;
      accountId: string;
    }) => {
      // Use the existing deleteAccountApi function which handles auth properly
      // Note: orgId is not used in the API call but kept for consistency with UI
      await deleteAccountApi(accountId);
    },
    onSuccess: (_, { orgId }) => {
      // Invalidate and refetch account lists for the organization
      queryClient.invalidateQueries({ queryKey: accountKeys.list(orgId) });
    },
    onError: (error) => {
      console.error("[useDeleteAccount] Error:", error);
    },
  });
};

export const useCreateAccount = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (accountData: {
      accountName: string;
      organizationId: string;
      industry: string;
      status: string;
      websites: string[];
      timezone: string;
      dataRegion: string;
      region: string[];
      estimatedAnnualAdBudget?: number | null;
      businessStrategyDocuments?: File[];
    }) => {
      // Transform camelCase to snake_case for API
      return createAccountApi({
        account_name: accountData.accountName,
        organization_id: accountData.organizationId,
        industry: accountData.industry,
        status: accountData.status,
        websites: accountData.websites,
        timezone: accountData.timezone,
        data_region: accountData.dataRegion,
        region: accountData.region,
        estimated_annual_ad_budget: accountData.estimatedAnnualAdBudget,
        business_strategy_documents: accountData.businessStrategyDocuments,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: accountKeys.lists() });
    },
    onError: (error) => {
      console.error("[useCreateAccount] Error:", error);
    },
  });
};

export const useUpdateAccount = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      accountId,
      updates,
    }: {
      accountId: string;
      updates: Partial<Account>;
    }) => {
      return updateAccountApi(accountId, updates);
    },
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({ queryKey: accountKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: accountKeys.detail(accountId),
      });
    },
    onError: (error) => {
      console.error("[useUpdateAccount] Error:", error);
    },
  });
};
