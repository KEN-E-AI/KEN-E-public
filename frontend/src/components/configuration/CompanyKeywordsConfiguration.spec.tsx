import { describe, test, expect, vi, beforeEach , type Mocked} from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CompanyKeywordsConfiguration from "./CompanyKeywordsConfiguration";
import { AuthContext } from "@/contexts/AuthContext";
import type { AuthContextType } from "@/contexts/AuthContext";
import axios from "axios";

// Mock axios
vi.mock("axios");
const mockedAxios = axios as Mocked<typeof axios>;

// Mock toast
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
  useToast: () => ({ toast: vi.fn() }),
}));

const mockAuthContext = {
  selectedOrgAccount: {
    account_id: "acc_123",
    account_name: "Test Account",
    organization_id: "org_456",
    industry: "Technology",
    status: "Active",
    websites: [],
    timezone: "UTC",
    data_region: "US",
    region: ["US"],
  },
} as unknown as Partial<AuthContextType>;

const renderComponent = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={mockAuthContext as AuthContextType}>
        <CompanyKeywordsConfiguration />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
};

describe("CompanyKeywordsConfiguration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders loading state initially", () => {
    mockedAxios.get.mockImplementation(() => new Promise(() => {})); // Never resolve
    renderComponent();

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  test("renders company keywords when data is loaded", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: ["tech", "software"],
          company_keywords: ["mycompany", "product"],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("Company Keywords")).toBeInTheDocument();
      expect(screen.getByText("mycompany")).toBeInTheDocument();
      expect(screen.getByText("product")).toBeInTheDocument();
    });
  });

  test("adds a new keyword", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: [],
          company_keywords: ["existing"],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("existing")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/add a keyword/i);
    const addButton = screen.getByRole("button", { name: /plus/i });

    await user.type(input, "newkeyword");
    await user.click(addButton);

    await waitFor(() => {
      expect(screen.getByText("newkeyword")).toBeInTheDocument();
    });
  });

  test("removes a keyword", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: [],
          company_keywords: ["keyword1", "keyword2"],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("keyword1")).toBeInTheDocument();
      expect(screen.getByText("keyword2")).toBeInTheDocument();
    });

    // Find and click the remove button for keyword1
    const keyword1Badge = screen.getByText("keyword1").closest(".badge");
    const removeButton = keyword1Badge?.querySelector("button");

    if (removeButton) {
      await user.click(removeButton);
    }

    await waitFor(() => {
      expect(screen.queryByText("keyword1")).not.toBeInTheDocument();
      expect(screen.getByText("keyword2")).toBeInTheDocument();
    });
  });

  test("saves changes when Save Changes is clicked", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: [],
          company_keywords: ["original"],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    mockedAxios.put.mockResolvedValueOnce({ data: { success: true } });

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("original")).toBeInTheDocument();
    });

    // Add a new keyword to trigger changes
    const input = screen.getByPlaceholderText(/add a keyword/i);
    await user.type(input, "newkeyword");
    await user.keyboard("{Enter}");

    // Save Changes button should appear
    const saveButton = await screen.findByText("Save Changes");
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockedAxios.put).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/monitoring-topics/acc_123/company"),
        {
          account_id: "acc_123",
          company_keywords: ["original", "newkeyword"],
        },
      );
    });
  });

  test("handles empty keywords state", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: [],
          company_keywords: [],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("No keywords added yet")).toBeInTheDocument();
    });
  });

  test("prevents duplicate keywords", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: [],
          company_keywords: ["existing"],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("existing")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/add a keyword/i);
    await user.type(input, "existing");
    await user.keyboard("{Enter}");

    // Should still only have one instance of "existing"
    const existingElements = screen.getAllByText("existing");
    expect(existingElements).toHaveLength(1);
  });

  test("trims and lowercases keywords", async () => {
    const mockData = {
      data: {
        data: {
          account_id: "acc_123",
          organization_id: "org_456",
          industry_keywords: [],
          company_keywords: [],
          customer_keywords: [],
          competitor_entries: [],
          created_at: "2025-01-01T00:00:00",
          updated_at: "2025-01-01T00:00:00",
        },
      },
    };

    mockedAxios.get.mockResolvedValueOnce(mockData);
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("Company Keywords")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/add a keyword/i);
    await user.type(input, "  UPPERCASE  ");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("uppercase")).toBeInTheDocument();
    });
  });
});
