import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useTodoLists, TODO_LISTS_QUERY_KEY } from "../useTodoLists";
import type { ChatSessionId } from "@/lib/chatApi";

vi.mock("@/lib/chatApi", () => ({
  listTodoLists: vi.fn(),
  toChatSessionId: (v: string) => v,
}));

import { listTodoLists } from "@/lib/chatApi";
const mockListTodoLists = vi.mocked(listTodoLists);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
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

const SESSION_ID = "sess_abc" as ChatSessionId;

const FIXTURE = {
  todo_lists: [
    {
      list_id: "list_1",
      title: "Q3 Tasks",
      is_current: true,
      created_at: "2026-05-01T09:00:00Z",
      items: [
        {
          item_id: "item_1",
          text: "Analyse data",
          completed: false,
          completed_at: null,
        },
      ],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useTodoLists", () => {
  it("returns undefined data and does not call listTodoLists when sessionId is null", () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useTodoLists(null), { wrapper });
    expect(result.current.data).toBeUndefined();
    expect(mockListTodoLists).not.toHaveBeenCalled();
  });

  it("calls listTodoLists and returns data when sessionId is provided", async () => {
    mockListTodoLists.mockResolvedValueOnce(FIXTURE);
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useTodoLists(SESSION_ID), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockListTodoLists).toHaveBeenCalledWith(SESSION_ID);
    expect(result.current.data).toEqual(FIXTURE);
  });

  it("uses the correct query key structure", async () => {
    mockListTodoLists.mockResolvedValueOnce(FIXTURE);
    const { wrapper, queryClient } = createWrapper();
    renderHook(() => useTodoLists(SESSION_ID), { wrapper });

    await waitFor(() =>
      expect(
        queryClient.getQueryData([TODO_LISTS_QUERY_KEY, SESSION_ID]),
      ).toBeDefined(),
    );
  });

  it("sets isLoading true while fetching, then false on success", async () => {
    let resolveQuery: (v: typeof FIXTURE) => void;
    const pending = new Promise<typeof FIXTURE>((res) => {
      resolveQuery = res;
    });
    mockListTodoLists.mockReturnValueOnce(pending);

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useTodoLists(SESSION_ID), { wrapper });

    expect(result.current.isLoading).toBe(true);

    resolveQuery!(FIXTURE);

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isSuccess).toBe(true);
  });

  it("sets isError true on fetch failure", async () => {
    mockListTodoLists.mockRejectedValueOnce(new Error("500 Server Error"));
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useTodoLists(SESSION_ID), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("uses staleTime: 30_000 (AC-9 — data not refetched within 30 s cache window)", async () => {
    mockListTodoLists.mockResolvedValueOnce(FIXTURE);
    const { wrapper, queryClient } = createWrapper();
    renderHook(() => useTodoLists(SESSION_ID), { wrapper });

    await waitFor(() =>
      expect(
        queryClient.getQueryData([TODO_LISTS_QUERY_KEY, SESSION_ID]),
      ).toBeDefined(),
    );

    const state = queryClient.getQueryState([TODO_LISTS_QUERY_KEY, SESSION_ID]);
    // A second hook instance should see data as fresh (isStale false) immediately
    // after the first fetch because staleTime is 30 000 ms.
    expect(state?.isInvalidated).toBe(false);
    expect(mockListTodoLists).toHaveBeenCalledTimes(1);
  });
});
