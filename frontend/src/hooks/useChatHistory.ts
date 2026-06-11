import { getConversationHistory } from "@/lib/chatApi";

/**
 * TanStack Query key for a single conversation's formatted history.
 *
 * The chat view fetches history imperatively (via `queryClient.fetchQuery`)
 * rather than with `useQuery`, because the load is wrapped in race guards that
 * must run inside an effect. Sharing this key + fetcher keeps the cache and the
 * per-turn invalidation (`invalidateQueries`) consistent across the app.
 */
export const CHAT_HISTORY_QUERY_KEY = "chat-history" as const;

export const chatHistoryQueryKey = (sessionId: string) =>
  [CHAT_HISTORY_QUERY_KEY, sessionId] as const;

/**
 * Options for caching a session's history. Used with `queryClient.fetchQuery`.
 * A 60s staleTime lets revisits / the session-status toggle reuse the cached
 * payload instead of re-hitting Vertex; a completed turn invalidates the key so
 * the next fetch picks up the new messages (and any charts).
 */
export const chatHistoryQueryOptions = (sessionId: string) => ({
  queryKey: chatHistoryQueryKey(sessionId),
  queryFn: () => getConversationHistory(sessionId),
  staleTime: 60_000,
});
