import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IndustrySelectDropdownAPI } from "./industry-select-dropdown-api";
import { templateService } from "@/services/templateService";

// Mock the template service
vi.mock("@/services/templateService", () => ({
  templateService: {
    getAllTemplates: vi.fn(),
  },
}));

describe("IndustrySelectDropdownAPI", () => {
  const mockOnValueChange = vi.fn();
  const mockTemplates = [
    {
      id: "retail_trade_b2c",
      industry: "Retail Trade [B2C]",
      name: "Retail Trade [B2C] Template",
      description: "Selling goods directly to consumers",
      defaultObjectives: [],
      defaultChannels: [],
      defaultKPIs: [],
      marketingChannels: [],
      productIntegrations: [],
      recommendedSettings: {
        timezone: "America/New_York",
        data_region: "United States",
        industry: "Retail Trade [B2C]",
      },
      defaultSettings: {
        data_retention: 90,
      },
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
    {
      id: "manufacturing",
      industry: "Manufacturing",
      name: "Manufacturing Template",
      description: "Transforming raw materials into new products",
      defaultObjectives: [],
      defaultChannels: [],
      defaultKPIs: [],
      marketingChannels: [],
      productIntegrations: [],
      recommendedSettings: {
        timezone: "America/New_York",
        data_region: "United States",
        industry: "Manufacturing",
      },
      defaultSettings: {
        data_retention: 90,
      },
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders with placeholder when no value selected", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI
        value=""
        onValueChange={mockOnValueChange}
        placeholder="Select an industry"
      />,
    );

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByRole("combobox")).not.toHaveTextContent(
        "Loading industries...",
      );
    });

    expect(screen.getByRole("combobox")).toHaveTextContent(
      "Select an industry",
    );
  });

  test("shows loading state while fetching industries", async () => {
    vi.mocked(templateService.getAllTemplates).mockImplementation(
      () => new Promise(() => {}), // Never resolves to keep loading
    );

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(screen.getByText("Loading industries...")).toBeInTheDocument();
    });
  });

  test("displays industries when dropdown is opened", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    // Wait for industries to load
    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    // Check if industries are displayed
    await waitFor(() => {
      expect(screen.getByText("Retail Trade [B2C]")).toBeInTheDocument();
      expect(screen.getByText("Manufacturing")).toBeInTheDocument();
    });
  });

  test("displays industry descriptions in dropdown", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    // Check if descriptions are displayed
    await waitFor(() => {
      expect(
        screen.getByText("Selling goods directly to consumers"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Transforming raw materials into new products"),
      ).toBeInTheDocument();
    });
  });

  test("calls onValueChange when industry is selected", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    // Select an industry
    await waitFor(() => {
      const retailOption = screen.getByText("Retail Trade [B2C]");
      expect(retailOption).toBeInTheDocument();
    });

    const retailOption = screen.getByText("Retail Trade [B2C]");
    await userEvent.click(retailOption);

    expect(mockOnValueChange).toHaveBeenCalledWith("Retail Trade [B2C]");
  });

  test("filters industries based on search input", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    // Type in search input
    const searchInput = screen.getByPlaceholderText("Search industries...");
    await userEvent.type(searchInput, "retail");

    // Check filtered results
    await waitFor(() => {
      expect(screen.getByText("Retail Trade [B2C]")).toBeInTheDocument();
      expect(screen.queryByText("Manufacturing")).not.toBeInTheDocument();
    });
  });

  test("displays selected value", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI
        value="Retail Trade [B2C]"
        onValueChange={mockOnValueChange}
      />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    expect(screen.getByRole("combobox")).toHaveTextContent(
      "Retail Trade [B2C]",
    );
  });

  test("handles API error gracefully", async () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    vi.mocked(templateService.getAllTemplates).mockRejectedValue(
      new Error("API Error"),
    );

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    // Check error message
    await waitFor(() => {
      expect(screen.getByText("Failed to load industries")).toBeInTheDocument();
    });

    consoleErrorSpy.mockRestore();
  });

  test("keyboard navigation works correctly", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Retail Trade [B2C]")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText("Search industries...");

    // Press arrow down to highlight first item
    fireEvent.keyDown(searchInput, { key: "ArrowDown" });

    // Press Enter to select
    fireEvent.keyDown(searchInput, { key: "Enter" });

    expect(mockOnValueChange).toHaveBeenCalledWith("Retail Trade [B2C]");
  });

  test("closes dropdown on Escape key", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Retail Trade [B2C]")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText("Search industries...");

    // Press Escape to close
    fireEvent.keyDown(searchInput, { key: "Escape" });

    // Dropdown should be closed
    await waitFor(() => {
      expect(
        screen.queryByPlaceholderText("Search industries..."),
      ).not.toBeInTheDocument();
    });
  });

  test("shows no results message when search yields no matches", async () => {
    vi.mocked(templateService.getAllTemplates).mockResolvedValue(mockTemplates);

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    // Type in search input that won't match
    const searchInput = screen.getByPlaceholderText("Search industries...");
    await userEvent.type(searchInput, "xyz123");

    // Check no results message
    await waitFor(() => {
      expect(screen.getByText("No industry found.")).toBeInTheDocument();
    });
  });

  test("sorts industries alphabetically", async () => {
    const unsortedTemplates = [
      { ...mockTemplates[1] }, // Manufacturing
      { ...mockTemplates[0] }, // Retail Trade [B2C]
    ];

    vi.mocked(templateService.getAllTemplates).mockResolvedValue(
      unsortedTemplates,
    );

    render(
      <IndustrySelectDropdownAPI value="" onValueChange={mockOnValueChange} />,
    );

    await waitFor(() => {
      expect(templateService.getAllTemplates).toHaveBeenCalled();
    });

    // Open dropdown
    const button = screen.getByRole("combobox");
    await userEvent.click(button);

    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options).toHaveLength(2);
      // Check that Manufacturing comes before Retail (alphabetical order)
      expect(options[0]).toHaveTextContent("Manufacturing");
      expect(options[1]).toHaveTextContent("Retail Trade [B2C]");
    });
  });
});
