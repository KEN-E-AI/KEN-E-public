import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { IconNavigation } from "./IconNavigation";
import { AuthProvider } from "@/contexts/AuthContext";

const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>,
  );
};

describe("IconNavigation", () => {
  test("renders all navigation items", () => {
    renderWithProviders(<IconNavigation />);

    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Performance" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Big Bets" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Data Exploration" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Knowledge Base" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Settings" }),
    ).toBeInTheDocument();
  });

  test("navigates to correct route when clicking navigation items", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IconNavigation />);

    await user.click(screen.getByRole("button", { name: "Performance" }));
    expect(window.location.pathname).toBe("/performance");

    await user.click(screen.getByRole("button", { name: "Big Bets" }));
    expect(window.location.pathname).toBe("/big-bets");

    await user.click(screen.getByRole("button", { name: "Data Exploration" }));
    expect(window.location.pathname).toBe("/exploration");
  });

  test("shows active state for current route", () => {
    window.history.pushState({}, "", "/performance");
    renderWithProviders(<IconNavigation />);

    const performanceButton = screen.getByRole("button", {
      name: "Performance",
    });
    expect(performanceButton).toHaveClass("bg-blue-600", "text-white");
  });

  test("renders brand logo at the top", () => {
    renderWithProviders(<IconNavigation />);

    expect(screen.getByText("K")).toBeInTheDocument();
  });

  test("renders user menu at the bottom", () => {
    renderWithProviders(<IconNavigation />);

    expect(
      screen.getByRole("button", { name: "User menu" }),
    ).toBeInTheDocument();
  });
});
