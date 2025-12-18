import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { marketingStrategyService } from "@/services/marketingStrategyService";
import type {
  StrategyType,
  MarketingStrategy,
  MarketingStrategyUpdate,
} from "@/services/marketingStrategyService";

interface RollupStrategiesData {
  problemAwareness: MarketingStrategy | null;
  brandAwareness: MarketingStrategy | null;
  consideration: MarketingStrategy | null;
  conversion: MarketingStrategy | null;
  loyalty: MarketingStrategy | null;
}

export const useRollupStrategies = (accountId: string | null) => {
  return useQuery<RollupStrategiesData | null>({
    queryKey: ["marketing", "rollup-strategies", accountId],
    queryFn: async () => {
      if (!accountId) return null;

      const [
        problemAwarenessRes,
        brandAwarenessRes,
        considerationRes,
        conversionRes,
        loyaltyRes,
      ] = await Promise.all([
        marketingStrategyService.listRollupStrategies(
          accountId,
          "problem-awareness",
        ),
        marketingStrategyService.listRollupStrategies(
          accountId,
          "brand-awareness",
        ),
        marketingStrategyService.listRollupStrategies(
          accountId,
          "consideration",
        ),
        marketingStrategyService.listRollupStrategies(accountId, "conversion"),
        marketingStrategyService.listRollupStrategies(accountId, "loyalty"),
      ]);

      return {
        problemAwareness: problemAwarenessRes.strategies[0] || null,
        brandAwareness: brandAwarenessRes.strategies[0] || null,
        consideration: considerationRes.strategies[0] || null,
        conversion: conversionRes.strategies[0] || null,
        loyalty: loyaltyRes.strategies[0] || null,
      };
    },
    enabled: !!accountId,
  });
};

export const useIndividualStrategies = (
  accountId: string | null,
  categoryId: string | null,
  profileId: string | null,
) => {
  return useQuery<MarketingStrategy[]>({
    queryKey: [
      "marketing",
      "individual-strategies",
      accountId,
      categoryId,
      profileId,
    ],
    queryFn: async () => {
      if (!accountId || !categoryId) return [];

      const strategyTypes: StrategyType[] = [
        "problem-awareness",
        "brand-awareness",
        "consideration",
        "conversion",
        "loyalty",
      ];

      const results = await Promise.all(
        strategyTypes.map((type) =>
          marketingStrategyService.listIndividualStrategies(accountId, type),
        ),
      );

      const allStrategies = results.flatMap((res) => res.strategies);

      return allStrategies.filter(
        (strategy) =>
          strategy.product_category_node_id === categoryId &&
          (!profileId || strategy.customer_profile_node_id === profileId),
      );
    },
    enabled: !!accountId && !!categoryId,
  });
};

export const useUpdateStrategy = (strategyType: StrategyType) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      accountId,
      nodeId,
      updates,
    }: {
      accountId: string;
      nodeId: string;
      updates: MarketingStrategyUpdate;
    }) => {
      return await marketingStrategyService.updateStrategy(
        accountId,
        strategyType,
        nodeId,
        updates,
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["marketing", "rollup-strategies", variables.accountId],
      });
      queryClient.invalidateQueries({
        queryKey: ["marketing", "individual-strategies", variables.accountId],
      });
    },
  });
};

export const useDeleteStrategy = (strategyType: StrategyType) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      accountId,
      nodeId,
    }: {
      accountId: string;
      nodeId: string;
    }) => {
      return await marketingStrategyService.deleteStrategy(
        accountId,
        strategyType,
        nodeId,
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["marketing", "individual-strategies", variables.accountId],
      });
    },
  });
};
