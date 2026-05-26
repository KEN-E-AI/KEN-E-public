import { useQuery } from "@tanstack/react-query";
import type { ChatSessionId, ListTodosResponse } from "@/lib/chatApi";
import { listTodoLists } from "@/lib/chatApi";

export const TODO_LISTS_QUERY_KEY = "todo-lists" as const;

export function useTodoLists(sessionId: ChatSessionId | null) {
  return useQuery<ListTodosResponse>({
    queryKey: [TODO_LISTS_QUERY_KEY, sessionId] as const,
    queryFn: () => listTodoLists(sessionId!),
    enabled: sessionId != null,
    staleTime: 30_000,
  });
}
