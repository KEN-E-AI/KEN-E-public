/**
 * Hook for account consistency checking and validation
 */

import { useQuery } from "@tanstack/react-query";
import {
  checkAccountConsistency,
  validateAccountCreationSuccess,
  detectPartialCreationFailure,
} from "@/lib/consistency";
import { useAccounts } from "@/queries/accounts";
import type { Account } from "@/data/organizationTypes";
import type { ConsistencyCheck, ConsistencyIssue } from "@/lib/consistency";

export interface UseAccountConsistencyOptions {
  organizationId: string | null;
  enabled?: boolean;
  refetchInterval?: number;
}

export interface UseAccountConsistencyResult {
  consistencyCheck: ConsistencyCheck | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  checkAccount: (account: Account, expectedData?: any) => boolean;
  detectPartialFailure: (account: Account) => ConsistencyIssue | null;
}

/**
 * Hook for checking account consistency and detecting partial creation failures
 */
export function useAccountConsistency({
  organizationId,
  enabled = true,
  refetchInterval,
}: UseAccountConsistencyOptions): UseAccountConsistencyResult {
  // Get accounts data
  const { data: accounts = [], isLoading: accountsLoading } =
    useAccounts(organizationId);

  // Perform consistency check
  const {
    data: consistencyCheck,
    isLoading: checkLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["account-consistency", organizationId],
    queryFn: () => {
      if (!accounts.length) {
        return {
          isConsistent: true,
          inconsistencies: [],
          totalAccounts: 0,
          lastChecked: new Date().toISOString(),
        } as ConsistencyCheck;
      }

      return checkAccountConsistency(accounts);
    },
    enabled:
      enabled && !!organizationId && !accountsLoading && accounts.length > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: refetchInterval,
    retry: (failureCount, error) => failureCount < 2, // Retry twice on failure
  });

  const checkAccount = (account: Account, expectedData?: any) => {
    return validateAccountCreationSuccess(account, expectedData || {});
  };

  const detectPartialFailure = (account: Account) => {
    return detectPartialCreationFailure(account);
  };

  return {
    consistencyCheck,
    isLoading: accountsLoading || checkLoading,
    error,
    refetch,
    checkAccount,
    detectPartialFailure,
  };
}

/**
 * Hook for real-time consistency checking after account operations
 */
export function useAccountOperationConsistency(organizationId: string | null) {
  const consistency = useAccountConsistency({
    organizationId,
    refetchInterval: 30000, // Check every 30 seconds
  });

  return {
    ...consistency,
    /**
     * Check consistency immediately after an account operation
     */
    checkAfterOperation: async () => {
      // Wait a moment for data to propagate
      await new Promise((resolve) => setTimeout(resolve, 1000));
      return consistency.refetch();
    },
  };
}
