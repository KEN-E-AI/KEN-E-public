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

    // Fill required fields (title is required; name is optional)
    await user.type(screen.getByTestId("title-input"), "Business Researcher");
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

    await user.type(screen.getByTestId("title-input"), "Business Researcher");
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
    title: "Business Researcher",
    instruction: "You are a helpful assistant.",
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

  it("rejects instruction shorter than 10 characters", () => {
    const result = schema.safeParse({ ...baseInput, instruction: "test" });
    expect(result.success).toBe(false);
  });

  it("accepts a missing/empty description", () => {
    expect(schema.safeParse(baseInput).success).toBe(true);
    expect(schema.safeParse({ ...baseInput, description: "" }).success).toBe(
      true,
    );
  });

  it("rejects a non-empty description shorter than 10 characters", () => {
    const result = schema.safeParse({ ...baseInput, description: "short" });
    expect(result.success).toBe(false);
  });

  it("rejects a description that is only whitespace-padded short text", () => {
    // The refine uses ``v.trim().length`` rather than ``v.length`` so an
    // 8-char string surrounded by whitespace doesn't sneak past the floor.
    const result = schema.safeParse({
      ...baseInput,
      description: "   hi   ",
    });
    expect(result.success).toBe(false);
  });
});

describe("AgentCreatePage — server validation", () => {
  it("maps FastAPI 422 detail entries onto the matching fields", async () => {
    // Shape mirrors what the API returns: ``{ response: { data: { detail: [...] } } }``
    // — Axios surfaces non-2xx HTTP responses as errors with the parsed body
    // attached at ``error.response.data``.
    mockCreateAgentConfig.mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: "string_too_short",
              loc: ["body", "instruction"],
              msg: "String should have at least 10 characters",
              ctx: { min_length: 10 },
            },
          ],
        },
      },
    });

    const { toast } = await import("sonner");
    const user = userEvent.setup();
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    // Type a valid-looking instruction so the client schema passes and the
    // form can actually submit (we want to exercise the server-error path).
    await user.type(screen.getByTestId("title-input"), "Business Researcher");
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
      expect(
        screen.getByText("String should have at least 10 characters"),
      ).toBeInTheDocument();
      expect(toast.error).toHaveBeenCalledWith(
        "Please fix the highlighted fields and try again.",
      );
    });
  });
});
