import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCreateChatSession } from "../useCreateChatSession";
import type {
  ConversationInfo,
  ChatSessionSidebarItem,
  ListChatSessionsResponse,
} from "@/lib/chatApi";

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/lib/chatApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/chatApi")>();
  return {
    ...actual,
    createChatConversation: vi.fn(),
  };
});

vi.mock("react-router-dom", () => ({
  useNavigate: vi.fn(),
}));

vi.mock("@/hooks/use-toast", () => ({
  toast: vi.fn(),
}));

import { createChatConversation } from "@/lib/chatApi";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";

const mockCreateConversation = createChatConversation as ReturnType<
  typeof vi.fn
>;
const mockUseNavigate = useNavigate as ReturnType<typeof vi.fn>;
const mockToast = toast as ReturnType<typeof vi.fn>;

// ─── Test helpers ─────────────────────────────────────────────────────────────

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function freshClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

const CHAT_SESSIONS_KEY = ["chat-sessions", "acc_test", "all", ""] as const;

function makeSidebarItem(
  overrides: Partial<ChatSessionSidebarItem> = {},
): ChatSessionSidebarItem {
  return {
    session_id: "session-abc" as ChatSessionSidebarItem["session_id"],
    title: "Existing session",
    category_id: null,
    category_name: null,
    last_message_preview: "Previous message",
    updated_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    is_agent_running: false,
    last_agent_message_at: null,
    last_viewed_at: null,
    ...overrides,
  };
}

function makeInfiniteData(
  items: ChatSessionSidebarItem[],
): InfiniteData<ListChatSessionsResponse> {
  return {
    pages: [{ items, next_cursor: null }],
    pageParams: [null],
  };
}

const mockConversationInfo: ConversationInfo = {
  session_id: "session-new-123",
  conversation_name: "My New Session",
  created_at: "2026-05-21T10:00:00Z",
  last_updated: "2026-05-21T10:00:00Z",
  message_count: 0,
  preview: null,
};

// ─── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useCreateChatSession — happy path", () => {
  it("prepends an optimistic 'Untitled session' row to every matching cache", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);

    // Deferred promise keeps the mutation in-flight so we can inspect the
    // intermediate optimistic state before onSuccess replaces the row.
    let resolveCreate: (v: ConversationInfo) => void;
    mockCreateConversation.mockReturnValue(
      new Promise<ConversationInfo>((res) => {
        resolveCreate = res;
      }),
    );

    const client = freshClient();
    const existingItem = makeSidebarItem();
    client.setQueryData(CHAT_SESSIONS_KEY, makeInfiniteData([existingItem]));

    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    act(() => {
      result.current.mutate({ account_id: "acc_test" });
    });

    // onMutate runs in the async mutation pipeline — wait for the prepend
    await waitFor(() => {
      const cache =
        client.getQueryData<InfiniteData<ListChatSessionsResponse>>(
          CHAT_SESSIONS_KEY,
        );
      expect(cache?.pages[0].items).toHaveLength(2);
    });

    const cacheAfterMutate =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(
        CHAT_SESSIONS_KEY,
      );

    const optimisticRow = cacheAfterMutate?.pages[0].items[0];
    expect(optimisticRow?.session_id).toMatch(/^optimistic-/);
    expect(optimisticRow?.title).toBe("Untitled session");
    expect(optimisticRow?.is_agent_running).toBe(false);

    // Original row is still second
    expect(cacheAfterMutate?.pages[0].items[1].session_id).toBe("session-abc");

    // Resolve to avoid unhandled-promise warnings
    act(() => {
      resolveCreate!(mockConversationInfo);
    });
  });

  it("updates ALL matching cache variants with the optimistic row", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);

    // Deferred promise keeps the mutation in-flight so we can inspect the
    // intermediate optimistic state before onSuccess replaces the row.
    let resolveCreate: (v: ConversationInfo) => void;
    mockCreateConversation.mockReturnValue(
      new Promise<ConversationInfo>((res) => {
        resolveCreate = res;
      }),
    );

    const client = freshClient();
    const KEY_ALL = ["chat-sessions", "acc_test", "all", ""] as const;
    const KEY_FILTERED = ["chat-sessions", "acc_test", "cat-123", ""] as const;
    const KEY_SEARCHED = ["chat-sessions", "acc_test", "all", "q3"] as const;

    client.setQueryData(KEY_ALL, makeInfiniteData([makeSidebarItem()]));
    client.setQueryData(
      KEY_FILTERED,
      makeInfiniteData([makeSidebarItem({ title: "Filtered session" })]),
    );
    client.setQueryData(
      KEY_SEARCHED,
      makeInfiniteData([makeSidebarItem({ title: "Q3 session" })]),
    );

    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    act(() => {
      result.current.mutate({ account_id: "acc_test" });
    });

    // Wait for onMutate to propagate across all cache variants
    await waitFor(() => {
      const cache =
        client.getQueryData<InfiniteData<ListChatSessionsResponse>>(KEY_ALL);
      expect(cache?.pages[0].items[0].session_id).toMatch(/^optimistic-/);
    });

    // All three variants get the optimistic prepend
    const cacheAll =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(KEY_ALL);
    const cacheFiltered =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(KEY_FILTERED);
    const cacheSearched =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(KEY_SEARCHED);

    expect(cacheAll?.pages[0].items[0].session_id).toMatch(/^optimistic-/);
    expect(cacheFiltered?.pages[0].items[0].session_id).toMatch(/^optimistic-/);
    expect(cacheSearched?.pages[0].items[0].session_id).toMatch(/^optimistic-/);

    // Resolve to avoid unhandled-promise warnings
    act(() => {
      resolveCreate!(mockConversationInfo);
    });
  });

  it("replaces the optimistic row with the real server row on success", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockResolvedValue(mockConversationInfo);

    const client = freshClient();
    client.setQueryData(
      CHAT_SESSIONS_KEY,
      makeInfiniteData([makeSidebarItem()]),
    );

    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const cacheAfter =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(
        CHAT_SESSIONS_KEY,
      );

    // Two rows: the real new session + the original existing session
    expect(cacheAfter?.pages[0].items).toHaveLength(2);

    const realRow = cacheAfter?.pages[0].items[0];
    expect(realRow?.session_id).toBe("session-new-123");
    expect(realRow?.title).toBe("My New Session");
    // No optimistic id remains in the cache
    const hasOptimistic = cacheAfter?.pages[0].items.some((i) =>
      String(i.session_id).startsWith("optimistic-"),
    );
    expect(hasOptimistic).toBe(false);
  });

  it("navigates to /chat?session=<id> with { replace: true } on success", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockResolvedValue(mockConversationInfo);

    const client = freshClient();
    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(navigateMock).toHaveBeenCalledOnce();
    expect(navigateMock).toHaveBeenCalledWith(
      `/chat?session=${encodeURIComponent("session-new-123")}`,
      { replace: true },
    );
  });

  it("derives 'idle' status from the optimistic row (no false-positive status dot)", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    // Hold the promise so we can inspect while in-flight
    let resolveCreate: (v: ConversationInfo) => void;
    mockCreateConversation.mockReturnValue(
      new Promise<ConversationInfo>((res) => {
        resolveCreate = res;
      }),
    );

    const client = freshClient();
    client.setQueryData(CHAT_SESSIONS_KEY, makeInfiniteData([]));

    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    act(() => {
      result.current.mutate({ account_id: "acc_test" });
    });

    // Wait for onMutate to insert the optimistic row
    await waitFor(() => {
      const cache =
        client.getQueryData<InfiniteData<ListChatSessionsResponse>>(
          CHAT_SESSIONS_KEY,
        );
      expect(cache?.pages[0].items).toHaveLength(1);
    });

    const cache =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(
        CHAT_SESSIONS_KEY,
      );
    const optimisticRow = cache?.pages[0].items[0];

    // Verify deriveSessionStatus would return "idle"
    expect(optimisticRow?.is_agent_running).toBe(false);
    expect(optimisticRow?.last_agent_message_at).toBeNull();

    // Resolve to avoid unhandled promise warnings
    act(() => {
      resolveCreate!(mockConversationInfo);
    });
  });
});

describe("useCreateChatSession — error path", () => {
  it("rolls back every cache to the pre-mutation snapshot on error", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockRejectedValue(new Error("Network error"));

    const client = freshClient();
    const existingItem = makeSidebarItem();
    client.setQueryData(CHAT_SESSIONS_KEY, makeInfiniteData([existingItem]));

    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    const cacheAfter =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(
        CHAT_SESSIONS_KEY,
      );

    // Cache is restored to the original single item — no ghost row
    expect(cacheAfter?.pages[0].items).toHaveLength(1);
    expect(cacheAfter?.pages[0].items[0].session_id).toBe("session-abc");
    expect(
      cacheAfter?.pages[0].items.some((i) =>
        String(i.session_id).startsWith("optimistic-"),
      ),
    ).toBe(false);
  });

  it("shows a destructive toast on error", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockRejectedValue(new Error("Network error"));

    const client = freshClient();
    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(mockToast).toHaveBeenCalledOnce();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "destructive" }),
    );
  });

  it("does not navigate on error", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockRejectedValue(new Error("Network error"));

    const client = freshClient();
    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("rolls back multiple cache variants independently on error", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockRejectedValue(new Error("fail"));

    const client = freshClient();
    const KEY_A = ["chat-sessions", "acc_test", "all", ""] as const;
    const KEY_B = ["chat-sessions", "acc_test", "cat-1", ""] as const;

    const itemA = makeSidebarItem({ title: "Session A" });
    const itemB = makeSidebarItem({
      session_id: "session-b" as ChatSessionSidebarItem["session_id"],
      title: "Session B",
    });
    client.setQueryData(KEY_A, makeInfiniteData([itemA]));
    client.setQueryData(KEY_B, makeInfiniteData([itemB]));

    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    const cacheA =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(KEY_A);
    const cacheB =
      client.getQueryData<InfiniteData<ListChatSessionsResponse>>(KEY_B);

    expect(cacheA?.pages[0].items).toHaveLength(1);
    expect(cacheA?.pages[0].items[0].title).toBe("Session A");
    expect(cacheB?.pages[0].items).toHaveLength(1);
    expect(cacheB?.pages[0].items[0].title).toBe("Session B");
  });
});

describe("useCreateChatSession — no sidebar mounted", () => {
  it("completes successfully without throwing when no chat-sessions cache exists", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);
    mockCreateConversation.mockResolvedValue(mockConversationInfo);

    // Completely empty client — no cache entries
    const client = freshClient();
    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      result.current.mutate({ account_id: "acc_test" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Navigation still happens even though no sidebar cache was updated
    expect(navigateMock).toHaveBeenCalledOnce();
    expect(navigateMock).toHaveBeenCalledWith(
      `/chat?session=${encodeURIComponent("session-new-123")}`,
      { replace: true },
    );
    // No toast
    expect(mockToast).not.toHaveBeenCalled();
  });
});

describe("useCreateChatSession — isPending", () => {
  it("is true while the mutation is in-flight and false before/after", async () => {
    const navigateMock = vi.fn();
    mockUseNavigate.mockReturnValue(navigateMock);

    let resolveCreate: (v: ConversationInfo) => void;
    mockCreateConversation.mockReturnValue(
      new Promise<ConversationInfo>((res) => {
        resolveCreate = res;
      }),
    );

    const client = freshClient();
    const { result } = renderHook(() => useCreateChatSession(), {
      wrapper: makeWrapper(client),
    });

    // Initially not pending
    expect(result.current.isPending).toBe(false);

    act(() => {
      result.current.mutate({ account_id: "acc_test" });
    });

    // Pending while in-flight (mutation pipeline is async)
    await waitFor(() => expect(result.current.isPending).toBe(true));

    // Resolve
    await act(async () => {
      resolveCreate!(mockConversationInfo);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.isPending).toBe(false);
  });
});
