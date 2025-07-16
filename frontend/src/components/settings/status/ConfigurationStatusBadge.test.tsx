import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ConfigurationStatusBadge,
  ConfigurationOverview,
} from "./ConfigurationStatusBadge";

describe("ConfigurationStatusBadge", () => {
  test("renders complete status correctly", () => {
    render(
      <ConfigurationStatusBadge
        status="complete"
        completedSteps={5}
        totalSteps={5}
        requiredSteps={4}
        lastUpdated="2 days ago"
      />,
    );

    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("5/5")).toBeInTheDocument();
  });

  test("renders warning status correctly", () => {
    render(
      <ConfigurationStatusBadge
        status="warning"
        completedSteps={3}
        totalSteps={5}
        requiredSteps={4}
        lastUpdated="1 week ago"
      />,
    );

    expect(screen.getByText("Needs Attention")).toBeInTheDocument();
    expect(screen.getByText("3/5")).toBeInTheDocument();
  });

  test("renders incomplete status correctly", () => {
    render(
      <ConfigurationStatusBadge
        status="incomplete"
        completedSteps={2}
        totalSteps={5}
        requiredSteps={4}
        lastUpdated="Never"
      />,
    );

    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("2/5")).toBeInTheDocument();
  });

  test("renders error status correctly", () => {
    render(
      <ConfigurationStatusBadge
        status="error"
        completedSteps={1}
        totalSteps={5}
        requiredSteps={4}
        lastUpdated="1 hour ago"
      />,
    );

    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("1/5")).toBeInTheDocument();
  });

  test("renders pending status correctly", () => {
    render(
      <ConfigurationStatusBadge
        status="pending"
        completedSteps={0}
        totalSteps={5}
        requiredSteps={4}
        lastUpdated="Never"
      />,
    );

    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("0/5")).toBeInTheDocument();
  });

  test("shows detailed view when showDetails is true", () => {
    render(
      <ConfigurationStatusBadge
        status="warning"
        completedSteps={3}
        totalSteps={5}
        requiredSteps={4}
        lastUpdated="1 week ago"
        showDetails={true}
      />,
    );

    expect(screen.getByText("Needs Attention")).toBeInTheDocument();
    expect(screen.getByText("3/5 steps")).toBeInTheDocument();
    expect(screen.getByText("Overall Progress")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("Required Steps")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Last updated: 1 week ago")).toBeInTheDocument();
  });

  test("handles different sizes correctly", () => {
    const { rerender } = render(
      <ConfigurationStatusBadge
        status="complete"
        completedSteps={5}
        totalSteps={5}
        size="sm"
      />,
    );

    expect(screen.getByText("Complete")).toBeInTheDocument();

    rerender(
      <ConfigurationStatusBadge
        status="complete"
        completedSteps={5}
        totalSteps={5}
        size="lg"
      />,
    );

    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  test("doesn't show required steps progress when equal to total", () => {
    render(
      <ConfigurationStatusBadge
        status="warning"
        completedSteps={3}
        totalSteps={5}
        requiredSteps={5}
        showDetails={true}
      />,
    );

    expect(screen.getByText("Overall Progress")).toBeInTheDocument();
    expect(screen.queryByText("Required Steps")).not.toBeInTheDocument();
  });

  test("calculates progress correctly", () => {
    render(
      <ConfigurationStatusBadge
        status="incomplete"
        completedSteps={2}
        totalSteps={8}
        requiredSteps={6}
        showDetails={true}
      />,
    );

    expect(screen.getByText("25%")).toBeInTheDocument(); // Overall progress: 2/8 = 25%
    expect(screen.getByText("33%")).toBeInTheDocument(); // Required progress: 2/6 = 33%
  });
});

describe("ConfigurationOverview", () => {
  const mockSections = [
    {
      id: "organization",
      title: "Organization Settings",
      description: "Organization profile and settings",
      status: "complete" as const,
      completedSteps: 4,
      totalSteps: 4,
      requiredSteps: 3,
      lastUpdated: "2 days ago",
    },
    {
      id: "account",
      title: "Account Management",
      description: "Account configuration",
      status: "warning" as const,
      completedSteps: 2,
      totalSteps: 3,
      requiredSteps: 2,
      lastUpdated: "1 week ago",
    },
    {
      id: "user",
      title: "User Settings",
      description: "Personal preferences",
      status: "incomplete" as const,
      completedSteps: 1,
      totalSteps: 3,
      requiredSteps: 2,
      lastUpdated: "Never",
    },
  ];

  test("renders configuration overview correctly", () => {
    render(<ConfigurationOverview sections={mockSections} />);

    expect(screen.getByText("Configuration Overview")).toBeInTheDocument();
    expect(screen.getByText("Organization Settings")).toBeInTheDocument();
    expect(screen.getByText("Account Management")).toBeInTheDocument();
    expect(screen.getByText("User Settings")).toBeInTheDocument();
  });

  test("calculates overall progress correctly", () => {
    render(<ConfigurationOverview sections={mockSections} />);

    // Overall progress: (4 + 2 + 1) / (4 + 3 + 3) = 7/10 = 70%
    expect(screen.getByText("70%")).toBeInTheDocument();

    // Required progress: (3 + 2 + 1) / (3 + 2 + 2) = 6/7 = 86%
    expect(screen.getByText("86%")).toBeInTheDocument();
  });

  test("shows correct overall status", () => {
    render(<ConfigurationOverview sections={mockSections} />);

    // Should show "warning" status because there are warnings but no errors
    const needsAttentionBadges = screen.getAllByText("Needs Attention");
    expect(needsAttentionBadges.length).toBeGreaterThan(0);
  });

  test("shows complete status when all sections complete", () => {
    const completeSections = mockSections.map((section) => ({
      ...section,
      status: "complete" as const,
      completedSteps: section.totalSteps,
    }));

    render(<ConfigurationOverview sections={completeSections} />);

    const completeBadges = screen.getAllByText("Complete");
    expect(completeBadges.length).toBeGreaterThan(0);
  });

  test("shows error status when any section has error", () => {
    const sectionsWithError = [
      ...mockSections,
      {
        id: "error-section",
        title: "Error Section",
        description: "Section with error",
        status: "error" as const,
        completedSteps: 0,
        totalSteps: 2,
        requiredSteps: 1,
        lastUpdated: "1 hour ago",
      },
    ];

    render(<ConfigurationOverview sections={sectionsWithError} />);

    const errorBadges = screen.getAllByText("Error");
    expect(errorBadges.length).toBeGreaterThan(0);
  });

  test("shows section descriptions", () => {
    render(<ConfigurationOverview sections={mockSections} />);

    expect(
      screen.getByText("Organization profile and settings"),
    ).toBeInTheDocument();
    expect(screen.getByText("Account configuration")).toBeInTheDocument();
    expect(screen.getByText("Personal preferences")).toBeInTheDocument();
  });

  test("handles empty sections array", () => {
    render(<ConfigurationOverview sections={[]} />);

    expect(screen.getByText("Configuration Overview")).toBeInTheDocument();
    const zeroPercents = screen.getAllByText("0%");
    expect(zeroPercents.length).toBe(2); // Both progress bars should show 0%
  });
});
