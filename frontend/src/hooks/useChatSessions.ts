import { useInfiniteQuery } from "@tanstack/react-query";
import type { AccountId } from "@/lib/branded-types";
import type { ChatCategoryId, ListChatSessionsResponse } from "@/lib/chatApi";
import { listChatSessions } from "@/lib/chatApi";

export const CHAT_SESSIONS_QUERY_KEY = "chat-sessions" as const;

interface UseChatSessionsParams {
  accountId: AccountId | null;
  categoryId?: ChatCategoryId;
  query?: string;
}

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
      listChatSessions({ cursor: pageParam, category_id: categoryId, query }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage: ListChatSessionsResponse) =>
      lastPage.next_cursor,
    enabled: accountId != null,
    // Pause polling when tab is hidden; resume on visibility change via refetchOnWindowFocus.
    refetchInterval: () =>
      document.visibilityState === "visible" ? 5000 : false,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}
