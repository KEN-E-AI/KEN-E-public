import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountProfileSettings } from "./AccountProfileSettings";

// Mock the AuthContext
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    selectedOrgAccount: {
      accountId: "test-account",
      metadata: {
        organization_name: "Test Org",
        account_name: "Test Account",
      },
    },
    user: {
      id: "test-user",
      firstName: "Test",
      lastName: "User",
      preferences: {
        language: "en",
        theme: "light",
      },
      settings: {
        timezone: "America/New_York",
      },
    },
    orgMetadata: {
      timezone: "America/Chicago",
      data_retention: 365,
    },
    accountMetadata: {
      industry: "Technology",
      template_id: "e-commerce",
    },
  }),
}));

// Mock the account templates
vi.mock("@/data/accountTemplates", () => ({
  getTemplateById: (id: string) => {
    if (id === "e-commerce") {
      return {
        id: "e-commerce",
        name: "E-Commerce",
        description: "E-commerce business template",
        category: "Retail",
        icon: () => null,
        defaultObjectives: ["Increase sales", "Improve conversion"],
        defaultChannels: ["Google Ads", "Facebook"],
        defaultKPIs: ["Revenue", "Conversion Rate"],
        recommendedSettings: {
          timezone: "America/Los_Angeles",
          language: "en",
        },
        defaultSettings: {
          data_retention: 730,
        },
      };
    }
    return null;
  },
}));

const mockAccountData = {
  account_name: "Test Account",
  industry: "Technology",
  status: "Active",
  timezone: "America/New_York",
  description: "Test description",
  website: "https://example.com",
  location: "New York, NY",
  template_id: "e-commerce",
};

const mockOnUpdate = vi.fn();

describe("AccountProfileSettings", () => {
  beforeEach(() => {
    mockOnUpdate.mockClear();
  });

  test("renders account profile information correctly", () => {
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    expect(screen.getByDisplayValue("Test Account")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Test description")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("New York, NY")).toBeInTheDocument();
  });

  test("enables editing mode when edit button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    const editButton = screen.getByText("Edit Profile");
    await user.click(editButton);

    expect(screen.getByText("Save Changes")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  test("calls onUpdate when form is submitted", async () => {
    const user = userEvent.setup();
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Modify account name
    const nameInput = screen.getByDisplayValue("Test Account");
    await user.clear(nameInput);
    await user.type(nameInput, "Updated Account");

    // Submit form
    await user.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          account_name: "Updated Account",
        }),
      );
    });
  });

  test("cancels editing and resets form when cancel is clicked", async () => {
    const user = userEvent.setup();
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Modify account name
    const nameInput = screen.getByDisplayValue("Test Account");
    await user.clear(nameInput);
    await user.type(nameInput, "Modified Account");

    // Cancel editing
    await user.click(screen.getByText("Cancel"));

    // Should exit edit mode and reset form
    expect(screen.getByText("Edit Profile")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Test Account")).toBeInTheDocument();
    expect(mockOnUpdate).not.toHaveBeenCalled();
  });

  test("displays template information when template_id is provided", () => {
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    expect(screen.getByText("Account Template")).toBeInTheDocument();
    expect(screen.getByText("E-Commerce")).toBeInTheDocument();
    // Use getAllByText to find the template badge specifically
    const retailTexts = screen.getAllByText("Retail");
    expect(retailTexts.length).toBeGreaterThan(0); // Should find at least one
  });

  test("renders form fields with correct initial values", () => {
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    expect(screen.getByDisplayValue("Test Account")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Test description")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("New York, NY")).toBeInTheDocument();
  });

  test("handles missing optional fields gracefully", () => {
    const minimalAccountData = {
      account_name: "Minimal Account",
      industry: "Technology",
      status: "Active",
    };

    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={minimalAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    expect(screen.getByDisplayValue("Minimal Account")).toBeInTheDocument();
    // Check that the description textarea is empty
    const descriptionTextarea = screen.getByRole("textbox", {
      name: /description/i,
    });
    expect(descriptionTextarea).toHaveValue("");
  });

  test("validates required fields and shows error messages", async () => {
    const user = userEvent.setup();
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Clear required field
    const nameInput = screen.getByDisplayValue("Test Account");
    await user.clear(nameInput);

    // Try to submit
    await user.click(screen.getByText("Save Changes"));

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText("Account name is required")).toBeInTheDocument();
    });

    // Should not call onUpdate
    expect(mockOnUpdate).not.toHaveBeenCalled();
  });

  test("allows empty website URL", async () => {
    const user = userEvent.setup();
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Clear the website field (empty string should be valid)
    const websiteInput = screen.getByDisplayValue("https://example.com");
    await user.clear(websiteInput);

    // Submit form
    await user.click(screen.getByText("Save Changes"));

    // Should call onUpdate with empty website
    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          website: "",
        }),
      );
    });
  });

  test("handles submission errors and shows error message", async () => {
    const user = userEvent.setup();
    mockOnUpdate.mockRejectedValue(new Error("Network error"));

    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Submit form
    await user.click(screen.getByText("Save Changes"));

    // Should show error message
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  test("shows loading state during submission", async () => {
    const user = userEvent.setup();
    mockOnUpdate.mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 100)),
    );

    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Submit form
    await user.click(screen.getByText("Save Changes"));

    // Should show loading state
    expect(screen.getByText("Saving...")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeDisabled();
  });

  test("clears validation errors when canceling", async () => {
    const user = userEvent.setup();
    render(
      <AccountProfileSettings
        accountId="test-account"
        accountData={mockAccountData}
        onUpdate={mockOnUpdate}
      />,
    );

    // Enter edit mode
    await user.click(screen.getByText("Edit Profile"));

    // Clear required field to trigger validation error
    const nameInput = screen.getByDisplayValue("Test Account");
    await user.clear(nameInput);

    // Try to submit to trigger validation error
    await user.click(screen.getByText("Save Changes"));

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText("Account name is required")).toBeInTheDocument();
    });

    // Cancel editing
    await user.click(screen.getByText("Cancel"));

    // Should clear validation errors and reset form
    expect(
      screen.queryByText("Account name is required"),
    ).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("Test Account")).toBeInTheDocument();
    expect(screen.getByText("Edit Profile")).toBeInTheDocument();
  });
});
