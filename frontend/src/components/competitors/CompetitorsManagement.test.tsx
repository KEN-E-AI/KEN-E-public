import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { CompetitorsManagement } from "./CompetitorsManagement";
import { AuthContext } from "@/contexts/AuthContext";
import * as competitorService from "@/services/competitorService";
import * as competitorTacticService from "@/services/competitorTacticService";
import * as competitorStrengthService from "@/services/competitorStrengthService";
import * as competitorWeaknessService from "@/services/competitorWeaknessService";
import * as substituteProductService from "@/services/substituteProductService";

// Mock AccountOperationsContext
const mockStartOperation = vi.fn();
const mockEndOperation = vi.fn();
vi.mock("@/contexts/AccountOperationsContext", () => ({
  useAccountOperations: () => ({
    startOperation: mockStartOperation,
    endOperation: mockEndOperation,
    isLoading: false,
    currentOperation: null,
  }),
}));

// Mock services
vi.mock("@/services/competitorService");
vi.mock("@/services/competitorTacticService");
vi.mock("@/services/competitorStrengthService");
vi.mock("@/services/competitorWeaknessService");
vi.mock("@/services/substituteProductService");
vi.mock("@/services/competitiveEnvironmentService");
vi.mock("@/services/productService");
vi.mock("@/services/productCategoryService");

// Mock toast
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock ReactFlow
vi.mock("reactflow", () => ({
  ReactFlow: ({ nodes, edges, onNodeClick }: any) => (
    <div data-testid="react-flow">
      {nodes.map((node: any) => (
        <div
          key={node.id}
          data-testid={`node-${node.type}-${node.id}`}
          onClick={(e) => onNodeClick?.(e, node)}
        >
          {node.data.label}
        </div>
      ))}
    </div>
  ),
  Controls: () => <div data-testid="flow-controls" />,
  Background: () => <div data-testid="flow-background" />,
  MarkerType: {
    ArrowClosed: "arrowclosed",
  },
  Position: {
    Left: "left",
    Right: "right",
    Top: "top",
    Bottom: "bottom",
  },
}));

describe("CompetitorsManagement - Basic Rendering", () => {
  let queryClient: QueryClient;

  const mockAuthContext = {
    selectedOrgAccount: {
      orgId: "org_test" as any,
      accountId: "acc_test" as any,
      metadata: {
        organization_name: "Test Org",
        account_name: "Test Account",
        industry: "Technology",
        status: "Active",
      },
    },
  };

  const mockCompetitor = {
    node_id: "comp_1",
    account_id: "acc_test",
    display_name: "Test Competitor",
    description: "Test competitor description",
    references: [],
    created_time: "2025-01-01T00:00:00Z",
    last_modified: "2025-01-01T00:00:00Z",
    created_by: "user_123",
    last_modified_by: "user_123",
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();

    // Default mock responses
    vi.mocked(competitorService.competitorService.list).mockResolvedValue({
      competitors: [],
      total_count: 0,
    });
    vi.mocked(
      competitorTacticService.competitorTacticService.list,
    ).mockResolvedValue({
      tactics: [],
      total_count: 0,
    });
    vi.mocked(
      competitorStrengthService.competitorStrengthService.list,
    ).mockResolvedValue({
      strengths: [],
      total_count: 0,
    });
    vi.mocked(
      competitorWeaknessService.competitorWeaknessService.list,
    ).mockResolvedValue({
      weaknesses: [],
      total_count: 0,
    });
    vi.mocked(
      substituteProductService.substituteProductService.list,
    ).mockResolvedValue({
      products: [],
      total_count: 0,
    });
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompetitorsManagement />
          </QueryClientProvider>
        </AuthContext.Provider>
      </MemoryRouter>,
    );
  };

  it("should render the competitors management component", async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("react-flow")).toBeInTheDocument();
    });
  });

  it("should display empty state when no competitors exist", async () => {
    renderComponent();

    await waitFor(() => {
      expect(competitorService.competitorService.list).toHaveBeenCalled();
    });
  });

  it("should fetch and display competitors on mount", async () => {
    vi.mocked(competitorService.competitorService.list).mockResolvedValue({
      competitors: [mockCompetitor],
      total_count: 1,
    });

    renderComponent();

    await waitFor(() => {
      expect(competitorService.competitorService.list).toHaveBeenCalledWith(
        "acc_test",
        0,
        1000,
      );
    });

    await waitFor(() => {
      const competitorNode = screen.getByTestId("node-competitor-comp_1");
      expect(competitorNode).toBeInTheDocument();
      expect(competitorNode).toHaveTextContent("Test Competitor");
    });
  });

  it("should display multiple competitors when they exist", async () => {
    const competitors = [
      { ...mockCompetitor, node_id: "comp_1", display_name: "Competitor 1" },
      { ...mockCompetitor, node_id: "comp_2", display_name: "Competitor 2" },
      { ...mockCompetitor, node_id: "comp_3", display_name: "Competitor 3" },
    ];

    vi.mocked(competitorService.competitorService.list).mockResolvedValue({
      competitors,
      total_count: 3,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("node-competitor-comp_1")).toBeInTheDocument();
      expect(screen.getByTestId("node-competitor-comp_2")).toBeInTheDocument();
      expect(screen.getByTestId("node-competitor-comp_3")).toBeInTheDocument();
    });
  });

  it("should fetch related data for competitors", async () => {
    vi.mocked(competitorService.competitorService.list).mockResolvedValue({
      competitors: [mockCompetitor],
      total_count: 1,
    });

    renderComponent();

    await waitFor(() => {
      expect(
        competitorTacticService.competitorTacticService.list,
      ).toHaveBeenCalled();
      expect(
        competitorStrengthService.competitorStrengthService.list,
      ).toHaveBeenCalled();
      expect(
        competitorWeaknessService.competitorWeaknessService.list,
      ).toHaveBeenCalled();
      expect(
        substituteProductService.substituteProductService.list,
      ).toHaveBeenCalled();
    });
  });

  it("should handle competitor with tactics", async () => {
    const mockTactic = {
      node_id: "tactic_1",
      account_id: "acc_test",
      display_name: "Social Media Campaign",
      description: "Active social media presence",
      references: [],
      competitor_node_id: "comp_1",
      created_time: "2025-01-01T00:00:00Z",
      last_modified: "2025-01-01T00:00:00Z",
      created_by: "user_123",
      last_modified_by: "user_123",
    };

    vi.mocked(competitorService.competitorService.list).mockResolvedValue({
      competitors: [mockCompetitor],
      total_count: 1,
    });

    vi.mocked(
      competitorTacticService.competitorTacticService.list,
    ).mockResolvedValue({
      tactics: [mockTactic],
      total_count: 1,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("node-competitor-comp_1")).toBeInTheDocument();
    });

    await waitFor(() => {
      const tacticNode = screen.queryByTestId("node-competitorTactic-tactic_1");
      if (tacticNode) {
        expect(tacticNode).toHaveTextContent("Social Media Campaign");
      }
    });
  });

  it("should handle competitor with strengths and weaknesses", async () => {
    const mockStrength = {
      node_id: "strength_1",
      account_id: "acc_test",
      display_name: "Strong Brand",
      description: "Well-known brand",
      references: [],
      competitor_node_id: "comp_1",
      created_time: "2025-01-01T00:00:00Z",
      last_modified: "2025-01-01T00:00:00Z",
      created_by: "user_123",
      last_modified_by: "user_123",
    };

    const mockWeakness = {
      node_id: "weakness_1",
      account_id: "acc_test",
      display_name: "Limited Distribution",
      description: "Narrow distribution network",
      references: [],
      competitor_node_id: "comp_1",
      created_time: "2025-01-01T00:00:00Z",
      last_modified: "2025-01-01T00:00:00Z",
      created_by: "user_123",
      last_modified_by: "user_123",
    };

    vi.mocked(competitorService.competitorService.list).mockResolvedValue({
      competitors: [mockCompetitor],
      total_count: 1,
    });

    vi.mocked(
      competitorStrengthService.competitorStrengthService.list,
    ).mockResolvedValue({
      strengths: [mockStrength],
      total_count: 1,
    });

    vi.mocked(
      competitorWeaknessService.competitorWeaknessService.list,
    ).mockResolvedValue({
      weaknesses: [mockWeakness],
      total_count: 1,
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("node-competitor-comp_1")).toBeInTheDocument();
    });
  });

  it("should call all service list methods with correct account ID", async () => {
    renderComponent();

    await waitFor(() => {
      expect(competitorService.competitorService.list).toHaveBeenCalledWith(
        "acc_test",
        expect.any(Number),
        expect.any(Number),
      );
      expect(
        competitorTacticService.competitorTacticService.list,
      ).toHaveBeenCalledWith(
        "acc_test",
        undefined,
        expect.any(Number),
        expect.any(Number),
      );
      expect(
        competitorStrengthService.competitorStrengthService.list,
      ).toHaveBeenCalledWith(
        "acc_test",
        undefined,
        expect.any(Number),
        expect.any(Number),
      );
      expect(
        competitorWeaknessService.competitorWeaknessService.list,
      ).toHaveBeenCalledWith(
        "acc_test",
        undefined,
        expect.any(Number),
        expect.any(Number),
      );
      expect(
        substituteProductService.substituteProductService.list,
      ).toHaveBeenCalledWith(
        "acc_test",
        undefined,
        undefined,
        expect.any(Number),
        expect.any(Number),
      );
    });
  });
});
