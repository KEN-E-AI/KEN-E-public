import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionsSidebar } from "./SessionsSidebar";

describe("SessionsSidebar (stub)", () => {
  test("renders collapsed by default with the testid hook", () => {
    render(<SessionsSidebar sessions={[]} />);

    expect(screen.getByTestId("sessions-sidebar")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /expand sessions sidebar/i }),
    ).toBeInTheDocument();
  });

  test("expands to full sidebar when expand control is clicked", async () => {
    const user = userEvent.setup();
    render(<SessionsSidebar sessions={[]} />);

    await user.click(
      screen.getByRole("button", { name: /expand sessions sidebar/i }),
    );

    expect(
      screen.getByRole("heading", { name: /sessions/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /search sessions/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/no sessions found/i)).toBeInTheDocument();
  });
});
