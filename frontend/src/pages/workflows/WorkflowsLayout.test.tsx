import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { WorkflowsLayout } from "./WorkflowsLayout";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("WorkflowsLayout", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  it("renders three tabs in order: Agents, Skills, Automations", () => {
    render(
      <MemoryRouter initialEntries={["/workflows/agents"]}>
        <WorkflowsLayout activeTab="agents">
          <div>content</div>
        </WorkflowsLayout>
      </MemoryRouter>,
    );

    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs[0]).toHaveTextContent("Agents");
    expect(tabs[1]).toHaveTextContent("Skills");
    expect(tabs[2]).toHaveTextContent("Automations");
  });

  it("marks the active tab as aria-selected=true", () => {
    render(
      <MemoryRouter initialEntries={["/workflows/skills"]}>
        <WorkflowsLayout activeTab="skills">
          <div>content</div>
        </WorkflowsLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /agents/i })).toHaveAttribute(
      "aria-selected",
      "false",
    );
    expect(screen.getByRole("tab", { name: /skills/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: /automations/i })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("calls navigate with /workflows/automations when Automations tab is clicked", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/workflows/agents"]}>
        <WorkflowsLayout activeTab="agents">
          <div>content</div>
        </WorkflowsLayout>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("tab", { name: /automations/i }));
    expect(mockNavigate).toHaveBeenCalledWith("/workflows/automations");
  });

  it("hides header and tab strip on /workflows/agents/new", () => {
    render(
      <MemoryRouter initialEntries={["/workflows/agents/new"]}>
        <WorkflowsLayout activeTab="agents">
          <div>content</div>
        </WorkflowsLayout>
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("heading", { name: "Workflows", exact: true }),
    ).toBeNull();
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("renders children in the content area", () => {
    render(
      <MemoryRouter initialEntries={["/workflows/agents"]}>
        <WorkflowsLayout activeTab="agents">
          <div data-testid="page-content">Tab Content</div>
        </WorkflowsLayout>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("page-content")).toBeInTheDocument();
  });
});
