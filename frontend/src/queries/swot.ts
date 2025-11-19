import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { strengthService } from "@/services/strengthService";
import { opportunityService } from "@/services/opportunityService";
import { weaknessService } from "@/services/weaknessService";
import { riskService } from "@/services/riskService";
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
import type {
  Weakness,
  WeaknessCreate,
  WeaknessUpdate,
} from "@/services/weaknessService";
import type { Risk, RiskCreate, RiskUpdate } from "@/services/riskService";
import type { AccountId } from "@/lib/branded-types";

// Query keys factory
export const swotKeys = {
  all: ["swot"] as const,
  strengths: (accountId: AccountId) =>
    [...swotKeys.all, "strengths", accountId] as const,
  weaknesses: (accountId: AccountId) =>
    [...swotKeys.all, "weaknesses", accountId] as const,
  opportunities: (accountId: AccountId, strengthId?: string) =>
    [...swotKeys.all, "opportunities", accountId, strengthId || "all"] as const,
  risks: (accountId: AccountId, weaknessId?: string) =>
    [...swotKeys.all, "risks", accountId, weaknessId || "all"] as const,
};

// ==================== STRENGTHS ====================

export const useStrengths = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? swotKeys.strengths(accountId)
      : (["swot", "strengths", "none"] as const),
    queryFn: async () => {
      if (!accountId) return { strengths: [], total_count: 0 };
      return strengthService.list(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

export const useCreateStrength = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; strength: StrengthCreate }) =>
      strengthService.create(data.accountId, data.strength),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: swotKeys.strengths(variables.accountId),
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
      queryClient.invalidateQueries({
        queryKey: swotKeys.strengths(variables.accountId),
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
      queryClient.invalidateQueries({
        queryKey: swotKeys.strengths(variables.accountId),
      });
    },
  });
};

// ==================== WEAKNESSES ====================

export const useWeaknesses = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? swotKeys.weaknesses(accountId)
      : (["swot", "weaknesses", "none"] as const),
    queryFn: async () => {
      if (!accountId) return { weaknesses: [], total_count: 0 };
      return weaknessService.list(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

export const useCreateWeakness = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; weakness: WeaknessCreate }) =>
      weaknessService.create(data.accountId, data.weakness),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: swotKeys.weaknesses(variables.accountId),
      });
    },
  });
};

export const useUpdateWeakness = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: WeaknessUpdate;
    }) => weaknessService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: swotKeys.weaknesses(variables.accountId),
      });
    },
  });
};

export const useDeleteWeakness = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; nodeId: string }) =>
      weaknessService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: swotKeys.weaknesses(variables.accountId),
      });
    },
  });
};

// ==================== OPPORTUNITIES ====================

export const useOpportunities = (
  accountId: AccountId | null,
  parentId: string | null, // Can be Strength or CompetitorWeakness node_id
  parentType?: "strength" | "weakness", // Hint for which parent type
) => {
  return useQuery({
    queryKey: accountId
      ? [
          ...swotKeys.opportunities(accountId, parentId || undefined),
          parentType,
        ]
      : (["swot", "opportunities", "none"] as const),
    queryFn: async () => {
      if (!accountId || !parentId) return { opportunities: [], total_count: 0 };

      // Pass to correct parameter based on parent type
      if (parentType === "weakness") {
        return opportunityService.list(accountId, undefined, parentId);
      } else {
        return opportunityService.list(accountId, parentId);
      }
    },
    enabled: !!accountId && !!parentId,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

export const useCreateOpportunity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      opportunity: OpportunityCreate;
    }) => opportunityService.create(data.accountId, data.opportunity),
    onSuccess: (newOpportunity, variables) => {
      // Invalidate queries for both strength and weakness parents
      const parentId =
        variables.opportunity.strength_node_id ||
        variables.opportunity.weakness_node_id;

      queryClient.invalidateQueries({
        queryKey: swotKeys.opportunities(variables.accountId, parentId),
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
      strengthId?: string; // Optional: for business SWOT
      weaknessId?: string; // Optional: for competitive
    }) => opportunityService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      const parentId = variables.strengthId || variables.weaknessId;
      queryClient.invalidateQueries({
        queryKey: swotKeys.opportunities(variables.accountId, parentId),
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
      strengthId?: string; // Optional: for business SWOT
      weaknessId?: string; // Optional: for competitive
    }) => opportunityService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      const parentId = variables.strengthId || variables.weaknessId;
      queryClient.invalidateQueries({
        queryKey: swotKeys.opportunities(variables.accountId, parentId),
      });
    },
  });
};

// ==================== RISKS ====================

export const useRisks = (
  accountId: AccountId | null,
  parentId: string | null, // Can be Weakness or CompetitorStrength node_id
  parentType?: "weakness" | "strength", // Hint for which parent type
) => {
  return useQuery({
    queryKey: accountId
      ? [...swotKeys.risks(accountId, parentId || undefined), parentType]
      : (["swot", "risks", "none"] as const),
    queryFn: async () => {
      if (!accountId || !parentId) return { risks: [], total_count: 0 };

      // Pass to correct parameter based on parent type
      if (parentType === "strength") {
        return riskService.list(accountId, undefined, parentId);
      } else {
        return riskService.list(accountId, parentId);
      }
    },
    enabled: !!accountId && !!parentId,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

export const useCreateRisk = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { accountId: AccountId; risk: RiskCreate }) =>
      riskService.create(data.accountId, data.risk),
    onSuccess: (newRisk, variables) => {
      // Invalidate queries for both weakness and strength parents
      const parentId =
        variables.risk.weakness_node_id || variables.risk.strength_node_id;

      queryClient.invalidateQueries({
        queryKey: swotKeys.risks(variables.accountId, parentId),
      });
    },
  });
};

export const useUpdateRisk = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      updates: RiskUpdate;
      weaknessId?: string; // For business SWOT
      strengthId?: string; // For competitive
    }) => riskService.update(data.accountId, data.nodeId, data.updates),
    onSuccess: (_, variables) => {
      const parentId = variables.weaknessId || variables.strengthId;
      queryClient.invalidateQueries({
        queryKey: swotKeys.risks(variables.accountId, parentId),
      });
    },
  });
};

export const useDeleteRisk = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      accountId: AccountId;
      nodeId: string;
      weaknessId?: string; // For business SWOT
      strengthId?: string; // For competitive
    }) => riskService.delete(data.accountId, data.nodeId),
    onSuccess: (_, variables) => {
      const parentId = variables.weaknessId || variables.strengthId;
      queryClient.invalidateQueries({
        queryKey: swotKeys.risks(variables.accountId, parentId),
      });
    },
  });
};
