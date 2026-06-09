import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import EarlyReleasePage from "./EarlyReleasePage";

vi.mock("@/queries/earlyRelease", () => ({
  useEarlyReleaseConfig: vi.fn(),
  useUpdateEarlyReleaseConfig: vi.fn(),
  useEarlyReleaseRedemptions: vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(() => ({ isSuperAdmin: true })),
  AuthContext: {
    Provider: ({ children }: { children: ReactNode }) => children,
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import {
  useEarlyReleaseConfig,
  useUpdateEarlyReleaseConfig,
  useEarlyReleaseRedemptions,
} from "@/queries/earlyRelease";
import { toast } from "sonner";

const mockUseConfig = useEarlyReleaseConfig as ReturnType<typeof vi.fn>;
const mockUseUpdate = useUpdateEarlyReleaseConfig as ReturnType<typeof vi.fn>;
const mockUseRedemptions = useEarlyReleaseRedemptions as ReturnType<
  typeof vi.fn
>;
const mockToastSuccess = toast.success as ReturnType<typeof vi.fn>;
const mockToastError = toast.error as ReturnType<typeof vi.fn>;

const sampleConfig = {
  code: "LAUNCH2025",
  is_active: true,
  expires_at: null,
  updated_by: "admin@ken-e.ai",
  updated_at: "2025-03-01T10:00:00Z",
  redemption_count: 5,
};

const emptyRedemptions = {
  data: { redemptions: [], total: 0, next_cursor: null },
  isLoading: false,
  isFetching: false,
};

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

function renderPage() {
  return render(<EarlyReleasePage />, { wrapper: makeWrapper() });
}

function defaultMutationHook(mutateFn = vi.fn()) {
  return { mutate: mutateFn, isPending: false };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseUpdate.mockReturnValue(defaultMutationHook());
  mockUseRedemptions.mockReturnValue(emptyRedemptions);
});

describe("EarlyReleasePage", () => {
  it("renders loading skeleton while config is loading", () => {
    mockUseConfig.mockReturnValue({ isLoading: true, isError: false });
    const { container } = renderPage();
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders the configured state with code and metadata", () => {
    mockUseConfig.mockReturnValue({
      data: sampleConfig,
      isLoading: false,
      isError: false,
    });
    renderPage();

    expect(screen.getByText("LAUNCH2025")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("admin@ken-e.ai")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders unset (404) empty state with Set initial code CTA", () => {
    mockUseConfig.mockReturnValue({
      isLoading: false,
      isError: true,
      error: { response: { status: 404 } },
    });
    renderPage();

    expect(
      screen.getByText(/no early release code has been set yet/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /set initial code/i }),
    ).toBeInTheDocument();
  });

  it("renders destructive alert with retry for non-404 errors", () => {
    mockUseConfig.mockReturnValue({
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
      refetch: vi.fn(),
    });
    renderPage();

    expect(
      screen.getByText(/failed to load early release config/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("clicking Retry calls refetch", async () => {
    const refetch = vi.fn();
    mockUseConfig.mockReturnValue({
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
      refetch,
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("toggle switch fires kill-switch PUT with {is_active: false}", async () => {
    const mutateFn = vi.fn();
    mockUseUpdate.mockReturnValue(defaultMutationHook(mutateFn));
    mockUseConfig.mockReturnValue({
      data: { ...sampleConfig, is_active: true },
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    renderPage();

    const toggle = screen.getByRole("switch", {
      name: /toggle early release code active state/i,
    });
    await user.click(toggle);

    expect(mutateFn).toHaveBeenCalledWith(
      { is_active: false },
      expect.any(Object),
    );
  });

  it("toggle switch fires kill-switch PUT with {is_active: true} when currently disabled", async () => {
    const mutateFn = vi.fn();
    mockUseUpdate.mockReturnValue(defaultMutationHook(mutateFn));
    mockUseConfig.mockReturnValue({
      data: { ...sampleConfig, is_active: false },
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    renderPage();

    const toggle = screen.getByRole("switch", {
      name: /toggle early release code active state/i,
    });
    await user.click(toggle);

    expect(mutateFn).toHaveBeenCalledWith(
      { is_active: true },
      expect.any(Object),
    );
  });

  it("toggle mutation error shows toast.error", async () => {
    const mutateFn = vi.fn((_, callbacks) => {
      callbacks.onError({
        response: { data: { detail: "Not found" } },
        message: "Not found",
      });
    });
    mockUseUpdate.mockReturnValue(defaultMutationHook(mutateFn));
    mockUseConfig.mockReturnValue({
      data: sampleConfig,
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    renderPage();

    const toggle = screen.getByRole("switch");
    await user.click(toggle);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Not found");
    });
  });

  it("copy button writes code to clipboard and shows success toast", async () => {
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined);

    mockUseConfig.mockReturnValue({
      data: sampleConfig,
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    renderPage();

    const copyBtn = screen.getByRole("button", { name: /copy code/i });
    await user.click(copyBtn);

    expect(writeText).toHaveBeenCalledWith("LAUNCH2025");
    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("Code copied to clipboard");
    });
  });

  it("clicking 'Set / Rotate code' button opens the rotate dialog", async () => {
    mockUseConfig.mockReturnValue({
      data: sampleConfig,
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    renderPage();

    const rotateBtn = screen.getByRole("button", {
      name: /set \/ rotate code/i,
    });
    await user.click(rotateBtn);

    expect(screen.getByText("Set / Rotate Code")).toBeInTheDocument();
  });

  it("successful rotate mutation shows success toast and closes dialog", async () => {
    const mutateFn = vi.fn((_, callbacks) => {
      callbacks.onSuccess();
    });
    mockUseUpdate.mockReturnValue(defaultMutationHook(mutateFn));
    mockUseConfig.mockReturnValue({
      data: sampleConfig,
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole("button", { name: /set \/ rotate code/i }),
    );

    const codeInput = screen.getByRole("textbox", { name: /new code/i });
    await user.type(codeInput, "NEWCODE2025");
    await user.click(screen.getByRole("button", { name: /rotate code/i }));

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith(
        "Early Release code updated",
      );
    });
  });
});
