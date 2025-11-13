import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { strengthService } from "@/services/strengthService";
import { opportunityService } from "@/services/opportunityService";
import type {
  Strength,
  StrengthCreate,
  StrengthUpdate,
} from "@/services/strengthService";
import type {
  Opportunity,
  OpportunityCreate,
  OpportunityUpdate,
} from "@/services/opportunityService";
import type { AccountId } from "@/lib/branded-types";

// Query keys factory
export const strengthKeys = {
  all: ["strengths"] as const,
  strengthList: (accountId: AccountId) =>
    [...strengthKeys.all, "list", accountId] as const,
  opportunities: (accountId: AccountId, strengthId?: string) =>
    [
      ...strengthKeys.all,
      "opportunities",
      accountId,
      strengthId || "all",
    ] as const,
};

// Strengths query with caching
export const useStrengths = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? strengthKeys.strengthList(accountId)
      : (["strengths", "list", "none"] as const),
    queryFn: async () => {
      if (!accountId) return { strengths: [], total_count: 0 };
      return strengthService.list(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Opportunities query with per-strength caching
export const useOpportunities = (
  accountId: AccountId | null,
  strengthId: string | null,
) => {
  return useQuery({
    queryKey: accountId
      ? strengthKeys.opportunities(accountId, strengthId || undefined)
      : (["strengths", "opportunities", "none"] as const),
    queryFn: async () => {
      if (!accountId || !strengthId)
        return { opportunities: [], total_count: 0 };
      return opportunityService.list(accountId, strengthId);
    },
    enabled: !!accountId && !!strengthId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// Strength mutations
export const useCreateStrength = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; strength: StrengthCreate }) =>
      strengthService.create(data.accountId, data.strength),
    onSuccess: (_, variables) => {
      // Invalidate strengths list
      queryClient.invalidateQueries({
        queryKey: strengthKeys.strengthList(variables.accountId),
      });
    },
  });
};

export const useUpdateStrength = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: StrengthUpdate;
    }) => strengthService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      // Invalidate strengths list
      queryClient.invalidateQueries({
        queryKey: strengthKeys.strengthList(variables.accountId),
      });
    },
  });
};

export const useDeleteStrength = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; nodeId: string }) =>
      strengthService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      // Invalidate strengths list
      queryClient.invalidateQueries({
        queryKey: strengthKeys.strengthList(variables.accountId),
      });
    },
  });
};

// Opportunity mutations
export const useCreateOpportunity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      opportunity: OpportunityCreate;
    }) => opportunityService.create(data.accountId, data.opportunity),
    onSuccess: (newOpportunity, variables) => {
      // Invalidate opportunities list for the specific strength
      queryClient.invalidateQueries({
        queryKey: strengthKeys.opportunities(
          variables.accountId,
          variables.opportunity.strength_node_id,
        ),
      });
    },
  });
};

export const useUpdateOpportunity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: OpportunityUpdate;
      strengthId: string;
    }) => opportunityService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      // Invalidate opportunities list for the specific strength
      queryClient.invalidateQueries({
        queryKey: strengthKeys.opportunities(
          variables.accountId,
          variables.strengthId,
        ),
      });
    },
  });
};

export const useDeleteOpportunity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      strengthId: string;
    }) => opportunityService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      // Invalidate opportunities list for the specific strength
      queryClient.invalidateQueries({
        queryKey: strengthKeys.opportunities(
          variables.accountId,
          variables.strengthId,
        ),
      });
    },
  });
};
