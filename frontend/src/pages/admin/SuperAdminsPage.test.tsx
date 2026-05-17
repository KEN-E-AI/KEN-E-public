import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import SuperAdminsPage from "./SuperAdminsPage";

vi.mock("@/queries/superAdmins", () => ({
  useSuperAdmins: vi.fn(),
  useGrantSuperAdmin: vi.fn(),
  useRevokeSuperAdmin: vi.fn(),
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
  useSuperAdmins,
  useGrantSuperAdmin,
  useRevokeSuperAdmin,
} from "@/queries/superAdmins";
import { toast } from "sonner";

const mockUseSuperAdmins = useSuperAdmins as ReturnType<typeof vi.fn>;
const mockUseGrantSuperAdmin = useGrantSuperAdmin as ReturnType<typeof vi.fn>;
const mockUseRevokeSuperAdmin = useRevokeSuperAdmin as ReturnType<typeof vi.fn>;
const mockToastSuccess = toast.success as ReturnType<typeof vi.fn>;
const mockToastError = toast.error as ReturnType<typeof vi.fn>;

const sampleEntries = [
  { uid: "uid-1", email: "alice@example.com" },
  { uid: "uid-2", email: "bob@example.com" },
];

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
  return render(<SuperAdminsPage />, { wrapper: makeWrapper() });
}

function defaultMutationHook(mutateFn = vi.fn()) {
  return { mutate: mutateFn, isPending: false };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseGrantSuperAdmin.mockReturnValue(defaultMutationHook());
  mockUseRevokeSuperAdmin.mockReturnValue(defaultMutationHook());
});

describe("SuperAdminsPage", () => {
  it("renders the list of super admins", () => {
    mockUseSuperAdmins.mockReturnValue({
      data: { super_admins: sampleEntries, total: 2 },
      isLoading: false,
    });

    renderPage();

    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    expect(screen.getByText("uid-1")).toBeInTheDocument();
    expect(screen.getByText("uid-2")).toBeInTheDocument();
  });

  it("renders empty state when no super admins", () => {
    mockUseSuperAdmins.mockReturnValue({
      data: { super_admins: [], total: 0 },
      isLoading: false,
    });

    renderPage();

    expect(screen.getByText("No super admins yet.")).toBeInTheDocument();
  });

  it("renders loading skeleton while isLoading", () => {
    mockUseSuperAdmins.mockReturnValue({ isLoading: true, data: undefined });

    const { container } = renderPage();

    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
    expect(screen.queryByText("No super admins yet.")).not.toBeInTheDocument();
  });

  it("grant by email success — calls mutate with email", async () => {
    mockUseSuperAdmins.mockReturnValue({
      data: { super_admins: [], total: 0 },
      isLoading: false,
    });

    const mutateFn = vi.fn();
    mockUseGrantSuperAdmin.mockReturnValue(defaultMutationHook(mutateFn));

    const user = userEvent.setup();
    renderPage();

    const emailInput = screen.getByRole("textbox", { name: /user email/i });
    await user.type(emailInput, "new@example.com");
    await user.click(screen.getByRole("button", { name: /^grant$/i }));

    expect(mutateFn).toHaveBeenCalledWith(
      { email: "new@example.com" },
      expect.any(Object),
    );
  });

  it("revoke opens dialog and confirm calls revoke mutate", async () => {
    mockUseSuperAdmins.mockReturnValue({
      data: { super_admins: sampleEntries, total: 2 },
      isLoading: false,
    });

    const mutateFn = vi.fn();
    mockUseRevokeSuperAdmin.mockReturnValue(defaultMutationHook(mutateFn));

    const user = userEvent.setup();
    renderPage();

    const revokeButtons = screen.getAllByRole("button", { name: /revoke/i });
    await user.click(revokeButtons[0]);

    const confirmButton = await screen.findByRole("button", {
      name: /^revoke$/i,
    });
    await user.click(confirmButton);

    expect(mutateFn).toHaveBeenCalledWith("uid-1", expect.any(Object));
  });

  it("revoke 409 shows last-admin-guard toast error", async () => {
    mockUseSuperAdmins.mockReturnValue({
      data: { super_admins: sampleEntries, total: 2 },
      isLoading: false,
    });

    const mutateFn = vi.fn((uid, callbacks) => {
      callbacks.onError({
        response: { status: 409, data: { detail: "Cannot revoke" } },
        message: "Request failed",
      });
    });
    mockUseRevokeSuperAdmin.mockReturnValue(defaultMutationHook(mutateFn));

    const user = userEvent.setup();
    renderPage();

    const revokeButtons = screen.getAllByRole("button", { name: /revoke/i });
    await user.click(revokeButtons[0]);

    const confirmButton = await screen.findByRole("button", {
      name: /^revoke$/i,
    });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Cannot revoke the last remaining super admin",
      );
    });
    expect(mockToastSuccess).not.toHaveBeenCalled();
  });
});
