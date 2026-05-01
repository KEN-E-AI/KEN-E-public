import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import NotFoundPage from "./NotFoundPage";

describe("NotFoundPage", () => {
  it("renders 404 content with full-height centering", () => {
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
    expect(innerDiv?.classList.contains("min-h-screen")).toBe(true);
  });
});
