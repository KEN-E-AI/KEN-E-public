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
  MergedAgentConfig,
} from "@/lib/api/agentConfigs";

// ─── Query key factory ────────────────────────────────────────────────────────

export const agentConfigKeys = {
  all: ["agentConfigs"] as const,
  lists: () => [...agentConfigKeys.all, "list"] as const,
  // Prefix for every list variant scoped to one account — regardless of
  // ``opts`` (e.g. ``visibleInFrontend``). Use this with TanStack's
  // ``setQueriesData`` / ``invalidateQueries`` to touch all list variants
  // for an account in one call.
  listsForAccount: (accountId: string) =>
    [...agentConfigKeys.lists(), accountId] as const,
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
    onSuccess: (updated, { configId }) => {
      if (!accountId) return;
      // Push the freshly-saved config straight into the caches that render
      // it so the agent card updates the moment the edit sheet closes — no
      // second GET roundtrip required. Previous behavior was
      // `invalidateQueries` which triggered a refetch of the list
      // endpoint; on top of the latency that added, the invalidation key
      // omitted `opts` so it didn't actually prefix-match the
      // `{visibleInFrontend: true}` list query AgentsListView uses.
      //
      // `listsForAccount(accountId)` is the 3-element prefix that
      // matches every list variant for this account, with or without
      // opts — atomic update across all list consumers.
      //
      // In-place map is safe today because `AgentConfigOverlayUpdate`
      // doesn't expose `visible_in_frontend`, so saving an overlay can't
      // change a config's membership in the visible-only list. If that
      // ever becomes editable here, switch to an add-or-update /
      // update-or-remove strategy per list variant.
      queryClient.setQueryData(
        agentConfigKeys.detail(accountId, configId),
        updated,
      );
      queryClient.setQueriesData<MergedAgentConfig[] | undefined>(
        { queryKey: agentConfigKeys.listsForAccount(accountId) },
        (prev) => prev?.map((c) => (c.config_id === configId ? updated : c)),
      );
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
        queryKey: agentConfigKeys.listsForAccount(accountId),
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
        queryKey: agentConfigKeys.listsForAccount(accountId),
      });
      queryClient.invalidateQueries({
        queryKey: agentConfigKeys.detail(accountId, configId),
      });
    },
  });
}
