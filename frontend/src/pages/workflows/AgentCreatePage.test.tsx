import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AgentCreatePage } from "./AgentCreatePage";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AgentCreatePage />
    </MemoryRouter>,
  );
}

describe("AgentCreatePage", () => {
  it("renders Step 1 fields all disabled", () => {
    renderPage();

    expect(screen.getByRole("textbox", { name: /agent name/i })).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /description/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: /instructions/i }),
    ).toBeDisabled();

    // Model tier buttons are disabled
    const modelButtons = screen
      .getAllByRole("button")
      .filter(
        (b) =>
          b.textContent?.includes("Fastest") ||
          b.textContent?.includes("Goldilocks") ||
          b.textContent?.includes("Smartest"),
      );
    expect(modelButtons.length).toBe(3);
    modelButtons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("navigates to Step 2 when Next is clicked and renders disabled tool buttons", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /next/i }));

    // Step 2 content visible
    expect(screen.getByText(/available tools & skills/i)).toBeInTheDocument();

    // Filter pills are disabled
    const filterButtons = screen
      .getAllByRole("button")
      .filter(
        (b) =>
          b.textContent === "All" ||
          b.textContent === "Native" ||
          b.textContent === "Integrations" ||
          b.textContent === "Skills",
      );
    expect(filterButtons.length).toBeGreaterThan(0);
    filterButtons.forEach((btn) => expect(btn).toBeDisabled());

    // Tool rows are disabled
    const toolButtons = screen
      .getAllByRole("button")
      .filter((b) => b.classList.contains("w-full"));
    expect(toolButtons.length).toBeGreaterThan(0);
    toolButtons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("navigates to Step 3 and clicking Create Agent fires toast.success", async () => {
    const { toast } = await import("sonner");
    const user = userEvent.setup();
    renderPage();

    // Step 1 → 2
    await user.click(screen.getByRole("button", { name: /next/i }));
    // Step 2 → 3
    await user.click(screen.getByRole("button", { name: /next/i }));

    // Step 3 content visible
    expect(
      screen.getByRole("heading", { name: /untitled agent/i }),
    ).toBeInTheDocument();

    // Click Create Agent
    await user.click(screen.getByRole("button", { name: /create agent/i }));

    expect(toast.success).toHaveBeenCalledOnce();
    expect(toast.success).toHaveBeenCalledWith("Agent created (mock)");
  });

  it("Previous button navigates back to Step 1 from Step 2", async () => {
    const user = userEvent.setup();
    renderPage();

    // Go to Step 2
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/available tools & skills/i)).toBeInTheDocument();

    // Go back to Step 1
    await user.click(screen.getByRole("button", { name: /previous/i }));
    expect(
      screen.getByRole("textbox", { name: /agent name/i }),
    ).toBeInTheDocument();
  });
});
