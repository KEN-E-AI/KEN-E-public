import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent, {
  PointerEventsCheckLevel,
} from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { CategoriesDropdown } from "../CategoriesDropdown";
import { runAxe } from "@/test/axe";
import { CategoryExistsError } from "@/lib/chatApi";
import type { ChatCategoryId, ChatSessionId } from "@/lib/chatApi";

vi.mock("@/hooks/useChatCategories", () => ({
  useChatCategories: vi.fn(),
}));

import { useChatCategories } from "@/hooks/useChatCategories";
import type { UseChatCategoriesResult } from "@/hooks/useChatCategories";
const mockUseChatCategories = vi.mocked(useChatCategories);

// ─── Test fixtures ────────────────────────────────────────────────────────────

const CAT_A_ID = "cat_aaa" as ChatCategoryId;
const CAT_B_ID = "cat_bbb" as ChatCategoryId;
const CAT_C_ID = "cat_ccc" as ChatCategoryId;
const SESSION_ID = "sess_xyz" as ChatSessionId;

const CATEGORIES = [
  {
    category_id: CAT_B_ID,
    name: "Beta Campaign",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    category_id: CAT_A_ID,
    name: "Alpha Campaign",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    category_id: CAT_C_ID,
    name: "Zeta Campaign",
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
  },
];

// ─── Mock helpers ─────────────────────────────────────────────────────────────

function createMockHook(
  overrides: Partial<UseChatCategoriesResult> = {},
): UseChatCategoriesResult {
  return {
    list: {
      data: CATEGORIES,
      isPending: false,
      isError: false,
      isSuccess: true,
    } as UseChatCategoriesResult["list"],
    create: {
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({
        category_id: "new_id" as ChatCategoryId,
        name: "New Cat",
        created_at: "",
        updated_at: "",
      }),
      isPending: false,
      isError: false,
      isSuccess: false,
    } as unknown as UseChatCategoriesResult["create"],
    remove: {
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue(undefined),
      isPending: false,
      isError: false,
      isSuccess: false,
    } as unknown as UseChatCategoriesResult["remove"],
    assign: {
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue(undefined),
      isPending: false,
      isError: false,
      isSuccess: false,
    } as unknown as UseChatCategoriesResult["assign"],
    ...overrides,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── TC-1: "All sessions" variant guard ───────────────────────────────────────

describe("CategoriesDropdown", () => {
  it("TC-1a: filter variant shows 'All sessions' option in the open menu", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    expect(
      screen.getByRole("menuitem", { name: /all sessions/i }),
    ).toBeInTheDocument();
  });

  it("TC-1b: assign variant does NOT show 'All sessions'", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown
        variant="assign"
        sessionId={SESSION_ID}
        currentCategoryId={null}
      />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /uncategorized/i }));
    expect(
      screen.queryByRole("menuitem", { name: /all sessions/i }),
    ).not.toBeInTheDocument();
  });

  // ─── TC-2: Inline create form ─────────────────────────────────────────────

  it("TC-2a: typing a name and clicking Add calls create.mutateAsync", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const createMutateAsync = vi.fn().mockResolvedValue({
      category_id: "new_id" as ChatCategoryId,
      name: "Brand New",
      created_at: "",
      updated_at: "",
    });
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        create: {
          mutate: vi.fn(),
          mutateAsync: createMutateAsync,
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["create"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(screen.getByRole("button", { name: /new category/i }));
    const input = screen.getByRole("textbox", { name: /new category name/i });
    // Use fireEvent.change to reliably update the controlled input value
    fireEvent.change(input, { target: { value: "Brand New" } });
    // Click the Add button (submission path)
    const addBtn = await waitFor(() =>
      screen.getByRole("button", { name: /^add$/i }),
    );
    fireEvent.click(addBtn);
    await waitFor(() =>
      expect(createMutateAsync).toHaveBeenCalledWith("Brand New"),
    );
  });

  it("TC-2b: X button closes the create form", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(screen.getByRole("button", { name: /new category/i }));
    expect(
      screen.getByRole("textbox", { name: /new category name/i }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /cancel new category/i }),
    );
    expect(
      screen.queryByRole("textbox", { name: /new category name/i }),
    ).not.toBeInTheDocument();
  });

  // ─── TC-3: Duplicate name error ───────────────────────────────────────────

  it("TC-3: 409 creates an inline error referencing the attempted name", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const createMutateAsync = vi
      .fn()
      .mockRejectedValue(new CategoryExistsError(null, "Q3 Campaign"));
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        create: {
          mutate: vi.fn(),
          mutateAsync: createMutateAsync,
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["create"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(screen.getByRole("button", { name: /new category/i }));
    await user.type(
      screen.getByRole("textbox", { name: /new category name/i }),
      "Q3 Campaign",
    );
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /Q3 Campaign.*already exists/i,
      ),
    );
  });

  // ─── TC-4: Trash-icon delete confirm ─────────────────────────────────────

  it("TC-4a: trash icon opens AlertDialog", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    const trashBtn = screen.getByRole("button", {
      name: /delete category alpha campaign/i,
    });
    await user.click(trashBtn);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(
      screen.getByText(/sessions will return to uncategorized/i),
    ).toBeInTheDocument();
  });

  it("TC-4b: Cancel does NOT fire remove.mutateAsync", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const removeMutateAsync = vi.fn().mockResolvedValue(undefined);
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        remove: {
          mutate: vi.fn(),
          mutateAsync: removeMutateAsync,
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["remove"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(
      screen.getByRole("button", { name: /delete category alpha campaign/i }),
    );
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(removeMutateAsync).not.toHaveBeenCalled();
  });

  it("TC-4c: destructive action fires remove.mutateAsync with category id", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const removeMutateAsync = vi.fn().mockResolvedValue(undefined);
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        remove: {
          mutate: vi.fn(),
          mutateAsync: removeMutateAsync,
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["remove"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(
      screen.getByRole("button", { name: /delete category alpha campaign/i }),
    );
    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await waitFor(() =>
      expect(removeMutateAsync).toHaveBeenCalledWith(CAT_A_ID),
    );
  });

  // ─── TC-5: Filter onChange ────────────────────────────────────────────────

  it("TC-5a: clicking a category row fires onChange with category_id", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const onChange = vi.fn();
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={onChange} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(screen.getByRole("menuitem", { name: /alpha campaign/i }));
    expect(onChange).toHaveBeenCalledWith(CAT_A_ID);
  });

  it("TC-5b: clicking 'All sessions' fires onChange(null)", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const onChange = vi.fn();
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown
        variant="filter"
        value={CAT_A_ID}
        onChange={onChange}
      />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /alpha campaign/i }));
    await user.click(screen.getByRole("menuitem", { name: /all sessions/i }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  // ─── TC-6: Assign variant mutations ─────────────────────────────────────

  it("TC-6a: assign variant clicking a category calls assign.mutate with sessionId + categoryId", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const assignMutate = vi.fn();
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        assign: {
          mutate: assignMutate,
          mutateAsync: vi.fn(),
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["assign"],
      }),
    );
    render(
      <CategoriesDropdown
        variant="assign"
        sessionId={SESSION_ID}
        currentCategoryId={null}
      />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /uncategorized/i }));
    await user.click(screen.getByRole("menuitem", { name: /alpha campaign/i }));
    expect(assignMutate).toHaveBeenCalledWith({
      sessionId: SESSION_ID,
      categoryId: CAT_A_ID,
    });
  });

  it("TC-6b: assign variant clicking 'Uncategorized' calls assign.mutate with categoryId: null", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const assignMutate = vi.fn();
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        assign: {
          mutate: assignMutate,
          mutateAsync: vi.fn(),
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["assign"],
      }),
    );
    render(
      <CategoriesDropdown
        variant="assign"
        sessionId={SESSION_ID}
        currentCategoryId={CAT_A_ID}
      />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /alpha campaign/i }));
    await user.click(screen.getByRole("menuitem", { name: /uncategorized/i }));
    expect(assignMutate).toHaveBeenCalledWith({
      sessionId: SESSION_ID,
      categoryId: null,
    });
  });

  // ─── TC-7: Keyboard navigation ───────────────────────────────────────────

  it("TC-7: arrow-key events on the menu do not throw", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    // Arrow-down then arrow-up — Radix handles the roving tabindex
    await expect(user.keyboard("{ArrowDown}")).resolves.not.toThrow();
    await expect(user.keyboard("{ArrowUp}")).resolves.not.toThrow();
  });

  // ─── TC-8: ARIA roles and labels ─────────────────────────────────────────

  it("TC-8a: trash buttons have aria-label 'Delete category {name}'", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    expect(
      screen.getByRole("button", { name: "Delete category Alpha Campaign" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete category Beta Campaign" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete category Zeta Campaign" }),
    ).toBeInTheDocument();
  });

  it("TC-8b: the dropdown content has role='menu'", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  // ─── TC-9: Alphabetical sort stability ───────────────────────────────────

  it("TC-9: categories render in alphabetical order (case-insensitive) and are stable", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    const { rerender } = render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    const items = screen.getAllByRole("menuitem");
    const names = items
      .map((el) => el.textContent?.replace(/^[\s✓]*/, "").trim())
      .filter(Boolean);
    const categoryNames = names.filter(
      (n) =>
        n && ["Alpha Campaign", "Beta Campaign", "Zeta Campaign"].includes(n),
    );
    expect(categoryNames).toEqual([
      "Alpha Campaign",
      "Beta Campaign",
      "Zeta Campaign",
    ]);

    // Force re-render and confirm stable
    rerender(
      <CategoriesDropdown
        variant="filter"
        value={CAT_A_ID}
        onChange={vi.fn()}
      />,
    );
    const itemsAfter = screen.getAllByRole("menuitem");
    const namesAfter = itemsAfter
      .map((el) => el.textContent?.replace(/^[\s✓]*/, "").trim())
      .filter(Boolean);
    const categoryNamesAfter = namesAfter.filter(
      (n) =>
        n && ["Alpha Campaign", "Beta Campaign", "Zeta Campaign"].includes(n),
    );
    expect(categoryNamesAfter).toEqual([
      "Alpha Campaign",
      "Beta Campaign",
      "Zeta Campaign",
    ]);
  });

  // ─── TC-10: axe accessibility ─────────────────────────────────────────────

  it("TC-10: open menu with 3 categories passes axe", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(createMockHook());
    const { container } = render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    const results = await runAxe(container);
    expect(results).toHaveNoViolations();
  });

  // ─── TC-11: data-testid anchors (CH-42 E2E contract) ─────────────────────

  it("TC-11a: filter variant trigger has data-testid='categories-dropdown-filter-trigger'", () => {
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    expect(
      screen.getByTestId("categories-dropdown-filter-trigger"),
    ).toBeInTheDocument();
  });

  it("TC-11b: assign variant trigger has data-testid='categories-dropdown-assign-trigger'", () => {
    mockUseChatCategories.mockReturnValue(createMockHook());
    render(
      <CategoriesDropdown
        variant="assign"
        sessionId={SESSION_ID}
        currentCategoryId={null}
      />,
      { wrapper: createWrapper() },
    );
    expect(
      screen.getByTestId("categories-dropdown-assign-trigger"),
    ).toBeInTheDocument();
  });

  // ─── TC-12: list.isError renders distinguishable from empty ──────────────

  it("TC-12: list.isError renders an alert distinguishable from the empty state", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        list: {
          data: undefined,
          isPending: false,
          isError: true,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["list"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load categories/i);
    expect(screen.queryByText(/no categories yet/i)).not.toBeInTheDocument();
  });

  // ─── TC-13: unexpected catch failures emit console.error ─────────────────

  it("TC-13a: unexpected create failure (non-CategoryExistsError) emits console.error", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const createMutateAsync = vi
      .fn()
      .mockRejectedValue(new Error("network down"));
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        create: {
          mutate: vi.fn(),
          mutateAsync: createMutateAsync,
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["create"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(screen.getByRole("button", { name: /new category/i }));
    await user.type(screen.getByLabelText(/new category name/i), "Foo");
    await user.click(screen.getByRole("button", { name: /add/i }));

    expect(createMutateAsync).toHaveBeenCalled();
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining("CategoriesDropdown.create: unexpected error"),
      expect.any(Error),
    );
    errSpy.mockRestore();
  });

  it("TC-13b: unexpected delete failure emits console.error", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const removeMutateAsync = vi
      .fn()
      .mockRejectedValue(new Error("network down"));
    mockUseChatCategories.mockReturnValue(
      createMockHook({
        remove: {
          mutate: vi.fn(),
          mutateAsync: removeMutateAsync,
          isPending: false,
          isError: false,
          isSuccess: false,
        } as unknown as UseChatCategoriesResult["remove"],
      }),
    );
    render(
      <CategoriesDropdown variant="filter" value={null} onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );
    await user.click(screen.getByRole("button", { name: /all sessions/i }));
    await user.click(
      screen.getByRole("button", { name: /delete category alpha campaign/i }),
    );
    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(removeMutateAsync).toHaveBeenCalled();
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining("CategoriesDropdown.delete: unexpected error"),
      expect.any(Error),
    );
    errSpy.mockRestore();
  });
});
