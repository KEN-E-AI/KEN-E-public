import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AgentsPage } from "./AgentsPage";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderAgentsPage() {
  return render(
    <MemoryRouter>
      <AgentsPage />
    </MemoryRouter>,
  );
}

describe("AgentsPage", () => {
  it("renders the Figma empty-state copy", () => {
    renderAgentsPage();
    expect(
      screen.getByText("Assemble specialist agents tailored to your workflow."),
    ).toBeInTheDocument();
  });

  it("renders the 'Create an agent' CTA", () => {
    renderAgentsPage();
    expect(
      screen.getByRole("button", { name: "Create an agent" }),
    ).toBeInTheDocument();
  });

  it("navigates to /workflows/agents/new when CTA is clicked", async () => {
    renderAgentsPage();
    await userEvent.click(
      screen.getByRole("button", { name: "Create an agent" }),
    );
    expect(mockNavigate).toHaveBeenCalledWith("/workflows/agents/new");
  });
});
