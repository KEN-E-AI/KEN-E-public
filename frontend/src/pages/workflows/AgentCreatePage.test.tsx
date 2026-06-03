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

const { mockCreateAgentConfig, mockGetAccountTools } = vi.hoisted(() => ({
  mockCreateAgentConfig: vi.fn(),
  mockGetAccountTools: vi.fn(),
}));

vi.mock("@/lib/api/agentConfigs", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api/agentConfigs")>();
  return { ...actual, createAgentConfig: mockCreateAgentConfig };
});

vi.mock("@/lib/api/tools", () => ({
  getAccountTools: mockGetAccountTools,
}));

// Default fixture for the tool inventory — keeps render quiet during tests
// that don't care about tools. Individual tests can override with their own
// ``mockGetAccountTools.mockResolvedValueOnce(...)``.
const defaultTools = {
  tools: [
    {
      tool_id: "function.create_visualization",
      name: "create_visualization",
      description: "Render a chart.",
      category: "general",
      source: "global_default",
      mcp_server: null,
      integration_platform: null,
    },
    {
      tool_id: "google_analytics_mcp.list_ga_accounts",
      name: "list_ga_accounts",
      description: "List GA accounts.",
      category: "analytics",
      source: "integration",
      mcp_server: "google_analytics_mcp",
      integration_platform: "google_analytics",
    },
  ],
};

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
  mockGetAccountTools.mockResolvedValue(defaultTools);
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

  it("submits tool_ids: [] by default when the user makes no selection", async () => {
    mockCreateAgentConfig.mockResolvedValueOnce({
      config_id: "custom_abc12345",
      customization_status: "custom_agent",
    });

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

    await waitFor(() =>
      expect(mockCreateAgentConfig).toHaveBeenCalledWith(
        "acc_test",
        expect.objectContaining({ tool_ids: [] }),
      ),
    );
  });

  it("submits the picked tool_ids when the user selects tools", async () => {
    mockCreateAgentConfig.mockResolvedValueOnce({
      config_id: "custom_abc12345",
      customization_status: "custom_agent",
    });

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

    // Wait for inventory to load — render shows checkboxes once the query
    // resolves.
    const checkbox = await screen.findByTestId(
      "tool-picker-checkbox-function.create_visualization",
    );
    await user.click(checkbox);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /create agent/i }),
      ).not.toBeDisabled(),
    );

    await user.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() =>
      expect(mockCreateAgentConfig).toHaveBeenCalledWith(
        "acc_test",
        expect.objectContaining({
          tool_ids: ["function.create_visualization"],
        }),
      ),
    );
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

  it("accepts up to 30 tool_ids", () => {
    const ids = Array.from({ length: 30 }, (_, i) => `function.t${i}`);
    expect(schema.safeParse({ ...baseInput, tool_ids: ids }).success).toBe(
      true,
    );
  });

  it("rejects more than 30 tool_ids", () => {
    const ids = Array.from({ length: 31 }, (_, i) => `function.t${i}`);
    const result = schema.safeParse({ ...baseInput, tool_ids: ids });
    expect(result.success).toBe(false);
  });

  it("defaults tool_ids to [] when omitted", () => {
    const result = schema.safeParse(baseInput);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.tool_ids).toEqual([]);
    }
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

describe("AgentCreatePage — ken_e_sub_agent toggle", () => {
  it("renders the toggle defaulting to on", () => {
    render(<AgentCreatePage />, { wrapper: makeWrapper() });
    const toggle = screen.getByTestId("ken-e-sub-agent-toggle");
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("data-state", "checked");
  });

  it("submits ken_e_sub_agent: true when left at the default", async () => {
    mockCreateAgentConfig.mockResolvedValueOnce({
      config_id: "custom_abc12345",
      customization_status: "custom_agent",
    });
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

    await waitFor(() =>
      expect(mockCreateAgentConfig).toHaveBeenCalledWith(
        "acc_test",
        expect.objectContaining({ ken_e_sub_agent: true }),
      ),
    );
  });

  it("submits ken_e_sub_agent: false when toggled off", async () => {
    mockCreateAgentConfig.mockResolvedValueOnce({
      config_id: "custom_abc12345",
      customization_status: "custom_agent",
    });
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

    // Turn the toggle off before submitting
    await user.click(screen.getByTestId("ken-e-sub-agent-toggle"));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /create agent/i }),
      ).not.toBeDisabled(),
    );
    await user.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() =>
      expect(mockCreateAgentConfig).toHaveBeenCalledWith(
        "acc_test",
        expect.objectContaining({ ken_e_sub_agent: false }),
      ),
    );
  });
});

// ─── AH-95: user-built GA agent via AgentToolPicker ───────────────────────────

describe("AgentCreatePage — GA MCP tool selection (AH-95)", () => {
  it("submits a GA MCP tool alongside a function tool in tool_ids", async () => {
    mockCreateAgentConfig.mockResolvedValueOnce({
      config_id: "custom_ga_abc123",
      customization_status: "custom_agent",
    });

    // Override the inventory to include GA MCP tools.
    const gaInventory = {
      tools: [
        {
          tool_id: "function.create_visualization",
          name: "create_visualization",
          description: "Render a chart.",
          category: "general",
          source: "global_default",
          mcp_server: null,
          integration_platform: null,
        },
        {
          tool_id: "google_analytics_mcp.list_ga_accounts",
          name: "list_ga_accounts",
          description: "List GA accounts.",
          category: "analytics",
          source: "integration",
          mcp_server: "google_analytics_mcp",
          integration_platform: "google_analytics",
        },
        {
          tool_id: "google_analytics_mcp.run_report",
          name: "run_report",
          description: "Run an analytics report.",
          category: "analytics",
          source: "integration",
          mcp_server: "google_analytics_mcp",
          integration_platform: "google_analytics",
        },
      ],
    };
    mockGetAccountTools.mockResolvedValue(gaInventory);

    const user = userEvent.setup();
    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    await user.type(screen.getByTestId("title-input"), "My GA Agent");
    await user.type(
      screen.getByTestId("instruction-field"),
      "You are a GA analytics assistant.",
    );
    await user.click(screen.getByTestId("model-select"));
    const modelOptions = await screen.findAllByRole("option");
    await user.click(modelOptions[0]);

    // Select the GA tool and the function tool.
    const gaCheckbox = await screen.findByTestId(
      "tool-picker-checkbox-google_analytics_mcp.list_ga_accounts",
    );
    await user.click(gaCheckbox);

    const vizCheckbox = screen.getByTestId(
      "tool-picker-checkbox-function.create_visualization",
    );
    await user.click(vizCheckbox);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /create agent/i }),
      ).not.toBeDisabled(),
    );

    await user.click(screen.getByRole("button", { name: /create agent/i }));

    await waitFor(() =>
      expect(mockCreateAgentConfig).toHaveBeenCalledWith(
        "acc_test",
        expect.objectContaining({
          tool_ids: expect.arrayContaining([
            "google_analytics_mcp.list_ga_accounts",
            "function.create_visualization",
          ]),
        }),
      ),
    );
  });

  it("shows the google_analytics_mcp group when GA tools are in inventory", async () => {
    const gaInventory = {
      tools: [
        {
          tool_id: "google_analytics_mcp.list_ga_accounts",
          name: "list_ga_accounts",
          description: "List GA accounts.",
          category: "analytics",
          source: "integration",
          mcp_server: "google_analytics_mcp",
          integration_platform: "google_analytics",
        },
      ],
    };
    mockGetAccountTools.mockResolvedValue(gaInventory);

    render(<AgentCreatePage />, { wrapper: makeWrapper() });

    // Wait for the picker to load and render the GA group.
    await screen.findByTestId("tool-picker-group-google_analytics_mcp");
  });
});
