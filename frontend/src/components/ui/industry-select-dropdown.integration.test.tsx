import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { IndustrySelectDropdown } from "./industry-select-dropdown";
import { INDUSTRY_OPTIONS } from "@/data/organizationTypes";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Test form schema
const formSchema = z.object({
  name: z.string().min(2, { message: "Name must be at least 2 characters" }),
  industry: z.string().min(1, { message: "Please select an industry" }),
  website: z.string().url().optional().or(z.literal("")),
});

// Test form component
function TestForm({ onSubmit }: { onSubmit: (data: any) => void }) {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      industry: "",
      website: "",
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Company Name</FormLabel>
              <FormControl>
                <Input {...field} placeholder="Enter company name" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="industry"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Industry</FormLabel>
              <FormControl>
                <IndustrySelectDropdown
                  value={field.value}
                  onValueChange={field.onChange}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="website"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Website</FormLabel>
              <FormControl>
                <Input {...field} type="url" placeholder="https://example.com" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit">Submit</Button>
      </form>
    </Form>
  );
}

describe("IndustrySelectDropdown Integration Tests", () => {
  const mockSubmit = vi.fn();

  beforeEach(() => {
    mockSubmit.mockClear();
  });

  test("integrates with React Hook Form", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Fill out the form
    await user.type(screen.getByPlaceholderText("Enter company name"), "Test Company");
    
    // Select an industry
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[0].label));

    await user.type(screen.getByPlaceholderText("https://example.com"), "https://test.com");

    // Submit the form
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalled();
      const callArgs = mockSubmit.mock.calls[0][0];
      expect(callArgs).toEqual({
        name: "Test Company",
        industry: INDUSTRY_OPTIONS[0].value,
        website: "https://test.com",
      });
    });
  });

  test("shows validation error when industry is not selected", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Fill out only name
    await user.type(screen.getByPlaceholderText("Enter company name"), "Test Company");

    // Submit without selecting industry
    await user.click(screen.getByRole("button", { name: "Submit" }));

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText("Please select an industry")).toBeInTheDocument();
    });

    // Form should not be submitted
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  test("clears validation error when industry is selected", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Submit without filling anything to trigger validation
    await user.click(screen.getByRole("button", { name: "Submit" }));

    // Should show validation errors
    await waitFor(() => {
      expect(screen.getByText("Please select an industry")).toBeInTheDocument();
    });

    // Fill the name field
    await user.type(screen.getByPlaceholderText("Enter company name"), "Test Company");

    // Select an industry
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[2].label));

    // Validation error should be cleared
    await waitFor(() => {
      expect(screen.queryByText("Please select an industry")).not.toBeInTheDocument();
    });
  });

  test("retains form state when dropdown is opened and closed", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Fill out the form
    await user.type(screen.getByPlaceholderText("Enter company name"), "Test Company");
    
    // Select an industry
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[3].label));

    // Close and reopen dropdown
    await user.click(screen.getByRole("combobox"));
    await user.click(document.body); // Close

    // Verify form still has the values
    expect(screen.getByPlaceholderText("Enter company name")).toHaveValue("Test Company");
    expect(screen.getByRole("combobox")).toHaveTextContent(INDUSTRY_OPTIONS[3].label);

    // Submit to verify data is intact
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalled();
      const callArgs = mockSubmit.mock.calls[0][0];
      expect(callArgs).toEqual({
        name: "Test Company",
        industry: INDUSTRY_OPTIONS[3].value,
        website: "",
      });
    });
  });

  test("allows changing selection multiple times", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Select first industry
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[0].label));
    expect(screen.getByRole("combobox")).toHaveTextContent(INDUSTRY_OPTIONS[0].label);

    // Change to different industry
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[5].label));
    expect(screen.getByRole("combobox")).toHaveTextContent(INDUSTRY_OPTIONS[5].label);

    // Change again
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[10].label));
    expect(screen.getByRole("combobox")).toHaveTextContent(INDUSTRY_OPTIONS[10].label);
  });

  test("works with keyboard navigation in form context", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Tab to name field
    await user.tab();
    expect(screen.getByPlaceholderText("Enter company name")).toHaveFocus();
    await user.type(screen.getByPlaceholderText("Enter company name"), "Test Co");

    // Tab to industry dropdown
    await user.tab();
    expect(screen.getByRole("combobox")).toHaveFocus();

    // Open with Enter key
    await user.keyboard("{Enter}");
    expect(screen.getByPlaceholderText("Search industries...")).toBeInTheDocument();

    // Navigate and select with keyboard
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    // Should have selected third item
    expect(screen.getByRole("combobox")).toHaveTextContent(INDUSTRY_OPTIONS[2].label);

    // Tab to next field (wait for dropdown to close)
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Search industries...")).not.toBeInTheDocument();
    });
    
    await user.tab();
    expect(screen.getByPlaceholderText("https://example.com")).toHaveFocus();
  });

  test("search functionality works within form", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Open dropdown and search
    await user.click(screen.getByRole("combobox"));
    const searchInput = screen.getByPlaceholderText("Search industries...");
    await user.type(searchInput, "software");

    // Select from filtered results
    await user.click(screen.getByText("Enterprise Software and SaaS [B2B]"));

    // Verify selection
    expect(screen.getByRole("combobox")).toHaveTextContent("Enterprise Software and SaaS [B2B]");

    // Fill other fields and submit
    await user.type(screen.getByPlaceholderText("Enter company name"), "Tech Corp");
    await user.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalled();
      const callArgs = mockSubmit.mock.calls[0][0];
      expect(callArgs).toEqual({
        name: "Tech Corp",
        industry: "Enterprise Software and SaaS [B2B]",
        website: "",
      });
    });
  });

  test("handles form reset correctly", async () => {
    const user = userEvent.setup();
    
    // Extended form with reset button
    function TestFormWithReset({ onSubmit }: { onSubmit: (data: any) => void }) {
      const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
          name: "",
          industry: "",
          website: "",
        },
      });

      return (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="industry"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Industry</FormLabel>
                  <FormControl>
                    <IndustrySelectDropdown
                      value={field.value}
                      onValueChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <Button type="submit">Submit</Button>
            <Button type="button" onClick={() => form.reset()}>Reset</Button>
          </form>
        </Form>
      );
    }

    render(<TestFormWithReset onSubmit={mockSubmit} />);

    // Select an industry
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText(INDUSTRY_OPTIONS[2].label));
    expect(screen.getByRole("combobox")).toHaveTextContent(INDUSTRY_OPTIONS[2].label);

    // Reset form
    await user.click(screen.getByRole("button", { name: "Reset" }));

    // Industry should be cleared
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveTextContent("Select industry");
    });
  });

  test("maintains proper focus management in form flow", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Tab through form fields
    await user.tab(); // Focus name
    await user.tab(); // Focus industry dropdown

    // Open dropdown with Enter
    await user.keyboard("{Enter}");
    
    // Wait for dropdown to open
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search industries...")).toBeInTheDocument();
    });

    // Search input should be focused (wait for async focus)
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search industries...")).toHaveFocus();
    });

    // Type to search
    await user.type(screen.getByPlaceholderText("Search industries..."), "health");

    // Select with Enter
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    // Focus should return to the button
    expect(screen.getByRole("combobox")).toHaveFocus();

    // Continue tabbing
    await user.tab();
    expect(screen.getByPlaceholderText("https://example.com")).toHaveFocus();
  });

  test("handles form submission with Enter key", async () => {
    const user = userEvent.setup();
    render(<TestForm onSubmit={mockSubmit} />);

    // Fill form using keyboard
    await user.tab();
    await user.type(screen.getByPlaceholderText("Enter company name"), "Quick Entry");
    
    await user.tab();
    await user.keyboard("{Enter}"); // Open dropdown
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}"); // Select item

    await user.tab();
    await user.type(screen.getByPlaceholderText("https://example.com"), "https://quick.com");

    // Submit with Enter
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalled();
      const callArgs = mockSubmit.mock.calls[0][0];
      expect(callArgs).toEqual({
        name: "Quick Entry",
        industry: INDUSTRY_OPTIONS[1].value,
        website: "https://quick.com",
      });
    });
  });
});