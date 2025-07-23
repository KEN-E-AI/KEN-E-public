import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IndustrySelectSearchable } from "./industry-select-searchable";
import { INDUSTRY_OPTIONS } from "@/data/organizationTypes";

describe("IndustrySelectSearchable", () => {
  const mockOnValueChange = vi.fn();

  beforeEach(() => {
    mockOnValueChange.mockClear();
  });

  test("renders with placeholder when no value is selected", () => {
    render(
      <IndustrySelectSearchable
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
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    expect(screen.getByRole("combobox")).toHaveTextContent("Select industry");
  });

  test("displays selected industry label", () => {
    const selectedIndustry = INDUSTRY_OPTIONS[0];
    render(
      <IndustrySelectSearchable
        value={selectedIndustry.value}
        onValueChange={mockOnValueChange}
      />,
    );

    expect(screen.getByRole("combobox")).toHaveTextContent(
      selectedIndustry.label,
    );
  });

  test("opens popover when button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    const trigger = screen.getByRole("combobox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByPlaceholderText("Search industries..."),
    ).toBeInTheDocument();
  });

  test("shows search input when opened", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    const searchInput = screen.getByPlaceholderText("Search industries...");
    expect(searchInput).toBeInTheDocument();
  });

  test("filters industries based on search input", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
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
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    const firstIndustry = screen.getByText(INDUSTRY_OPTIONS[0].label);
    await user.click(firstIndustry);

    expect(mockOnValueChange).toHaveBeenCalledWith(INDUSTRY_OPTIONS[0].value);
  });

  test("closes popover after selection", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");

    const firstIndustry = screen.getByText(INDUSTRY_OPTIONS[0].label);
    await user.click(firstIndustry);

    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  test("shows empty state when search returns no results", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.type(searchInput, "xyzabc123");

    expect(screen.getByText("No industry found.")).toBeInTheDocument();
  });

  test("applies custom className to trigger button", () => {
    render(
      <IndustrySelectSearchable
        value=""
        onValueChange={mockOnValueChange}
        className="custom-class"
      />,
    );

    const trigger = screen.getByRole("combobox");
    expect(trigger).toHaveClass("custom-class");
  });

  test("forwards ref to trigger button", () => {
    const ref = vi.fn();
    render(
      <IndustrySelectSearchable
        ref={ref as any}
        value=""
        onValueChange={mockOnValueChange}
      />,
    );

    expect(ref).toHaveBeenCalled();
    expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLButtonElement);
  });

  test("search is case insensitive", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.type(searchInput, "SOFTWARE");

    // Should still find software industry despite uppercase search
    expect(
      screen.getByText("Enterprise Software and SaaS [B2B]"),
    ).toBeInTheDocument();
  });

  test("keyboard navigation moves one item at a time", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    // Get option elements by role
    const options = screen.getAllByRole("option");

    // First item should be highlighted by default
    expect(options[0]).toHaveClass("bg-accent");

    // Press ArrowDown once - should move to second item (index 1)
    await user.keyboard("{ArrowDown}");
    expect(options[1]).toHaveClass("bg-accent");
    expect(options[0]).not.toHaveClass("bg-accent");
    expect(options[2]).not.toHaveClass("bg-accent");

    // Press ArrowDown again - should move to third item (index 2)
    await user.keyboard("{ArrowDown}");
    expect(options[2]).toHaveClass("bg-accent");
    expect(options[1]).not.toHaveClass("bg-accent");
    expect(options[3]).not.toHaveClass("bg-accent");

    // Press ArrowUp once - should go back to second item (index 1)
    await user.keyboard("{ArrowUp}");
    expect(options[1]).toHaveClass("bg-accent");
    expect(options[0]).not.toHaveClass("bg-accent");
    expect(options[2]).not.toHaveClass("bg-accent");
  });

  test("keyboard navigation selects correct item", async () => {
    const user = userEvent.setup();
    render(
      <IndustrySelectSearchable value="" onValueChange={mockOnValueChange} />,
    );

    await user.click(screen.getByRole("combobox"));

    // Press ArrowDown to move to second item
    await user.keyboard("{ArrowDown}");

    // Press Enter - should select the second item
    await user.keyboard("{Enter}");
    expect(mockOnValueChange).toHaveBeenCalledWith(INDUSTRY_OPTIONS[1].value);
    expect(mockOnValueChange).toHaveBeenCalledTimes(1);
  });
});
