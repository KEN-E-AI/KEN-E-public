import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  RequiredIndicator,
  FieldRequiredIndicator,
  RequiredFieldsOverview,
} from "./RequiredIndicator";

describe("RequiredIndicator", () => {
  test("renders asterisk variant for required field", () => {
    render(<RequiredIndicator required={true} variant="asterisk" />);

    expect(screen.getByText("*")).toBeInTheDocument();
  });

  test("renders badge variant for required field", () => {
    render(<RequiredIndicator required={true} variant="badge" />);

    expect(screen.getByText("Required")).toBeInTheDocument();
  });

  test("renders badge variant for optional field", () => {
    render(<RequiredIndicator required={false} variant="badge" />);

    expect(screen.getByText("Optional")).toBeInTheDocument();
  });

  test("renders subtle variant for required field", () => {
    render(<RequiredIndicator required={true} variant="subtle" />);

    expect(screen.getByText("Required")).toBeInTheDocument();
  });

  test("renders nothing for optional field with asterisk variant", () => {
    const { container } = render(
      <RequiredIndicator required={false} variant="asterisk" />,
    );

    expect(container.firstChild).toBeNull();
  });

  test("renders custom label", () => {
    render(
      <RequiredIndicator required={true} variant="badge" label="Mandatory" />,
    );

    expect(screen.getByText("Mandatory")).toBeInTheDocument();
  });

  test("renders scope badge when scope is provided", () => {
    render(<RequiredIndicator required={true} scope="organization" />);

    expect(screen.getByText("Organization")).toBeInTheDocument();
  });

  test("handles different sizes", () => {
    const { rerender } = render(
      <RequiredIndicator required={true} variant="badge" size="sm" />,
    );

    expect(screen.getByText("Required")).toBeInTheDocument();

    rerender(<RequiredIndicator required={true} variant="badge" size="lg" />);

    expect(screen.getByText("Required")).toBeInTheDocument();
  });

  test("shows tooltip when provided", () => {
    render(
      <RequiredIndicator
        required={true}
        variant="asterisk"
        tooltip="This field is required for configuration"
      />,
    );

    expect(screen.getByText("*")).toBeInTheDocument();
    // Note: Testing tooltip hover behavior would require user interaction testing
  });
});

describe("FieldRequiredIndicator", () => {
  test("renders field-specific tooltip for required field", () => {
    render(
      <FieldRequiredIndicator
        required={true}
        fieldName="Email Address"
        scope="user"
      />,
    );

    expect(screen.getByText("*")).toBeInTheDocument();
    // The tooltip text would be "Email Address is required for user configuration"
  });

  test("renders field-specific tooltip for optional field", () => {
    render(
      <FieldRequiredIndicator
        required={false}
        fieldName="Phone Number"
        scope="user"
      />,
    );

    // Should render nothing for optional field with asterisk variant
    expect(screen.queryByText("*")).not.toBeInTheDocument();
  });
});

describe("RequiredFieldsOverview", () => {
  const mockFields = [
    {
      name: "Email Address",
      required: true,
      completed: true,
      scope: "user" as const,
    },
    {
      name: "First Name",
      required: true,
      completed: false,
      scope: "user" as const,
    },
    {
      name: "Phone Number",
      required: false,
      completed: true,
      scope: "user" as const,
    },
    {
      name: "Company Website",
      required: false,
      completed: false,
      scope: "organization" as const,
    },
  ];

  test("renders required fields overview correctly", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    expect(screen.getByText("Required Fields")).toBeInTheDocument();
    expect(screen.getByText("Optional Fields")).toBeInTheDocument();
    expect(screen.getByText("Field Status")).toBeInTheDocument();
  });

  test("calculates required fields progress correctly", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    // Required fields: 1 completed out of 2 total = 50%
    const progressTexts = screen.getAllByText("1/2");
    expect(progressTexts.length).toBeGreaterThan(0);
  });

  test("calculates optional fields progress correctly", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    // Optional fields: 1 completed out of 2 total = 50%
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  test("displays all fields with their status", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    expect(screen.getByText("Email Address")).toBeInTheDocument();
    expect(screen.getByText("First Name")).toBeInTheDocument();
    expect(screen.getByText("Phone Number")).toBeInTheDocument();
    expect(screen.getByText("Company Website")).toBeInTheDocument();
  });

  test("shows completed badges for completed fields", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    const completedBadges = screen.getAllByText("Completed");
    expect(completedBadges).toHaveLength(2); // Email Address and Phone Number
  });

  test("shows pending badges for incomplete fields", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    const pendingBadges = screen.getAllByText("Pending");
    expect(pendingBadges).toHaveLength(2); // First Name and Company Website
  });

  test("shows scope badges for fields with scope", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    expect(screen.getAllByText("User")).toHaveLength(3); // Three user-scoped fields
    expect(screen.getByText("Organization")).toBeInTheDocument(); // One org-scoped field
  });

  test("shows required indicators for required fields", () => {
    render(<RequiredFieldsOverview fields={mockFields} />);

    const requiredIndicators = screen.getAllByText("*");
    expect(requiredIndicators).toHaveLength(2); // Two required fields
  });

  test("handles empty fields array", () => {
    render(<RequiredFieldsOverview fields={[]} />);

    expect(screen.getByText("Required Fields")).toBeInTheDocument();
    expect(screen.getByText("Optional Fields")).toBeInTheDocument();
    expect(screen.getByText("0/0")).toBeInTheDocument(); // Both should show 0/0
  });

  test("handles all required fields completed", () => {
    const allCompletedFields = mockFields.map((field) => ({
      ...field,
      completed: true,
    }));

    render(<RequiredFieldsOverview fields={allCompletedFields} />);

    expect(screen.getByText("2/2")).toBeInTheDocument(); // Required fields
    expect(screen.getByText("2/2")).toBeInTheDocument(); // Optional fields
  });

  test("handles no required fields", () => {
    const optionalOnlyFields = mockFields.filter((field) => !field.required);

    render(<RequiredFieldsOverview fields={optionalOnlyFields} />);

    expect(screen.getByText("0/0")).toBeInTheDocument(); // No required fields
    expect(screen.getByText("1/2")).toBeInTheDocument(); // Optional fields
  });

  test("handles no optional fields", () => {
    const requiredOnlyFields = mockFields.filter((field) => field.required);

    render(<RequiredFieldsOverview fields={requiredOnlyFields} />);

    expect(screen.getByText("1/2")).toBeInTheDocument(); // Required fields
    expect(screen.getByText("0/0")).toBeInTheDocument(); // No optional fields
  });
});
