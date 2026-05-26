import { useQuery } from "@tanstack/react-query";
import type { ChatSessionId, ListArtifactsResponse } from "@/lib/chatApi";
import { listArtifacts } from "@/lib/chatApi";

export const ARTIFACTS_QUERY_KEY = "artifacts" as const;

export function useArtifacts(sessionId: ChatSessionId | null) {
  return useQuery<ListArtifactsResponse>({
    queryKey: [ARTIFACTS_QUERY_KEY, sessionId] as const,
    queryFn: () => listArtifacts(sessionId!),
    enabled: sessionId != null,
    staleTime: 30_000,
  });
}
