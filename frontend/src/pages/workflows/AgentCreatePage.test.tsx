import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AgentCreatePage, schema } from "./AgentCreatePage";

// ─── Mocks ───

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    selectedOrgAccount: { accountId: "acc_test" },
  }),
}));

const { mockCreateAgentConfig } = vi.hoisted(() => ({
  mockCreateAgentConfig: vi.fn(),
}));

vi.mock("@/lib/api/agentConfigs", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api/agentConfigs")>();
  return { ...actual, createAgentConfig: mockCreateAgentConfig };
});

// ─── Wrapper ───

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Tests ───

describe("AgentCreatePage", () => {
  it("submit button disabled when required fields are empty", async () => {
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    const submitBtn = screen.getByRole("button", { name: /create agent/i });
    expect(submitBtn).toBeDisabled();
  });

  it("successful submission navigates to the new agent's edit view", async () => {
    mockCreateAgentConfig.mockResolvedValueOnce({
      config_id: "custom_abc12345",
      customization_status: "custom_agent",
    });

    const { toast } = await import("sonner");
    const user = userEvent.setup();
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    // Fill required fields
    await user.type(screen.getByTestId("name-input"), "My Agent");
    await user.type(
      screen.getByTestId("instruction-field"),
      "You are a helpful assistant.",
    );

    // Select model via Select component
    await user.click(screen.getByTestId("model-select"));
    const modelOptions = await screen.findAllByRole("option");
    await user.click(modelOptions[0]);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /create agent/i }),
      ).not.toBeDisabled(),
    );

    await user.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        "/workflows/agents?edit=custom_abc12345",
      );
      expect(toast.success).toHaveBeenCalledWith("Agent created.");
    });
  });

  it("shows toast.error when submission fails", async () => {
    mockCreateAgentConfig.mockRejectedValueOnce(new Error("Network error"));
    const { toast } = await import("sonner");
    const user = userEvent.setup();
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    await user.type(screen.getByTestId("name-input"), "My Agent");
    await user.type(
      screen.getByTestId("instruction-field"),
      "You are a helpful assistant.",
    );

    await user.click(screen.getByTestId("model-select"));
    const modelOptions = await screen.findAllByRole("option");
    await user.click(modelOptions[0]);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /create agent/i }),
      ).not.toBeDisabled(),
    );

    await user.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Failed to create agent.");
    });
  });

  it("renders the default temperature value on the slider thumb", () => {
    render(<AgentCreatePage />, { wrapper: makeWrapper() });
    expect(screen.getByTestId("temperature-slider")).toHaveTextContent("0.3");
  });

  it("renders two disabled placeholder rows with correct tooltip text", () => {
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    expect(screen.getByTestId("disabled-row-skills")).toBeInTheDocument();
    expect(
      screen.getByTestId("disabled-row-sandbox-code-execution"),
    ).toBeInTheDocument();
  });

  it("Cancel button navigates to /workflows/agents", async () => {
    const user = userEvent.setup();
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/workflows/agents");
  });
});

describe("AgentCreatePage — schema", () => {
  const baseInput = {
    name: "x",
    instruction: "y",
    model: "gemini-2.5-flash",
  };

  it("rejects temperature below 0.1", () => {
    const result = schema.safeParse({ ...baseInput, temperature: 0 });
    expect(result.success).toBe(false);
  });

  it("rejects temperature above 0.9", () => {
    const result = schema.safeParse({ ...baseInput, temperature: 1 });
    expect(result.success).toBe(false);
  });

  it("accepts temperature within [0.1, 0.9]", () => {
    expect(schema.safeParse({ ...baseInput, temperature: 0.1 }).success).toBe(
      true,
    );
    expect(schema.safeParse({ ...baseInput, temperature: 0.9 }).success).toBe(
      true,
    );
  });
});
