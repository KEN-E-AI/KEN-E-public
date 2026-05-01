import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import NotFoundPage from "./NotFoundPage";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("NotFoundPage", () => {
  it("authenticated: renders content without min-h-screen on inner div", () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
    } as ReturnType<typeof useAuth>);

    const { container } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: /404/i })).toBeInTheDocument();
    expect(
      screen.getByText(/the page you're looking for doesn't exist/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /back to home/i }),
    ).toBeInTheDocument();

    const innerDiv = container.firstElementChild;
    expect(innerDiv?.classList.contains("min-h-screen")).toBe(false);
  });

  it("unauthenticated: renders content with min-h-screen on inner div", () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: false,
    } as ReturnType<typeof useAuth>);

    const { container } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: /404/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /back to home/i }),
    ).toBeInTheDocument();

    const innerDiv = container.firstElementChild;
    expect(innerDiv?.classList.contains("min-h-screen")).toBe(true);
  });
});
