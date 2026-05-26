import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { TodoListsPanel } from "../TodoListsPanel";
import { runAxe } from "@/test/axe";
import type { ChatSessionId, ListTodosResponse } from "@/lib/chatApi";

vi.mock("@/hooks/useTodoLists", () => ({
  useTodoLists: vi.fn(),
}));

import { useTodoLists } from "@/hooks/useTodoLists";
const mockUseTodoLists = vi.mocked(useTodoLists);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

const SESSION_ID = "sess_abc" as ChatSessionId;

const LIST_WITH_ITEMS: ListTodosResponse = {
  todo_lists: [
    {
      list_id: "list_1",
      title: "Q3 Campaign Tasks",
      is_current: true,
      created_at: "2026-05-01T09:00:00Z",
      items: [
        {
          item_id: "item_1",
          text: "Analyse performance data",
          completed: true,
          completed_at: "2026-05-01T10:00:00Z",
        },
        {
          item_id: "item_2",
          text: "Draft recommendations",
          completed: false,
          completed_at: null,
        },
      ],
    },
  ],
};

const INACTIVE_LIST: ListTodosResponse = {
  todo_lists: [
    {
      list_id: "list_2",
      title: "Old Tasks",
      is_current: false,
      created_at: "2026-04-01T09:00:00Z",
      items: [],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── TC-1: null sessionId renders nothing ───────────────────────────────────

describe("TodoListsPanel", () => {
  it("TC-1: renders nothing when sessionId is null", () => {
    mockUseTodoLists.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      isSuccess: false,
    } as ReturnType<typeof useTodoLists>);
    const { container } = render(<TodoListsPanel sessionId={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  // ─── TC-2: loading skeletons ───────────────────────────────────────────────

  it("TC-2: shows loading skeletons while fetching", () => {
    mockUseTodoLists.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      isSuccess: false,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.getByLabelText("Loading todo lists")).toBeInTheDocument();
  });

  // ─── TC-3: error state ────────────────────────────────────────────────────

  it("TC-3: shows error message on fetch failure", () => {
    mockUseTodoLists.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      isSuccess: false,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("Failed to load todo lists.")).toBeInTheDocument();
  });

  // ─── TC-4: empty state ────────────────────────────────────────────────────

  it("TC-4: shows empty state message when no todo lists", () => {
    mockUseTodoLists.mockReturnValue({
      data: { todo_lists: [] },
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("No todo lists yet.")).toBeInTheDocument();
  });

  // ─── TC-5: renders list title and Active badge ────────────────────────────

  it("TC-5: renders list title and Active badge for is_current=true", () => {
    mockUseTodoLists.mockReturnValue({
      data: LIST_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("Q3 Campaign Tasks")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  // ─── TC-6: no Active badge for is_current=false ───────────────────────────

  it("TC-6: does not render Active badge for is_current=false", () => {
    mockUseTodoLists.mockReturnValue({
      data: INACTIVE_LIST,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.queryByText("Active")).not.toBeInTheDocument();
  });

  // ─── TC-7: current list is expanded by default ────────────────────────────

  it("TC-7: current list (is_current=true) starts expanded showing items", () => {
    mockUseTodoLists.mockReturnValue({
      data: LIST_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.getByText("Analyse performance data")).toBeInTheDocument();
    expect(screen.getByText("Draft recommendations")).toBeInTheDocument();
  });

  // ─── TC-8: click toggle collapses then expands ────────────────────────────

  it("TC-8: clicking toggle button collapses then expands list", () => {
    mockUseTodoLists.mockReturnValue({
      data: LIST_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);

    const toggle = screen.getByRole("button", { name: /Q3 Campaign Tasks/i });
    // Currently expanded — items visible
    expect(screen.getByText("Analyse performance data")).toBeInTheDocument();

    // Collapse
    fireEvent.click(toggle);
    expect(
      screen.queryByText("Analyse performance data"),
    ).not.toBeInTheDocument();

    // Expand again
    fireEvent.click(toggle);
    expect(screen.getByText("Analyse performance data")).toBeInTheDocument();
  });

  // ─── TC-9: completed item has line-through ────────────────────────────────

  it("TC-9: completed item text has line-through class", () => {
    mockUseTodoLists.mockReturnValue({
      data: LIST_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    const completedText = screen.getByText("Analyse performance data");
    expect(completedText.className).toContain("line-through");
  });

  // ─── TC-10: progress fraction rendered ────────────────────────────────────

  it("TC-10: renders completed/total fraction", () => {
    mockUseTodoLists.mockReturnValue({
      data: LIST_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    render(<TodoListsPanel sessionId={SESSION_ID} />);
    expect(screen.getByLabelText("1 of 2 completed")).toBeInTheDocument();
  });

  // ─── TC-11: axe accessibility ─────────────────────────────────────────────

  it("TC-11: passes axe accessibility check with a populated list", async () => {
    mockUseTodoLists.mockReturnValue({
      data: LIST_WITH_ITEMS,
      isLoading: false,
      isError: false,
      isSuccess: true,
    } as ReturnType<typeof useTodoLists>);
    const { container } = render(<TodoListsPanel sessionId={SESSION_ID} />);
    const results = await runAxe(container);
    expect(results).toHaveNoViolations();
  });
});
