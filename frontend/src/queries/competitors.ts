import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { competitiveEnvironmentService } from "@/services/competitiveEnvironmentService";
import type {
  CompetitiveEnvironment,
  CompetitiveEnvironmentUpdate,
} from "@/services/competitiveEnvironmentService";
import { competitorService } from "@/services/competitorService";
import type {
  Competitor,
  CompetitorCreate,
  CompetitorUpdate,
} from "@/services/competitorService";
import { competitorTacticService } from "@/services/competitorTacticService";
import type {
  CompetitorTactic,
  CompetitorTacticCreate,
  CompetitorTacticUpdate,
} from "@/services/competitorTacticService";
import { competitorStrengthService } from "@/services/competitorStrengthService";
import type {
  CompetitorStrength,
  CompetitorStrengthCreate,
  CompetitorStrengthUpdate,
} from "@/services/competitorStrengthService";
import { competitorWeaknessService } from "@/services/competitorWeaknessService";
import type {
  CompetitorWeakness,
  CompetitorWeaknessCreate,
  CompetitorWeaknessUpdate,
} from "@/services/competitorWeaknessService";
import { substituteProductService } from "@/services/substituteProductService";
import type {
  SubstituteProduct,
  SubstituteProductCreate,
  SubstituteProductUpdate,
} from "@/services/substituteProductService";

// ==================== COMPETITIVE ENVIRONMENT ====================

export function useCompetitiveEnvironment(accountId: string | null) {
  return useQuery<CompetitiveEnvironment | null>({
    queryKey: ["competitive-environment", accountId],
    queryFn: async () => {
      if (!accountId) return null;
      try {
        return await competitiveEnvironmentService.get(accountId);
      } catch (error: any) {
        // 404 is expected if no competitive environment exists yet
        if (error.response?.status === 404) return null;
        throw error;
      }
    },
    enabled: !!accountId,
  });
}

export function useUpdateCompetitiveEnvironment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      updates,
    }: {
      accountId: string;
      updates: CompetitiveEnvironmentUpdate;
    }) => competitiveEnvironmentService.update(accountId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitive-environment", variables.accountId],
      });
    },
  });
}

// ==================== COMPETITORS ====================

export function useCompetitors(
  accountId: string | null,
  skip = 0,
  limit = 1000,
) {
  return useQuery({
    queryKey: ["competitors", accountId, skip, limit],
    queryFn: () => competitorService.list(accountId!, skip, limit),
    enabled: !!accountId,
  });
}

export function useCompetitor(accountId: string | null, nodeId: string | null) {
  return useQuery({
    queryKey: ["competitors", accountId, nodeId],
    queryFn: () => competitorService.get(accountId!, nodeId!),
    enabled: !!accountId && !!nodeId,
  });
}

export function useCreateCompetitor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      competitor,
    }: {
      accountId: string;
      competitor: CompetitorCreate;
    }) => competitorService.create(accountId, competitor),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitors", variables.accountId],
      });
      queryClient.invalidateQueries({
        queryKey: ["competitive-environment", variables.accountId],
      });
    },
  });
}

export function useUpdateCompetitor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: CompetitorUpdate;
    }) => competitorService.update(accountId, nodeId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitors", variables.accountId],
      });
    },
  });
}

export function useDeleteCompetitor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
    }: {
      accountId: string;
      nodeId: string;
    }) => competitorService.delete(accountId, nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitors", variables.accountId],
      });
    },
  });
}

// ==================== COMPETITOR TACTICS ====================

export function useCompetitorTactics(
  accountId: string | null,
  competitorId: string | null,
  skip = 0,
  limit = 1000,
) {
  return useQuery({
    queryKey: ["competitor-tactics", accountId, competitorId, skip, limit],
    queryFn: () =>
      competitorTacticService.list(
        accountId!,
        competitorId || undefined,
        skip,
        limit,
      ),
    enabled: !!accountId,
  });
}

export function useCreateCompetitorTactic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      tactic,
    }: {
      accountId: string;
      tactic: CompetitorTacticCreate;
    }) => competitorTacticService.create(accountId, tactic),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-tactics", variables.accountId],
      });
    },
  });
}

export function useUpdateCompetitorTactic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: CompetitorTacticUpdate;
    }) => competitorTacticService.update(accountId, nodeId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-tactics", variables.accountId],
      });
    },
  });
}

export function useDeleteCompetitorTactic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
    }: {
      accountId: string;
      nodeId: string;
    }) => competitorTacticService.delete(accountId, nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-tactics", variables.accountId],
      });
    },
  });
}

// ==================== COMPETITOR STRENGTHS ====================

export function useCompetitorStrengths(
  accountId: string | null,
  competitorId: string | null,
  skip = 0,
  limit = 1000,
) {
  return useQuery({
    queryKey: ["competitor-strengths", accountId, competitorId, skip, limit],
    queryFn: () =>
      competitorStrengthService.list(
        accountId!,
        competitorId || undefined,
        skip,
        limit,
      ),
    enabled: !!accountId,
  });
}

export function useCreateCompetitorStrength() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      strength,
    }: {
      accountId: string;
      strength: CompetitorStrengthCreate;
    }) => competitorStrengthService.create(accountId, strength),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-strengths", variables.accountId],
      });
    },
  });
}

export function useUpdateCompetitorStrength() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: CompetitorStrengthUpdate;
    }) => competitorStrengthService.update(accountId, nodeId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-strengths", variables.accountId],
      });
    },
  });
}

export function useDeleteCompetitorStrength() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
    }: {
      accountId: string;
      nodeId: string;
    }) => competitorStrengthService.delete(accountId, nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-strengths", variables.accountId],
      });
    },
  });
}

// ==================== COMPETITOR WEAKNESSES ====================

export function useCompetitorWeaknesses(
  accountId: string | null,
  competitorId: string | null,
  skip = 0,
  limit = 1000,
) {
  return useQuery({
    queryKey: ["competitor-weaknesses", accountId, competitorId, skip, limit],
    queryFn: () =>
      competitorWeaknessService.list(
        accountId!,
        competitorId || undefined,
        skip,
        limit,
      ),
    enabled: !!accountId,
  });
}

export function useCreateCompetitorWeakness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      weakness,
    }: {
      accountId: string;
      weakness: CompetitorWeaknessCreate;
    }) => competitorWeaknessService.create(accountId, weakness),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-weaknesses", variables.accountId],
      });
    },
  });
}

export function useUpdateCompetitorWeakness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: CompetitorWeaknessUpdate;
    }) => competitorWeaknessService.update(accountId, nodeId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-weaknesses", variables.accountId],
      });
    },
  });
}

export function useDeleteCompetitorWeakness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
    }: {
      accountId: string;
      nodeId: string;
    }) => competitorWeaknessService.delete(accountId, nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["competitor-weaknesses", variables.accountId],
      });
    },
  });
}

// ==================== SUBSTITUTE PRODUCTS ====================

export function useSubstituteProducts(
  accountId: string | null,
  competitorId: string | null,
  productNodeId?: string | null,
  skip = 0,
  limit = 1000,
) {
  return useQuery({
    queryKey: ["substitute-products", accountId, competitorId, productNodeId, skip, limit],
    queryFn: () =>
      substituteProductService.list(
        accountId!,
        competitorId || undefined,
        productNodeId || undefined,
        skip,
        limit,
      ),
    enabled: !!accountId && (!!competitorId || !!productNodeId),
  });
}

export function useCreateSubstituteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      product,
    }: {
      accountId: string;
      product: SubstituteProductCreate;
    }) => substituteProductService.create(accountId, product),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["substitute-products", variables.accountId],
      });
    },
  });
}

export function useUpdateSubstituteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: SubstituteProductUpdate;
    }) => substituteProductService.update(accountId, nodeId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["substitute-products", variables.accountId],
      });
    },
  });
}

export function useDeleteSubstituteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      nodeId,
    }: {
      accountId: string;
      nodeId: string;
    }) => substituteProductService.delete(accountId, nodeId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["substitute-products", variables.accountId],
      });
    },
  });
}

// ==================== PRODUCT-SUBSTITUTE RELATIONSHIP MUTATIONS ====================

export function useLinkProductToSubstitute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      substituteProductId,
      productNodeId,
    }: {
      accountId: string;
      substituteProductId: string;
      productNodeId: string;
    }) =>
      substituteProductService.linkProduct(
        accountId,
        substituteProductId,
        productNodeId,
      ),
    onSuccess: (_, variables) => {
      // Invalidate products list for this substitute
      queryClient.invalidateQueries({
        queryKey: ["products", "list", variables.accountId],
      });
    },
  });
}

export function useUnlinkProductFromSubstitute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      substituteProductId,
      productNodeId,
    }: {
      accountId: string;
      substituteProductId: string;
      productNodeId: string;
    }) =>
      substituteProductService.unlinkProduct(
        accountId,
        substituteProductId,
        productNodeId,
      ),
    onSuccess: (_, variables) => {
      // Invalidate products list for this substitute
      queryClient.invalidateQueries({
        queryKey: ["products", "list", variables.accountId],
      });
    },
  });
}
