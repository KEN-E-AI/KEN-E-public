import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title only", () => {
    render(<EmptyState title="No items yet." />);
    expect(screen.getByText("No items yet.")).toBeInTheDocument();
  });

  it("renders title and description when description is provided", () => {
    render(
      <EmptyState
        title="No items yet."
        description="Add something to get started."
      />,
    );
    expect(screen.getByText("No items yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Add something to get started."),
    ).toBeInTheDocument();
  });

  it("does not render description paragraph when description is omitted", () => {
    const { container } = render(<EmptyState title="No items yet." />);
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("renders the CTA button when actionLabel and onAction are both provided", async () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        title="No items."
        actionLabel="Create item"
        onAction={onAction}
      />,
    );
    const button = screen.getByRole("button", { name: "Create item" });
    expect(button).toBeInTheDocument();
    await userEvent.click(button);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("does not render CTA button when actionLabel is omitted", () => {
    render(<EmptyState title="No items." onAction={vi.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("does not render CTA button when onAction is omitted", () => {
    render(<EmptyState title="No items." actionLabel="Create item" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders a custom icon when provided", () => {
    render(
      <EmptyState
        title="No items."
        icon={<span data-testid="custom-icon" />}
      />,
    );
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });
});
