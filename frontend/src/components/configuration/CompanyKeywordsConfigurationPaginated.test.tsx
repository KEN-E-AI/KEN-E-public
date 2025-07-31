import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CompanyKeywordsConfigurationPaginated from "./CompanyKeywordsConfigurationPaginated";
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

describe("CompanyKeywordsConfigurationPaginated", () => {
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

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  describe("Loading state", () => {
    it("shows skeleton loader while fetching data", () => {
      vi.mocked(api.get).mockImplementation(() => new Promise(() => {})); // Never resolve

      const { container } = render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      // Check for loading skeleton elements
      const skeletons = container.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe("Pagination", () => {
    it("displays paginated keywords with page controls", async () => {
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: Array.from({ length: 150 }, (_, i) => `keyword_${i}`)
          } 
        },
      };

      const mockPaginatedData = {
        data: {
          keywords: Array.from({ length: 50 }, (_, i) => `keyword_${i}`),
          total: 150,
          page: 1,
          page_size: 50,
          total_pages: 3,
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          return Promise.resolve(mockPaginatedData);
        }
        return Promise.resolve(mockTopicsData);
      });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("keyword_0")).toBeInTheDocument();
        expect(screen.getByText("keyword_49")).toBeInTheDocument();
        expect(screen.queryByText("keyword_50")).not.toBeInTheDocument();
      });

      // Check pagination info
      expect(screen.getByText("Showing 1-50 of 150 keywords")).toBeInTheDocument();
      
      // Check pagination controls
      expect(screen.getByText("Previous")).toBeDisabled();
      expect(screen.getByText("Next")).not.toBeDisabled();
      expect(screen.getByText("1")).toHaveClass("bg-primary");
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
    });

    it("navigates between pages", async () => {
      const user = userEvent.setup();
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: Array.from({ length: 150 }, (_, i) => `keyword_${i}`)
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          const urlObj = new URL(url, 'http://localhost');
          const page = parseInt(urlObj.searchParams.get('page') || '1');
          const pageSize = parseInt(urlObj.searchParams.get('page_size') || '50');
          const start = (page - 1) * pageSize;
          const end = start + pageSize;
          
          return Promise.resolve({
            data: {
              keywords: Array.from({ length: pageSize }, (_, i) => `keyword_${start + i}`),
              total: 150,
              page,
              page_size: pageSize,
              total_pages: 3,
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("keyword_0")).toBeInTheDocument();
      });

      // Click next page
      await user.click(screen.getByText("Next"));

      await waitFor(() => {
        expect(screen.queryByText("keyword_0")).not.toBeInTheDocument();
        expect(screen.getByText("keyword_50")).toBeInTheDocument();
        expect(screen.getByText("keyword_99")).toBeInTheDocument();
        expect(screen.getByText("Showing 51-100 of 150 keywords")).toBeInTheDocument();
      });

      // Click page 3
      await user.click(screen.getByText("3"));

      await waitFor(() => {
        expect(screen.getByText("keyword_100")).toBeInTheDocument();
        expect(screen.getByText("keyword_149")).toBeInTheDocument();
        expect(screen.getByText("Showing 101-150 of 150 keywords")).toBeInTheDocument();
      });
    });

    it("changes page size", async () => {
      const user = userEvent.setup();
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: Array.from({ length: 150 }, (_, i) => `keyword_${i}`)
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          const urlObj = new URL(url, 'http://localhost');
          const pageSize = parseInt(urlObj.searchParams.get('page_size') || '50');
          
          return Promise.resolve({
            data: {
              keywords: Array.from({ length: pageSize }, (_, i) => `keyword_${i}`),
              total: 150,
              page: 1,
              page_size: pageSize,
              total_pages: Math.ceil(150 / pageSize),
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("keyword_0")).toBeInTheDocument();
      });

      // Change page size to 20
      const pageSizeSelect = screen.getByRole('combobox');
      await user.click(pageSizeSelect);
      await user.click(screen.getByText("20"));

      await waitFor(() => {
        expect(screen.getByText("keyword_19")).toBeInTheDocument();
        expect(screen.queryByText("keyword_20")).not.toBeInTheDocument();
        expect(screen.getByText("Showing 1-20 of 150 keywords")).toBeInTheDocument();
      });
    });
  });

  describe("Search functionality", () => {
    it("filters keywords based on search term", async () => {
      const user = userEvent.setup();
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: ["apple", "banana", "apricot", "cherry", "application"]
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          const urlObj = new URL(url, 'http://localhost');
          const search = urlObj.searchParams.get('search') || '';
          
          const allKeywords = ["apple", "banana", "apricot", "cherry", "application"];
          const filtered = search 
            ? allKeywords.filter(k => k.toLowerCase().includes(search.toLowerCase()))
            : allKeywords;
          
          return Promise.resolve({
            data: {
              keywords: filtered,
              total: filtered.length,
              page: 1,
              page_size: 50,
              total_pages: 1,
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("apple")).toBeInTheDocument();
        expect(screen.getByText("banana")).toBeInTheDocument();
      });

      // Search for "app"
      const searchInput = screen.getByPlaceholderText("Search keywords...");
      await user.type(searchInput, "app");

      await waitFor(() => {
        expect(screen.getByText("apple")).toBeInTheDocument();
        expect(screen.getByText("application")).toBeInTheDocument();
        expect(screen.queryByText("banana")).not.toBeInTheDocument();
        expect(screen.getByText("Showing 1-2 of 2 keywords (filtered)")).toBeInTheDocument();
      });
    });

    it("shows no results message when search yields no matches", async () => {
      const user = userEvent.setup();
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: ["apple", "banana"]
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          const urlObj = new URL(url, 'http://localhost');
          const search = urlObj.searchParams.get('search') || '';
          
          if (search === "xyz") {
            return Promise.resolve({
              data: {
                keywords: [],
                total: 0,
                page: 1,
                page_size: 50,
                total_pages: 0,
              },
            });
          }
          
          return Promise.resolve({
            data: {
              keywords: ["apple", "banana"],
              total: 2,
              page: 1,
              page_size: 50,
              total_pages: 1,
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("apple")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText("Search keywords...");
      await user.type(searchInput, "xyz");

      await waitFor(() => {
        expect(screen.getByText("No keywords match your search")).toBeInTheDocument();
      });
    });
  });

  describe("Keyword management with pagination", () => {
    it("adds keyword and refreshes paginated view", async () => {
      const user = userEvent.setup();
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: ["existing"]
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          return Promise.resolve({
            data: {
              keywords: ["existing"],
              total: 1,
              page: 1,
              page_size: 50,
              total_pages: 1,
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      vi.mocked(api.put).mockResolvedValueOnce({ data: { success: true } });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("existing")).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/add a keyword/i);
      await user.type(input, "newkeyword{enter}");

      await waitFor(() => {
        expect(vi.mocked(api.put)).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/monitoring-topics/acc_123/company"),
          {
            account_id: "acc_123",
            company_keywords: ["existing", "newkeyword"],
          },
        );
      });
    });

    it("removes keyword and updates immediately", async () => {
      const user = userEvent.setup();
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: ["keyword1", "keyword2", "keyword3"]
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          return Promise.resolve({
            data: {
              keywords: ["keyword1", "keyword2", "keyword3"],
              total: 3,
              page: 1,
              page_size: 50,
              total_pages: 1,
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      vi.mocked(api.put).mockResolvedValueOnce({ data: { success: true } });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        expect(screen.getByText("keyword2")).toBeInTheDocument();
      });

      // Remove keyword2
      const keyword2Badge = screen.getByText("keyword2").closest(".badge");
      const removeButton = keyword2Badge?.querySelector("button");
      
      if (removeButton) {
        await user.click(removeButton);
      }

      await waitFor(() => {
        expect(vi.mocked(api.put)).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/monitoring-topics/acc_123/company"),
          {
            account_id: "acc_123",
            company_keywords: ["keyword1", "keyword3"],
          },
        );
      });
    });
  });

  describe("Performance with large datasets", () => {
    it("handles 1000+ keywords efficiently", async () => {
      const manyKeywords = Array.from({ length: 1500 }, (_, i) => `keyword_${i}`);
      const mockTopicsData = {
        data: { 
          data: { 
            company_keywords: manyKeywords
          } 
        },
      };

      vi.mocked(api.get).mockImplementation((url) => {
        if (url.includes("/company/paginated")) {
          return Promise.resolve({
            data: {
              keywords: manyKeywords.slice(0, 50),
              total: 1500,
              page: 1,
              page_size: 50,
              total_pages: 30,
            },
          });
        }
        return Promise.resolve(mockTopicsData);
      });

      render(
        <AuthContext.Provider value={mockAuthContext as any}>
          <QueryClientProvider client={queryClient}>
            <CompanyKeywordsConfigurationPaginated />
          </QueryClientProvider>
        </AuthContext.Provider>,
      );

      await waitFor(() => {
        // Should only render 50 keywords at a time
        expect(screen.getByText("keyword_0")).toBeInTheDocument();
        expect(screen.getByText("keyword_49")).toBeInTheDocument();
        expect(screen.queryByText("keyword_50")).not.toBeInTheDocument();
        
        // Should show correct total
        expect(screen.getByText("Showing 1-50 of 1500 keywords")).toBeInTheDocument();
      });
    });
  });
});