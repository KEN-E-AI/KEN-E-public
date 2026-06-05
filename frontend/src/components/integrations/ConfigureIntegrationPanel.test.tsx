import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigureIntegrationPanel } from "./ConfigureIntegrationPanel";
import api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth?client_id=x";

const renderPanel = () =>
  render(
    <ConfigureIntegrationPanel
      integration={{ name: "Google Analytics" }}
      accountId="acc_1"
      onClose={vi.fn()}
    />,
  );

describe("ConfigureIntegrationPanel", () => {
  let originalLocation: Location;

  beforeEach(() => {
    vi.clearAllMocks();
    originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { href: "" },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  it("starts the OAuth flow when Connect is clicked while disconnected", async () => {
    mockApi.get.mockImplementation((url: string) =>
      url.includes("/authorize/")
        ? Promise.resolve({ data: { auth_url: AUTH_URL } })
        : Promise.resolve({ data: { status: "not_configured" } }),
    );
    const user = userEvent.setup();

    renderPanel();

    const connectButton = await screen.findByRole("button", {
      name: /connect google analytics/i,
    });
    await user.click(connectButton);

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith(
        "/api/oauth/authorize/google-analytics?account_id=acc_1",
      );
      expect(window.location.href).toBe(AUTH_URL);
    });
  });

  it("shows Disconnect and Manage Properties when connected", async () => {
    mockApi.get.mockResolvedValue({
      data: { status: "configured", user_email: "u@e.com", property_count: 2 },
    });

    renderPanel();

    expect(
      await screen.findByRole("button", { name: /disconnect/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /manage properties/i }),
    ).toBeInTheDocument();
  });

  it("calls the disconnect endpoint when Disconnect is clicked", async () => {
    mockApi.get.mockResolvedValue({
      data: { status: "configured", user_email: "u@e.com", property_count: 1 },
    });
    mockApi.delete.mockResolvedValue({ data: {} });
    const user = userEvent.setup();

    renderPanel();

    await user.click(
      await screen.findByRole("button", { name: /disconnect/i }),
    );

    await waitFor(() =>
      expect(mockApi.delete).toHaveBeenCalledWith(
        "/api/oauth/disconnect/acc_1/google-analytics",
      ),
    );
  });

  it("renders the permissions section as a coming-soon placeholder", async () => {
    mockApi.get.mockResolvedValue({ data: { status: "not_configured" } });

    renderPanel();

    expect(
      await screen.findByText(/per-user permission controls are coming soon/i),
    ).toBeInTheDocument();
  });
});
