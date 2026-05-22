// Production wiring for CH-PRD-02. Consumes useChatSessions (CH-22),
// SessionStatusDot / deriveSessionStatus (CH-21), and lib/chatApi.ts types (CH-18).
// Collapse state is owned by Chat.tsx (persisted to localStorage) and passed as props.
// CH-PRD-03 will swap the native <select> for CategoriesDropdown when it ships.

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Plus, ChevronLeft, Filter } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import type { FlagKey } from "@/lib/featureFlags/types";
import type { AccountId } from "@/lib/branded-types";
import {
  deriveSessionStatus,
  isOptimisticSessionId,
  listChatCategories,
  tryChatCategoryId,
} from "@/lib/chatApi";
import type { ChatSessionId, ChatCategoryId } from "@/lib/chatApi";
import { useChatSessions } from "@/hooks/useChatSessions";
import { SessionStatusDot } from "./SessionStatusDot";

export type { ChatSessionId };

// ─── Props ────────────────────────────────────────────────────────────────────

export type SessionsSidebarProps = {
  accountId: AccountId | null;
  currentSessionId: ChatSessionId | null;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onSessionSelect: (id: ChatSessionId) => void;
  onNewSession: () => void;
  isNewSessionPending: boolean;
};

// ─── Component ────────────────────────────────────────────────────────────────

export function SessionsSidebar({
  accountId,
  currentSessionId,
  isCollapsed,
  onToggleCollapse,
  onSessionSelect,
  onNewSession,
  isNewSessionPending,
}: SessionsSidebarProps) {
  // ── Raw search input + debounced query (300 ms) ─────────────────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // ── Category filter ─────────────────────────────────────────────────────────
  const [selectedCategoryId, setSelectedCategoryId] =
    useState<ChatCategoryId | null>(null);

  // ── Feature flags ───────────────────────────────────────────────────────────
  const { enabled: chatCategoriesEnabled } = useFeatureFlag(
    "chat_categories_enabled" as FlagKey,
  );

  // ── Categories (only fetched when flag is on) ───────────────────────────────
  const { data: categoriesData } = useQuery({
    queryKey: ["chat-categories"],
    queryFn: listChatCategories,
    enabled: chatCategoriesEnabled,
    staleTime: 60_000,
  });
  const categories = categoriesData ?? [];

  // ── Infinite query for sessions ─────────────────────────────────────────────
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isError,
    isFetchNextPageError,
  } = useChatSessions({
    accountId,
    categoryId: selectedCategoryId ?? undefined,
    query: debouncedQuery || undefined,
  });

  const allItems = data?.pages.flatMap((p) => p.items) ?? [];

  // ── Counts derived from the retained page (maxPages:1 sliding window) ───────
  // pages[0] is whichever page is currently retained, not necessarily the
  // chronological first. Counts are an approximation for the visible window.
  const firstPageItems = data?.pages[0]?.items ?? [];
  const realItems = firstPageItems.filter(
    (item) => !isOptimisticSessionId(item.session_id),
  );
  const activeCount = realItems.filter(
    (item) => deriveSessionStatus(item) === "active",
  ).length;
  const needsReviewCount = realItems.filter(
    (item) => deriveSessionStatus(item) === "needs-review",
  ).length;

  // ── Infinite-scroll sentinel ─────────────────────────────────────────────────
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const lastFetchAtRef = useRef<number>(0);
  // Refs let the observer callback read live values without being a dep, so the
  // observer is created once per fetchNextPage identity change rather than on
  // every hasNextPage / isFetchingNextPage render cycle.
  const hasNextPageRef = useRef(hasNextPage);
  const isFetchingNextPageRef = useRef(isFetchingNextPage);
  useEffect(() => {
    hasNextPageRef.current = hasNextPage;
  }, [hasNextPage]);
  useEffect(() => {
    isFetchingNextPageRef.current = isFetchingNextPage;
  }, [isFetchingNextPage]);

  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return;
        if (!hasNextPageRef.current) return;
        if (isFetchingNextPageRef.current) return;
        const now = Date.now();
        if (now - lastFetchAtRef.current < 1000) return; // 1 fetch/sec rate limit
        lastFetchAtRef.current = now;
        fetchNextPage();
      },
      { rootMargin: "80px" },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [fetchNextPage]);

  // ═══════════════════════════════════════════════════════════════════════════
  // Collapsed state (64 px rail)
  // ═══════════════════════════════════════════════════════════════════════════
  if (isCollapsed) {
    const nonIdleItems = allItems
      .filter((item) => deriveSessionStatus(item) !== "idle")
      .slice(0, 10);

    return (
      <div
        data-testid="sessions-sidebar"
        data-slot="sessions-sidebar"
        className="w-16 bg-[var(--color-bg-elevated)] flex flex-col items-center py-4 gap-4 h-full min-h-0"
        style={{ borderRight: "2px dashed var(--color-border-default)" }}
      >
        {/* Expand chevron */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          aria-label="Expand sessions sidebar"
          className="shrink-0"
        >
          <ChevronLeft className="size-4 rotate-180" />
        </Button>

        {/* New Session */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onNewSession}
          aria-label="New session"
          disabled={isNewSessionPending}
          className="shrink-0"
        >
          <Plus className="size-4" />
        </Button>

        {/* Non-idle session dots (up to 10) */}
        <div className="flex flex-col gap-2 mt-4">
          {nonIdleItems.map((item) => {
            const status = deriveSessionStatus(item);
            const isActive = status === "active";
            return (
              <button
                key={item.session_id}
                onClick={() => onSessionSelect(item.session_id)}
                className={cn(
                  "size-2.5 rounded-full transition-all hover:scale-125",
                  isActive ? "bg-[var(--color-teal-500)]" : "bg-[#F97066]",
                )}
                style={{
                  boxShadow: isActive
                    ? "0 0 4px rgba(16, 185, 129, 0.5)"
                    : "0 0 4px rgba(249, 112, 102, 0.5)",
                }}
                title={item.title ?? "Untitled session"}
              />
            );
          })}
        </div>

        {/* Error indicator */}
        {isError && (
          <div className="mt-auto pb-2">
            <div
              className="size-2.5 rounded-full bg-[#F97066] mx-auto"
              title="Couldn't load sessions"
              style={{ boxShadow: "0 0 4px rgba(249, 112, 102, 0.5)" }}
            />
          </div>
        )}
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Expanded state (384 px panel)
  // ═══════════════════════════════════════════════════════════════════════════
  return (
    <div
      data-testid="sessions-sidebar"
      data-slot="sessions-sidebar"
      className="w-96 bg-[var(--color-bg-elevated)] flex flex-col overflow-x-hidden"
      style={{ borderRight: "2px dashed var(--color-border-default)" }}
    >
      {/* Header */}
      <div className="p-4 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2
              className="text-[var(--text-heading-sm)] font-bold"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Sessions
            </h2>
            <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
              {activeCount} active • {needsReviewCount} need review
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            aria-label="Collapse sessions sidebar"
            className="shrink-0"
          >
            <ChevronLeft className="size-4" />
          </Button>
        </div>

        {/* New Session Button */}
        <Button
          onClick={onNewSession}
          className="w-full mb-4"
          size="sm"
          disabled={isNewSessionPending}
        >
          <Plus className="size-4 mr-2" />
          New Session
        </Button>

        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-text-tertiary)]" />
          <Input
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
            aria-label="Search sessions"
          />
        </div>

        {/* Category Filter — only rendered when chat_categories_enabled is on */}
        {chatCategoriesEnabled && (
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--color-text-tertiary)]" />
            <select
              value={selectedCategoryId ?? ""}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedCategoryId(tryChatCategoryId(val) ?? null);
              }}
              aria-label="Filter sessions by category"
              className="w-full pl-9 pr-3 py-2 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)] text-[var(--text-body-sm)] focus:outline-none focus:ring-2 focus:ring-[var(--color-violet-500)]"
            >
              <option value="">All sessions</option>
              {categories.map((cat) => (
                <option key={cat.category_id} value={cat.category_id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Sessions List */}
      <ScrollArea className="flex-1">
        <div className="px-4 pb-4 space-y-2">
          {isError && (
            <p className="text-[var(--text-body-sm)] text-[var(--color-text-tertiary)] text-center py-4">
              Couldn&apos;t load sessions — retrying…
            </p>
          )}

          {!isError && allItems.length === 0 && (
            <p className="text-[var(--text-body-sm)] text-[var(--color-text-tertiary)] text-center py-8">
              {debouncedQuery
                ? "No sessions found"
                : "No sessions yet — start one with New Session"}
            </p>
          )}

          {allItems.map((item) => {
            const isActiveSession =
              currentSessionId !== null && currentSessionId === item.session_id;
            const sessionStatus = deriveSessionStatus(item);
            return (
              <button
                key={item.session_id}
                data-slot="session-list-item"
                data-status={sessionStatus}
                onClick={() => onSessionSelect(item.session_id)}
                className={cn(
                  "w-full text-left p-2 rounded-[var(--radius-md)] border-2 transition-all group block",
                  "hover:bg-[var(--color-accent)] hover:border-[var(--color-violet-300)]",
                  isActiveSession
                    ? "border-[var(--color-violet-300)] bg-[var(--color-accent)]"
                    : "border-[var(--color-border-default)] bg-[var(--color-bg-primary)]",
                )}
                style={{
                  transitionTimingFunction: "var(--ease-default)",
                  transitionDuration: "var(--duration-fast)",
                }}
              >
                <div className="flex items-start gap-2 min-w-0">
                  {/* Status dot */}
                  <div className="shrink-0 mt-1">
                    <SessionStatusDot item={item} />
                  </div>

                  {/* Session info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--text-body-sm)] font-medium truncate">
                      {item.title ?? "Untitled session"}
                    </p>
                    {item.category_name && (
                      <p className="text-[0.6875rem] text-[var(--color-text-tertiary)] truncate">
                        {item.category_name}
                      </p>
                    )}
                    {item.last_message_preview && (
                      <p className="text-[0.625rem] text-[var(--color-text-tertiary)] truncate mt-0.5">
                        {item.last_message_preview}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            );
          })}

          {/* Infinite-scroll sentinel */}
          <div ref={loadMoreRef} aria-hidden="true" />

          {/* fetchNextPage error — shown below the sentinel so it appears at the end of the list */}
          {isFetchNextPageError && (
            <div className="text-center py-2">
              <p className="text-[var(--text-body-sm)] text-[var(--color-text-tertiary)] mb-1">
                Couldn&apos;t load more sessions
              </p>
              <button
                onClick={() => fetchNextPage()}
                className="text-[var(--text-body-sm)] text-[var(--color-violet-500)] hover:underline"
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
