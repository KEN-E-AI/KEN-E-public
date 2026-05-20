import { createContext, useContext, useCallback, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { evaluate } from "@/lib/featureFlags/client";
import { KNOWN_FLAGS } from "@/lib/featureFlags/registry";
import { getDevOverride } from "@/lib/featureFlags/devOverride";
import type {
  FlagKey,
  FlagEvaluation,
  FeatureFlagsContextValue,
  UseFeatureFlagResult,
} from "@/lib/featureFlags/types";

const EMPTY_EVALUATIONS: Record<FlagKey, FlagEvaluation> = {} as Record<
  FlagKey,
  FlagEvaluation
>;

export const FeatureFlagsContext = createContext<
  FeatureFlagsContextValue | undefined
>(undefined);

export const useFeatureFlagsContext = (): FeatureFlagsContextValue => {
  const context = useContext(FeatureFlagsContext);
  if (context === undefined) {
    throw new Error(
      "useFeatureFlagsContext must be used within a FeatureFlagsProvider",
    );
  }
  return context;
};

type FeatureFlagsProviderProps = {
  children: ReactNode;
};

export const FeatureFlagsProvider = ({
  children,
}: FeatureFlagsProviderProps) => {
  const { user, selectedOrgAccount } = useAuth();
  const queryClient = useQueryClient();

  const accountId = selectedOrgAccount?.accountId;

  const { data, isLoading } = useQuery({
    queryKey: ["feature-flags", user?.id, accountId],
    queryFn: () => evaluate(KNOWN_FLAGS),
    staleTime: 60_000,
    enabled: !!user && KNOWN_FLAGS.length > 0,
  });

  const evaluations = data
    ? (data as Record<FlagKey, FlagEvaluation>)
    : EMPTY_EVALUATIONS;

  const refetch = useCallback(async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["feature-flags"] });
  }, [queryClient]);

  return (
    <FeatureFlagsContext.Provider value={{ evaluations, isLoading, refetch }}>
      {children}
    </FeatureFlagsContext.Provider>
  );
};

export const useFeatureFlag = (key: FlagKey): UseFeatureFlagResult => {
  const context = useContext(FeatureFlagsContext);
  if (context === undefined) {
    throw new Error(
      "useFeatureFlag must be used within a FeatureFlagsProvider",
    );
  }

  const { evaluations, isLoading } = context;

  const override = getDevOverride(key);
  if (override !== undefined) {
    return { enabled: override, reason: "dev_override", isLoading: false };
  }

  const evaluation = evaluations[key];
  if (evaluation !== undefined) {
    return {
      enabled: evaluation.enabled,
      reason: evaluation.reason,
      isLoading,
    };
  }

  if (import.meta.env.VITE_ENVIRONMENT !== "production") {
    console.warn(
      `[FeatureFlags] useFeatureFlag("${key}") called but "${key}" is not in KNOWN_FLAGS. Add it to frontend/src/lib/featureFlags/registry.ts before use.`,
    );
  }

  return { enabled: false, reason: "unknown_flag", isLoading: false };
};
