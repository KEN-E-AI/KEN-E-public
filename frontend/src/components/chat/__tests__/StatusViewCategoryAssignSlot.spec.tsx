// Unit tests for StatusViewCategoryAssignSlot (CH-40).
//
// CategoriesDropdown is mocked via a factory function so this spec is isolated from
// the stub's implementation (CategoriesDropdown.tsx is committed alongside this PR) and
// will survive CH-37 replacing the stub with the real implementation.
//
// useFeatureFlag is mocked following the pattern in useChatCategories.spec.ts:28-30.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import type { ChatCategoryId, ChatSessionId } from "@/lib/chatApi";

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("@/contexts/FeatureFlagsContext", () => ({
  useFeatureFlag: vi.fn(),
}));

vi.mock("@/components/chat/CategoriesDropdown", () => ({
  CategoriesDropdown: vi.fn(() => null),
}));

import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";
import { CategoriesDropdown } from "@/components/chat/CategoriesDropdown";
import { StatusViewCategoryAssignSlot } from "../StatusViewCategoryAssignSlot";

const mockUseFeatureFlag = vi.mocked(useFeatureFlag);
const mockCategoriesDropdown = vi.mocked(CategoriesDropdown);

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const SESSION_ID = "sess_abc" as ChatSessionId;
const CATEGORY_ID = "cat_xyz" as ChatCategoryId;

// ─── Setup ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("StatusViewCategoryAssignSlot", () => {
  it("renders null when chat_categories_enabled flag is off", () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default",
      isLoading: false,
    });

    const { container } = render(
      <StatusViewCategoryAssignSlot
        sessionId={SESSION_ID}
        currentCategoryId={CATEGORY_ID}
      />,
    );

    expect(container.firstChild).toBeNull();
    expect(mockCategoriesDropdown).not.toHaveBeenCalled();
  });

  it("renders CategoriesDropdown with variant=assign when flag is on", () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "default",
      isLoading: false,
    });

    render(
      <StatusViewCategoryAssignSlot
        sessionId={SESSION_ID}
        currentCategoryId={CATEGORY_ID}
      />,
    );

    expect(mockCategoriesDropdown).toHaveBeenCalledTimes(1);
    expect(mockCategoriesDropdown).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: "assign",
        sessionId: SESSION_ID,
        currentCategoryId: CATEGORY_ID,
      }),
      expect.anything(),
    );
  });

  it("renders null while flag evaluation is loading", () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default",
      isLoading: true,
    });

    const { container } = render(
      <StatusViewCategoryAssignSlot
        sessionId={SESSION_ID}
        currentCategoryId={CATEGORY_ID}
      />,
    );

    expect(container.firstChild).toBeNull();
    expect(mockCategoriesDropdown).not.toHaveBeenCalled();
  });

  it("forwards currentCategoryId=null to CategoriesDropdown", () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "default",
      isLoading: false,
    });

    render(
      <StatusViewCategoryAssignSlot
        sessionId={SESSION_ID}
        currentCategoryId={null}
      />,
    );

    expect(mockCategoriesDropdown).toHaveBeenCalledTimes(1);
    expect(mockCategoriesDropdown).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: "assign",
        sessionId: SESSION_ID,
        currentCategoryId: null,
      }),
      expect.anything(),
    );
  });

  // CH-42 E2E selector contract: the slot wrapper must expose
  // data-testid="status-view-category-assign-slot" so Playwright scopes
  // assign-dropdown locators away from the sidebar filter variant.
  it("wraps the dropdown in a div with data-testid='status-view-category-assign-slot'", () => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: true,
      reason: "default",
      isLoading: false,
    });

    const { getByTestId } = render(
      <StatusViewCategoryAssignSlot
        sessionId={SESSION_ID}
        currentCategoryId={CATEGORY_ID}
      />,
    );

    expect(getByTestId("status-view-category-assign-slot")).toBeInTheDocument();
  });
});
