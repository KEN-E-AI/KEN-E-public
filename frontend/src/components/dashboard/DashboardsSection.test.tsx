import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: {
    info: vi.fn(),
  },
}));

import { toast } from "sonner";
import { DashboardsSection } from "@/components/dashboard/DashboardsSection";
import { mockDashboards } from "@/data/mockDashboards";

const mockToastInfo = toast.info as ReturnType<typeof vi.fn>;

describe("DashboardsSection", () => {
  beforeEach(() => {
    mockToastInfo.mockClear();
  });

  it("renders one card per dashboard with the count summary", () => {
    render(<DashboardsSection />);

    const expectedCount = `${mockDashboards.length} dashboard${
      mockDashboards.length === 1 ? "" : "s"
    }`;
    expect(screen.getByText(expectedCount)).toBeInTheDocument();
    expect(screen.getByText(mockDashboards[0].name)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /configure/i })).toHaveLength(
      mockDashboards.length,
    );
  });

  it("renders the empty state when there are no dashboards", () => {
    render(<DashboardsSection dashboards={[]} />);

    expect(screen.getByText("No dashboards created yet.")).toBeInTheDocument();
    expect(screen.getByText("0 dashboards")).toBeInTheDocument();
  });

  it("shows a Release 2 toast instead of navigating when Configure is clicked", () => {
    render(<DashboardsSection dashboards={mockDashboards.slice(0, 1)} />);

    fireEvent.click(screen.getByRole("button", { name: /configure/i }));

    expect(mockToastInfo).toHaveBeenCalledWith(
      "Dashboard details arrive in Release 2.",
    );
  });

  it("disables the New Dashboard button (creation unavailable until Release 2)", () => {
    render(<DashboardsSection dashboards={[]} />);

    expect(
      screen.getByRole("button", { name: /new dashboard/i }),
    ).toBeDisabled();
  });
});
