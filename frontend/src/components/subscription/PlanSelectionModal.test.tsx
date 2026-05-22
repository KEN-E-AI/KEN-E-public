import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlanSelectionModal } from "./PlanSelectionModal";
import * as subscriptionApi from "@/data/subscriptionPlansApi";
import * as organizationApi from "@/data/organizationApi";
import type { Organization } from "@/data/organizationTypes";
import type { SubscriptionPlanDefinition } from "@/types/subscription";

// Mock the API modules
vi.mock("@/data/subscriptionPlansApi");
vi.mock("@/data/organizationApi");
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

const mockOrganization = {
  organization_id: "org_test123",
  organization_name: "Test Organization",
  plan: "Free Plan",
  website: "",
  agency: false,
  child_organizations: [],
  subscription: {
    plan_name: "Free Plan",
    plan_description: "Basic features for getting started",
    price: 0,
    currency: "USD",
    billing_cycle: "monthly",
    next_billing_date: "2024-02-01",
    features: ["Basic Reports", "1 User"],
    usage: {
      reports_generated: 5,
      reports_limit: 10,
    },
  },
  billing: {
    payment_method: {
      last_four: "",
      brand: "",
      expires: "",
    },
    address: "",
    tax_id: "",
  },
  team: {
    members_used: 1,
    members_limit: 1,
    pending_invitations: 0,
  },
} as unknown as Organization;

const mockPlans: SubscriptionPlanDefinition[] = [
  {
    plan_id: "free-plan",
    plan_name: "Free Plan",
    plan_description: "Basic features for getting started",
    price: 0,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 1,
      max_reports: 10,
      features: ["Basic Reports", "1 User", "Email Support"],
    },
    is_default: true,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    plan_id: "starter-plan",
    plan_name: "Starter Plan",
    plan_description: "Perfect for small teams",
    price: 49,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 5,
      max_reports: 50,
      features: [
        "Advanced Reports",
        "Up to 5 Users",
        "Priority Email Support",
        "API Access",
      ],
    },
    is_default: false,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    plan_id: "professional-plan",
    plan_name: "Professional Plan",
    plan_description: "For growing organizations",
    price: 149,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 20,
      max_reports: 200,
      features: [
        "Premium Reports",
        "Up to 20 Users",
        "24/7 Phone Support",
        "Advanced API Access",
      ],
    },
    is_default: false,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

describe("PlanSelectionModal", () => {
  const mockOnOpenChange = vi.fn();
  const mockOnSubscriptionChanged = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(subscriptionApi.getSubscriptionPlans).mockResolvedValue(
      mockPlans,
    );
  });

  test("renders modal with subscription plans", async () => {
    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Choose Your Subscription Plan"),
      ).toBeInTheDocument();
    });

    // Check all plans are displayed
    expect(screen.getByText("Free Plan")).toBeInTheDocument();
    expect(screen.getByText("Starter Plan")).toBeInTheDocument();
    expect(screen.getByText("Professional Plan")).toBeInTheDocument();

    // Check current plan badge
    expect(screen.getByText("Current Plan")).toBeInTheDocument();
  });

  test("displays plan features correctly", async () => {
    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Up to 5 team members")).toBeInTheDocument();
      expect(screen.getByText("50 reports per month")).toBeInTheDocument();
      expect(screen.getByText("API Access")).toBeInTheDocument();
    });
  });

  test("formats prices correctly", async () => {
    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("$0.00/monthly")).toBeInTheDocument();
      expect(screen.getByText("$49.00/monthly")).toBeInTheDocument();
      expect(screen.getByText("$149.00/monthly")).toBeInTheDocument();
    });
  });

  test("allows selecting a different plan", async () => {
    const user = userEvent.setup();

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Starter Plan")).toBeInTheDocument();
    });

    // Click on Starter Plan radio button
    const starterPlanRadio = screen.getByRole("radio", {
      name: /starter-plan/i,
    });
    await user.click(starterPlanRadio);

    expect(starterPlanRadio).toBeChecked();
  });

  test("disables Change Plan button when current plan is selected", async () => {
    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      const changePlanButton = screen.getByRole("button", {
        name: /change plan/i,
      });
      expect(changePlanButton).toBeDisabled();
    });
  });

  test("enables Change Plan button when different plan is selected", async () => {
    const user = userEvent.setup();

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Starter Plan")).toBeInTheDocument();
    });

    const starterPlanRadio = screen.getByRole("radio", {
      name: /starter-plan/i,
    });
    await user.click(starterPlanRadio);

    const changePlanButton = screen.getByRole("button", {
      name: /change plan/i,
    });
    expect(changePlanButton).toBeEnabled();
  });

  test("handles plan change successfully", async () => {
    const user = userEvent.setup();
    const updatedOrg = { ...mockOrganization, plan: "Starter Plan" };

    vi.mocked(organizationApi.updateOrganizationSubscription).mockResolvedValue(
      updatedOrg,
    );

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Starter Plan")).toBeInTheDocument();
    });

    // Select starter plan
    const starterPlanRadio = screen.getByRole("radio", {
      name: /starter-plan/i,
    });
    await user.click(starterPlanRadio);

    // Click change plan
    const changePlanButton = screen.getByRole("button", {
      name: /change plan/i,
    });
    await user.click(changePlanButton);

    await waitFor(() => {
      expect(
        organizationApi.updateOrganizationSubscription,
      ).toHaveBeenCalledWith("org_test123", "starter-plan");
      expect(mockOnSubscriptionChanged).toHaveBeenCalledWith(updatedOrg);
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });

  test("handles plan change error", async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    vi.mocked(organizationApi.updateOrganizationSubscription).mockRejectedValue(
      new Error("Failed to update"),
    );

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Starter Plan")).toBeInTheDocument();
    });

    // Select starter plan
    const starterPlanRadio = screen.getByRole("radio", {
      name: /starter-plan/i,
    });
    await user.click(starterPlanRadio);

    // Click change plan
    const changePlanButton = screen.getByRole("button", {
      name: /change plan/i,
    });
    await user.click(changePlanButton);

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Failed to change subscription plan:",
        expect.any(Error),
      );
    });

    consoleErrorSpy.mockRestore();
  });

  test("shows loading state while fetching plans", () => {
    vi.mocked(subscriptionApi.getSubscriptionPlans).mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    expect(screen.getByRole("status")).toBeInTheDocument(); // Loading spinner
  });

  test("handles API error when loading plans", async () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    vi.mocked(subscriptionApi.getSubscriptionPlans).mockRejectedValue(
      new Error("Failed to load plans"),
    );

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Failed to load subscription plans:",
        expect.any(Error),
      );
    });

    consoleErrorSpy.mockRestore();
  });

  test("closes modal when cancel button is clicked", async () => {
    const user = userEvent.setup();

    render(
      <PlanSelectionModal
        open={true}
        onOpenChange={mockOnOpenChange}
        currentOrganization={mockOrganization}
        accountId="test-user-123"
        onSubscriptionChanged={mockOnSubscriptionChanged}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Choose Your Subscription Plan"),
      ).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    await user.click(cancelButton);

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });
});
