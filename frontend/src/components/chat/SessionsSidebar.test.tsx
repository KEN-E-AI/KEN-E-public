import { describe, test, expect, vi, beforeAll, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import { SessionsSidebar } from "./SessionsSidebar";
import type { SessionsSidebarProps } from "./SessionsSidebar";
import type {
  ListChatSessionsResponse,
  ChatSessionSidebarItem,
} from "@/lib/chatApi";
import { toChatSessionId, toChatCategoryId } from "@/lib/chatApi";

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("@/hooks/useChatSessions", () => ({
  useChatSessions: vi.fn(),
}));

vi.mock("@/contexts/FeatureFlagsContext", () => ({
  useFeatureFlag: vi.fn(),
}));

vi.mock("@/lib/chatApi", async (importActual) => {
  const actual = await importActual<typeof import("@/lib/chatApi")>();
  return { ...actual };
});

// Stub CategoriesDropdown so sidebar tests focus on flag-gating + state
// plumbing, not on the dropdown's internal Radix wiring.
vi.mock("./CategoriesDropdown", () => ({
  CategoriesDropdown: vi.fn(),
}));

vi.mock("@/hooks/useChatCategories", () => ({
  useChatCategories: vi.fn(),
}));

import { useChatSessions } from "@/hooks/useChatSessions";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import { CategoriesDropdown } from "./CategoriesDropdown";
import { useChatCategories } from "@/hooks/useChatCategories";

const mockUseChatSessions = vi.mocked(useChatSessions);
const mockUseFeatureFlag = vi.mocked(useFeatureFlag);
const mockUseChatCategories = vi.mocked(useChatCategories);

// ─── IntersectionObserver stub (jsdom doesn't provide one) ───────────────────

beforeAll(() => {
  vi.stubGlobal(
    "IntersectionObserver",
    vi.fn(() => ({ observe: vi.fn(), disconnect: vi.fn() })),
  );
});

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeSession(
  overrides: Partial<ChatSessionSidebarItem> = {},
): ChatSessionSidebarItem {
  return {
    session_id: toChatSessionId("ses_abc123"),
    title: "Test session",
    category_id: null,
    category_name: null,
    last_message_preview: null,
    updated_at: "2024-01-01T00:00:00Z",
    created_at: "2024-01-01T00:00:00Z",
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

const emptyChatSessions = {
  data: makeInfiniteData([]),
  fetchNextPage: vi.fn(),
  hasNextPage: false,
  isFetchingNextPage: false,
  isError: false,
};

const defaultProps: SessionsSidebarProps = {
  accountId: null,
  currentSessionId: null,
  isCollapsed: false,
  onToggleCollapse: vi.fn(),
  onSessionSelect: vi.fn(),
  onNewSession: vi.fn(),
  isNewSessionPending: false,
};

function renderSidebar(props: Partial<SessionsSidebarProps> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionsSidebar {...defaultProps} {...props} />
    </QueryClientProvider>,
  );
}

// ─── Default mock values (re-applied before each test) ───────────────────────

beforeEach(() => {
  mockUseChatSessions.mockReturnValue(emptyChatSessions as any);
  mockUseFeatureFlag.mockReturnValue({
    enabled: false,
    reason: "default" as const,
    isLoading: false,
  });

  // Default: categories list is not loaded (flag off / query disabled)
  mockUseChatCategories.mockReturnValue({
    list: { data: undefined, isLoading: false, isError: false },
    create: { mutateAsync: vi.fn() },
    remove: { mutateAsync: vi.fn() },
    assign: { mutateAsync: vi.fn() },
  } as any);

  // Default CategoriesDropdown implementation (same as the old inline mock)
  vi.mocked(CategoriesDropdown).mockImplementation(
    ({ variant, value }: { variant: string; value?: string | null }) =>
      (
        <div
          data-testid="categories-dropdown"
          data-variant={variant}
          data-value={value ?? ""}
        />
      ) as unknown as React.ReactElement,
  );
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("SessionsSidebar", () => {
  // ── TC-1: Collapsed render ──────────────────────────────────────────────────
  test("TC-1: collapsed state renders 64 px rail with expand button only", () => {
    renderSidebar({ isCollapsed: true });

    expect(screen.getByTestId("sessions-sidebar")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /expand sessions sidebar/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /sessions/i }),
    ).not.toBeInTheDocument();
  });

  // ── TC-2: Expanded render ───────────────────────────────────────────────────
  test("TC-2: expanded state renders heading, New Session button, and search", () => {
    renderSidebar();

    expect(
      screen.getByRole("heading", { name: /sessions/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /new session/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /search sessions/i }),
    ).toBeInTheDocument();
  });

  // ── TC-3: Empty state — no search query ────────────────────────────────────
  test("TC-3: shows onboarding message when no sessions and no search query", () => {
    renderSidebar();

    expect(
      screen.getByText(/no sessions yet.*new session/i),
    ).toBeInTheDocument();
  });

  // ── TC-4: 300 ms search debounce ───────────────────────────────────────────
  test("TC-4: empty-state message flips to 'no sessions found' after 300 ms debounce", () => {
    vi.useFakeTimers();

    renderSidebar();

    // Before typing: onboarding message (no active search)
    expect(screen.getByText(/no sessions yet/i)).toBeInTheDocument();

    act(() => {
      fireEvent.change(
        screen.getByRole("textbox", { name: /search sessions/i }),
        { target: { value: "hello" } },
      );
    });

    // Immediately after change — debounce hasn't fired yet
    expect(screen.getByText(/no sessions yet/i)).toBeInTheDocument();

    // Advance past the 300 ms debounce window
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // debouncedQuery is now "hello" → empty state switches to search message
    expect(screen.getByText(/no sessions found/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  // ── TC-5: Session list items ────────────────────────────────────────────────
  test("TC-5: session titles from useChatSessions appear in the list", () => {
    mockUseChatSessions.mockReturnValue({
      ...emptyChatSessions,
      data: makeInfiniteData([
        makeSession({
          session_id: toChatSessionId("ses_1"),
          title: "Alpha session",
        }),
        makeSession({
          session_id: toChatSessionId("ses_2"),
          title: "Beta session",
        }),
      ]),
    } as any);

    renderSidebar();

    expect(screen.getByText("Alpha session")).toBeInTheDocument();
    expect(screen.getByText("Beta session")).toBeInTheDocument();
  });

  // ── TC-6: Active item highlight ─────────────────────────────────────────────
  test("TC-6: currently selected session item has violet border class", () => {
    const sessionId = toChatSessionId("ses_selected");
    mockUseChatSessions.mockReturnValue({
      ...emptyChatSessions,
      data: makeInfiniteData([
        makeSession({ session_id: sessionId, title: "Selected session" }),
      ]),
    } as any);

    renderSidebar({ currentSessionId: sessionId });

    const btn = screen.getByRole("button", { name: /selected session/i });
    expect(btn.className).toContain("border-[var(--color-violet-300)]");
  });

  // ── TC-7: Category filter — flag on ────────────────────────────────────────
  test("TC-7: CategoriesDropdown with variant=filter renders when chat_categories_enabled is on", () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "default" as const,
      isLoading: false,
    });

    renderSidebar();

    const dropdown = screen.getByTestId("categories-dropdown");
    expect(dropdown).toBeInTheDocument();
    expect(dropdown).toHaveAttribute("data-variant", "filter");
  });

  // ── TC-8: Category filter — flag off ───────────────────────────────────────
  test("TC-8: CategoriesDropdown is absent when chat_categories_enabled is off", () => {
    renderSidebar();

    expect(screen.queryByTestId("categories-dropdown")).not.toBeInTheDocument();
  });

  // ── TC-9: Active / needs-review counts ─────────────────────────────────────
  test("TC-9: header shows correct active and needs-review counts from first page", () => {
    const now = new Date().toISOString();
    const earlier = "2024-01-01T00:00:00Z";

    mockUseChatSessions.mockReturnValue({
      ...emptyChatSessions,
      data: makeInfiniteData([
        // 1 active: agent is running
        makeSession({
          session_id: toChatSessionId("ses_active"),
          is_agent_running: true,
        }),
        // 1 needs-review: agent replied after last view
        makeSession({
          session_id: toChatSessionId("ses_review"),
          is_agent_running: false,
          last_agent_message_at: now,
          last_viewed_at: earlier,
        }),
        // 1 idle: no new activity
        makeSession({
          session_id: toChatSessionId("ses_idle"),
          is_agent_running: false,
        }),
      ]),
    } as any);

    renderSidebar();

    expect(screen.getByText(/1 active.*1 need review/i)).toBeInTheDocument();
  });

  // ── TC-10: selectedCategoryId reset on category deletion ────────────────────
  test("TC-10: resets selectedCategoryId to null when selected category disappears from list", () => {
    const CAT_ID = toChatCategoryId("cat-001");

    // Enable categories so the filter dropdown is rendered and onChange is wired
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "default" as const,
      isLoading: false,
    });

    // Initially: categories list contains CAT_ID
    mockUseChatCategories.mockReturnValue({
      list: { data: [{ category_id: CAT_ID, name: "Q3 Campaigns" }] },
      create: { mutateAsync: vi.fn() },
      remove: { mutateAsync: vi.fn() },
      assign: { mutateAsync: vi.fn() },
    } as any);

    // Override CategoriesDropdown to capture the filter onChange callback
    let capturedOnChange: ((v: typeof CAT_ID | null) => void) | undefined;
    vi.mocked(CategoriesDropdown).mockImplementation(
      ({ variant, value, onChange }: any) => {
        if (variant === "filter") capturedOnChange = onChange;
        return (
          <div
            data-testid="categories-dropdown"
            data-variant={variant}
            data-value={value ?? ""}
          />
        );
      },
    );

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <SessionsSidebar {...defaultProps} />
      </QueryClientProvider>,
    );

    // Simulate the user selecting CAT_ID via the dropdown onChange
    act(() => {
      capturedOnChange?.(CAT_ID);
    });

    // useChatSessions should now be called with the selected category
    expect(mockUseChatSessions).toHaveBeenLastCalledWith(
      expect.objectContaining({ categoryId: CAT_ID }),
    );

    // Simulate the category being deleted: categories list no longer includes CAT_ID
    mockUseChatCategories.mockReturnValue({
      list: { data: [] },
      create: { mutateAsync: vi.fn() },
      remove: { mutateAsync: vi.fn() },
      assign: { mutateAsync: vi.fn() },
    } as any);

    // Re-render so the component picks up the updated mock and runs the useEffect
    act(() => {
      rerender(
        <QueryClientProvider client={qc}>
          <SessionsSidebar {...defaultProps} />
        </QueryClientProvider>,
      );
    });

    // After the useEffect fires, selectedCategoryId must be null →
    // useChatSessions is called without a categoryId filter
    expect(mockUseChatSessions).toHaveBeenLastCalledWith(
      expect.objectContaining({ categoryId: undefined }),
    );
  });
});
