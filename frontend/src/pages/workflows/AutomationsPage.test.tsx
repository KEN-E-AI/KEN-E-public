import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AutomationsPage from "./AutomationsPage";
import { EmptyState } from "./components/EmptyState";

describe("AutomationsPage", () => {
  it("renders the PRD empty-state heading verbatim", () => {
    render(
      <MemoryRouter>
        <AutomationsPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: /schedule recurring work/i }),
    ).toBeInTheDocument();
  });

  it("renders the PRD empty-state description verbatim", () => {
    render(
      <MemoryRouter>
        <AutomationsPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByText("Let KEN-E take it from here."),
    ).toBeInTheDocument();
  });

  it("renders the CTA button with correct label", () => {
    render(
      <MemoryRouter>
        <AutomationsPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: /create an automation/i }),
    ).toBeInTheDocument();
  });

  it("CTA button click does not throw", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AutomationsPage />
      </MemoryRouter>,
    );
    await user.click(
      screen.getByRole("button", { name: /create an automation/i }),
    );
  });
});

describe("EmptyState — CTA handler", () => {
  it("invokes onAction when the CTA button is clicked", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();

    render(
      <EmptyState
        title="Schedule recurring work."
        description="Let KEN-E take it from here."
        actionLabel="Create an automation"
        onAction={onAction}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /create an automation/i }),
    );
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("renders no CTA button when actionLabel is omitted", () => {
    render(
      <EmptyState
        title="Schedule recurring work."
        description="Let KEN-E take it from here."
      />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
