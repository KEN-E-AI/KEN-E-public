import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useChatCategories,
  CHAT_CATEGORIES_QUERY_KEY,
} from "../useChatCategories";
import type { ChatCategoryId, ChatSessionId } from "@/lib/chatApi";
import { CategoryExistsError } from "@/lib/chatApi";
import { CHAT_SESSIONS_QUERY_KEY } from "../useChatSessions";

// ─── Module mocks ─────────────────────────────────────────────────────────────

// Spread the real chatApi so CategoryExistsError keeps its real implementation;
// only the four API functions are stubbed out (pattern from SessionsSidebar.test.tsx).
vi.mock("@/lib/chatApi", async (importActual) => {
  const real = await importActual<typeof import("@/lib/chatApi")>();
  return {
    ...real,
    listChatCategories: vi.fn(),
    createChatCategory: vi.fn(),
    deleteChatCategory: vi.fn(),
    assignSessionCategory: vi.fn(),
  };
});

vi.mock("@/contexts/FeatureFlagsContext", () => ({
  useFeatureFlag: vi.fn(),
}));

vi.mock("../useChatSessions", () => ({
  CHAT_SESSIONS_QUERY_KEY: "chat-sessions",
}));

import {
  listChatCategories,
  createChatCategory,
  deleteChatCategory,
  assignSessionCategory,
} from "@/lib/chatApi";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";

const mockListChatCategories = vi.mocked(listChatCategories);
const mockCreateChatCategory = vi.mocked(createChatCategory);
const mockDeleteChatCategory = vi.mocked(deleteChatCategory);
const mockAssignSessionCategory = vi.mocked(assignSessionCategory);
const mockUseFeatureFlag = vi.mocked(useFeatureFlag);

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const CATEGORY_ID = "cat_abc" as ChatCategoryId;
const SESSION_ID = "sess_abc" as ChatSessionId;
const CATEGORY_FIXTURE = {
  category_id: CATEGORY_ID,
  name: "Q3 Campaigns",
  created_at: "2026-05-01T09:00:00Z",
  updated_at: "2026-05-01T09:00:00Z",
};

// ─── Helper ───────────────────────────────────────────────────────────────────

function createWrapper(queryClient?: QueryClient) {
  const qc =
    queryClient ??
    new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    });
  return {
    queryClient: qc,
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: flag on, list returns empty array
  mockUseFeatureFlag.mockReturnValue({
    enabled: true,
    reason: "default",
    isLoading: false,
  });
  mockListChatCategories.mockResolvedValue([]);
});

// ─── Flag-gating ──────────────────────────────────────────────────────────────

describe("useChatCategories — flag gating", () => {
  it("disables the list query when chat_categories_enabled=false", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default",
      isLoading: false,
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatCategories(), { wrapper });

    // fetchStatus idle → query did not attempt to run
    expect(result.current.list.fetchStatus).toBe("idle");
    expect(mockListChatCategories).not.toHaveBeenCalled();
  });

  it("enables the list query when chat_categories_enabled=true", async () => {
    mockListChatCategories.mockResolvedValueOnce([CATEGORY_FIXTURE]);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatCategories(), { wrapper });

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));

    expect(mockListChatCategories).toHaveBeenCalledTimes(1);
    expect(result.current.list.data).toEqual([CATEGORY_FIXTURE]);
  });

  it("idles while flag evaluations are loading, then fires on enable", async () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default",
      isLoading: true,
    });
    mockListChatCategories.mockResolvedValueOnce([CATEGORY_FIXTURE]);

    const { wrapper } = createWrapper();
    const { result, rerender } = renderHook(() => useChatCategories(), {
      wrapper,
    });

    expect(result.current.list.fetchStatus).toBe("idle");
    expect(mockListChatCategories).not.toHaveBeenCalled();

    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "default",
      isLoading: false,
    });
    rerender();

    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));
    expect(mockListChatCategories).toHaveBeenCalledTimes(1);
  });
});

// ─── Query key ────────────────────────────────────────────────────────────────

describe("useChatCategories — query key", () => {
  it("CHAT_CATEGORIES_QUERY_KEY constant value is 'chat-categories'", () => {
    expect(CHAT_CATEGORIES_QUERY_KEY).toBe("chat-categories");
  });

  it("stores query data under [CHAT_CATEGORIES_QUERY_KEY]", async () => {
    mockListChatCategories.mockResolvedValueOnce([CATEGORY_FIXTURE]);
    const { wrapper, queryClient } = createWrapper();

    renderHook(() => useChatCategories(), { wrapper });

    await waitFor(() =>
      expect(
        queryClient.getQueryData([CHAT_CATEGORIES_QUERY_KEY]),
      ).toBeDefined(),
    );

    expect(queryClient.getQueryData([CHAT_CATEGORIES_QUERY_KEY])).toEqual([
      CATEGORY_FIXTURE,
    ]);
  });
});

// ─── create mutation ──────────────────────────────────────────────────────────

describe("useChatCategories — create mutation", () => {
  it("calls createChatCategory with the name and invalidates [chat-categories]", async () => {
    mockCreateChatCategory.mockResolvedValueOnce(CATEGORY_FIXTURE);

    const { wrapper, queryClient } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useChatCategories(), { wrapper });

    await act(async () => {
      await result.current.create.mutateAsync("Q3 Campaigns");
    });

    expect(mockCreateChatCategory).toHaveBeenCalledWith("Q3 Campaigns");
    expect(spy).toHaveBeenCalledWith({
      queryKey: [CHAT_CATEGORIES_QUERY_KEY],
    });
    // Should NOT invalidate chat-sessions on create
    expect(spy).not.toHaveBeenCalledWith({
      queryKey: [CHAT_SESSIONS_QUERY_KEY],
    });
  });

  it("surfaces CategoryExistsError on the mutation error state after a 409", async () => {
    const existingError = new CategoryExistsError(CATEGORY_ID, "q3 campaigns");
    mockCreateChatCategory.mockRejectedValueOnce(existingError);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatCategories(), { wrapper });

    // mutateAsync throws — catch it so the test doesn't fail on the thrown promise
    await act(async () => {
      result.current.create.mutate("q3 campaigns");
    });

    await waitFor(() => expect(result.current.create.isError).toBe(true));

    expect(result.current.create.error).toBeInstanceOf(CategoryExistsError);
    const err = result.current.create.error as CategoryExistsError;
    expect(err.existingCategoryId).toBe(CATEGORY_ID);
    expect(err.attemptedName).toBe("q3 campaigns");
  });
});

// ─── remove mutation ──────────────────────────────────────────────────────────

describe("useChatCategories — remove mutation", () => {
  it("calls deleteChatCategory and invalidates both [chat-categories] and [chat-sessions]", async () => {
    mockDeleteChatCategory.mockResolvedValueOnce({ sessions_reassigned: 3 });

    const { wrapper, queryClient } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useChatCategories(), { wrapper });

    await act(async () => {
      await result.current.remove.mutateAsync(CATEGORY_ID);
    });

    expect(mockDeleteChatCategory).toHaveBeenCalledWith(CATEGORY_ID);

    expect(spy).toHaveBeenCalledWith({
      queryKey: [CHAT_CATEGORIES_QUERY_KEY],
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: [CHAT_SESSIONS_QUERY_KEY] });
    expect(spy).toHaveBeenCalledTimes(2);
  });
});

// ─── assign mutation ──────────────────────────────────────────────────────────

describe("useChatCategories — assign mutation", () => {
  it("calls assignSessionCategory with sessionId and categoryId, invalidates [chat-sessions]", async () => {
    mockAssignSessionCategory.mockResolvedValueOnce(undefined);

    const { wrapper, queryClient } = createWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useChatCategories(), { wrapper });

    await act(async () => {
      await result.current.assign.mutateAsync({
        sessionId: SESSION_ID,
        categoryId: CATEGORY_ID,
      });
    });

    expect(mockAssignSessionCategory).toHaveBeenCalledWith(
      SESSION_ID,
      CATEGORY_ID,
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: [CHAT_SESSIONS_QUERY_KEY] });
    // Should NOT invalidate chat-categories on assign
    expect(spy).not.toHaveBeenCalledWith({
      queryKey: [CHAT_CATEGORIES_QUERY_KEY],
    });
  });

  it("accepts null categoryId to unassign a session", async () => {
    mockAssignSessionCategory.mockResolvedValueOnce(undefined);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useChatCategories(), { wrapper });

    await act(async () => {
      await result.current.assign.mutateAsync({
        sessionId: SESSION_ID,
        categoryId: null,
      });
    });

    expect(mockAssignSessionCategory).toHaveBeenCalledWith(SESSION_ID, null);
  });
});
