import { useInfiniteQuery } from "@tanstack/react-query";
import type { AccountId } from "@/lib/branded-types";
import type { ChatCategoryId, ListChatSessionsResponse } from "@/lib/chatApi";
import { listChatSessions } from "@/lib/chatApi";

export const CHAT_SESSIONS_QUERY_KEY = "chat-sessions" as const;

type UseChatSessionsParams = {
  accountId: AccountId | null;
  categoryId?: ChatCategoryId;
  query?: string;
};

export function useChatSessions({
  accountId,
  categoryId,
  query,
}: UseChatSessionsParams) {
  return useInfiniteQuery({
    queryKey: [
      CHAT_SESSIONS_QUERY_KEY,
      accountId,
      categoryId ?? "all",
      query ?? "",
    ] as const,
    queryFn: ({ pageParam }) =>
      listChatSessions({
        cursor: pageParam,
        category_id: categoryId,
        query,
        account_id: accountId,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage: ListChatSessionsResponse) =>
      lastPage.next_cursor,
    enabled: accountId != null,
    // Cap retained pages at 1 so each poll fetches a single page regardless
    // of how far the user has scrolled. Without this, useInfiniteQuery refetches
    // every loaded page on every tick, multiplying API load by the page count.
    // `fetchNextPage` still works — it replaces the retained page (sliding window).
    maxPages: 1,
    // Pause polling when tab is hidden; resume on visibility change via refetchOnWindowFocus.
    // 10s cadence (not 5s) halves sidebar read load; raised in response to
    // server-side p95 latency on the conversations endpoint under poll load.
    refetchInterval: () =>
      document.visibilityState === "visible" ? 10000 : false,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}
