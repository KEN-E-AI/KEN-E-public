import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AutomationDetailsPage } from "./AutomationDetailsPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/workflows/automations/test-plan"]}>
      <AutomationDetailsPage />
    </MemoryRouter>,
  );
}

describe("AutomationDetailsPage", () => {
  it("renders without error inside MemoryRouter", () => {
    renderPage();
  });

  it("renders the mocked title and Active status badge", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: /sample automation/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders both Overview and Outputs tab triggers", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /outputs/i })).toBeInTheDocument();
  });

  it("shows the DAG placeholder on the default Overview tab", () => {
    renderPage();
    expect(screen.getByText("DAG renders here")).toBeInTheDocument();
    expect(screen.queryByText("No outputs yet")).not.toBeInTheDocument();
  });

  it("switches to Outputs tab and shows empty-state, hides DAG placeholder", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: /outputs/i }));
    expect(screen.getByText("No outputs yet")).toBeInTheDocument();
    expect(screen.queryByText("DAG renders here")).not.toBeInTheDocument();
  });
});
