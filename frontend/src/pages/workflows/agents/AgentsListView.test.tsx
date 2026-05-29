import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AgentsListView } from "./AgentsListView";
import type { MergedAgentConfig } from "@/lib/api/agentConfigs";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/queries/agentConfigs", () => ({
  useAgentConfigsList: vi.fn(),
}));

import { useAuth } from "@/contexts/AuthContext";
import { useAgentConfigsList } from "@/queries/agentConfigs";

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>;
const mockUseAgentConfigsList = useAgentConfigsList as ReturnType<typeof vi.fn>;

// ─── Test fixtures ────────────────────────────────────────────────────────────

const defaultConfig: MergedAgentConfig = {
  config_id: "google_analytics_specialist",
  title: "Google Analytics Specialist",
  name: null,
  instruction: "You are a GA specialist.",
  model: "gemini-2.5-flash",
  description: "Analyzes Google Analytics data.",
  temperature: 0.2,
  code_execution_enabled: true,
  mcp_servers: ["google_analytics_mcp"],
  skill_ids: [],
  tool_ids: [],
  sandbox_code_executor_enabled: false,
  response_schema: null,
  available_to_copy: true,
  automatically_available: true,
  visible_in_frontend: true,
  ken_e_sub_agent: true,
  customization_status: "default",
  based_on_version: null,
};

const customizedConfig: MergedAgentConfig = {
  ...defaultConfig,
  config_id: "google_analytics_specialist",
  customization_status: "customized",
  based_on_version: 1,
  temperature: 0.5,
};

const customAgentConfig: MergedAgentConfig = {
  config_id: "custom_abc123",
  title: "My Custom Agent",
  name: "My Custom Agent",
  instruction: "Do something special.",
  model: "gemini-2.5-pro",
  description: "A custom agent for my use case.",
  temperature: 0.3,
  code_execution_enabled: false,
  mcp_servers: [],
  skill_ids: [],
  tool_ids: [],
  sandbox_code_executor_enabled: false,
  response_schema: null,
  available_to_copy: false,
  automatically_available: false,
  visible_in_frontend: true,
  ken_e_sub_agent: true,
  customization_status: "custom_agent",
  based_on_version: null,
};

// ─── Wrapper ──────────────────────────────────────────────────────────────────

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
    selectedOrgAccount: { accountId: "acc_test123" },
  });
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AgentsListView — loading state", () => {
  it("renders skeleton cards while loading", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    // Skeleton renders without text content — confirm no cards appear
    expect(screen.queryByRole("button", { name: /configure/i })).toBeNull();
  });
});

describe("AgentsListView — error state", () => {
  it("shows an error message when the query fails", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByText(/failed to load agents/i)).toBeInTheDocument();
  });
});

describe("AgentsListView — empty state", () => {
  it("shows the empty state copy when no configs are returned", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(
      screen.getByText(/Assemble specialist agents tailored to your workflow/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create an agent/i }),
    ).toBeInTheDocument();
  });
});

describe("AgentsListView — no account selected", () => {
  it("shows 'select an account' message when accountId is null", () => {
    mockUseAuth.mockReturnValue({ selectedOrgAccount: null });
    mockUseAgentConfigsList.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(
      screen.getByText(/select an account to view agents/i),
    ).toBeInTheDocument();
  });
});

describe("AgentsListView — renders cards", () => {
  it("renders three cards with correct customization statuses", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig, customizedConfig, customAgentConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });

    // All three configure buttons are rendered
    const configureButtons = screen.getAllByRole("button", {
      name: /configure/i,
    });
    expect(configureButtons).toHaveLength(3);
  });

  it("renders 'Default' badge for default customization status", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByText("Default")).toBeInTheDocument();
  });

  it("renders 'Customized' badge for customized status", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [customizedConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByText("Customized")).toBeInTheDocument();
  });

  it("renders 'Custom Agent' badge for custom_agent status", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [customAgentConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByText("Custom Agent")).toBeInTheDocument();
  });

  it("shows the model name for each card", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByText("gemini-2.5-flash")).toBeInTheDocument();
  });

  it("shows the description when provided", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(
      screen.getByText("Analyzes Google Analytics data."),
    ).toBeInTheDocument();
  });
});

describe("AgentsListView — top action button", () => {
  it("renders the New Agent button when configs are present", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByTestId("new-agent-button")).toBeInTheDocument();
  });

  it("renders the New Agent button in the empty state", () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    expect(screen.getByTestId("new-agent-button")).toBeInTheDocument();
  });

  it("New Agent button navigates to /workflows/agents/new", async () => {
    const user = userEvent.setup();
    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });
    await user.click(screen.getByTestId("new-agent-button"));
    expect(mockNavigate).toHaveBeenCalledWith("/workflows/agents/new");
  });
});

describe("AgentsListView — interactions", () => {
  it("calls onEdit with configId when Configure button is clicked", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();

    mockUseAgentConfigsList.mockReturnValue({
      data: [defaultConfig],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={onEdit} />, { wrapper: makeWrapper() });

    await user.click(
      screen.getByRole("button", {
        name: /configure google analytics specialist/i,
      }),
    );
    expect(onEdit).toHaveBeenCalledWith("google_analytics_specialist");
  });

  it("passes visibleInFrontend: true to the query hook", async () => {
    mockUseAgentConfigsList.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    render(<AgentsListView onEdit={vi.fn()} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(mockUseAgentConfigsList).toHaveBeenCalledWith("acc_test123", {
        visibleInFrontend: true,
      });
    });
  });
});
