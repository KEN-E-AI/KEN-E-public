import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopNav } from "./TopNav";

vi.mock("./AccountSwitcher", () => ({
  AccountSwitcher: ({ compact }: { compact?: boolean }) => (
    <div
      data-testid="account-switcher"
      data-compact={compact ? "true" : "false"}
    />
  ),
}));
vi.mock("./NotificationBell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));
vi.mock("./ProfileMenu", () => ({
  ProfileMenu: ({ compact }: { compact?: boolean }) => (
    <div data-testid="profile-menu" data-compact={compact ? "true" : "false"} />
  ),
}));

describe("TopNav", () => {
  test("renders all three children", () => {
    render(<TopNav />);
    expect(screen.getByTestId("account-switcher")).toBeInTheDocument();
    expect(screen.getByTestId("notification-bell")).toBeInTheDocument();
    expect(screen.getByTestId("profile-menu")).toBeInTheDocument();
  });

  test("forwards compact=false by default", () => {
    render(<TopNav />);
    expect(screen.getByTestId("account-switcher")).toHaveAttribute(
      "data-compact",
      "false",
    );
    expect(screen.getByTestId("profile-menu")).toHaveAttribute(
      "data-compact",
      "false",
    );
  });

  test("forwards compact=true when passed", () => {
    render(<TopNav compact />);
    expect(screen.getByTestId("account-switcher")).toHaveAttribute(
      "data-compact",
      "true",
    );
    expect(screen.getByTestId("profile-menu")).toHaveAttribute(
      "data-compact",
      "true",
    );
  });
});
