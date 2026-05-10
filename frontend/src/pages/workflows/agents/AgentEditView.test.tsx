import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AgentEditView } from "./AgentEditView";
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

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { useAuth } from "@/contexts/AuthContext";
import {
  useAgentConfig,
  useUpsertAgentConfigOverlay,
  useDeleteAgentConfig,
} from "@/queries/agentConfigs";

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;
const mockUseAgentConfig = useAgentConfig as ReturnType<typeof vi.fn>;
const mockUseUpsertOverlay = useUpsertAgentConfigOverlay as ReturnType<
  typeof vi.fn
>;
const mockUseDeleteAgentConfig = useDeleteAgentConfig as ReturnType<
  typeof vi.fn
>;

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const baseConfig: MergedAgentConfig = {
  config_id: "google_analytics_specialist",
  name: null,
  instruction: "You are a GA specialist.",
  model: "gemini-2.5-flash",
  description: "Analyzes GA data.",
  temperature: 0.2,
  code_execution_enabled: true,
  mcp_servers: [],
  skill_ids: [],
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
