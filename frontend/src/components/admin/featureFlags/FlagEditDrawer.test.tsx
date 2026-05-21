import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  FlagEditDrawer,
  BUCKETING_ENTITY_HELP_TEXT,
  targetingRulesSchema,
} from "./FlagEditDrawer";
import type { FeatureFlag } from "@/lib/featureFlags/types";
import { toFlagKey } from "@/lib/featureFlags/types";

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: "u1",
      email: "admin@ken-e.ai",
      firstName: "Admin",
      lastName: "User",
    },
  })),
}));

vi.mock("@/lib/featureFlags/hooks", () => ({
  useCreateFlag: vi.fn(),
  useUpdateFlag: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

import { useCreateFlag, useUpdateFlag } from "@/lib/featureFlags/hooks";

const mockUseCreateFlag = useCreateFlag as ReturnType<typeof vi.fn>;
const mockUseUpdateFlag = useUpdateFlag as ReturnType<typeof vi.fn>;

// ─── Test helpers ─────────────────────────────────────────────────────────────

function freshClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function makeMutateMock(opts?: {
  resolveWith?: FeatureFlag;
  rejectWith?: Error;
}) {
  return vi.fn(
    (
      _payload: unknown,
      callbacks: {
        onSuccess?: (data: FeatureFlag) => void;
        onError?: (err: Error) => void;
      },
    ) => {
      if (opts?.rejectWith) {
        callbacks?.onError?.(opts.rejectWith);
      } else if (opts?.resolveWith) {
        callbacks?.onSuccess?.(opts.resolveWith);
      }
    },
  );
}

const sampleFlag: FeatureFlag = {
  key: toFlagKey("test_flag"),
  description: "A test flag",
  default_enabled: false,
  is_active: true,
  owner: "owner@ken-e.ai",
  expected_ga_release: "Release 2",
  bucketing_entity: "account",
  targeting_rules: {
    user_emails: [],
    email_domains: [],
    organization_ids: [],
    account_ids: [],
    rollout_percentage: 0,
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDrawer(
  props: React.ComponentProps<typeof FlagEditDrawer>,
  client?: QueryClient,
) {
  const qc = client ?? freshClient();
  const Wrapper = makeWrapper(qc);
  return render(
    <Wrapper>
      <FlagEditDrawer {...props} />
    </Wrapper>,
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockUseCreateFlag.mockReturnValue({ mutate: vi.fn(), isPending: false });
  mockUseUpdateFlag.mockReturnValue({ mutate: vi.fn(), isPending: false });
});

describe("FlagEditDrawer — create mode", () => {
  it("renders the sheet with 'New feature flag' title", () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    expect(screen.getByText("New feature flag")).toBeInTheDocument();
  });

  it("mounts as Sheet side=right", () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    const content = document.querySelector("[data-slot='sheet-content']");
    expect(content).toBeInTheDocument();
  });

  it("key field is editable in create mode", () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    const keyInput = screen.getByRole("textbox", { name: /flag key/i });
    expect(keyInput).not.toBeDisabled();
  });

  it("defaults owner to the logged-in user email", () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    const ownerInput = screen.getByRole("textbox", { name: /owner/i });
    expect(ownerInput).toHaveValue("admin@ken-e.ai");
  });

  it("shows inline error for invalid key (fails FLAG_KEY_REGEX)", async () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    const keyInput = screen.getByRole("textbox", { name: /flag key/i });
    await userEvent.type(keyInput, "INVALID KEY!!!");
    const submitBtn = screen.getByRole("button", { name: /create flag/i });
    await userEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText(/must match/i)).toBeInTheDocument();
    });
  });

  it("shows inline error for empty key", async () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    const submitBtn = screen.getByRole("button", { name: /create flag/i });
    await userEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText(/key is required/i)).toBeInTheDocument();
    });
  });

  it("calls useCreateFlag.mutate with a valid payload on submit", async () => {
    const mutate = makeMutateMock({ resolveWith: sampleFlag });
    mockUseCreateFlag.mockReturnValue({ mutate, isPending: false });

    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });

    await userEvent.type(
      screen.getByRole("textbox", { name: /flag key/i }),
      "test_flag",
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "A test flag",
    );

    await userEvent.click(screen.getByRole("button", { name: /create flag/i }));

    await waitFor(() => {
      expect(mutate).toHaveBeenCalledOnce();
      const [payload] = mutate.mock.calls[0];
      expect(payload).toMatchObject({
        key: "test_flag",
        description: "A test flag",
        is_active: true,
        default_enabled: false,
        bucketing_entity: "account",
      });
    });
  });

  it("calls onOpenChange(false) and onSuccess on successful create", async () => {
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    const mutate = makeMutateMock({ resolveWith: sampleFlag });
    mockUseCreateFlag.mockReturnValue({ mutate, isPending: false });

    renderDrawer({
      open: true,
      onOpenChange,
      mode: "create",
      onSuccess,
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: /flag key/i }),
      "test_flag",
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "A test flag",
    );
    await userEvent.click(screen.getByRole("button", { name: /create flag/i }));

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
      expect(onSuccess).toHaveBeenCalledWith(sampleFlag);
    });
  });

  it("shows inline error for invalid owner email", async () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    const ownerInput = screen.getByRole("textbox", { name: /owner/i });
    await userEvent.clear(ownerInput);
    await userEvent.type(ownerInput, "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: /create flag/i }));
    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    });
  });

  it("cancel button calls onOpenChange(false) without firing a mutation", async () => {
    const onOpenChange = vi.fn();
    const mutate = vi.fn();
    mockUseCreateFlag.mockReturnValue({ mutate, isPending: false });

    renderDrawer({ open: true, onOpenChange, mode: "create" });
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(mutate).not.toHaveBeenCalled();
  });
});

describe("FlagEditDrawer — edit mode", () => {
  it("renders 'Edit feature flag' title", () => {
    renderDrawer({
      open: true,
      onOpenChange: vi.fn(),
      mode: "edit",
      flag: sampleFlag,
    });
    expect(screen.getByText("Edit feature flag")).toBeInTheDocument();
  });

  it("pre-fills form fields from the flag prop", () => {
    renderDrawer({
      open: true,
      onOpenChange: vi.fn(),
      mode: "edit",
      flag: sampleFlag,
    });
    expect(screen.getByRole("textbox", { name: /flag key/i })).toHaveValue(
      "test_flag",
    );
    expect(screen.getByRole("textbox", { name: /owner/i })).toHaveValue(
      "owner@ken-e.ai",
    );
    expect(
      screen.getByRole("textbox", { name: /expected ga release/i }),
    ).toHaveValue("Release 2");
  });

  it("key field is disabled in edit mode", () => {
    renderDrawer({
      open: true,
      onOpenChange: vi.fn(),
      mode: "edit",
      flag: sampleFlag,
    });
    expect(screen.getByRole("textbox", { name: /flag key/i })).toBeDisabled();
  });

  it("calls useUpdateFlag.mutate with key + body on submit", async () => {
    const mutate = makeMutateMock({ resolveWith: sampleFlag });
    mockUseUpdateFlag.mockReturnValue({ mutate, isPending: false });

    renderDrawer({
      open: true,
      onOpenChange: vi.fn(),
      mode: "edit",
      flag: sampleFlag,
    });

    await userEvent.click(
      screen.getByRole("button", { name: /save changes/i }),
    );

    await waitFor(() => {
      expect(mutate).toHaveBeenCalledOnce();
      const [{ key, body }] = mutate.mock.calls[0];
      expect(key).toBe("test_flag");
      expect(body).toMatchObject({ description: "A test flag" });
    });
  });
});

describe("FlagEditDrawer — bucketing_entity help text (AC-12)", () => {
  it("renders the BUCKETING_ENTITY_HELP_TEXT constant in the form", () => {
    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });
    expect(screen.getByText(BUCKETING_ENTITY_HELP_TEXT)).toBeInTheDocument();
  });

  it("BUCKETING_ENTITY_HELP_TEXT matches the canonical README §7.3 marker-delimited block", () => {
    const readmePath = path.resolve(
      __dirname,
      "../../../../../docs/design/components/feature-flags/README.md",
    );
    const readmeContent = fs.readFileSync(readmePath, "utf-8");

    const startMarker = "<!-- BUCKETING_ENTITY_HELP_TEXT_START -->";
    const endMarker = "<!-- BUCKETING_ENTITY_HELP_TEXT_END -->";

    const startIndex = readmeContent.indexOf(startMarker);
    const endIndex = readmeContent.indexOf(endMarker);

    expect(startIndex).toBeGreaterThan(-1);
    expect(endIndex).toBeGreaterThan(startIndex);

    // Exactly one start and one end marker
    const startCount = (
      readmeContent.match(/<!-- BUCKETING_ENTITY_HELP_TEXT_START -->/g) ?? []
    ).length;
    const endCount = (
      readmeContent.match(/<!-- BUCKETING_ENTITY_HELP_TEXT_END -->/g) ?? []
    ).length;
    expect(startCount).toBe(1);
    expect(endCount).toBe(1);

    const between = readmeContent
      .slice(startIndex + startMarker.length, endIndex)
      .trim();

    expect(between).toBe(BUCKETING_ENTITY_HELP_TEXT);
  });
});

describe("FlagEditDrawer — schema validation (AC-9)", () => {
  it("rejects rollout_percentage below 0", () => {
    const result = targetingRulesSchema.safeParse({
      user_emails: [],
      email_domains: [],
      organization_ids: [],
      account_ids: [],
      rollout_percentage: -1,
    });
    expect(result.success).toBe(false);
  });

  it("rejects rollout_percentage above 100", () => {
    const result = targetingRulesSchema.safeParse({
      user_emails: [],
      email_domains: [],
      organization_ids: [],
      account_ids: [],
      rollout_percentage: 101,
    });
    expect(result.success).toBe(false);
  });

  it("accepts rollout_percentage at the boundaries 0 and 100", () => {
    const base = {
      user_emails: [],
      email_domains: [],
      organization_ids: [],
      account_ids: [],
    };
    expect(
      targetingRulesSchema.safeParse({ ...base, rollout_percentage: 0 })
        .success,
    ).toBe(true);
    expect(
      targetingRulesSchema.safeParse({ ...base, rollout_percentage: 100 })
        .success,
    ).toBe(true);
  });
});

describe("FlagEditDrawer — error handling", () => {
  it("shows a toast on mutation error", async () => {
    const { toast } = await import("sonner");
    const mutate = makeMutateMock({ rejectWith: new Error("Server error") });
    mockUseCreateFlag.mockReturnValue({ mutate, isPending: false });

    renderDrawer({ open: true, onOpenChange: vi.fn(), mode: "create" });

    await userEvent.type(
      screen.getByRole("textbox", { name: /flag key/i }),
      "test_flag",
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "A test flag",
    );
    await userEvent.click(screen.getByRole("button", { name: /create flag/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Server error");
    });
  });
});
