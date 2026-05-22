import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import FeatureFlagsPage from "./FeatureFlagsPage";

vi.mock("@/lib/featureFlags/hooks", () => ({
  useFeatureFlags: vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

// Mock the heavy children — their own behavior is covered by their colocated
// tests. This page-level test verifies only the page's responsibilities:
// the loading / error / populated branches and that create + row-click open
// the drawer in the correct mode.
vi.mock("@/components/admin/featureFlags/FlagTable", () => ({
  FlagTable: ({
    flags,
    onCreate,
    onRowClick,
  }: {
    flags: { key: string }[];
    onCreate?: () => void;
    onRowClick?: (flag: { key: string }) => void;
  }) => (
    <div data-testid="flag-table">
      <span>flags:{flags.length}</span>
      <button onClick={() => onCreate?.()}>new-flag</button>
      <button onClick={() => onRowClick?.({ key: "row-flag" })}>row</button>
    </div>
  ),
}));

vi.mock("@/components/admin/featureFlags/FlagEditDrawer", () => ({
  FlagEditDrawer: ({
    open,
    mode,
    flag,
  }: {
    open: boolean;
    mode: "create" | "edit";
    flag?: { key: string };
  }) =>
    open ? (
      <div data-testid="drawer">
        drawer-open mode:{mode} flag:{flag?.key ?? "none"}
      </div>
    ) : null,
}));

import { useFeatureFlags } from "@/lib/featureFlags/hooks";
import { useAuth } from "@/contexts/AuthContext";
import { SuperAdminGuard } from "@/components/auth/SuperAdminGuard";

const mockUseFeatureFlags = useFeatureFlags as ReturnType<typeof vi.fn>;
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  // Safe default — FeatureFlagsPage itself doesn't call useAuth, but guarding
  // here prevents undefined from the hook if the page ever gains a direct call.
  mockUseAuth.mockReturnValue({
    isSuperAdmin: false,
    isSuperAdminLoading: false,
  });
});

describe("FeatureFlagsPage", () => {
  it("renders the table when the list loads", () => {
    mockUseFeatureFlags.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [{ key: "a" }, { key: "b" }],
    });

    render(<FeatureFlagsPage />);

    expect(screen.getByTestId("flag-table")).toHaveTextContent("flags:2");
  });

  it("shows a skeleton while loading, not the table or an error", () => {
    mockUseFeatureFlags.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
    });

    const { container } = render(<FeatureFlagsPage />);

    expect(
      container.querySelectorAll("[data-slot='skeleton']").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByTestId("flag-table")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an error state (not 'no flags') when the list query fails", () => {
    mockUseFeatureFlags.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      data: undefined,
      refetch: vi.fn(),
    });

    render(<FeatureFlagsPage />);

    expect(
      screen.getByText(/failed to load feature flags/i),
    ).toBeInTheDocument();
    // Critical: a failed load must NOT render the table's empty state.
    expect(screen.queryByTestId("flag-table")).not.toBeInTheDocument();
  });

  it("retry button calls refetch", async () => {
    const refetch = vi.fn();
    mockUseFeatureFlags.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      data: undefined,
      refetch,
    });

    const user = userEvent.setup();
    render(<FeatureFlagsPage />);

    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("'+ New flag' opens the drawer in create mode", async () => {
    mockUseFeatureFlags.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
    });

    const user = userEvent.setup();
    render(<FeatureFlagsPage />);

    expect(screen.queryByTestId("drawer")).not.toBeInTheDocument();
    await user.click(screen.getByText("new-flag"));

    expect(screen.getByTestId("drawer")).toHaveTextContent("mode:create");
  });

  it("clicking a row opens the drawer in edit mode with that flag", async () => {
    mockUseFeatureFlags.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [{ key: "row-flag" }],
    });

    const user = userEvent.setup();
    render(<FeatureFlagsPage />);

    await user.click(screen.getByText("row"));

    const drawer = screen.getByTestId("drawer");
    expect(drawer).toHaveTextContent("mode:edit");
    expect(drawer).toHaveTextContent("flag:row-flag");
  });

  describe("FeatureFlagsPage — route guard", () => {
    // Factory function rather than a const to avoid any shared-element-reference
    // confusion between tests.
    function makeGuardRoute() {
      return (
        <MemoryRouter initialEntries={["/admin/feature-flags"]}>
          <Routes>
            {/* SuperAdminGuard is intentionally NOT mocked — these tests verify
                the real guard behavior against the mocked useAuth. */}
            <Route
              path="/admin/feature-flags"
              element={
                <SuperAdminGuard>
                  <FeatureFlagsPage />
                </SuperAdminGuard>
              }
            />
            <Route path="/" element={<div>home</div>} />
          </Routes>
        </MemoryRouter>
      );
    }

    beforeEach(() => {
      mockUseFeatureFlags.mockReturnValue({
        isLoading: false,
        isError: false,
        data: [],
      });
    });

    it("renders the page when isSuperAdmin=true and isSuperAdminLoading=false", () => {
      mockUseAuth.mockReturnValue({
        isSuperAdmin: true,
        isSuperAdminLoading: false,
      });

      render(makeGuardRoute());

      expect(screen.getByTestId("flag-table")).toBeInTheDocument();
    });

    it("redirects to '/' when isSuperAdmin=false and isSuperAdminLoading=false", () => {
      mockUseAuth.mockReturnValue({
        isSuperAdmin: false,
        isSuperAdminLoading: false,
      });

      render(makeGuardRoute());

      expect(screen.getByText("home")).toBeVisible();
      expect(screen.queryByTestId("flag-table")).not.toBeInTheDocument();
      // Confirm the page heading is absent — guards against a guard that renders
      // both branches simultaneously.
      expect(
        screen.queryByRole("heading", { name: /feature flags/i }),
      ).not.toBeInTheDocument();
    });

    it("renders nothing when isSuperAdminLoading=true", () => {
      mockUseAuth.mockReturnValue({
        isSuperAdmin: false,
        isSuperAdminLoading: true,
      });

      render(makeGuardRoute());

      expect(screen.queryByText("home")).not.toBeInTheDocument();
      expect(screen.queryByTestId("flag-table")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: /feature flags/i }),
      ).not.toBeInTheDocument();
    });
  });
});
