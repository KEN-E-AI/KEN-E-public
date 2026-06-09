import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getEarlyReleaseConfig,
  updateEarlyReleaseConfig,
  listEarlyReleaseRedemptions,
} from "@/data/admin-earlyReleaseApi";
import type { EarlyReleaseAdminUpdateRequest } from "@/data/admin-earlyReleaseApi";

export const earlyReleaseKeys = {
  config: () => ["earlyRelease", "config"] as const,
  redemptions: (cursor?: string) =>
    ["earlyRelease", "redemptions", cursor ?? null] as const,
};

export function useEarlyReleaseConfig() {
  return useQuery({
    queryKey: earlyReleaseKeys.config(),
    queryFn: getEarlyReleaseConfig,
    staleTime: 1000 * 30,
    retry: (failureCount, error) => {
      const axiosErr = error as { response?: { status?: number } };
      if (axiosErr.response?.status === 404) return false;
      return failureCount < 3;
    },
  });
}

export function useUpdateEarlyReleaseConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EarlyReleaseAdminUpdateRequest) =>
      updateEarlyReleaseConfig(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: earlyReleaseKeys.config() });
    },
  });
}

export function useEarlyReleaseRedemptions(cursor?: string) {
  return useQuery({
    queryKey: earlyReleaseKeys.redemptions(cursor),
    queryFn: () => listEarlyReleaseRedemptions(cursor),
    staleTime: 1000 * 30,
  });
}
