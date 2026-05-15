import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AccountSettingsTabs } from "./AccountSettingsTabs";
import { getAccountById, updateAccount } from "@/data/organizationApi";
import { useAuth } from "@/contexts/AuthContext";
import type { AccountId } from "@/lib/branded-types";

vi.mock("@/data/organizationApi");
vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const mockGetAccountById = getAccountById as ReturnType<typeof vi.fn>;
const mockUpdateAccount = updateAccount as ReturnType<typeof vi.fn>;
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;

const mockAccount = {
  account_id: "acc_1",
  organization_id: "org_1",
  account_name: "Bank of America Brand",
  industry: "Retail Trade [B2C]",
  status: "active",
  timezone: "America/New_York",
  data_region: "US",
  region: ["NA"],
  websites: ["bofa.com"],
  marketing_channels: ["Email Marketing"],
  product_integrations: ["Google Analytics"],
};

const renderTabs = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
  return render(<AccountSettingsTabs accountId={"acc_1" as AccountId} />, {
    wrapper,
  });
};

describe("AccountSettingsTabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      orgMetadata: {
        org_1: { organization_name: "Bank of America" },
        org_2: { organization_name: "Globex" },
      },
    });
  });

  it("loads the account name and industry from the fetched account", async () => {
    mockGetAccountById.mockResolvedValue(mockAccount);

    renderTabs();

    const nameInput =
      await screen.findByLabelText<HTMLInputElement>("Account Name");
    expect(nameInput.value).toBe("Bank of America Brand");
    // The Industry select trigger shows the persisted Neo4j taxonomy value.
    expect(screen.getByText("Retail Trade [B2C]")).toBeInTheDocument();
  });

  it("persists an edited account name via updateAccount on Save", async () => {
    mockGetAccountById.mockResolvedValue(mockAccount);
    mockUpdateAccount.mockResolvedValue({
      ...mockAccount,
      account_name: "Renamed Account",
    });
    const user = userEvent.setup();

    renderTabs();

    const nameInput =
      await screen.findByLabelText<HTMLInputElement>("Account Name");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed Account");

    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(mockUpdateAccount).toHaveBeenCalledWith(
        "acc_1",
        expect.objectContaining({ account_name: "Renamed Account" }),
      ),
    );
  });

  it("disables Save until a field is edited", async () => {
    mockGetAccountById.mockResolvedValue(mockAccount);
    const user = userEvent.setup();

    renderTabs();

    const saveButton = await screen.findByRole("button", {
      name: /save changes/i,
    });
    expect(saveButton).toBeDisabled();

    const nameInput = screen.getByLabelText<HTMLInputElement>("Account Name");
    await user.type(nameInput, "X");

    expect(saveButton).toBeEnabled();
  });

  it("shows an error state when the account cannot be loaded", async () => {
    mockGetAccountById.mockResolvedValue(undefined);

    renderTabs();

    expect(
      await screen.findByText(/couldn't load this account/i),
    ).toBeInTheDocument();
  });

  it("integrations card grid uses responsive grid classes for reflow", async () => {
    mockGetAccountById.mockResolvedValue(mockAccount);
    const user = userEvent.setup();

    const { container } = renderTabs();

    await screen.findByLabelText("Account Name");
    await user.click(screen.getByRole("tab", { name: /integrations/i }));

    await waitFor(() => {
      const grid = container.querySelector(".grid-cols-1");
      expect(grid).toBeInTheDocument();
      expect(grid).toHaveClass("md:grid-cols-2");
      expect(grid).toHaveClass("lg:grid-cols-3");
      expect(grid).toHaveClass("gap-4");
    });
  });
});
