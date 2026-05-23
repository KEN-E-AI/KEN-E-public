import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import { markRead, toChatSessionId } from "@/lib/chatApi";
import { CHAT_SESSIONS_QUERY_KEY } from "@/hooks/useChatSessions";
import type {
  ListChatSessionsResponse,
  ChatSessionSidebarItem,
} from "@/lib/chatApi";

type UseMarkReadParams = {
  sessionId: string | null;
  latestMessageRef: RefObject<HTMLElement | null>;
  // Re-run the effect whenever the observed element changes (new assistant
  // message mounted). Without this, the observer stays bound to the previous
  // detached DOM node after React re-points the ref to a new message node.
  latestMessageId: string | null;
};

export function useMarkRead({
  sessionId,
  latestMessageRef,
  latestMessageId,
}: UseMarkReadParams): void {
  const queryClient = useQueryClient();
  // Map<sessionId, lastFireTimestampMs>
  const lastFireRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const el = latestMessageRef.current;
    if (!sessionId || !el) return;

    let timerId: ReturnType<typeof setTimeout> | null = null;
    let isCancelled = false;

    const fire = async () => {
      if (isCancelled) return;
      // Per-session dedup: don't re-fire within 5s of the last *successful* fire
      const lastFire = lastFireRef.current.get(sessionId) ?? 0;
      if (Date.now() - lastFire < 5000) return;

      try {
        const result = await markRead(toChatSessionId(sessionId));
        if (isCancelled) return;
        // Stamp only on success so transient errors don't consume the 5s window
        lastFireRef.current.set(sessionId, Date.now());
        const newLastViewedAt = result.last_viewed_at;

        // Optimistically patch last_viewed_at across every ["chat-sessions", ...] cache variant
        queryClient.setQueriesData<InfiniteData<ListChatSessionsResponse>>(
          { queryKey: [CHAT_SESSIONS_QUERY_KEY] },
          (old) => {
            if (!old) return old;
            return {
              ...old,
              pages: old.pages.map((page) => ({
                ...page,
                items: page.items.map(
                  (item): ChatSessionSidebarItem =>
                    item.session_id === sessionId
                      ? { ...item, last_viewed_at: newLastViewedAt }
                      : item,
                ),
              })),
            };
          },
        );

        // Belt-and-braces: invalidate so the next poll reconciles authoritatively
        queryClient.invalidateQueries({ queryKey: [CHAT_SESSIONS_QUERY_KEY] });
      } catch (err) {
        // Silent — mark-read is a UX signal; surfacing errors would be intrusive
        console.debug("[useMarkRead] mark-read failed:", err);
      }
    };

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry) return;
        if (entry.isIntersecting) {
          timerId = setTimeout(fire, 500);
        } else {
          if (timerId !== null) {
            clearTimeout(timerId);
            timerId = null;
          }
        }
      },
      { threshold: 0.5 },
    );

    observer.observe(el);

    return () => {
      isCancelled = true;
      observer.disconnect();
      if (timerId !== null) clearTimeout(timerId);
    };
    // latestMessageRef is intentionally excluded: it is a stable useRef object.
    // latestMessageId is the signal that ref.current has moved to a new DOM node.
  }, [sessionId, queryClient, latestMessageId]);
}
