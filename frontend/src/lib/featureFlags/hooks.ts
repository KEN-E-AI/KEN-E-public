/**
 * React Query hooks for the Feature Flags admin API.
 *
 * NOTE: This file exports admin-config hooks for managing flag settings.
 * The runtime evaluation hook (useFeatureFlag returning {enabled, reason})
 * is in frontend/src/contexts/FeatureFlagsContext.tsx (FF-PRD-03).
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listFlags,
  getFlag,
  createFlag,
  updateFlag,
  deleteFlag,
  getFlagAudit,
} from "./adminClient";
import type { FeatureFlagCreate, FeatureFlagUpdate } from "./adminClient";
import type { FlagKey } from "./types";

// ─── Query-key factory ────────────────────────────────────────────────────────

export const featureFlagKeys = {
  all: ["featureFlags"] as const,
  list: () => [...featureFlagKeys.all, "list"] as const,
  detail: (key: FlagKey) => [...featureFlagKeys.all, "detail", key] as const,
  audit: (key: FlagKey, cursor: string | null = null) =>
    [...featureFlagKeys.detail(key), "audit", cursor] as const,
};

// ─── Query hooks ──────────────────────────────────────────────────────────────

export function useFeatureFlags() {
  return useQuery({
    queryKey: featureFlagKeys.list(),
    queryFn: listFlags,
    staleTime: 1000 * 60,
  });
}

export function useFeatureFlag(key: FlagKey | undefined) {
  return useQuery({
    queryKey: key ? featureFlagKeys.detail(key) : featureFlagKeys.all,
    queryFn: () => getFlag(key!),
    enabled: !!key,
    staleTime: 1000 * 60,
  });
}

export function useFlagAudit(key: FlagKey, cursor: string | null = null) {
  return useQuery({
    queryKey: featureFlagKeys.audit(key, cursor),
    queryFn: () => getFlagAudit(key, { cursor }),
    staleTime: 1000 * 30,
  });
}

// ─── Mutation hooks ───────────────────────────────────────────────────────────

export function useCreateFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FeatureFlagCreate) => createFlag(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: featureFlagKeys.list() });
    },
  });
}

export function useUpdateFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, body }: { key: FlagKey; body: FeatureFlagUpdate }) =>
      updateFlag(key, body),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: featureFlagKeys.list() });
      queryClient.invalidateQueries({
        queryKey: featureFlagKeys.detail(variables.key),
      });
    },
  });
}

export function useDeleteFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (key: FlagKey) => deleteFlag(key),
    onSuccess: (_data, key) => {
      queryClient.invalidateQueries({ queryKey: featureFlagKeys.list() });
      queryClient.invalidateQueries({
        queryKey: featureFlagKeys.detail(key),
      });
    },
  });
}
