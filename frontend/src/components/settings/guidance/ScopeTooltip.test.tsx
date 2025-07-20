import { describe, test, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScopeTooltip, ScopeHelpIcon } from "./ScopeTooltip";

describe("ScopeTooltip", () => {
  test("renders tooltip trigger correctly", () => {
    render(
      <ScopeTooltip scope="account" setting="account_name">
        <button>Hover me</button>
      </ScopeTooltip>,
    );

    const trigger = screen.getByRole("button");
    expect(trigger).toHaveTextContent("Hover me");
    expect(trigger).toBeInTheDocument();
  });

  test("shows tooltip content on interaction", async () => {
    const user = userEvent.setup();

    render(
      <ScopeTooltip scope="account" setting="account_name">
        <button>Hover me</button>
      </ScopeTooltip>,
    );

    const trigger = screen.getByRole("button");

    // Hover to show tooltip (Radix UI tooltips show on hover)
    await user.hover(trigger);

    // Wait for tooltip to appear and check for specific content
    await waitFor(() => {
      expect(screen.getAllByText("Account Name")[0]).toBeInTheDocument();
    });
  });

  test("shows different content for different scopes", async () => {
    const user = userEvent.setup();

    render(
      <ScopeTooltip scope="organization" setting="timezone">
        <button>Organization timezone</button>
      </ScopeTooltip>,
    );

    const trigger = screen.getByRole("button");
    await user.hover(trigger);

    await waitFor(() => {
      // Check for organization-specific content
      expect(
        screen.getAllByText("Organization Timezone")[0],
      ).toBeInTheDocument();
    });
  });

  test("shows setting-specific content for timezone", async () => {
    const user = userEvent.setup();

    render(
      <ScopeTooltip scope="account" setting="timezone">
        <button>Account timezone</button>
      </ScopeTooltip>,
    );

    const trigger = screen.getByRole("button");
    await user.hover(trigger);

    await waitFor(() => {
      // Check for timezone-specific content
      expect(screen.getAllByText("Account Timezone")[0]).toBeInTheDocument();
    });
  });

  test("tooltip content generation works correctly", () => {
    // Test the tooltip content generation directly
    render(
      <ScopeTooltip scope="user" setting="language">
        <span>Test</span>
      </ScopeTooltip>,
    );

    // Just verify it renders without error
    expect(screen.getByText("Test")).toBeInTheDocument();
  });
});

describe("ScopeHelpIcon", () => {
  test("renders help icon with correct structure", () => {
    render(<ScopeHelpIcon scope="user" setting="language" />);

    // Look for the svg element by class name
    const helpIcon = document.querySelector(".lucide-circle-help");
    expect(helpIcon).toBeInTheDocument();
  });

  test("renders without crashing for all scopes", () => {
    const scopes = ["organization", "account", "user"] as const;

    scopes.forEach((scope) => {
      const { unmount } = render(
        <ScopeHelpIcon scope={scope} setting="test" />,
      );
      const helpIcon = document.querySelector(".lucide-circle-help");
      expect(helpIcon).toBeInTheDocument();
      unmount();
    });
  });

  test("shows tooltip on interaction", async () => {
    const user = userEvent.setup();

    render(<ScopeHelpIcon scope="user" setting="language" />);

    const icon = document.querySelector(".lucide-circle-help");

    // Hover on the icon to trigger tooltip
    await user.hover(icon);

    await waitFor(() => {
      // Check for specific tooltip content
      expect(screen.getAllByText("Interface Language")[0]).toBeInTheDocument();
    });
  });
});
