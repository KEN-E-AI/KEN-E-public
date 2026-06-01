import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { FlagKey } from "@/lib/featureFlags/types";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import {
  listChatCategories,
  createChatCategory,
  deleteChatCategory,
  assignSessionCategory,
} from "@/lib/chatApi";
import type {
  ChatCategory,
  ChatCategoryId,
  ChatSessionId,
} from "@/lib/chatApi";
import { CHAT_SESSIONS_QUERY_KEY } from "@/hooks/useChatSessions";

export const CHAT_CATEGORIES_QUERY_KEY = "chat-categories" as const;

export type AssignCategoryArgs = {
  sessionId: ChatSessionId;
  categoryId: ChatCategoryId | null;
};

export function useChatCategories() {
  const queryClient = useQueryClient();
  const { enabled } = useFeatureFlag("chat_categories_enabled" as FlagKey);

  const list = useQuery<ChatCategory[]>({
    queryKey: [CHAT_CATEGORIES_QUERY_KEY],
    queryFn: listChatCategories,
    enabled,
    staleTime: 60_000,
  });

  const create = useMutation({
    mutationFn: (name: string) => createChatCategory(name),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: [CHAT_CATEGORIES_QUERY_KEY],
      });
    },
  });

  const remove = useMutation({
    mutationFn: (id: ChatCategoryId) => deleteChatCategory(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: [CHAT_CATEGORIES_QUERY_KEY],
        }),
        queryClient.invalidateQueries({
          queryKey: [CHAT_SESSIONS_QUERY_KEY],
        }),
      ]);
    },
  });

  const assign = useMutation({
    mutationFn: ({ sessionId, categoryId }: AssignCategoryArgs) =>
      assignSessionCategory(sessionId, categoryId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: [CHAT_SESSIONS_QUERY_KEY],
      });
    },
  });

  return { list, create, remove, assign };
}

export type UseChatCategoriesResult = ReturnType<typeof useChatCategories>;
