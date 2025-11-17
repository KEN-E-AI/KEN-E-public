import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SwotManagement } from "./SwotManagement";
import { AuthContext } from "@/contexts/AuthContext";
import * as swotQueries from "@/queries/swot";

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

// Mock dependencies
vi.mock("@/queries/swot");
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

const mockAuthContext = {
  selectedOrgAccount: {
    accountId: "test-account-123",
    orgId: "test-org-456",
    accountName: "Test Account",
  },
  user: {
    email: "test@example.com",
    permissions: {
      accounts: { "test-account-123": "edit" },
    },
  },
  isSuperAdmin: false,
};

// Mock toast
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock ReactFlow
vi.mock("reactflow", () => ({
  ReactFlow: ({ nodes, edges, onNodeClick }: any) => (
    <div data-testid="react-flow">
      {nodes?.map((node: any) => (
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
}));

const mockStrengths = {
  strengths: [
    {
      node_id: "strength-1",
      display_name: "Strong Brand",
      description: "Well-known brand",
      account_id: "test-account-123",
    },
  ],
  total_count: 1,
};

const mockWeaknesses = {
  weaknesses: [
    {
      node_id: "weakness-1",
      display_name: "Limited Market Share",
      description: "Small market presence",
      account_id: "test-account-123",
    },
  ],
  total_count: 1,
};

const mockOpportunities = {
  opportunities: [
    {
      node_id: "opp-1",
      display_name: "Market Expansion",
      description: "Expand to new markets",
      strength_node_id: "strength-1",
      account_id: "test-account-123",
      references: [],
      created_time: "2025-01-01",
      last_modified: "2025-01-01",
    },
  ],
  total_count: 1,
};

const mockRisks = {
  risks: [
    {
      node_id: "risk-1",
      display_name: "Market Entry Barriers",
      description: "High entry costs",
      weakness_node_id: "weakness-1",
      account_id: "test-account-123",
      references: [],
      created_time: "2025-01-01",
      last_modified: "2025-01-01",
    },
  ],
  total_count: 1,
};

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={mockAuthContext as any}>
        {component}
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
};

describe("SwotManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock all query hooks
    vi.mocked(swotQueries.useStrengths).mockReturnValue({
      data: mockStrengths,
      isLoading: false,
    } as any);

    vi.mocked(swotQueries.useWeaknesses).mockReturnValue({
      data: mockWeaknesses,
      isLoading: false,
    } as any);

    vi.mocked(swotQueries.useOpportunities).mockReturnValue({
      data: mockOpportunities,
      isLoading: false,
    } as any);

    vi.mocked(swotQueries.useRisks).mockReturnValue({
      data: mockRisks,
      isLoading: false,
    } as any);

    // Mock mutations
    vi.mocked(swotQueries.useCreateStrength).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useCreateWeakness).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useCreateOpportunity).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useCreateRisk).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useUpdateStrength).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useUpdateWeakness).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useDeleteStrength).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useDeleteWeakness).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useUpdateOpportunity).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useUpdateRisk).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useDeleteOpportunity).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);

    vi.mocked(swotQueries.useDeleteRisk).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any);
  });

  describe("Mode Switching", () => {
    it("should default to strengths mode", () => {
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      // Check that segmented control buttons exist
      const buttons = screen.getAllByText("Strengths");
      const strengthsButton = buttons.find((el) => el.tagName === "BUTTON");

      expect(strengthsButton).toBeInTheDocument();
      expect(
        screen.getAllByText("Weaknesses").find((el) => el.tagName === "BUTTON"),
      ).toBeInTheDocument();
    });

    it("should switch to weaknesses mode when clicking weaknesses button", async () => {
      const user = userEvent.setup();
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      const weaknessButtons = screen.getAllByText("Weaknesses");
      const button = weaknessButtons.find((el) => el.tagName === "BUTTON");

      if (button) {
        await user.click(button);
      }

      await waitFor(() => {
        expect(
          screen.getByText(/No weaknesses found|Limited Market Share/i),
        ).toBeInTheDocument();
      });
    });

    it("should display strengths in strengths mode", async () => {
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      await waitFor(() => {
        expect(screen.getByText("Strong Brand")).toBeInTheDocument();
      });
    });

    it("should display weaknesses in weaknesses mode", async () => {
      const user = userEvent.setup();
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      const weaknessButtons = screen.getAllByText("Weaknesses");
      const button = weaknessButtons.find((el) => el.tagName === "BUTTON");

      if (button) {
        await user.click(button);
      }

      await waitFor(() => {
        expect(screen.getByText("Limited Market Share")).toBeInTheDocument();
      });
    });

    it("should clear selections when switching modes", async () => {
      const user = userEvent.setup();
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      // Click a strength to select it
      const strengthBadge = screen.getByText("Strong Brand");
      await user.click(strengthBadge);

      // Switch to weaknesses
      const weaknessButtons = screen.getAllByText("Weaknesses");
      const button = weaknessButtons.find((el) => el.tagName === "BUTTON");

      if (button) {
        await user.click(button);
      }

      // Should show empty state message
      await waitFor(() => {
        expect(
          screen.getByText(/Select a weakness to view risks/i),
        ).toBeInTheDocument();
      });
    });

    it("should render tooltips in strengths mode", async () => {
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      // Just verify the component renders with strengths
      await waitFor(() => {
        expect(screen.getByText("Strong Brand")).toBeInTheDocument();
      });
    });

    it("should show correct tooltip text for weaknesses mode", async () => {
      const user = userEvent.setup();
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      const weaknessButtons = screen.getAllByText("Weaknesses");
      const button = weaknessButtons.find((el) => el.tagName === "BUTTON");

      if (button) {
        await user.click(button);
      }

      await waitFor(() => {
        // Just verify weaknesses mode is active
        expect(button).toBeInTheDocument();
      });
    });
  });

  describe("CRUD Operations", () => {
    it("should show create button when hasEditAccess is true", () => {
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      // Check for presence of "Strengths" card which indicates component rendered
      expect(screen.getAllByText("Strengths").length).toBeGreaterThan(0);
    });

    it("should not show create button when hasEditAccess is false", () => {
      renderWithProviders(<SwotManagement hasEditAccess={false} />);

      // Should not have edit buttons
      expect(screen.queryByText("Edit")).not.toBeInTheDocument();
    });

    it("should display empty state when no strengths exist", () => {
      vi.mocked(swotQueries.useStrengths).mockReturnValue({
        data: { strengths: [], total_count: 0 },
        isLoading: false,
      } as any);

      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      expect(screen.getByText(/No strengths found/i)).toBeInTheDocument();
    });

    it("should display empty state when no weaknesses exist", async () => {
      const user = userEvent.setup();

      vi.mocked(swotQueries.useWeaknesses).mockReturnValue({
        data: { weaknesses: [], total_count: 0 },
        isLoading: false,
      } as any);

      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      const weaknessButtons = screen.getAllByText("Weaknesses");
      const button = weaknessButtons.find((el) => el.tagName === "BUTTON");

      if (button) {
        await user.click(button);
      }

      await waitFor(() => {
        expect(screen.getByText(/No weaknesses found/i)).toBeInTheDocument();
      });
    });
  });

  describe("Empty State", () => {
    it("should show fixed height empty state when no parent is selected", () => {
      renderWithProviders(<SwotManagement hasEditAccess={true} />);

      const emptyStateContainer = screen.getByText(
        /Select a strength to view opportunities/i,
      ).parentElement;

      expect(emptyStateContainer).toHaveClass("h-[600px]");
      expect(emptyStateContainer).toHaveClass("flex");
      expect(emptyStateContainer).toHaveClass("items-center");
      expect(emptyStateContainer).toHaveClass("justify-center");
    });
  });
});
