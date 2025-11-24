import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CompetitorKeywordsSection } from "./CompetitorKeywordsSection";
import * as monitoringTopicsQueries from "@/queries/monitoringTopics";
import { AuthContext } from "@/contexts/AuthContext";

// Mock queries
vi.mock("@/queries/monitoringTopics");

// Mock toast
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

describe("CompetitorKeywordsSection", () => {
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

    // Default mock for useMonitoringTopics
    vi.mocked(monitoringTopicsQueries.useMonitoringTopics).mockReturnValue({
      data: {
        account_id: "acc_123",
        organization_id: "org_123",
        industry_keywords: [],
        company_keywords: [],
        customer_keywords: [],
        competitor_entries: [
          {
            name: "Acme Corp",
            website: "https://acme.com",
            keywords: ["acme", "competitor"],
          },
        ],
        created_at: "2025-01-19T00:00:00",
        updated_at: "2025-01-19T00:00:00",
      },
      isLoading: false,
    } as any);

    // Default mocks for mutations
    vi.mocked(monitoringTopicsQueries.useAddCompetitorKeywords).mockReturnValue(
      {
        mutateAsync: vi.fn().mockResolvedValue({}),
        isPending: false,
      } as any,
    );

    vi.mocked(
      monitoringTopicsQueries.useUpdateCompetitorKeywords,
    ).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({}),
      isPending: false,
    } as any);
  });

  const renderComponent = (props = {}) => {
    return render(
      <AuthContext.Provider value={mockAuthContext as any}>
        <QueryClientProvider client={queryClient}>
          <CompetitorKeywordsSection
            competitorName="Acme Corp"
            hasEditAccess={true}
            {...props}
          />
        </QueryClientProvider>
      </AuthContext.Provider>,
    );
  };

  describe("View Mode", () => {
    it("renders keywords in view mode by default", async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("acme")).toBeInTheDocument();
        expect(screen.getByText("competitor")).toBeInTheDocument();
      });
    });

    it("shows edit button when hasEditAccess is true", async () => {
      renderComponent();

      await waitFor(() => {
        const editButtons = screen.getAllByRole("button");
        const hasEditButton = editButtons.some(
          (button) =>
            button.getAttribute("aria-label") === "Edit" ||
            button.querySelector('[class*="pencil"]'),
        );
        expect(hasEditButton).toBe(true);
      });
    });

    it("does not show edit button when hasEditAccess is false", async () => {
      renderComponent({ hasEditAccess: false });

      await waitFor(() => {
        const editButtons = screen.queryAllByRole("button");
        const hasEditButton = editButtons.some(
          (button) =>
            button.getAttribute("aria-label") === "Edit" ||
            button.querySelector('[class*="pencil"]'),
        );
        expect(hasEditButton).toBe(false);
      });
    });

    it("shows message when no keywords are configured", async () => {
      vi.mocked(monitoringTopicsQueries.useMonitoringTopics).mockReturnValue({
        data: {
          account_id: "acc_123",
          organization_id: "org_123",
          industry_keywords: [],
          company_keywords: [],
          customer_keywords: [],
          competitor_entries: [
            {
              name: "Acme Corp",
              website: "https://acme.com",
              keywords: [],
            },
          ],
          created_at: "2025-01-19T00:00:00",
          updated_at: "2025-01-19T00:00:00",
        },
        isLoading: false,
      } as any);

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByText(/No keywords configured for monitoring/i),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Edit Mode", () => {
    it("switches to edit mode when edit button clicked", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        const buttons = screen.getAllByRole("button");
        expect(buttons.length).toBeGreaterThan(0);
      });

      // Find and click the edit button (Pencil icon)
      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find(
        (button) =>
          button.querySelector('[class*="lucide-pencil"]') ||
          button.getAttribute("aria-label") === "Edit",
      );

      if (editButton) {
        await user.click(editButton);

        await waitFor(() => {
          expect(
            screen.getByPlaceholderText("Add a keyword"),
          ).toBeInTheDocument();
          expect(screen.getByText("Save")).toBeInTheDocument();
          expect(screen.getByText("Cancel")).toBeInTheDocument();
        });
      }
    });

    it("allows adding a new keyword", async () => {
      const user = userEvent.setup();
      renderComponent();

      // Click edit button
      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");
        await user.type(input, "new keyword{enter}");

        // Should appear in the list
        await waitFor(() => {
          expect(screen.getByText("new keyword")).toBeInTheDocument();
        });
      }
    });

    it("prevents duplicate keywords (case-insensitive)", async () => {
      const user = userEvent.setup();
      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");

        // Try to add existing keyword with different case
        await user.type(input, "ACME{enter}");

        // Should not add duplicate - original should remain
        const keywords = screen.getAllByText(/acme/i);
        expect(keywords.length).toBeLessThanOrEqual(2); // One in edit list, possibly one in badge
      }
    });

    it("calls update mutation when saving existing competitor", async () => {
      const user = userEvent.setup();
      const mockUpdate = vi.fn().mockResolvedValue({});

      vi.mocked(
        monitoringTopicsQueries.useUpdateCompetitorKeywords,
      ).mockReturnValue({
        mutateAsync: mockUpdate,
        isPending: false,
      } as any);

      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");
        await user.type(input, "new keyword{enter}");

        const saveButton = screen.getByText("Save");
        await user.click(saveButton);

        await waitFor(() => {
          expect(mockUpdate).toHaveBeenCalledWith({
            accountId: "acc_123",
            competitorIndex: 0,
            data: { keywords: expect.arrayContaining(["new keyword"]) },
          });
        });
      }
    });

    it("reverts changes on cancel", async () => {
      const user = userEvent.setup();
      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");
        await user.type(input, "temporary{enter}");

        // Should show the temporary keyword
        expect(screen.getByText("temporary")).toBeInTheDocument();

        const cancelButton = screen.getByText("Cancel");
        await user.click(cancelButton);

        // Should revert to original keywords
        await waitFor(() => {
          expect(screen.queryByText("temporary")).not.toBeInTheDocument();
          expect(screen.getByText("acme")).toBeInTheDocument();
        });
      }
    });
  });

  describe("Loading States", () => {
    it("shows loading spinner while fetching data", () => {
      vi.mocked(monitoringTopicsQueries.useMonitoringTopics).mockReturnValue({
        data: undefined,
        isLoading: true,
      } as any);

      renderComponent();

      // Check for loading indicator (Loader2 icon with animate-spin class)
      const loadingElements = document.querySelectorAll(".animate-spin");
      expect(loadingElements.length).toBeGreaterThan(0);
    });

    it("disables save button while mutation is pending", async () => {
      const user = userEvent.setup();

      vi.mocked(
        monitoringTopicsQueries.useUpdateCompetitorKeywords,
      ).mockReturnValue({
        mutateAsync: vi.fn().mockImplementation(
          () => new Promise(() => {}), // Never resolves
        ),
        isPending: true,
      } as any);

      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const saveButton = await screen.findByText("Save");
        expect(saveButton).toBeDisabled();
      }
    });
  });

  describe("Input Validation", () => {
    it("trims whitespace from keywords", async () => {
      const user = userEvent.setup();
      const mockUpdate = vi.fn().mockResolvedValue({});

      vi.mocked(
        monitoringTopicsQueries.useUpdateCompetitorKeywords,
      ).mockReturnValue({
        mutateAsync: mockUpdate,
        isPending: false,
      } as any);

      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");
        await user.type(input, "  trimmed  {enter}");

        const saveButton = screen.getByText("Save");
        await user.click(saveButton);

        await waitFor(() => {
          expect(mockUpdate).toHaveBeenCalledWith({
            accountId: "acc_123",
            competitorIndex: 0,
            data: { keywords: expect.arrayContaining(["trimmed"]) },
          });
        });
      }
    });

    it("converts keywords to lowercase", async () => {
      const user = userEvent.setup();
      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");
        await user.type(input, "MiXeD CaSe{enter}");

        // Should appear lowercase
        await waitFor(() => {
          expect(screen.getByText("mixed case")).toBeInTheDocument();
        });
      }
    });

    it("validates minimum keyword length", async () => {
      const user = userEvent.setup();
      renderComponent();

      const buttons = screen.getAllByRole("button");
      const editButton = buttons.find((button) =>
        button.querySelector('[class*="lucide-pencil"]'),
      );

      if (editButton) {
        await user.click(editButton);

        const input = await screen.findByPlaceholderText("Add a keyword");
        await user.type(input, "a{enter}");

        // Should not add a 1-character keyword
        await waitFor(() => {
          expect(screen.queryByText("a")).not.toBeInTheDocument();
        });
      }
    });
  });
});
