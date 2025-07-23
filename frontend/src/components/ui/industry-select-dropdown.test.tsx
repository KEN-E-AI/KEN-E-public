import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IndustrySelectDropdown } from "./industry-select-dropdown";
import { INDUSTRY_OPTIONS } from "@/data/organizationTypes";

describe("IndustrySelectDropdown", () => {
  const mockOnValueChange = vi.fn();

  beforeEach(() => {
    mockOnValueChange.mockClear();
  });

  test("renders with placeholder when no value is selected", () => {
    render(
      <IndustrySelectDropdown
        value=""
        onValueChange={mockOnValueChange}
        placeholder="Choose an industry"
      />,
    );

    expect(screen.getByRole("combobox")).toHaveTextContent(
      "Choose an industry",
    );
  });

  test("renders with default placeholder when not provided", () => {
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    expect(screen.getByRole("combobox")).toHaveTextContent("Select industry");
  });

  test("displays selected industry label", () => {
    const selectedIndustry = INDUSTRY_OPTIONS[0];
    render(
      <IndustrySelectDropdown
        value={selectedIndustry.value}
        onValueChange={mockOnValueChange}
      />,
    );

    expect(screen.getByRole("combobox")).toHaveTextContent(
      selectedIndustry.label,
    );
  });

  test("opens dropdown when button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    const trigger = screen.getByRole("combobox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByPlaceholderText("Search industries..."),
    ).toBeInTheDocument();
  });

  test("filters industries based on search input", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.type(searchInput, "software");

    // Should show software-related industry
    expect(
      screen.getByText("Enterprise Software and SaaS [B2B]"),
    ).toBeInTheDocument();

    // Should not show unrelated industries
    expect(
      screen.queryByText("Agriculture, Forestry, Fishing and Hunting"),
    ).not.toBeInTheDocument();
  });

  test("calls onValueChange when an industry is selected", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    const firstIndustry = screen.getByText(INDUSTRY_OPTIONS[0].label);
    await user.click(firstIndustry);

    expect(mockOnValueChange).toHaveBeenCalledWith(INDUSTRY_OPTIONS[0].value);
  });

  test("closes dropdown after selection", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");

    const firstIndustry = screen.getByText(INDUSTRY_OPTIONS[0].label);
    await user.click(firstIndustry);

    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  test("keyboard navigation moves one item at a time", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    // Wait for dropdown to be ready
    await screen.findByPlaceholderText("Search industries...");

    // Focus the search input to ensure keyboard events work
    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.click(searchInput);

    // Get option elements by role
    const options = screen.getAllByRole("option");

    // First item should be highlighted by default
    expect(options[0]).toHaveClass("bg-accent");

    // Press ArrowDown once - should move to second item (index 1)
    await user.keyboard("{ArrowDown}");
    expect(options[1]).toHaveClass("bg-accent");
    expect(options[0]).not.toHaveClass("bg-accent");

    // Press ArrowDown again - should move to third item (index 2)
    await user.keyboard("{ArrowDown}");
    expect(options[2]).toHaveClass("bg-accent");
    expect(options[1]).not.toHaveClass("bg-accent");

    // Press ArrowUp once - should go back to second item (index 1)
    await user.keyboard("{ArrowUp}");
    expect(options[1]).toHaveClass("bg-accent");
    expect(options[0]).not.toHaveClass("bg-accent");
  });

  // Edge case tests
  test("handles keyboard navigation at list boundaries", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    // Navigate to the last item
    for (let i = 0; i < INDUSTRY_OPTIONS.length - 1; i++) {
      await user.keyboard("{ArrowDown}");
    }

    // Get fresh reference to options after navigation
    let options = screen.getAllByRole("option");

    // Should be at the last item
    expect(options[INDUSTRY_OPTIONS.length - 1]).toHaveClass("bg-accent");

    // Press ArrowDown at the bottom - should stay at last item
    await user.keyboard("{ArrowDown}");
    options = screen.getAllByRole("option");
    expect(options[INDUSTRY_OPTIONS.length - 1]).toHaveClass("bg-accent");

    // Navigate back to first item
    for (let i = 0; i < INDUSTRY_OPTIONS.length - 1; i++) {
      await user.keyboard("{ArrowUp}");
    }

    // Get fresh reference again
    options = screen.getAllByRole("option");

    // Should be at the first item
    expect(options[0]).toHaveClass("bg-accent");

    // Press ArrowUp at the top - should stay at first item
    await user.keyboard("{ArrowUp}");
    options = screen.getAllByRole("option");
    expect(options[0]).toHaveClass("bg-accent");
  });

  test("handles special characters in search", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));
    const searchInput = screen.getByPlaceholderText("Search industries...");

    // Test with special characters
    await user.type(searchInput, "[B2B]");
    expect(
      screen.getByText("Enterprise Software and SaaS [B2B]"),
    ).toBeInTheDocument();

    await user.clear(searchInput);
    await user.type(searchInput, "&");
    // Should show industries with & in their name
    const optionsWithAmpersand = screen.getAllByRole("option");
    expect(optionsWithAmpersand.length).toBeGreaterThan(0);
  });

  test("clears search on close and reopen", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    // Open and search
    await user.click(screen.getByRole("combobox"));
    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.type(searchInput, "software");

    // Close by clicking outside
    await user.click(document.body);

    // Reopen
    await user.click(screen.getByRole("combobox"));
    const newSearchInput = screen.getByPlaceholderText("Search industries...");

    // Search should be cleared
    expect(newSearchInput).toHaveValue("");
    // All options should be visible
    expect(screen.getAllByRole("option")).toHaveLength(INDUSTRY_OPTIONS.length);
  });

  test("handles escape key to close dropdown", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");

    // Focus search input and press Escape
    const searchInput = await screen.findByPlaceholderText(
      "Search industries...",
    );
    await user.click(searchInput);
    await user.keyboard("{Escape}");

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByPlaceholderText("Search industries..."),
    ).not.toBeInTheDocument();
  });

  test("maintains highlighted index when filtering", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    // Navigate down a few items
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{ArrowDown}");

    // Start searching
    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.type(searchInput, "a");

    // First filtered item should be highlighted
    const filteredOptions = screen.getAllByRole("option");
    expect(filteredOptions[0]).toHaveClass("bg-accent");
  });

  test("handles mouse and keyboard interaction together", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));
    const options = screen.getAllByRole("option");

    // Use keyboard to navigate to second item
    await user.keyboard("{ArrowDown}");
    expect(options[1]).toHaveClass("bg-accent");

    // Hover over fourth item
    await user.hover(options[3]);
    expect(options[3]).toHaveClass("bg-accent");
    expect(options[1]).not.toHaveClass("bg-accent");

    // Use keyboard again - should continue from hovered item
    await user.keyboard("{ArrowDown}");
    expect(options[4]).toHaveClass("bg-accent");
  });

  test("handles rapid search input changes", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));
    const searchInput = screen.getByPlaceholderText("Search industries...");

    // Type rapidly
    await user.type(searchInput, "tech");
    await user.clear(searchInput);
    await user.type(searchInput, "health");
    await user.clear(searchInput);
    await user.type(searchInput, "software");

    // Should show correct filtered results
    expect(
      screen.getByText("Enterprise Software and SaaS [B2B]"),
    ).toBeInTheDocument();
  });

  test("handles empty search results gracefully", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectDropdown value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));
    const searchInput = screen.getByPlaceholderText("Search industries...");

    // Search for something that doesn't exist
    await user.type(searchInput, "xyzabc123notfound");

    expect(screen.getByText("No industry found.")).toBeInTheDocument();
    expect(screen.queryAllByRole("option")).toHaveLength(0);

    // Keyboard navigation should do nothing
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    // Should not call onValueChange
    expect(mockOnValueChange).not.toHaveBeenCalled();
  });

  test("preserves selection when reopening", async () => {
    const user = userEvent.setup();
    const selectedIndustry = INDUSTRY_OPTIONS[5];
    const { rerender } = render(
      <IndustrySelectDropdown
        value={selectedIndustry.value}
        onValueChange={mockOnValueChange}
      />,
    );

    // Open dropdown
    await user.click(screen.getByRole("combobox"));

    // Selected item should have checkmark visible
    const selectedOptions = screen.getAllByText(selectedIndustry.label);
    // Get the one in the dropdown (not the button)
    const selectedOption = selectedOptions[1].parentElement?.parentElement;
    const checkIcon = selectedOption?.querySelector("svg.opacity-100");
    expect(checkIcon).toBeInTheDocument();

    // Close and reopen
    await user.click(document.body);
    await user.click(screen.getByRole("combobox"));

    // Selection should be preserved
    const stillSelectedOptions = screen.getAllByText(selectedIndustry.label);
    const stillSelectedOption =
      stillSelectedOptions[1].parentElement?.parentElement;
    const stillCheckIcon =
      stillSelectedOption?.querySelector("svg.opacity-100");
    expect(stillCheckIcon).toBeInTheDocument();
  });
});
