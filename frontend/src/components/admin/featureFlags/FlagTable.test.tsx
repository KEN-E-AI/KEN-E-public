import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { FlagTable } from "./FlagTable";
import type { FeatureFlag } from "@/lib/featureFlags/types";
import { toFlagKey } from "@/lib/featureFlags/types";

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/lib/featureFlags/hooks", () => ({
  featureFlagKeys: {
    all: ["featureFlags"],
    list: () => ["featureFlags", "list"],
    detail: (key: string) => ["featureFlags", "detail", key],
    audit: (key: string, cursor: string | null = null) => [
      "featureFlags",
      "detail",
      key,
      "audit",
      cursor,
    ],
  },
  useUpdateFlag: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { useUpdateFlag } from "@/lib/featureFlags/hooks";
import { toast } from "sonner";

const mockUseUpdateFlag = useUpdateFlag as ReturnType<typeof vi.fn>;
const mockToastSuccess = toast.success as ReturnType<typeof vi.fn>;
const mockToastError = toast.error as ReturnType<typeof vi.fn>;

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function makeFlag(overrides: Partial<FeatureFlag> = {}): FeatureFlag {
  return {
    key: toFlagKey("automations_beta"),
    description: "Automations beta feature",
    default_enabled: false,
    is_active: true,
    targeting_rules: {
      user_emails: [],
      email_domains: [],
      organization_ids: [],
      account_ids: [],
      rollout_percentage: 10,
    },
    bucketing_entity: "account",
    owner: "eng@ken-e.ai",
    expected_ga_release: "Release 2",
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-10T00:00:00Z",
    ...overrides,
  };
}

const flagAlpha = makeFlag({
  key: toFlagKey("zzz_alpha_flag"),
  description: "Alpha feature",
  expected_ga_release: "Release 1",
  updated_at: "2026-05-01T00:00:00Z",
});

const flagBeta = makeFlag({
  key: toFlagKey("automations_beta"),
  description: "Beta feature",
  expected_ga_release: "Release 2",
  updated_at: "2026-05-10T00:00:00Z",
});

const flagNoRelease = makeFlag({
  key: toFlagKey("new_chat_feature"),
  description: "No GA release set",
  expected_ga_release: null,
  updated_at: "2026-05-05T00:00:00Z",
});

// ─── Test helpers ─────────────────────────────────────────────────────────────

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

function defaultMutateFn() {
  return vi.fn();
}

function defaultMutationHook(mutateFn = defaultMutateFn()) {
  return { mutate: mutateFn, isPending: false };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseUpdateFlag.mockReturnValue(defaultMutationHook());
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("FlagTable", () => {
  describe("rendering", () => {
    it("renders all 8 columns for each flag row", () => {
      mockUseUpdateFlag.mockReturnValue(defaultMutationHook());

      render(<FlagTable flags={[flagBeta]} />, { wrapper: makeWrapper() });

      // Key column
      expect(screen.getByText("automations_beta")).toBeInTheDocument();
      // Description column
      expect(screen.getByText("Beta feature")).toBeInTheDocument();
      // Rollout % column
      expect(screen.getByText("10%")).toBeInTheDocument();
      // Owner column
      expect(screen.getByText("eng@ken-e.ai")).toBeInTheDocument();
      // GA Release column
      expect(screen.getByText("Release 2")).toBeInTheDocument();
      // Default enabled badge
      expect(screen.getByText("Off")).toBeInTheDocument();
      // Active switch should be present
      expect(
        screen.getByRole("switch", {
          name: /toggle automations_beta active state/i,
        }),
      ).toBeInTheDocument();
    });

    it("renders '—' for blank expected_ga_release", () => {
      render(<FlagTable flags={[flagNoRelease]} />, { wrapper: makeWrapper() });

      expect(screen.getByText("—")).toBeInTheDocument();
    });

    it("renders empty state when flags list is empty", () => {
      render(<FlagTable flags={[]} />, { wrapper: makeWrapper() });

      expect(
        screen.getByTestId("feature-flags-table-empty"),
      ).toBeInTheDocument();
      expect(screen.getByText("No feature flags yet.")).toBeInTheDocument();
    });

    it("renders + New flag button only when onCreate is provided", () => {
      const { rerender } = render(<FlagTable flags={[flagBeta]} />, {
        wrapper: makeWrapper(),
      });
      expect(
        screen.queryByRole("button", { name: /new flag/i }),
      ).not.toBeInTheDocument();

      const onCreate = vi.fn();
      rerender(<FlagTable flags={[flagBeta]} onCreate={onCreate} />);
      expect(
        screen.getByRole("button", { name: /new flag/i }),
      ).toBeInTheDocument();
    });
  });

  describe("default sort (updated_at descending)", () => {
    it("renders flags sorted by updated_at descending by default", () => {
      render(<FlagTable flags={[flagAlpha, flagNoRelease, flagBeta]} />, {
        wrapper: makeWrapper(),
      });

      const rows = screen.getAllByRole("row").slice(1); // skip header
      // flagBeta: 2026-05-10 (newest), flagNoRelease: 2026-05-05, flagAlpha: 2026-05-01 (oldest)
      expect(within(rows[0]).getByText("automations_beta")).toBeInTheDocument();
      expect(within(rows[1]).getByText("new_chat_feature")).toBeInTheDocument();
      expect(within(rows[2]).getByText("zzz_alpha_flag")).toBeInTheDocument();
    });
  });

  describe("expected_ga_release sort (AC-13)", () => {
    it("sorts by expected_ga_release ascending when header is clicked", async () => {
      const user = userEvent.setup();
      render(<FlagTable flags={[flagAlpha, flagNoRelease, flagBeta]} />, {
        wrapper: makeWrapper(),
      });

      await user.click(
        screen.getByRole("columnheader", { name: /ga release/i }),
      );

      const rows = screen.getAllByRole("row").slice(1);
      // asc: "Release 1" < "Release 2" < blank (last)
      expect(within(rows[0]).getByText("zzz_alpha_flag")).toBeInTheDocument();
      expect(within(rows[1]).getByText("automations_beta")).toBeInTheDocument();
      expect(within(rows[2]).getByText("new_chat_feature")).toBeInTheDocument();
    });

    it("sorts by expected_ga_release descending on second click, blanks still last", async () => {
      const user = userEvent.setup();
      render(<FlagTable flags={[flagAlpha, flagNoRelease, flagBeta]} />, {
        wrapper: makeWrapper(),
      });

      const gaReleaseHeader = screen.getByRole("columnheader", {
        name: /ga release/i,
      });
      await user.click(gaReleaseHeader); // asc
      await user.click(gaReleaseHeader); // desc

      const rows = screen.getAllByRole("row").slice(1);
      // desc: "Release 2" > "Release 1" > blank (last)
      expect(within(rows[0]).getByText("automations_beta")).toBeInTheDocument();
      expect(within(rows[1]).getByText("zzz_alpha_flag")).toBeInTheDocument();
      expect(within(rows[2]).getByText("new_chat_feature")).toBeInTheDocument();
    });

    it("keeps blank expected_ga_release rows last in both sort directions", async () => {
      const user = userEvent.setup();
      render(<FlagTable flags={[flagNoRelease, flagAlpha, flagBeta]} />, {
        wrapper: makeWrapper(),
      });

      const gaReleaseHeader = screen.getByRole("columnheader", {
        name: /ga release/i,
      });

      // asc — blank last
      await user.click(gaReleaseHeader);
      let rows = screen.getAllByRole("row").slice(1);
      expect(within(rows[2]).getByText("new_chat_feature")).toBeInTheDocument();

      // desc — blank still last
      await user.click(gaReleaseHeader);
      rows = screen.getAllByRole("row").slice(1);
      expect(within(rows[2]).getByText("new_chat_feature")).toBeInTheDocument();
    });
  });

  describe("kill-switch toggle (AC-10)", () => {
    it("calls mutate with correct payload when the is_active switch is clicked", async () => {
      const mutateFn = vi.fn();
      mockUseUpdateFlag.mockReturnValue(defaultMutationHook(mutateFn));

      const user = userEvent.setup();
      render(<FlagTable flags={[flagBeta]} />, { wrapper: makeWrapper() });

      const switchEl = screen.getByRole("switch", {
        name: /toggle automations_beta active state/i,
      });
      await user.click(switchEl);

      expect(mutateFn).toHaveBeenCalledWith(
        expect.objectContaining({
          key: flagBeta.key,
          body: expect.objectContaining({
            key: flagBeta.key,
            is_active: false, // toggled from true → false
          }),
        }),
        expect.any(Object),
      );
    });

    it("calls toast.success with the SLO string on mutation success", async () => {
      const mutateFn = vi.fn((_vars, callbacks: { onSuccess?: () => void }) => {
        callbacks.onSuccess?.();
      });
      mockUseUpdateFlag.mockReturnValue(defaultMutationHook(mutateFn));

      const user = userEvent.setup();
      render(<FlagTable flags={[flagBeta]} />, { wrapper: makeWrapper() });

      await user.click(
        screen.getByRole("switch", {
          name: /toggle automations_beta active state/i,
        }),
      );

      expect(mockToastSuccess).toHaveBeenCalledWith(
        "Kill switch applied. Fully effective within 60 s across all servers.",
      );
    });

    it("calls toast.error and does not call toast.success on mutation error", async () => {
      const mutateFn = vi.fn(
        (
          _vars,
          callbacks: {
            onError?: (err: unknown) => void;
            onSuccess?: () => void;
          },
        ) => {
          callbacks.onError?.({
            response: { data: { detail: "Server error" } },
          });
        },
      );
      mockUseUpdateFlag.mockReturnValue(defaultMutationHook(mutateFn));

      const user = userEvent.setup();
      render(<FlagTable flags={[flagBeta]} />, { wrapper: makeWrapper() });

      await user.click(
        screen.getByRole("switch", {
          name: /toggle automations_beta active state/i,
        }),
      );

      expect(mockToastError).toHaveBeenCalledWith("Server error");
      expect(mockToastSuccess).not.toHaveBeenCalled();
    });

    it("falls back to error message when detail is absent", async () => {
      const mutateFn = vi.fn(
        (_vars, callbacks: { onError?: (err: unknown) => void }) => {
          callbacks.onError?.({ message: "Network timeout" });
        },
      );
      mockUseUpdateFlag.mockReturnValue(defaultMutationHook(mutateFn));

      const user = userEvent.setup();
      render(<FlagTable flags={[flagBeta]} />, { wrapper: makeWrapper() });

      await user.click(
        screen.getByRole("switch", {
          name: /toggle automations_beta active state/i,
        }),
      );

      expect(mockToastError).toHaveBeenCalledWith("Network timeout");
    });
  });

  describe("row click callback", () => {
    it("calls onRowClick with the flag when a row is clicked", async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();
      render(<FlagTable flags={[flagBeta]} onRowClick={onRowClick} />, {
        wrapper: makeWrapper(),
      });

      // Click on the key cell (not the switch cell)
      await user.click(screen.getByText("automations_beta"));

      expect(onRowClick).toHaveBeenCalledWith(flagBeta);
    });

    it("switch click does not propagate to onRowClick", async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();
      render(<FlagTable flags={[flagBeta]} onRowClick={onRowClick} />, {
        wrapper: makeWrapper(),
      });

      await user.click(
        screen.getByRole("switch", {
          name: /toggle automations_beta active state/i,
        }),
      );

      expect(onRowClick).not.toHaveBeenCalled();
    });
  });
});
