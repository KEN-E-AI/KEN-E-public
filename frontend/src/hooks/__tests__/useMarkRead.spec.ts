import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import React, { useRef } from "react";
import { useMarkRead } from "../useMarkRead";
import type { ListChatSessionsResponse } from "@/lib/chatApi";

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("@/lib/chatApi", () => ({
  markRead: vi.fn(),
  toChatSessionId: (v: string) => v,
  isPendingSessionId: (id: string) => id.startsWith("pending_"),
}));

vi.mock("@/hooks/useChatSessions", () => ({
  CHAT_SESSIONS_QUERY_KEY: "chat-sessions",
}));

import { markRead } from "@/lib/chatApi";
const mockMarkRead = vi.mocked(markRead);

// ─── IntersectionObserver stub ────────────────────────────────────────────────
// Per-element map so that triggerIntersect(el, bool) only fires the callback
// bound to that specific element — accurately models browser behavior where
// each observed element has its own observer instance.

type IOCallback = (entries: IntersectionObserverEntry[]) => void;
const observerMap = new Map<Element, IOCallback>();

function triggerIntersect(el: Element, isIntersecting: boolean) {
  const cb = observerMap.get(el);
  cb?.([{ isIntersecting } as unknown as IntersectionObserverEntry]);
}

const MockIntersectionObserver = vi
  .fn()
  .mockImplementation((cb: IOCallback) => {
    return {
      observe: vi.fn((el: Element) => {
        observerMap.set(el, cb);
      }),
      // disconnect() takes no args per spec; identify entries by callback reference
      disconnect: vi.fn(() => {
        for (const [key, stored] of observerMap) {
          if (stored === cb) observerMap.delete(key);
        }
      }),
    };
  });

vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SESSION_A = "sess_a";
const SESSION_B = "sess_b";
const PENDING_SESSION = "pending_161bca48-5b10-4fd5-a286-c34b34c568ea";
const LAST_VIEWED_AT = "2026-01-01T12:00:00Z";

function makeInfiniteData(
  sessionId: string,
  lastViewedAt: string | null = null,
): InfiniteData<ListChatSessionsResponse> {
  return {
    pages: [
      {
        items: [
          {
            session_id: sessionId as import("@/lib/chatApi").ChatSessionId,
            title: "Test",
            category_id: null,
            category_name: null,
            last_message_preview: null,
            updated_at: "2026-01-01T00:00:00Z",
            created_at: "2026-01-01T00:00:00Z",
            is_agent_running: false,
            last_agent_message_at: "2026-01-01T11:00:00Z",
            last_viewed_at: lastViewedAt,
          },
        ],
        next_cursor: null,
      },
    ],
    pageParams: [null],
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        // Prevent fake-timer GC from evicting cache entries during tests
        gcTime: Infinity,
      },
    },
  });
  return {
    queryClient,
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        QueryClientProvider,
        { client: queryClient },
        children,
      ),
  };
}

// A helper hook that creates a ref pointing at a real DOM element
function useTestRef(el: HTMLElement | null) {
  const ref = useRef<HTMLElement | null>(el);
  ref.current = el;
  return ref;
}

describe("useMarkRead", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    observerMap.clear();
    mockMarkRead.mockResolvedValue({ last_viewed_at: LAST_VIEWED_AT });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── AC-1: no-op when sessionId is null ────────────────────────────────────
  it("no-ops and does not construct IntersectionObserver when sessionId is null", () => {
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: null,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );
    expect(MockIntersectionObserver).not.toHaveBeenCalled();
    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  // ── AC-1b: no-op for pending_ placeholder session ids ─────────────────────
  it("no-ops and does not construct IntersectionObserver when sessionId is a pending_ placeholder", () => {
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: PENDING_SESSION,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );
    expect(MockIntersectionObserver).not.toHaveBeenCalled();
    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  // ── AC-1c: fires once the pending id resolves to a real session id ────────
  it("fires markRead after a pending_ id resolves to a real session id", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    let sessionId = PENDING_SESSION;
    const { rerender } = renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    // While pending: visible for 500ms, but the guard suppresses the call.
    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(mockMarkRead).not.toHaveBeenCalled();

    // Pending id resolves to the real session id → effect re-runs and arms.
    sessionId = SESSION_A;
    rerender();
    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    expect(mockMarkRead).toHaveBeenCalledTimes(1);
    expect(mockMarkRead).toHaveBeenCalledWith(SESSION_A);
  });

  // ── AC-2: no-op when ref.current is null ─────────────────────────────────
  it("no-ops and does not construct IntersectionObserver when ref.current is null", () => {
    const { wrapper } = createWrapper();
    renderHook(
      () => {
        const ref = useTestRef(null);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );
    expect(MockIntersectionObserver).not.toHaveBeenCalled();
    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  // ── AC-3: fires markRead after 500ms continuous visibility ────────────────
  it("fires markRead exactly once after 500ms of continuous visibility", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    // Enter intersection
    act(() => {
      triggerIntersect(el, true);
    });

    // Not fired yet — timer hasn't elapsed
    expect(mockMarkRead).not.toHaveBeenCalled();

    // Advance 500ms
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    expect(mockMarkRead).toHaveBeenCalledTimes(1);
  });

  // ── AC-4: 5s dedup suppresses re-fire for same sessionId ─────────────────
  it("second visibility cycle within 5s of a prior fire does NOT re-fire (same sessionId)", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    // First fire
    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(mockMarkRead).toHaveBeenCalledTimes(1);

    // Exit + re-enter within 5s
    act(() => {
      triggerIntersect(el, false);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    }); // only 1s since first fire
    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    // Still only 1 call because 5s dedup hasn't elapsed
    expect(mockMarkRead).toHaveBeenCalledTimes(1);
  });

  // ── AC-5: different sessionId within 5s DOES fire ────────────────────────
  it("second visibility cycle for a DIFFERENT sessionId within 5s DOES fire", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    let sessionId = SESSION_A;
    const { rerender } = renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    // First fire for SESSION_A
    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(mockMarkRead).toHaveBeenCalledTimes(1);

    // Switch to SESSION_B — rerender triggers the effect with the new sessionId
    act(() => {
      triggerIntersect(el, false);
    });
    sessionId = SESSION_B;
    rerender();

    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    // Second call for the different session
    expect(mockMarkRead).toHaveBeenCalledTimes(2);
  });

  // ── AC-6: visibility < 500ms does NOT fire ───────────────────────────────
  it("visibility for less than 500ms (exit before timer fires) does NOT fire", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    }); // only 300ms
    act(() => {
      triggerIntersect(el, false);
    }); // exit before 500ms
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    }); // advance well past 500ms

    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  // ── AC-7: cache patch + invalidation on 200 response ────────────────────
  it("patches last_viewed_at in cache and calls invalidateQueries on 200 response", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { queryClient, wrapper } = createWrapper();

    // Pre-populate the cache with a session row
    queryClient.setQueryData(
      ["chat-sessions", "acc_1", "all", ""],
      makeInfiniteData(SESSION_A, null),
    );

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    act(() => {
      triggerIntersect(el, true);
    });
    // Advance 500ms to fire the setTimeout, then flush the resulting async promise
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    // Yield to the microtask queue so the async fire() body completes
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockMarkRead).toHaveBeenCalled();

    // Cache should be patched
    const cachedData = queryClient.getQueryData<
      InfiniteData<ListChatSessionsResponse>
    >(["chat-sessions", "acc_1", "all", ""]);
    expect(cachedData?.pages[0].items[0].last_viewed_at).toBe(LAST_VIEWED_AT);

    // invalidateQueries was called with the prefix key
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["chat-sessions"] });
  });

  // ── AC-8: errors are swallowed (no throw, no cache mutation) ─────────────
  it("swallows errors — no throw, no cache mutation, debug log emitted", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { queryClient, wrapper } = createWrapper();

    queryClient.setQueryData(
      ["chat-sessions", "acc_1", "all", ""],
      makeInfiniteData(SESSION_A, null),
    );

    mockMarkRead.mockRejectedValueOnce(new Error("500 Internal Server Error"));
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});

    renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    act(() => {
      triggerIntersect(el, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    // Yield to the microtask queue so the async fire() catch block runs
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(debugSpy).toHaveBeenCalled();

    // Cache is untouched (last_viewed_at still null)
    const cachedData = queryClient.getQueryData<
      InfiniteData<ListChatSessionsResponse>
    >(["chat-sessions", "acc_1", "all", ""]);
    expect(cachedData?.pages[0].items[0].last_viewed_at).toBeNull();

    debugSpy.mockRestore();
  });

  // ── AC-9: cleanup on unmount disconnects observer + clears timer ─────────
  it("disconnects observer and clears pending timer on unmount (no leak, no stale fire)", async () => {
    vi.useFakeTimers();
    const el = document.createElement("div");
    const { wrapper } = createWrapper();
    const { unmount } = renderHook(
      () => {
        const ref = useTestRef(el);
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: "msg_1",
        });
      },
      { wrapper },
    );

    act(() => {
      triggerIntersect(el, true);
    }); // start the 500ms timer

    // Unmount before timer fires
    unmount();

    // Advance past 500ms — should NOT fire
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  // ── AC-10: observer re-arms onto new DOM node when latestMessageId changes ─
  it("re-arms the observer on the new element when latestMessageId changes (new assistant message)", async () => {
    vi.useFakeTimers();
    const el1 = document.createElement("div");
    const el2 = document.createElement("div");
    const { wrapper } = createWrapper();

    let currentEl = el1;
    let currentMsgId = "msg_1";

    const { rerender } = renderHook(
      () => {
        const ref = useRef<HTMLElement | null>(currentEl);
        ref.current = currentEl;
        useMarkRead({
          sessionId: SESSION_A,
          latestMessageRef: ref,
          latestMessageId: currentMsgId,
        });
      },
      { wrapper },
    );

    // First fire: el1 becomes visible → markRead fires after 500ms
    act(() => {
      triggerIntersect(el1, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(mockMarkRead).toHaveBeenCalledTimes(1);

    // Advance past the 5s per-session dedup window so the next fire isn't suppressed
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5001);
    });

    // New message arrives — ref moves to el2, latestMessageId changes → effect re-runs
    currentEl = el2;
    currentMsgId = "msg_2";
    rerender();

    // el1 should no longer have an active observer (disconnected by effect cleanup)
    expect(observerMap.has(el1)).toBe(false);
    // el2 should now be observed
    expect(observerMap.has(el2)).toBe(true);

    // el2 becomes visible → second markRead should fire
    act(() => {
      triggerIntersect(el2, true);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockMarkRead).toHaveBeenCalledTimes(2);
  });
});
