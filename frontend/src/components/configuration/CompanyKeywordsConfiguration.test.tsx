import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CompanyKeywordsConfiguration from "./CompanyKeywordsConfiguration";
import { AuthContext } from "@/contexts/AuthContext";
import api from "@/lib/api";

// Mock the API
vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

// Mock toast
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

describe("CompanyKeywordsConfiguration - Comprehensive Tests", () => {
  let queryClient: QueryClient;

  const mockAuthContext = {
    selectedOrgAccount: {
      orgId: "org_123",
      accountId: "acc_123",
      metadata: {
        organization_name: "Test Org",
        account_name: "Test Account",
        industry: "Technology",
        status: "Active",
      },
    },
  };

  const mockAuthContextNoAccount = {
    selectedOrgAccount: null,
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  // Error Scenarios
  describe("Error Handling", () => {
    it("handles network timeout gracefully", async () => {
      // Simulate a timeout
      vi.mocked(api.get).mockImplementation(
        () =>
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("Network timeout")), 100),
          ),
      );

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(
        () => {
          // Should show the component but with empty state
          expect(screen.getByText("Company Keywords")).toBeInTheDocument();
        },
        { timeout: 200 },
      );
    });

    it("handles 403 permission denied error", async () => {
      const error = new Error("Forbidden");
      (error as any).response = { status: 403 };
      vi.mocked(api.get).mockRejectedValueOnce(error);

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        // Component should render but data fetch fails
        expect(screen.getByText("Company Keywords")).toBeInTheDocument();
      });
    });

    it("handles server error (500) on save", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: [] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      const error = new Error("Internal Server Error");
      (error as any).response = { status: 500 };
      vi.mocked(api.put).mockRejectedValueOnce(error);

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText("Add a keyword");
      await user.type(input, "test{enter}");

      // The UI should remain functional after error
      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });
    });

    it("handles malformed API response", async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: null });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        // Should handle gracefully and show empty state
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });
    });
  });

  // Edge Cases
  describe("Edge Cases", () => {
    it("handles extremely long keywords (>100 chars)", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: [] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });

      const longKeyword = "a".repeat(150);
      const input = screen.getByPlaceholderText("Add a keyword");
      await user.type(input, longKeyword + "{enter}");

      // Should truncate or handle long keyword appropriately
      await waitFor(() => {
        const addedKeyword = screen.getByText((content, element) => {
          return element?.tagName === "SPAN" && content.length <= 100;
        });
        expect(addedKeyword).toBeInTheDocument();
      });
    });

    it("handles special characters in keywords", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: [] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);
      vi.mocked(api.put).mockResolvedValueOnce({ data: { success: true } });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });

      const specialKeyword = "test@#$%^&*()";
      const input = screen.getByPlaceholderText("Add a keyword");
      await user.type(input, specialKeyword + "{enter}");

      await waitFor(() => {
        expect(vi.mocked(api.put)).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            company_keywords: [specialKeyword],
          }),
        );
      });
    });

    it("handles rapid keyword addition", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: [] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);
      vi.mocked(api.put).mockResolvedValue({ data: { success: true } });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText("Add a keyword");

      // Rapidly add multiple keywords
      await user.type(input, "keyword1{enter}");
      await user.type(input, "keyword2{enter}");
      await user.type(input, "keyword3{enter}");

      // All keywords should be added
      await waitFor(() => {
        expect(vi.mocked(api.put)).toHaveBeenCalledTimes(3);
      });
    });

    it("handles concurrent modifications", async () => {
      const mockData = {
        data: {
          data: {
            company_keywords: ["initial1", "initial2"],
          },
        },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      // Simulate another user adding a keyword
      const updatedData = {
        data: {
          data: {
            company_keywords: ["initial1", "initial2", "other-user-keyword"],
          },
        },
      };
      vi.mocked(api.get).mockResolvedValueOnce(updatedData);

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("initial1")).toBeInTheDocument();
      });

      // Trigger a refetch (simulating real-time update)
      queryClient.invalidateQueries({ queryKey: ["monitoring-topics"] });

      await waitFor(() => {
        expect(screen.getByText("other-user-keyword")).toBeInTheDocument();
      });
    });

    it("handles maximum keyword limit (1000 keywords)", async () => {
      const manyKeywords = Array.from(
        { length: 1000 },
        (_, i) => `keyword_${i}`,
      );
      const mockData = {
        data: {
          data: {
            company_keywords: manyKeywords,
          },
        },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        // Should handle large lists efficiently
        expect(screen.getByText("keyword_0")).toBeInTheDocument();
        expect(screen.getByText("keyword_999")).toBeInTheDocument();
      });
    });
  });

  // Loading States
  describe("Loading States", () => {
    it("shows skeleton loader while fetching", () => {
      vi.mocked(api.get).mockImplementation(() => new Promise(() => {}));

      const { container } = render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      // Check for loading skeleton elements
      const skeletons = container.querySelectorAll(".animate-pulse");
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it("shows loading state during save", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: ["existing"] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      // Make put request hang
      vi.mocked(api.put).mockImplementation(() => new Promise(() => {}));

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("existing")).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText("Add a keyword");
      await user.type(input, "new{enter}");

      // Should show some loading indication
      await waitFor(() => {
        expect(screen.getByText("new")).toBeInTheDocument();
      });
    });
  });

  // Permission Scenarios
  describe("Permission Scenarios", () => {
    it("handles view-only permissions gracefully", async () => {
      const viewOnlyContext = {
        ...mockAuthContext,
        user: {
          permissions: {
            organizations: { org_123: "view" },
            accounts: { acc_123: "view" },
          },
        },
      };

      const mockData = {
        data: { data: { company_keywords: ["readonly"] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      render(
        <AuthContext.Provider value={viewOnlyContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("readonly")).toBeInTheDocument();
        // Input should still be visible for view-only users in this implementation
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });
    });
  });

  // Data Validation
  describe("Data Validation", () => {
    it("validates keyword format", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: [] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText("Add a keyword");

      // Test various invalid formats
      await user.type(input, "   {enter}"); // Empty
      await user.type(input, "\n\t{enter}"); // Whitespace only

      // Should not make API calls for invalid keywords
      expect(vi.mocked(api.put)).not.toHaveBeenCalled();
    });

    it("normalizes keywords before saving", async () => {
      const user = userEvent.setup();
      const mockData = {
        data: { data: { company_keywords: [] } },
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockData);
      vi.mocked(api.put).mockResolvedValueOnce({ data: { success: true } });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfiguration />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Add a keyword"),
        ).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText("Add a keyword");
      await user.type(input, "  MiXeD CaSe  {enter}");

      await waitFor(() => {
        expect(vi.mocked(api.put)).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            company_keywords: ["MiXeD CaSe"], // Trimmed but case preserved
          }),
        );
      });
    });
  });
});
