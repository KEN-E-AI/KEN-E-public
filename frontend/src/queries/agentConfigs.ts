import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAgentConfigs,
  getAgentConfig,
  upsertAgentConfigOverlay,
  deleteAgentConfig,
  createAgentConfig,
} from "@/lib/api/agentConfigs";
import type {
  AgentConfigOverlayUpdate,
  AgentConfigCreate,
} from "@/lib/api/agentConfigs";

// ─── Query key factory ────────────────────────────────────────────────────────

export const agentConfigKeys = {
  all: ["agentConfigs"] as const,
  lists: () => [...agentConfigKeys.all, "list"] as const,
  list: (accountId: string, opts?: { visibleInFrontend?: boolean }) =>
    [...agentConfigKeys.lists(), accountId, opts] as const,
  details: () => [...agentConfigKeys.all, "detail"] as const,
  detail: (accountId: string, configId: string) =>
    [...agentConfigKeys.details(), accountId, configId] as const,
};

// ─── Queries ──────────────────────────────────────────────────────────────────

export function useAgentConfigsList(
  accountId: string | null | undefined,
  opts: { visibleInFrontend?: boolean } = {},
) {
  return useQuery({
    queryKey: agentConfigKeys.list(accountId ?? "", opts),
    queryFn: () =>
      listAgentConfigs(accountId!, {
        visibleInFrontend: opts.visibleInFrontend,
      }),
    enabled: !!accountId,
    staleTime: 1000 * 60,
  });
}

export function useAgentConfig(
  accountId: string | null | undefined,
  configId: string | null | undefined,
) {
  return useQuery({
    queryKey: agentConfigKeys.detail(accountId ?? "", configId ?? ""),
    queryFn: () => getAgentConfig(accountId!, configId!),
    enabled: !!accountId && !!configId,
    staleTime: 1000 * 60,
  });
}

// ─── Mutations ────────────────────────────────────────────────────────────────

export function useUpsertAgentConfigOverlay(
  accountId: string | null | undefined,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      configId,
      body,
    }: {
      configId: string;
      body: AgentConfigOverlayUpdate;
    }) => {
      if (!accountId) return Promise.reject(new Error("No account selected"));
      return upsertAgentConfigOverlay(accountId, configId, body);
    },
    onSuccess: (_, { configId }) => {
      if (!accountId) return;
      queryClient.invalidateQueries({
        queryKey: agentConfigKeys.list(accountId),
      });
      queryClient.invalidateQueries({
        queryKey: agentConfigKeys.detail(accountId, configId),
      });
    },
  });
}

export function useCreateAgentConfig(accountId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: AgentConfigCreate) => {
      if (!accountId) return Promise.reject(new Error("No account selected"));
      return createAgentConfig(accountId, body);
    },
    onSuccess: () => {
      if (!accountId) return;
      queryClient.invalidateQueries({
        queryKey: agentConfigKeys.list(accountId),
      });
    },
  });
}

export function useDeleteAgentConfig(accountId: string | null | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ configId }: { configId: string }) => {
      if (!accountId) return Promise.reject(new Error("No account selected"));
      return deleteAgentConfig(accountId, configId);
    },
    onSuccess: (_, { configId }) => {
      if (!accountId) return;
      queryClient.invalidateQueries({
        queryKey: agentConfigKeys.list(accountId),
      });
      queryClient.invalidateQueries({
        queryKey: agentConfigKeys.detail(accountId, configId),
      });
    },
  });
}
