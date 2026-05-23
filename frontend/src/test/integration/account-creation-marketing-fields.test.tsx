import { describe, test, expect, beforeEach, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import { AccountCreationWizard } from "@/components/settings/AccountCreationWizard";
import * as organizationApi from "@/data/organizationApi";

// Mock API modules
vi.mock("@/data/organizationApi");
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

const mockCreateAccount = organizationApi.createAccount as any;

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
    organization_name: "E-commerce Company",
    company_size: "Medium",
    agency: false,
    child_organizations: [],
    subscription: {
      plan_name: "Pro Plan",
      features: ["Advanced Analytics", "Account Management"],
    },
    accounts: [],
  },
};

// Fixture uses a legacy AuthContext shape (selectedOrganization /
// selectedAccount / hasPermission). The current AuthContextType has
// `selectedOrgAccount`, `currentOrganizationId`, etc. The cast through
// unknown is acceptable here: the integration tests below only exercise
// the wizard flow, not the legacy fields above.
const mockAuthContext = {
  user: mockUser,
  selectedOrganization: "org-123",
  selectedAccount: null,
  orgMetadata: mockOrgMetadata,
  accountMetadata: {},
  setSelectedOrganization: vi.fn(),
  setSelectedAccount: vi.fn(),
  setOrgMetadata: vi.fn(),
  setAccountMetadata: vi.fn(),
  signOut: vi.fn(),
  loading: false,
  hasPermission: vi.fn().mockReturnValue(true),
  getAccountPermission: vi.fn().mockReturnValue("admin"),
  getOrganizationPermission: vi.fn().mockReturnValue("admin"),
} as unknown as AuthContextType;

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={mockAuthContext}>
          {children}
        </AuthContext.Provider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

describe("Account Creation Integration - Marketing Fields", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("should create account with marketing channels and product integrations through complete wizard flow", async () => {
    // Setup - Mock successful account creation
    const mockCreatedAccount = {
      account_id: "acc-integration-test-123",
      account_name: "Integration Test Account",
      organization_id: "org-123",
      industry: "E-commerce",
      status: "Active",
      websites: ["https://teststore.example.com"],
      timezone: "America/New_York",
      data_region: "United States",
      region: ["US", "CA"],
      marketing_channels: ["google_ads", "facebook", "email"],
      product_integrations: ["google_analytics", "shopify", "mailchimp"],
      estimated_annual_ad_budget: 100000,
    };

    mockCreateAccount.mockResolvedValue(mockCreatedAccount);

    const user = userEvent.setup();

    // Render wizard
    const onComplete = vi.fn();
    render(
      <TestWrapper>
        <AccountCreationWizard
          isOpen={true}
          onClose={vi.fn()}
          onComplete={onComplete}
        />
      </TestWrapper>,
    );

    // **STEP 1: Basic Info**
    await waitFor(() => {
      expect(screen.getByText("Account Information")).toBeInTheDocument();
    });

    // Fill basic account info
    const accountNameInput = screen.getByLabelText(/account name/i);
    await user.clear(accountNameInput);
    await user.type(accountNameInput, "Integration Test Account");

    const industrySelect = screen.getByRole("combobox", { name: /industry/i });
    await user.click(industrySelect);
    await user.click(screen.getByText("E-commerce"));

    // Add website
    const websiteInput = screen.getByLabelText(/website url/i);
    await user.type(websiteInput, "https://teststore.example.com");
    await user.click(screen.getByRole("button", { name: /add website/i }));

    // Set timezone
    const timezoneSelect = screen.getByRole("combobox", { name: /timezone/i });
    await user.click(timezoneSelect);
    await user.click(screen.getByText(/New York/));

    // Set data region
    const dataRegionSelect = screen.getByRole("combobox", {
      name: /data region/i,
    });
    await user.click(dataRegionSelect);
    await user.click(screen.getByText("United States"));

    // Set customer region
    const regionButton = screen.getByRole("button", {
      name: /add customer region/i,
    });
    await user.click(regionButton);
    await user.click(screen.getByText("United States"));
    await user.click(screen.getByText("Canada"));

    // Set budget
    const budgetInput = screen.getByLabelText(
      /estimated annual advertising budget/i,
    );
    await user.clear(budgetInput);
    await user.type(budgetInput, "100000");

    // Next to step 2
    await user.click(screen.getByRole("button", { name: /next/i }));

    // **STEP 2: Marketing Channels**
    await waitFor(() => {
      expect(screen.getByText("Marketing Channels")).toBeInTheDocument();
    });

    // Select marketing channels
    const googleAdsCheckbox = screen.getByRole("checkbox", {
      name: /google ads/i,
    });
    await user.click(googleAdsCheckbox);

    const facebookCheckbox = screen.getByRole("checkbox", {
      name: /facebook/i,
    });
    await user.click(facebookCheckbox);

    const emailCheckbox = screen.getByRole("checkbox", {
      name: /email marketing/i,
    });
    await user.click(emailCheckbox);

    // Verify selections are shown
    await waitFor(() => {
      expect(
        screen.getByText("Selected Marketing Channels (3)"),
      ).toBeInTheDocument();
    });

    // Next to step 3
    await user.click(screen.getByRole("button", { name: /next/i }));

    // **STEP 3: Product Integrations**
    await waitFor(() => {
      expect(screen.getByText("Product Integrations")).toBeInTheDocument();
    });

    // Select product integrations
    const googleAnalyticsCard =
      screen.getByText("Google Analytics").closest("div[role='checkbox']") ||
      screen.getByText("Google Analytics").closest("[data-testid]") ||
      screen.getByText("Google Analytics");
    await user.click(googleAnalyticsCard);

    const shopifyCard =
      screen.getByText("Shopify").closest("div[role='checkbox']") ||
      screen.getByText("Shopify").closest("[data-testid]") ||
      screen.getByText("Shopify");
    await user.click(shopifyCard);

    const mailchimpCard =
      screen.getByText("Mailchimp").closest("div[role='checkbox']") ||
      screen.getByText("Mailchimp").closest("[data-testid]") ||
      screen.getByText("Mailchimp");
    await user.click(mailchimpCard);

    // Verify selections summary
    await waitFor(() => {
      expect(screen.getByText("Selected Integrations (3)")).toBeInTheDocument();
    });

    // Next to step 4 (Configuration)
    await user.click(screen.getByRole("button", { name: /next/i }));

    // **STEP 4: Skip Configuration (optional step)**
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /next/i }));

    // **STEP 5: Confirmation & Create**
    await waitFor(() => {
      expect(screen.getByText(/review your account/i)).toBeInTheDocument();
    });

    // Verify all data is shown in confirmation
    expect(screen.getByText("Integration Test Account")).toBeInTheDocument();
    expect(screen.getByText("E-commerce")).toBeInTheDocument();
    expect(
      screen.getByText("https://teststore.example.com"),
    ).toBeInTheDocument();
    expect(screen.getByText("$100,000")).toBeInTheDocument();

    // Create the account
    const createButton = screen.getByRole("button", {
      name: /create account/i,
    });
    await user.click(createButton);

    // **VERIFICATION: API Called with Correct Data**
    await waitFor(() => {
      expect(mockCreateAccount).toHaveBeenCalledTimes(1);
    });

    const apiCallArgs = mockCreateAccount.mock.calls[0][0];

    // Verify all fields are included in API call
    expect(apiCallArgs).toEqual({
      account_name: "Integration Test Account",
      organization_id: "org-123",
      industry: "E-commerce",
      status: "Active",
      websites: ["https://teststore.example.com"],
      timezone: "America/New_York",
      data_region: "United States",
      region: ["US", "CA"],
      marketing_channels: ["google_ads", "facebook", "email"],
      product_integrations: ["google_analytics", "shopify", "mailchimp"],
      estimated_annual_ad_budget: 100000,
      business_strategy_documents: [],
    });

    // Verify critical new fields are present
    expect(apiCallArgs.marketing_channels).toHaveLength(3);
    expect(apiCallArgs.product_integrations).toHaveLength(3);
    expect(apiCallArgs.marketing_channels).toContain("google_ads");
    expect(apiCallArgs.product_integrations).toContain("google_analytics");

    // Verify completion callback
    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledWith(mockCreatedAccount);
    });
  });

  test("should handle empty marketing channels and product integrations gracefully", async () => {
    // Setup - Mock successful account creation with empty arrays
    const mockCreatedAccount = {
      account_id: "acc-empty-test-456",
      account_name: "Empty Fields Test Account",
      organization_id: "org-123",
      industry: "Technology",
      status: "Active",
      websites: ["https://techcompany.example.com"],
      timezone: "America/Los_Angeles",
      data_region: "United States",
      region: ["US"],
      marketing_channels: [],
      product_integrations: [],
      estimated_annual_ad_budget: null,
    };

    mockCreateAccount.mockResolvedValue(mockCreatedAccount);

    const user = userEvent.setup();
    const onComplete = vi.fn();

    render(
      <TestWrapper>
        <AccountCreationWizard
          isOpen={true}
          onClose={vi.fn()}
          onComplete={onComplete}
        />
      </TestWrapper>,
    );

    // Fill minimal required fields only
    await waitFor(() => {
      expect(screen.getByLabelText(/account name/i)).toBeInTheDocument();
    });

    const accountNameInput = screen.getByLabelText(/account name/i);
    await user.clear(accountNameInput);
    await user.type(accountNameInput, "Empty Fields Test Account");

    const industrySelect = screen.getByRole("combobox", { name: /industry/i });
    await user.click(industrySelect);
    await user.click(screen.getByText("Technology"));

    const websiteInput = screen.getByLabelText(/website url/i);
    await user.type(websiteInput, "https://techcompany.example.com");
    await user.click(screen.getByRole("button", { name: /add website/i }));

    // Navigate through wizard without selecting marketing channels or integrations
    await user.click(screen.getByRole("button", { name: /next/i })); // Step 1 → 2
    await user.click(screen.getByRole("button", { name: /next/i })); // Step 2 → 3 (no selections)
    await user.click(screen.getByRole("button", { name: /next/i })); // Step 3 → 4 (no selections)
    await user.click(screen.getByRole("button", { name: /next/i })); // Step 4 → 5

    // Create account
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /create account/i }));

    // Verify API called with empty arrays
    await waitFor(() => {
      expect(mockCreateAccount).toHaveBeenCalledTimes(1);
    });

    const apiCallArgs = mockCreateAccount.mock.calls[0][0];
    expect(apiCallArgs.marketing_channels).toEqual([]);
    expect(apiCallArgs.product_integrations).toEqual([]);
  });

  test("should handle API errors gracefully during account creation", async () => {
    // Setup - Mock API failure
    const apiError = new Error("Neo4j connection failed");
    mockCreateAccount.mockRejectedValue(apiError);

    const user = userEvent.setup();
    const onComplete = vi.fn();

    render(
      <TestWrapper>
        <AccountCreationWizard
          isOpen={true}
          onClose={vi.fn()}
          onComplete={onComplete}
        />
      </TestWrapper>,
    );

    // Fill minimal form and submit
    await waitFor(() => {
      expect(screen.getByLabelText(/account name/i)).toBeInTheDocument();
    });

    const accountNameInput = screen.getByLabelText(/account name/i);
    await user.type(accountNameInput, "Error Test Account");

    const industrySelect = screen.getByRole("combobox", { name: /industry/i });
    await user.click(industrySelect);
    await user.click(screen.getByText("Technology"));

    // Navigate to final step and attempt creation
    await user.click(screen.getByRole("button", { name: /next/i }));
    await user.click(screen.getByRole("button", { name: /next/i }));
    await user.click(screen.getByRole("button", { name: /next/i }));
    await user.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /create account/i }));

    // Verify error handling
    await waitFor(() => {
      expect(mockCreateAccount).toHaveBeenCalledTimes(1);
      // onComplete should NOT be called on error
      expect(onComplete).not.toHaveBeenCalled();
      // Error should be displayed (implementation dependent)
    });
  });
});
