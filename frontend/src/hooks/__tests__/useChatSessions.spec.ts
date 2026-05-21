import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useChatSessions, CHAT_SESSIONS_QUERY_KEY } from "../useChatSessions";
import type { AccountId } from "@/lib/branded-types";
import type { ListChatSessionsResponse } from "@/lib/chatApi";

vi.mock("@/lib/chatApi", () => ({
  listChatSessions: vi.fn(),
}));

import { listChatSessions } from "@/lib/chatApi";

const mockListChatSessions = vi.mocked(listChatSessions);

const ACCOUNT_ID = "acc_test123" as AccountId;

const PAGE_1: ListChatSessionsResponse = {
  items: [
    {
      session_id: "sess_1" as import("@/lib/chatApi").ChatSessionId,
      title: "Session 1",
      category_id: null,
      category_name: null,
      last_message_preview: "Hello",
      updated_at: "2026-01-01T00:00:00Z",
      created_at: "2026-01-01T00:00:00Z",
      is_agent_running: false,
      last_agent_message_at: null,
      last_viewed_at: null,
    },
  ],
  next_cursor: "cursor_page2",
};

const PAGE_2: ListChatSessionsResponse = {
  items: [
    {
      session_id: "sess_2" as import("@/lib/chatApi").ChatSessionId,
      title: "Session 2",
      category_id: null,
      category_name: null,
      last_message_preview: "World",
      updated_at: "2026-01-01T01:00:00Z",
      created_at: "2026-01-01T01:00:00Z",
      is_agent_running: false,
      last_agent_message_at: null,
      last_viewed_at: null,
    },
  ],
  next_cursor: null,
};

// Flush fake timers + microtasks for TanStack polling tests.
// Only used inside the nested "polling" describe where fake timers are active.
const flush = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useChatSessions", () => {
  beforeEach(() => {
    mockListChatSessions.mockResolvedValue(PAGE_1);
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ── Non-polling tests: real timers, waitFor works normally ─────────────────

  it("does not fetch when accountId is null", async () => {
    const { result } = renderHook(() => useChatSessions({ accountId: null }), {
      wrapper: createWrapper(),
    });

    await act(async () => {});

    expect(result.current.status).toBe("pending");
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockListChatSessions).not.toHaveBeenCalled();
  });

  it("fetches first page when accountId is provided", async () => {
    const { result } = renderHook(
      () => useChatSessions({ accountId: ACCOUNT_ID }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockListChatSessions).toHaveBeenCalledWith({
      cursor: null,
      category_id: undefined,
      query: undefined,
    });
    expect(result.current.data?.pages[0]).toEqual(PAGE_1);
  });

  it("fetches next page via fetchNextPage and slides the window (maxPages=1)", async () => {
    mockListChatSessions
      .mockResolvedValueOnce(PAGE_1)
      .mockResolvedValueOnce(PAGE_2);

    const { result } = renderHook(
      () => useChatSessions({ accountId: ACCOUNT_ID }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pages).toEqual([PAGE_1]);

    // Fire without awaiting the returned promise — waitFor below polls until state settles.
    // Wrapping in act() suppresses "not wrapped in act" console noise from React 18.
    act(() => {
      result.current.fetchNextPage();
    });

    // maxPages: 1 → fetching the next page drops the previous one; only the most-recent is retained.
    await waitFor(() => expect(result.current.data?.pages).toEqual([PAGE_2]));

    expect(result.current.hasNextPage).toBe(false);
  });

  it("includes CHAT_SESSIONS_QUERY_KEY in the query key", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { result } = renderHook(
      () => useChatSessions({ accountId: ACCOUNT_ID }),
      {
        wrapper: ({ children }) =>
          React.createElement(
            QueryClientProvider,
            { client: queryClient },
            children,
          ),
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const queries = queryClient.getQueryCache().findAll({
      queryKey: [CHAT_SESSIONS_QUERY_KEY],
    });
    expect(queries.length).toBe(1);
    expect(queries[0].queryKey[0]).toBe(CHAT_SESSIONS_QUERY_KEY);
  });

  // ── Polling tests: fake timers required for time-travel control ────────────

  describe("polling behavior", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("polls every 5 seconds while visible", async () => {
      const { result } = renderHook(
        () => useChatSessions({ accountId: ACCOUNT_ID }),
        { wrapper: createWrapper() },
      );

      await flush();
      expect(result.current.isSuccess).toBe(true);

      const callsAfterFirstFetch = mockListChatSessions.mock.calls.length;

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });

      expect(mockListChatSessions.mock.calls.length).toBeGreaterThan(
        callsAfterFirstFetch,
      );
    });

    it("stops polling when tab becomes hidden", async () => {
      const { result } = renderHook(
        () => useChatSessions({ accountId: ACCOUNT_ID }),
        { wrapper: createWrapper() },
      );

      await flush();
      expect(result.current.isSuccess).toBe(true);

      // Simulate tab hidden — dispatch to both document and window for TanStack's focusManager
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => "hidden",
      });
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("visibilitychange"));

      // Allow any in-flight timer to fire (one extra poll may have been scheduled)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5100);
      });

      const callsAfterHide = mockListChatSessions.mock.calls.length;

      // Advance several more poll intervals — should NOT trigger new fetches
      await act(async () => {
        await vi.advanceTimersByTimeAsync(15000);
      });

      expect(mockListChatSessions.mock.calls.length).toBe(callsAfterHide);
    });
  });
});
