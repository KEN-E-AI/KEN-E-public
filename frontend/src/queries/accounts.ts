import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAccountsByOrganizationId,
  deleteAccount as deleteAccountApi,
  createAccount as createAccountApi,
  updateAccount as updateAccountApi,
} from "@/data/organizationApi";
import type { Account } from "@/data/organizationTypes";

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
      const accounts = await getAccountsByOrganizationId(organizationId);
      return accounts;
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
      marketing_channels: string[];
      product_integrations: string[];
      estimatedAnnualAdBudget?: number | null;
      businessStrategyDocuments?: File[];
    }) => {
      // Generate idempotency key for retry safety
      const idempotencyKey = `account_create_${accountData.organizationId}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      try {
        // Transform camelCase to snake_case for API with runtime validation
        const result = await createAccountApi(
          {
            account_name: accountData.accountName,
            organization_id: accountData.organizationId,
            industry: accountData.industry,
            status: accountData.status,
            websites: accountData.websites,
            timezone: accountData.timezone,
            data_region: accountData.dataRegion,
            region: accountData.region,
            marketing_channels: Array.isArray(accountData.marketing_channels)
              ? accountData.marketing_channels
              : [],
            product_integrations: Array.isArray(
              accountData.product_integrations,
            )
              ? accountData.product_integrations
              : [],
            estimated_annual_ad_budget: accountData.estimatedAnnualAdBudget,
            business_strategy_documents: accountData.businessStrategyDocuments,
          },
          { idempotencyKey },
        );

        console.log("[useCreateAccount] Account created successfully:", result);
        return result;
      } catch (error: any) {
        console.error("[useCreateAccount] Account creation failed:", error);

        // Enhanced error handling with specific error types
        if (error.response?.status === 500) {
          throw new Error(
            "Account creation failed due to a server error. Please check if the account was created before retrying.",
          );
        } else if (error.response?.status === 504) {
          throw new Error(
            "Account creation timed out. Please check your accounts list to see if the account was created.",
          );
        } else if (error.response?.status === 409) {
          throw new Error(
            "An account with this name already exists in your organization.",
          );
        } else if (error.response?.status === 422) {
          throw new Error(
            "Invalid account data. Please check your inputs and try again.",
          );
        } else if (!error.response && error.code === "ECONNABORTED") {
          throw new Error(
            "Request timeout. Please check your internet connection and try again.",
          );
        }

        // Re-throw original error for unknown cases
        throw error;
      }
    },

    // Retry configuration for transient failures
    retry: (failureCount, error: any) => {
      // Don't retry client errors (4xx)
      if (error.response?.status >= 400 && error.response?.status < 500) {
        return false;
      }

      // Don't retry if account might have been created
      if (error.message.includes("check if the account was created")) {
        return false;
      }

      // Retry server errors and network issues up to 2 times
      return failureCount < 2;
    },

    // Exponential backoff with jitter
    retryDelay: (attemptIndex) => {
      const baseDelay = 1000 * Math.pow(2, attemptIndex); // 1s, 2s, 4s
      const jitter = Math.random() * 500; // 0-500ms random jitter
      return Math.min(baseDelay + jitter, 5000); // Cap at 5 seconds
    },

    onSuccess: (_, variables) => {
      // Invalidate the specific organization's account list
      queryClient.invalidateQueries({
        queryKey: accountKeys.list(variables.organizationId),
      });
      // Also invalidate all lists for broader cache consistency
      queryClient.invalidateQueries({ queryKey: accountKeys.lists() });

      console.log(
        "[useCreateAccount] Cache invalidated for organization:",
        variables.organizationId,
      );
    },

    onError: (error: any, variables) => {
      console.error("[useCreateAccount] Final error after retries:", error);

      // Don't show toast here - let the UI component handle it
      // This allows for more contextual error handling
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
