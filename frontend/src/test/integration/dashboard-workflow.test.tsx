import { describe, test, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import Performance from "@/pages/Performance";
import Home from "@/pages/Home";
import BigBets from "@/pages/BigBets";
import Insights from "@/pages/Insights";
import axios from "axios";

// Mock axios at the top level
vi.mock("axios");

// Mock organizationApi
vi.mock("@/data/organizationApi", () => ({
  getOrganizations: vi.fn().mockResolvedValue([]),
  getAccountsByOrganizationId: vi.fn().mockResolvedValue([]),
  getOrganizationById: vi.fn().mockResolvedValue(null),
  getAccountById: vi.fn().mockResolvedValue(null),
  getAllAccounts: vi.fn().mockResolvedValue([]),
  organizations: Promise.resolve([]),
  accounts: Promise.resolve([]),
}));

// Mock data
const mockUser = {
  id: "user-123",
  firstName: "John",
  lastName: "Doe",
  email: "john.doe@example.com",
  permissions: {
    organizations: {
      "org-123": "admin",
    },
  },
};

const mockOrgMetadata = {
  "org-123": {
    organization_id: "org-123",
    organization_name: "Test Organization",
    company_size: "Medium",
    agency: false,
    child_organizations: [],
  },
};

const mockSelectedOrgAccount = {
  organization_id: "org-123",
  account_id: "account-456",
  metadata: {
    organization_name: "Test Organization",
    account_name: "Test Account",
  },
};

const mockMetrics = [
  {
    id: "metric-1",
    name: "Revenue",
    value: 150000,
    change: 12.5,
    trend: "up",
    period: "month",
  },
  {
    id: "metric-2",
    name: "Conversion Rate",
    value: 3.2,
    change: -2.1,
    trend: "down",
    period: "month",
  },
  {
    id: "metric-3",
    name: "Customer Acquisition Cost",
    value: 45,
    change: 8.3,
    trend: "up",
    period: "month",
  },
];

const mockInsights = [
  {
    id: "insight-1",
    title: "Revenue Growth Opportunity",
    description: "Social media campaigns are showing 25% higher engagement",
    type: "opportunity",
    priority: "high",
    date: "2024-01-15",
  },
  {
    id: "insight-2",
    title: "Budget Optimization",
    description: "Email marketing ROI is 40% below industry average",
    type: "warning",
    priority: "medium",
    date: "2024-01-14",
  },
];

const mockAuthContext: AuthContextType = {
  user: mockUser,
  isAuthenticated: true,
  isLoading: false,
  orgMetadata: mockOrgMetadata,
  selectedOrgAccount: mockSelectedOrgAccount,
  currentOrganizationId: "org-123",
  notifications: [], // Add notifications array
  setNotifications: vi.fn(),
  notificationSettings: [],
  securitySettings: [],
  setCurrentOrganization: vi.fn(),
  setOrgMetadata: vi.fn(),
  updateUser: vi.fn(),
  setNotificationSettings: vi.fn(),
  signOut: vi.fn(),
  resetWorkspaceSelection: vi.fn(),
  completeWorkspaceSelection: vi.fn(),
  getUserOrganizations: vi.fn(),
  getOrganizationData: vi.fn(),
  refetchUser: vi.fn(),
  clearUserData: vi.fn(),
};

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthContext.Provider value={mockAuthContext}>
          {children}
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe("Dashboard Workflow Integration Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Configure axios mock
    vi.mocked(axios.get).mockResolvedValue({
      data: {
        metrics: mockMetrics,
        insights: mockInsights,
      },
    });
    vi.mocked(axios.post).mockResolvedValue({ data: {} });
    vi.mocked(axios.put).mockResolvedValue({ data: {} });
  });

  describe("Home Dashboard Flow", () => {
    test("should render home dashboard with key components", async () => {
      render(
        <TestWrapper>
          <Home />
        </TestWrapper>,
      );

      // Verify main dashboard elements
      await waitFor(() => {
        expect(screen.getByText("KEN-E")).toBeInTheDocument();
      });

      // Verify dashboard layout
      expect(screen.getByText("Welcome to KEN-E")).toBeInTheDocument();
      expect(
        screen.getByText("Your AI-powered marketing assistant"),
      ).toBeInTheDocument();
    });

    test("should display organization context", async () => {
      render(
        <TestWrapper>
          <Home />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Test Organization")).toBeInTheDocument();
      });

      // Verify organization context is available
      expect(screen.getByText("Test Account")).toBeInTheDocument();
    });

    test("should handle chat interactions", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Home />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("KEN-E")).toBeInTheDocument();
      });

      // Find chat input
      const chatInput = screen.getByPlaceholderText("Ask KEN-E anything...");
      expect(chatInput).toBeInTheDocument();

      // Type message
      await user.type(chatInput, "Show me performance metrics");

      // Send message
      const sendButton = screen.getByText("Send");
      await user.click(sendButton);

      // Verify message was sent
      expect(chatInput).toHaveValue("");
    });
  });

  describe("Performance Dashboard Flow", () => {
    test("should render performance dashboard with metrics", async () => {
      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Verify performance page loads
      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Verify metrics are displayed
      expect(screen.getByText("Key Metrics")).toBeInTheDocument();
      expect(screen.getByText("Revenue")).toBeInTheDocument();
      expect(screen.getByText("Conversion Rate")).toBeInTheDocument();
      expect(screen.getByText("Customer Acquisition Cost")).toBeInTheDocument();
    });

    test("should handle metric filtering", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Find and interact with filter options
      const timeFilter = screen.getByText("This Month");
      await user.click(timeFilter);

      // Select different time period
      const quarterFilter = screen.getByText("This Quarter");
      await user.click(quarterFilter);

      // Verify filter was applied
      expect(screen.getByText("This Quarter")).toBeInTheDocument();
    });

    test("should display metric trends correctly", async () => {
      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Verify trend indicators
      expect(screen.getByText("↑ 12.5%")).toBeInTheDocument(); // Revenue increase
      expect(screen.getByText("↓ 2.1%")).toBeInTheDocument(); // Conversion rate decrease
      expect(screen.getByText("↑ 8.3%")).toBeInTheDocument(); // CAC increase
    });

    test("should handle metric drill-down", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Click on a metric for drill-down
      const revenueMetric = screen.getByText("Revenue");
      await user.click(revenueMetric);

      // Verify drill-down view
      expect(screen.getByText("Revenue Details")).toBeInTheDocument();
    });
  });

  describe("Big Bets Dashboard Flow", () => {
    test("should render big bets dashboard", async () => {
      render(
        <TestWrapper>
          <BigBets />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Big Bets")).toBeInTheDocument();
      });

      // Verify big bets components
      expect(screen.getByText("Strategic Initiatives")).toBeInTheDocument();
      expect(screen.getByText("Current Bets")).toBeInTheDocument();
    });

    test("should handle bet creation workflow", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <BigBets />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Big Bets")).toBeInTheDocument();
      });

      // Click create new bet button
      const createButton = screen.getByText("Create New Bet");
      await user.click(createButton);

      // Verify create bet modal/form
      expect(screen.getByText("New Strategic Bet")).toBeInTheDocument();

      // Fill in bet details
      const betTitleInput = screen.getByPlaceholderText("Enter bet title...");
      await user.type(betTitleInput, "Increase social media ROI");

      const betDescriptionInput = screen.getByPlaceholderText(
        "Describe your bet...",
      );
      await user.type(
        betDescriptionInput,
        "Focus on Instagram and TikTok campaigns",
      );

      // Save bet
      const saveButton = screen.getByText("Save Bet");
      await user.click(saveButton);

      // Verify bet was created
      expect(screen.getByText("Increase social media ROI")).toBeInTheDocument();
    });

    test("should track bet progress", async () => {
      render(
        <TestWrapper>
          <BigBets />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Big Bets")).toBeInTheDocument();
      });

      // Verify progress tracking
      expect(screen.getByText("Progress")).toBeInTheDocument();
      expect(screen.getByText("75%")).toBeInTheDocument(); // Sample progress

      // Verify status indicators
      expect(screen.getByText("On Track")).toBeInTheDocument();
      expect(screen.getByText("At Risk")).toBeInTheDocument();
    });
  });

  describe("Insights Dashboard Flow", () => {
    test("should render insights dashboard", async () => {
      render(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Insights")).toBeInTheDocument();
      });

      // Verify insights components
      expect(screen.getByText("AI Insights")).toBeInTheDocument();
      expect(screen.getByText("Recommendations")).toBeInTheDocument();
    });

    test("should display insights by category", async () => {
      render(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Insights")).toBeInTheDocument();
      });

      // Verify insight categories
      expect(screen.getByText("Opportunities")).toBeInTheDocument();
      expect(screen.getByText("Warnings")).toBeInTheDocument();
      expect(screen.getByText("Trends")).toBeInTheDocument();
    });

    test("should handle insight interactions", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Insights")).toBeInTheDocument();
      });

      // Click on an insight
      const insightCard = screen.getByText("Revenue Growth Opportunity");
      await user.click(insightCard);

      // Verify insight details
      expect(
        screen.getByText(
          "Social media campaigns are showing 25% higher engagement",
        ),
      ).toBeInTheDocument();

      // Verify action buttons
      expect(screen.getByText("Act on This")).toBeInTheDocument();
      expect(screen.getByText("Dismiss")).toBeInTheDocument();
    });

    test("should filter insights by priority", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Insights")).toBeInTheDocument();
      });

      // Filter by high priority
      const highPriorityFilter = screen.getByText("High Priority");
      await user.click(highPriorityFilter);

      // Verify filtering
      expect(
        screen.getByText("Revenue Growth Opportunity"),
      ).toBeInTheDocument();
      expect(screen.queryByText("Budget Optimization")).not.toBeInTheDocument();
    });
  });

  describe("Cross-Dashboard Navigation", () => {
    test("should navigate between dashboard sections", async () => {
      const user = userEvent.setup();

      const { rerender } = render(
        <TestWrapper>
          <Home />
        </TestWrapper>,
      );

      // Start at home
      await waitFor(() => {
        expect(screen.getByText("KEN-E")).toBeInTheDocument();
      });

      // Navigate to performance
      rerender(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Navigate to insights
      rerender(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Insights")).toBeInTheDocument();
      });
    });

    test("should maintain context across navigation", async () => {
      const { rerender } = render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Verify context in performance
      await waitFor(() => {
        expect(screen.getByText("Test Organization")).toBeInTheDocument();
      });

      // Navigate to insights
      rerender(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      // Verify context is maintained
      await waitFor(() => {
        expect(screen.getByText("Test Organization")).toBeInTheDocument();
      });
    });
  });

  describe("Data Loading and Error Handling", () => {
    test("should handle loading states", async () => {
      // Mock slow loading
      vi.mocked(axios.get).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100)),
      );

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Should show loading state
      expect(screen.getByText("Loading...")).toBeInTheDocument();

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });
    });

    test("should handle API errors gracefully", async () => {
      // Mock API error
      vi.mocked(axios.get).mockRejectedValue(new Error("API Error"));

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Should show error state
      await waitFor(() => {
        expect(screen.getByText("Error loading data")).toBeInTheDocument();
      });

      // Should show retry button
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });

    test("should handle network connectivity issues", async () => {
      // Mock network error
      vi.mocked(axios.get).mockRejectedValue(new Error("Network Error"));

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Should show network error message
      await waitFor(() => {
        expect(
          screen.getByText("Network connection issue"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Real-time Updates", () => {
    test("should handle real-time metric updates", async () => {
      const { rerender } = render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Initial metric value
      await waitFor(() => {
        expect(screen.getByText("$150,000")).toBeInTheDocument();
      });

      // Simulate real-time update
      const updatedMetrics = [
        {
          ...mockMetrics[0],
          value: 155000,
          change: 15.2,
        },
        ...mockMetrics.slice(1),
      ];

      // Mock updated API response
      vi.mocked(axios.get).mockResolvedValue({
        data: { metrics: updatedMetrics },
      });

      // Trigger update
      rerender(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      // Should show updated value
      await waitFor(() => {
        expect(screen.getByText("$155,000")).toBeInTheDocument();
        expect(screen.getByText("↑ 15.2%")).toBeInTheDocument();
      });
    });

    test("should handle new insight notifications", async () => {
      const { rerender } = render(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      // Initial insights
      await waitFor(() => {
        expect(
          screen.getByText("Revenue Growth Opportunity"),
        ).toBeInTheDocument();
      });

      // Add new insight
      const newInsight = {
        id: "insight-3",
        title: "New Marketing Channel Opportunity",
        description: "LinkedIn ads showing promising early results",
        type: "opportunity",
        priority: "high",
        date: new Date().toISOString(),
      };

      // Mock updated API response
      vi.mocked(axios.get).mockResolvedValue({
        data: { insights: [...mockInsights, newInsight] },
      });

      // Trigger update
      rerender(
        <TestWrapper>
          <Insights />
        </TestWrapper>,
      );

      // Should show new insight
      await waitFor(() => {
        expect(
          screen.getByText("New Marketing Channel Opportunity"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("User Interaction Workflows", () => {
    test("should handle metric customization", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Click customize button
      const customizeButton = screen.getByText("Customize Metrics");
      await user.click(customizeButton);

      // Verify customization modal
      expect(screen.getByText("Customize Dashboard")).toBeInTheDocument();

      // Toggle metric visibility
      const revenueToggle = screen.getByText("Revenue");
      await user.click(revenueToggle);

      // Save customization
      const saveButton = screen.getByText("Save Changes");
      await user.click(saveButton);

      // Verify changes applied
      expect(screen.queryByText("Revenue")).not.toBeInTheDocument();
    });

    test("should handle dashboard export", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Performance />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByText("Performance")).toBeInTheDocument();
      });

      // Click export button
      const exportButton = screen.getByText("Export Data");
      await user.click(exportButton);

      // Verify export options
      expect(screen.getByText("Export Format")).toBeInTheDocument();
      expect(screen.getByText("PDF")).toBeInTheDocument();
      expect(screen.getByText("Excel")).toBeInTheDocument();
      expect(screen.getByText("CSV")).toBeInTheDocument();
    });
  });
});
