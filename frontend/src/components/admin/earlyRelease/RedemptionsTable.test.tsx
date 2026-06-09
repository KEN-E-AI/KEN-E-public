import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RedemptionsTable } from "./RedemptionsTable";
import type { EarlyReleaseRedemption } from "@/data/admin-earlyReleaseApi";

const sampleRedemptions: EarlyReleaseRedemption[] = [
  {
    user_id: "uid-1",
    email: "alice@example.com",
    org_id: "org-111",
    redeemed_at: "2025-03-01T10:00:00Z",
  },
  {
    user_id: "uid-2",
    email: "bob@example.com",
    org_id: "org-222",
    redeemed_at: "2025-03-02T11:00:00Z",
  },
];

describe("RedemptionsTable", () => {
  it("renders loading skeletons when isLoading is true", () => {
    const { container } = render(
      <RedemptionsTable
        redemptions={[]}
        nextCursor={null}
        isLoading={true}
        isLoadingMore={false}
        onLoadMore={vi.fn()}
      />,
    );
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders empty state when there are no redemptions", () => {
    render(
      <RedemptionsTable
        redemptions={[]}
        nextCursor={null}
        isLoading={false}
        isLoadingMore={false}
        onLoadMore={vi.fn()}
      />,
    );
    expect(screen.getByText("No redemptions yet")).toBeInTheDocument();
  });

  it("renders redemption rows with email and org id", () => {
    render(
      <RedemptionsTable
        redemptions={sampleRedemptions}
        nextCursor={null}
        isLoading={false}
        isLoadingMore={false}
        onLoadMore={vi.fn()}
      />,
    );
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    expect(screen.getByText("org-111")).toBeInTheDocument();
    expect(screen.getByText("org-222")).toBeInTheDocument();
  });

  it("does not render Load more button when nextCursor is null", () => {
    render(
      <RedemptionsTable
        redemptions={sampleRedemptions}
        nextCursor={null}
        isLoading={false}
        isLoadingMore={false}
        onLoadMore={vi.fn()}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  it("renders Load more button when nextCursor is provided and calls onLoadMore on click", async () => {
    const onLoadMore = vi.fn();
    const user = userEvent.setup();

    render(
      <RedemptionsTable
        redemptions={sampleRedemptions}
        nextCursor="uid-2"
        isLoading={false}
        isLoadingMore={false}
        onLoadMore={onLoadMore}
      />,
    );

    const loadMoreBtn = screen.getByRole("button", { name: /load more/i });
    expect(loadMoreBtn).toBeInTheDocument();
    await user.click(loadMoreBtn);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it("shows 'Loading…' and disables Load more button when isLoadingMore is true", () => {
    render(
      <RedemptionsTable
        redemptions={sampleRedemptions}
        nextCursor="uid-2"
        isLoading={false}
        isLoadingMore={true}
        onLoadMore={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", { name: /loading…/i });
    expect(btn).toBeDisabled();
  });
});
