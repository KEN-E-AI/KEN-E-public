import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import {
  OPTIMISTIC_SESSION_ID_PREFIX,
  createChatConversation,
  toChatSessionId,
} from "@/lib/chatApi";
import type {
  ConversationInfo,
  ChatSessionSidebarItem,
  ListChatSessionsResponse,
} from "@/lib/chatApi";

type CreateChatSessionInput = {
  conversation_name?: string;
  account_id?: string;
};

// Server-generated session IDs: alphanumeric + underscore/hyphen, 1–128 chars.
// Matches Chat.tsx SESSION_ID_RE; validate here so a crafted server response
// cannot produce a malformed URL or silent session-drop in the page.
const SESSION_ID_RE = /^[a-zA-Z0-9_-]{1,128}$/;

/**
 * Maps the `ConversationInfo` returned by POST /conversations into the
 * `ChatSessionSidebarItem` shape the sidebar cache expects.
 *
 * The side-table fields not present on `ConversationInfo` are set to the
 * defaults a freshly-created session would have (CH-PRD-01 §4.1):
 * no agent invocation yet → is_agent_running=false, all timestamps null.
 *
 * When CH-30 lands and the POST endpoint returns the full sidebar shape,
 * this mapper is deleted and the server row passes through directly.
 */
function mapConversationInfoToSidebarItem(
  info: ConversationInfo,
): ChatSessionSidebarItem {
  return {
    session_id: toChatSessionId(info.session_id),
    title: info.conversation_name ?? null,
    category_id: null,
    category_name: null,
    last_message_preview: info.preview ?? null,
    updated_at: info.last_updated,
    created_at: info.created_at,
    is_agent_running: false,
    last_agent_message_at: null,
    last_viewed_at: new Date().toISOString(),
  };
}

/**
 * Prepends `item` to the first page of an InfiniteData<ListChatSessionsResponse>
 * cache entry. If the cache is empty / undefined, returns it unchanged so
 * setQueriesData remains a no-op (the "no sidebar mounted" path).
 */
function prependToInfiniteCache(
  item: ChatSessionSidebarItem,
  old: InfiniteData<ListChatSessionsResponse> | undefined,
): InfiniteData<ListChatSessionsResponse> | undefined {
  if (!old || old.pages.length === 0) return old;
  const [firstPage, ...rest] = old.pages;
  return {
    ...old,
    pages: [{ ...firstPage, items: [item, ...firstPage.items] }, ...rest],
  };
}

/**
 * Replaces the optimistic placeholder row (identified by `tempId`) with the
 * real sidebar item from the server response.
 */
function replaceInInfiniteCache(
  tempId: string,
  realItem: ChatSessionSidebarItem,
  old: InfiniteData<ListChatSessionsResponse> | undefined,
): InfiniteData<ListChatSessionsResponse> | undefined {
  if (!old) return old;
  return {
    ...old,
    pages: old.pages.map((page) => ({
      ...page,
      items: page.items.map((i) => (i.session_id === tempId ? realItem : i)),
    })),
  };
}

/**
 * Hook for the "New Session" button flow (CH-PRD-02 AC-8).
 *
 * Calls POST /api/v1/chat/conversations, optimistically prepends an
 * "Untitled session" placeholder to every cached ["chat-sessions", …] entry,
 * then on success replaces the placeholder with the real row and navigates to
 * /chat?session=<id>. On error the placeholder is removed and a destructive
 * toast is shown.
 *
 * Exposes `isPending` so callers can disable the trigger button to prevent
 * a double-click from spawning two ghost rows.
 */
export function useCreateChatSession() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (input: CreateChatSessionInput) =>
      createChatConversation(input),

    onMutate: async (_input) => {
      // Cancel any in-flight background refetches for the sidebar so they
      // don't overwrite the optimistic row when they settle.
      await queryClient.cancelQueries({ queryKey: ["chat-sessions"] });

      // Prefix uses ':' (not in Chat.tsx's SESSION_ID_RE) so a click on the
      // placeholder before onSuccess fires cannot produce a routable URL.
      const tempId = toChatSessionId(
        `${OPTIMISTIC_SESSION_ID_PREFIX}${crypto.randomUUID()}`,
      );
      const now = new Date().toISOString();
      const optimisticItem: ChatSessionSidebarItem = {
        session_id: tempId,
        title: "Untitled session",
        category_id: null,
        category_name: null,
        last_message_preview: null,
        updated_at: now,
        created_at: now,
        is_agent_running: false,
        last_agent_message_at: null,
        last_viewed_at: now,
      };

      // Snapshot every cache that matches the ["chat-sessions"] prefix so
      // onError can restore them precisely.
      const snapshots = queryClient.getQueriesData<
        InfiniteData<ListChatSessionsResponse>
      >({ queryKey: ["chat-sessions"] });

      // Prepend the optimistic row to every variant (different account, filter,
      // search query). setQueriesData is a no-op when no cache entries match.
      queryClient.setQueriesData<InfiniteData<ListChatSessionsResponse>>(
        { queryKey: ["chat-sessions"] },
        (old) => prependToInfiniteCache(optimisticItem, old),
      );

      return { tempId, snapshots };
    },

    onSuccess: (data, _input, context) => {
      if (!context) return;
      const { tempId, snapshots } = context;

      // Validate the server-returned session_id before using it in a URL.
      // A malformed id would cause Chat.tsx to silently drop the session;
      // treat it as a creation failure and roll back.
      if (!SESSION_ID_RE.test(data.session_id)) {
        snapshots.forEach(([queryKey, snapshotData]) => {
          queryClient.setQueryData(queryKey, snapshotData);
        });
        toast({
          variant: "destructive",
          title: "Couldn't start a new session",
          description: "Please try again.",
        });
        return;
      }

      const realItem = mapConversationInfoToSidebarItem(data);

      // Replace the optimistic placeholder with the real server row.
      queryClient.setQueriesData<InfiniteData<ListChatSessionsResponse>>(
        { queryKey: ["chat-sessions"] },
        (old) => replaceInInfiniteCache(tempId, realItem, old),
      );

      navigate(`/chat?session=${encodeURIComponent(data.session_id)}`, {
        replace: true,
      });
    },

    onError: (_error, _input, context) => {
      if (!context) return;
      const { snapshots } = context;

      // Restore every cache to its pre-mutation snapshot.
      snapshots.forEach(([queryKey, snapshotData]) => {
        queryClient.setQueryData(queryKey, snapshotData);
      });

      toast({
        variant: "destructive",
        title: "Couldn't start a new session",
        description: "Please try again.",
      });
    },
  });
}
