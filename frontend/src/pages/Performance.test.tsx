import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: {
    info: vi.fn(),
  },
}));

import Performance from "@/pages/Performance";

describe("Performance page", () => {
  it("renders the Performance header and the Dashboards section", () => {
    render(<Performance />);

    expect(
      screen.getByRole("heading", { name: "Performance" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Scheduled dashboards that automatically compile/i),
    ).toBeInTheDocument();
  });

  it("does not render a tab selector (only the Dashboards surface is built)", () => {
    render(<Performance />);

    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Analysis" }),
    ).not.toBeInTheDocument();
  });
});
