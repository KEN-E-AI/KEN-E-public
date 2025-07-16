import { describe, test, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountCreationWizard } from "./AccountCreationWizard";

const mockOnClose = vi.fn();
const mockOnComplete = vi.fn();

describe("AccountCreationWizard", () => {
  beforeEach(() => {
    mockOnClose.mockClear();
    mockOnComplete.mockClear();
  });

  test("renders wizard when isOpen is true", () => {
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    expect(screen.getByText("Create New Account")).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(screen.getByText("Basic Info")).toBeInTheDocument();
  });

  test("does not render wizard when isOpen is false", () => {
    render(
      <AccountCreationWizard
        isOpen={false}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    expect(screen.queryByText("Create New Account")).not.toBeInTheDocument();
  });

  test("calls onClose when cancel button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    await user.click(screen.getByText("Cancel"));
    expect(mockOnClose).toHaveBeenCalled();
  });

  test("disables Next button when required fields are empty", () => {
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    const nextButton = screen.getByText("Next");
    expect(nextButton).toBeDisabled();
  });

  test("enables Next button when required fields are filled", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Fill required fields
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));

    const nextButton = screen.getByText("Next");
    expect(nextButton).not.toBeDisabled();
  });

  test("progresses through wizard steps", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Step 1: Fill basic info
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    // Step 2: Should show template selection
    expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    expect(screen.getByText("Choose Template")).toBeInTheDocument();
  });

  test("navigates back to previous step", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Fill basic info and go to step 2
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    // Go back to step 1
    await user.click(screen.getByText("Previous"));
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(screen.getByText("Basic Information")).toBeInTheDocument();
  });

  test("selects template and updates form data", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate to step 2
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    // Select template
    const saasTemplate = screen.getByText("SaaS");
    await user.click(saasTemplate.closest('.cursor-pointer')!);

    // Template should be selected (visual feedback)
    expect(screen.getByText("SaaS")).toBeInTheDocument();
    expect(screen.getByText("Technology")).toBeInTheDocument();
  });

  test("validates template selection before proceeding", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate to step 2
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    // Try to proceed without selecting template
    const nextButton = screen.getByText("Next");
    expect(nextButton).toBeDisabled();
  });

  test("filters templates by category", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate to step 2
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    // Filter by Technology category
    await user.click(screen.getByText("Technology"));
    expect(screen.getByText("SaaS")).toBeInTheDocument();
    
    // Filter by Retail category
    await user.click(screen.getByText("Retail"));
    expect(screen.getByText("E-Commerce")).toBeInTheDocument();
  });

  test("shows configuration step with selected template data", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate through steps
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    // Select SaaS template
    const saasTemplate = screen.getByText("SaaS");
    await user.click(saasTemplate.closest('.cursor-pointer')!);
    await user.click(screen.getByText("Next"));

    // Step 3: Configuration
    expect(screen.getByText("Step 3 of 4")).toBeInTheDocument();
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText("Objectives")).toBeInTheDocument();
  });

  test("validates configuration step before proceeding", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate to step 3
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    const saasTemplate = screen.getByText("SaaS");
    await user.click(saasTemplate.closest('.cursor-pointer')!);
    await user.click(screen.getByText("Next"));

    // Uncheck all objectives and channels
    const checkboxes = screen.getAllByRole("checkbox");
    for (const checkbox of checkboxes) {
      if (checkbox.checked) {
        await user.click(checkbox);
      }
    }

    // Next button should be disabled
    const nextButton = screen.getByText("Next");
    expect(nextButton).toBeDisabled();
  });

  test("shows final step with settings and summary", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate to final step
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    const saasTemplate = screen.getByText("SaaS");
    await user.click(saasTemplate.closest('.cursor-pointer')!);
    await user.click(screen.getByText("Next"));
    await user.click(screen.getByText("Next"));

    // Step 4: Settings
    expect(screen.getByText("Step 4 of 4")).toBeInTheDocument();
    expect(screen.getByText("Settings & Preferences")).toBeInTheDocument();
    expect(screen.getByText("Account Summary")).toBeInTheDocument();
  });

  test("completes wizard and calls onComplete", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Navigate through all steps
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    const saasTemplate = screen.getByText("SaaS");
    await user.click(saasTemplate.closest('.cursor-pointer')!);
    await user.click(screen.getByText("Next"));
    await user.click(screen.getByText("Next"));

    // Complete wizard
    await user.click(screen.getByText("Create Account"));

    expect(mockOnComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        account_name: "Test Account",
        industry: "Technology",
        template_id: "saas",
      })
    );
  });

  test("updates progress bar correctly", async () => {
    const user = userEvent.setup();
    render(
      <AccountCreationWizard
        isOpen={true}
        onClose={mockOnClose}
        onComplete={mockOnComplete}
      />
    );

    // Check initial progress
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();

    // Navigate to step 2
    await user.type(screen.getByPlaceholderText("e.g., Q1 2024 Campaign"), "Test Account");
    await user.click(screen.getByText("Technology"));
    await user.click(screen.getByText("Next"));

    expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
  });
});