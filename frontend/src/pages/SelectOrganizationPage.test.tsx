import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import SelectOrganizationPage, {
  PLACEHOLDER_ORGS,
  PLACEHOLDER_ACCOUNTS,
} from "./SelectOrganizationPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <SelectOrganizationPage />
    </MemoryRouter>,
  );
}

describe("SelectOrganizationPage", () => {
  it("renders the page heading", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: /choose a workspace/i }),
    ).toBeInTheDocument();
  });

  it("renders both Organizations and Accounts card titles", () => {
    renderPage();
    expect(screen.getByText("Organizations")).toBeInTheDocument();
    expect(screen.getByText("Accounts")).toBeInTheDocument();
  });

  it("renders the Continue button as disabled by default", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
  });

  it("enables Continue button after selecting an org and account", async () => {
    const user = userEvent.setup();
    renderPage();

    // Initially disabled
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();

    // Select an organization placeholder row
    const orgRows = screen.getAllByRole("button", {
      name: new RegExp(PLACEHOLDER_ORGS[0].name, "i"),
    });
    await user.click(orgRows[0]);

    // Account rows now appear; select one
    const accountRows = screen.getAllByRole("button", {
      name: new RegExp(PLACEHOLDER_ACCOUNTS[0].name, "i"),
    });
    await user.click(accountRows[0]);

    // Continue button should now be enabled
    expect(screen.getByRole("button", { name: /continue/i })).toBeEnabled();
  });

  it("renders the Contact Support mailto link", () => {
    renderPage();
    const link = screen.getByRole("link", { name: /contact support/i });
    expect(link).toHaveAttribute("href", "mailto:support@ken-e.com");
  });

  it("does not render a BackgroundEffects component inside the page", () => {
    renderPage();
    // The global BackgroundEffects mounts bg-blobs and bg-static testids.
    // The page itself must not render them — they live in App.tsx.
    expect(screen.queryAllByTestId("bg-blobs").length).toBe(0);
    expect(screen.queryAllByTestId("bg-static").length).toBe(0);
  });
});
