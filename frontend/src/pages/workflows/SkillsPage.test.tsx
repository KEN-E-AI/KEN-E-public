import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SkillsPage from "./SkillsPage";
import { EmptyState } from "./components/EmptyState";

describe("SkillsPage", () => {
  it("renders the PRD empty-state description verbatim", () => {
    render(<SkillsPage />);
    expect(
      screen.getByText(/Package your team's playbooks as reusable skills/),
    ).toBeInTheDocument();
  });

  it("renders no CTA button until skill authoring lands (SK-PRD-03)", () => {
    render(<SkillsPage />);
    expect(
      screen.queryByRole("button", { name: /create a skill/i }),
    ).not.toBeInTheDocument();
  });
});

describe("EmptyState — CTA handler", () => {
  it("invokes onAction when the CTA button is clicked", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();

    render(
      <EmptyState
        title="No skills yet"
        description="Package your team's playbooks as reusable skills."
        actionLabel="Create a skill"
        onAction={onAction}
      />,
    );

    await user.click(screen.getByRole("button", { name: /create a skill/i }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
