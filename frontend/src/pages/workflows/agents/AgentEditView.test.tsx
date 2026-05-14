import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AgentEditView, snapTemperatureToGrid } from "./AgentEditView";
import type { MergedAgentConfig } from "@/lib/api/agentConfigs";
import { toAgentConfigId } from "@/lib/api/agentConfigs";

// ─── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/queries/agentConfigs", () => ({
  useAgentConfig: vi.fn(),
  useUpsertAgentConfigOverlay: vi.fn(),
  useDeleteAgentConfig: vi.fn(),
}));

vi.mock("@/queries/tools", () => ({
  useAccountTools: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { useAuth } from "@/contexts/AuthContext";
import {
  useAgentConfig,
  useUpsertAgentConfigOverlay,
  useDeleteAgentConfig,
} from "@/queries/agentConfigs";
import { useAccountTools } from "@/queries/tools";

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;
const mockUseAgentConfig = useAgentConfig as ReturnType<typeof vi.fn>;
const mockUseUpsertOverlay = useUpsertAgentConfigOverlay as ReturnType<
  typeof vi.fn
>;
const mockUseDeleteAgentConfig = useDeleteAgentConfig as ReturnType<
  typeof vi.fn
>;
const mockUseAccountTools = useAccountTools as ReturnType<typeof vi.fn>;

const fixtureTools = {
  tools: [
    {
      tool_id: "function.create_visualization",
      name: "create_visualization",
      description: "Render a chart.",
      category: "general",
      source: "global_default" as const,
      mcp_server: null,
      integration_platform: null,
    },
    {
      tool_id: "google_analytics_mcp.list_ga_accounts",
      name: "list_ga_accounts",
      description: "List GA accounts.",
      category: "analytics",
      source: "integration" as const,
      mcp_server: "google_analytics_mcp",
      integration_platform: "google_analytics",
    },
  ],
};

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const baseConfig: MergedAgentConfig = {
  config_id: "google_analytics_specialist",
  name: null,
  title: null,
  instruction: "You are a GA specialist.",
  model: "gemini-2.5-flash",
  description: "Analyzes GA data.",
  temperature: 0.2,
  code_execution_enabled: true,
  mcp_servers: [],
  skill_ids: [],
  // Legacy default — pre-AH-PRD-06 agents store null here.
  tool_ids: null,
  sandbox_code_executor_enabled: false,
  response_schema: null,
  available_to_copy: true,
  automatically_available: true,
  visible_in_frontend: true,
  customization_status: "default",
  based_on_version: null,
};

const customizedConfig: MergedAgentConfig = {
  ...baseConfig,
  customization_status: "customized",
  based_on_version: 2,
  temperature: 0.5,
};

const customAgentConfig: MergedAgentConfig = {
  ...baseConfig,
  config_id: "custom_abc123",
  name: "My Custom Agent",
  customization_status: "custom_agent",
  based_on_version: null,
};

// ─── Wrapper + default mutation stubs ─────────────────────────────────────────

const mockMutate = vi.fn();

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
  mockUseAuth.mockReturnValue({
    selectedOrgAccount: { accountId: "acc_test" },
  });
  mockUseUpsertOverlay.mockReturnValue({
    mutate: mockMutate,
    isPending: false,
  });
  mockUseDeleteAgentConfig.mockReturnValue({
    mutate: mockMutate,
    isPending: false,
  });
  // Default: inventory loaded with two tools. Individual tests can override
  // for loading / error / empty states.
  mockUseAccountTools.mockReturnValue({
    data: fixtureTools,
    isLoading: false,
    isError: false,
  });
});

const configId = toAgentConfigId("google_analytics_specialist");

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AgentEditView — loading state", () => {
  it("renders skeleton while config is loading", () => {
    mockUseAgentConfig.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    // Skeletons render; form fields absent
    expect(screen.queryByTestId("instruction-field")).toBeNull();
  });
});

describe("AgentEditView — error state", () => {
  it("shows an error message when config fetch fails", () => {
    mockUseAgentConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(
      screen.getByText(/failed to load agent configuration/i),
    ).toBeInTheDocument();
  });
});

describe("AgentEditView — form fields", () => {
  beforeEach(() => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });
  });

  it("renders instruction, temperature, model, description fields", () => {
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("instruction-field")).toBeInTheDocument();
    expect(screen.getByTestId("temperature-slider")).toBeInTheDocument();
    expect(screen.getByTestId("model-select")).toBeInTheDocument();
    expect(screen.getByTestId("description-field")).toBeInTheDocument();
  });

  it("populates instruction with the loaded config value", () => {
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    const textarea = screen.getByTestId(
      "instruction-field",
    ) as HTMLTextAreaElement;
    expect(textarea.value).toBe("You are a GA specialist.");
  });
});

describe("AgentEditView — dirty indicator", () => {
  it("shows no dirty dots initially (all fields match loaded config)", () => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.queryAllByTestId("dirty-indicator")).toHaveLength(0);
  });

  it("shows a dirty dot when instruction is modified", async () => {
    const user = userEvent.setup();
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    const textarea = screen.getByTestId("instruction-field");
    await user.clear(textarea);
    await user.type(textarea, "Modified instruction.");

    await waitFor(() => {
      expect(screen.getAllByTestId("dirty-indicator").length).toBeGreaterThan(
        0,
      );
    });
  });
});

describe("AgentEditView — Save Changes", () => {
  it("Save Changes button is disabled when no fields are dirty", () => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("save-button")).toBeDisabled();
  });

  it("calls upsertAgentConfigOverlay mutation with only dirty fields", async () => {
    const user = userEvent.setup();
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    const textarea = screen.getByTestId("instruction-field");
    await user.clear(textarea);
    await user.type(textarea, "Updated instruction.");

    const saveBtn = screen.getByTestId("save-button");
    await waitFor(() => expect(saveBtn).not.toBeDisabled());
    await user.click(saveBtn);

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        configId: "google_analytics_specialist",
        body: expect.objectContaining({ instruction: "Updated instruction." }),
      }),
      expect.anything(),
    );
  });
});

describe("AgentEditView — client validation", () => {
  beforeEach(() => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });
  });

  it("disables Save and shows an error when instruction is shortened below 10 chars", async () => {
    const user = userEvent.setup();
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    const textarea = screen.getByTestId("instruction-field");
    await user.clear(textarea);
    await user.type(textarea, "too short");

    await waitFor(() => {
      expect(
        screen.getByText("Instruction must be at least 10 characters"),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("save-button")).toBeDisabled();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("disables Save when description is non-empty but shorter than 10 chars", async () => {
    const user = userEvent.setup();
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    const descField = screen.getByTestId("description-field");
    await user.clear(descField);
    await user.type(descField, "short");

    await waitFor(() => {
      expect(
        screen.getByText("Description must be at least 10 characters"),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("save-button")).toBeDisabled();
  });

  it("disables Save when description is cleared on an existing agent", async () => {
    // Regression: clearing description used to slip past validation and
    // ``handleSave`` would send ``{description: null}``, leaving the agent
    // saved to Firestore with no description.
    const user = userEvent.setup();
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    const descField = screen.getByTestId("description-field");
    await user.clear(descField);

    await waitFor(() => {
      expect(screen.getByText("Description is required")).toBeInTheDocument();
    });
    expect(screen.getByTestId("save-button")).toBeDisabled();
    expect(mockMutate).not.toHaveBeenCalled();
  });
});

describe("AgentEditView — server validation", () => {
  it("maps FastAPI 422 detail entries onto the matching fields", async () => {
    // Capture the onError callback the component passes to ``mutate`` so we
    // can drive the 422 path explicitly — the mock mutation doesn't actually
    // call the API, so we need to invoke it ourselves.
    const capture = vi.fn();
    mockUseUpsertOverlay.mockReturnValue({
      mutate: capture,
      isPending: false,
    });
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    const { toast } = await import("sonner");
    const user = userEvent.setup();
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    // Make a valid edit so save is enabled.
    const textarea = screen.getByTestId("instruction-field");
    await user.clear(textarea);
    await user.type(textarea, "Updated instruction text.");

    await user.click(screen.getByTestId("save-button"));

    // The component currently passes a callbacks object as ``mutate``'s
    // second arg; we grab ``onError`` off the captured call and invoke it
    // with a synthetic 422 to drive the server-validation path. If we ever
    // migrate to ``mutateAsync().catch(...)`` or move ``onError`` into the
    // hook itself, this test will need a corresponding update.
    const [, opts] = capture.mock.calls[0];
    act(() => {
      opts.onError({
        response: {
          status: 422,
          data: {
            detail: [
              {
                type: "string_too_short",
                loc: ["body", "description"],
                msg: "String should have at least 10 characters",
                ctx: { min_length: 10 },
              },
            ],
          },
        },
      });
    });

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

describe("AgentEditView — Revert button", () => {
  it("hides Revert button for default configs", () => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.queryByTestId("revert-button")).toBeNull();
  });

  it("shows 'Revert to default' for customized configs", () => {
    mockUseAgentConfig.mockReturnValue({
      data: customizedConfig,
      isLoading: false,
      isError: false,
    });
    const customizedId = toAgentConfigId("google_analytics_specialist");

    render(<AgentEditView configId={customizedId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(
      screen.getByRole("button", { name: /revert to default/i }),
    ).toBeInTheDocument();
  });

  it("shows 'Delete agent' for custom_agent configs", () => {
    mockUseAgentConfig.mockReturnValue({
      data: customAgentConfig,
      isLoading: false,
      isError: false,
    });
    const customId = toAgentConfigId("custom_abc123");

    render(<AgentEditView configId={customId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(
      screen.getByRole("button", { name: /delete agent/i }),
    ).toBeInTheDocument();
  });

  it("calls deleteAgentConfig mutation when Revert is clicked", async () => {
    const user = userEvent.setup();
    mockUseAgentConfig.mockReturnValue({
      data: customizedConfig,
      isLoading: false,
      isError: false,
    });
    const customizedId = toAgentConfigId("google_analytics_specialist");

    render(<AgentEditView configId={customizedId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    await user.click(screen.getByTestId("revert-button"));
    expect(mockMutate).toHaveBeenCalledWith(
      { configId: "google_analytics_specialist" },
      expect.anything(),
    );
  });
});

describe("AgentEditView — based_on_version", () => {
  it("displays 'v2' chip when based_on_version is 2", () => {
    mockUseAgentConfig.mockReturnValue({
      data: customizedConfig,
      isLoading: false,
      isError: false,
    });
    const customizedId = toAgentConfigId("google_analytics_specialist");

    render(<AgentEditView configId={customizedId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("based-on-version-chip")).toHaveTextContent("v2");
  });

  it("does not render version chip when based_on_version is null", () => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.queryByTestId("based-on-version-chip")).toBeNull();
  });
});

describe("AgentEditView — disabled placeholder rows", () => {
  beforeEach(() => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });
  });

  it("renders the Skills disabled row", () => {
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("disabled-row-skills")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
  });

  it("renders the Sandbox code execution disabled row", () => {
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(
      screen.getByTestId("disabled-row-sandbox-code-execution"),
    ).toBeInTheDocument();
    expect(screen.getByText("Sandbox code execution")).toBeInTheDocument();
  });
});

describe("snapTemperatureToGrid", () => {
  it("rounds within-range values to the nearest 0.1", () => {
    // 0.34/0.36 chosen rather than 0.35 to avoid the IEEE 754 representation
    // of 0.35 (≈0.34999...) which is technically below the midpoint.
    expect(snapTemperatureToGrid(0.34)).toBe(0.3);
    expect(snapTemperatureToGrid(0.36)).toBe(0.4);
    expect(snapTemperatureToGrid(0.56)).toBe(0.6);
    expect(snapTemperatureToGrid(0.7)).toBe(0.7);
  });

  it("clamps below 0.1 up to 0.1", () => {
    expect(snapTemperatureToGrid(0)).toBe(0.1);
    expect(snapTemperatureToGrid(0.05)).toBe(0.1);
  });

  it("clamps above 0.9 down to 0.9", () => {
    expect(snapTemperatureToGrid(1)).toBe(0.9);
    expect(snapTemperatureToGrid(0.97)).toBe(0.9);
  });

  it("falls back to 0.3 when null/undefined", () => {
    expect(snapTemperatureToGrid(null)).toBe(0.3);
    expect(snapTemperatureToGrid(undefined)).toBe(0.3);
  });
});

// ─── Tool picker (AH-PRD-06) ─────────────────────────────────────────────────

describe("AgentEditView — tool picker", () => {
  it("pre-selects every available tool when stored tool_ids is null (legacy)", async () => {
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig, // tool_ids: null
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() =>
      expect(screen.getByTestId("tool-picker-summary")).toHaveTextContent(
        "2 of 2 selected",
      ),
    );
  });

  it("pre-selects exactly the stored tool_ids when set", async () => {
    mockUseAgentConfig.mockReturnValue({
      data: {
        ...baseConfig,
        tool_ids: ["function.create_visualization"],
      },
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    await waitFor(() =>
      expect(screen.getByTestId("tool-picker-summary")).toHaveTextContent(
        "1 of 2 selected",
      ),
    );
  });

  it("does not include tool_ids in PUT when the picker is untouched (legacy null)", async () => {
    const user = userEvent.setup();
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig, // tool_ids: null
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    // Make a different field dirty so save is enabled.
    const textarea = screen.getByTestId("instruction-field");
    await user.clear(textarea);
    await user.type(textarea, "Updated instruction text.");

    await waitFor(() =>
      expect(screen.getByTestId("save-button")).not.toBeDisabled(),
    );
    await user.click(screen.getByTestId("save-button"));

    expect(mockMutate).toHaveBeenCalled();
    const [args] = mockMutate.mock.calls[0];
    expect(args.body).not.toHaveProperty("tool_ids");
  });

  it("includes tool_ids in PUT when the user toggles a tool", async () => {
    const user = userEvent.setup();
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig, // tool_ids: null → all available pre-selected
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    // Wait for the picker to seed.
    const builtinCheckbox = await screen.findByTestId(
      "tool-picker-checkbox-function.create_visualization",
    );
    // Deselecting one tool makes the selection differ from the seed.
    await user.click(builtinCheckbox);

    await waitFor(() =>
      expect(screen.getByTestId("save-button")).not.toBeDisabled(),
    );
    await user.click(screen.getByTestId("save-button"));

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          tool_ids: ["google_analytics_mcp.list_ga_accounts"],
        }),
      }),
      expect.anything(),
    );
  });

  it("clears the dirty flag when the user toggles a tool back to its seeded state", async () => {
    const user = userEvent.setup();
    mockUseAgentConfig.mockReturnValue({
      data: {
        ...baseConfig,
        tool_ids: ["function.create_visualization"],
      },
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    const builtinCheckbox = await screen.findByTestId(
      "tool-picker-checkbox-function.create_visualization",
    );

    // Toggle off then back on — the dirty dot should appear and disappear.
    await user.click(builtinCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId("save-button")).not.toBeDisabled(),
    );

    await user.click(builtinCheckbox);
    await waitFor(() =>
      expect(screen.getByTestId("save-button")).toBeDisabled(),
    );
  });

  it("surfaces a server 422 on tool_ids onto the picker section", async () => {
    const capture = vi.fn();
    mockUseUpsertOverlay.mockReturnValue({
      mutate: capture,
      isPending: false,
    });
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    const user = userEvent.setup();
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });

    // Make any change so save is enabled (server can't reject a no-op save).
    const builtinCheckbox = await screen.findByTestId(
      "tool-picker-checkbox-function.create_visualization",
    );
    await user.click(builtinCheckbox);

    await waitFor(() =>
      expect(screen.getByTestId("save-button")).not.toBeDisabled(),
    );
    await user.click(screen.getByTestId("save-button"));

    const [, opts] = capture.mock.calls[0];
    act(() => {
      opts.onError({
        response: {
          status: 422,
          data: {
            detail: [
              {
                type: "value_error",
                loc: ["body", "tool_ids"],
                msg: "Unknown tool_ids — not present in the tool catalogue",
              },
            ],
          },
        },
      });
    });

    await waitFor(() =>
      expect(screen.getByText(/unknown tool_ids/i)).toBeInTheDocument(),
    );
  });

  it("renders a loading skeleton while the inventory is fetching", () => {
    mockUseAccountTools.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    mockUseAgentConfig.mockReturnValue({
      data: baseConfig,
      isLoading: false,
      isError: false,
    });

    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("tool-picker-loading")).toBeInTheDocument();
  });
});

describe("AgentEditView — response-style slider", () => {
  it("renders the snapped value on the slider thumb", () => {
    mockUseAgentConfig.mockReturnValue({
      data: { ...baseConfig, temperature: 0.2 },
      isLoading: false,
      isError: false,
    });
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("temperature-slider")).toHaveTextContent("0.2");
  });

  it("snaps an off-grid stored value quietly (no dirty dot on first render)", () => {
    mockUseAgentConfig.mockReturnValue({
      data: { ...baseConfig, temperature: 0.36 },
      isLoading: false,
      isError: false,
    });
    render(<AgentEditView configId={configId} onClose={vi.fn()} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByTestId("temperature-slider")).toHaveTextContent("0.4");
    // Temperature row is not marked dirty after the silent snap.
    expect(screen.queryAllByTestId("dirty-indicator")).toHaveLength(0);
  });
});
