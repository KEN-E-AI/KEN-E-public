import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppErrorBoundary } from "./AppErrorBoundary";

vi.mock("@/utils/authRecovery", () => ({
  forceCleanLogout: vi.fn(),
}));

const ThrowOnRender = ({ shouldThrow }: { shouldThrow: boolean }) => {
  if (shouldThrow) throw new Error("test error");
  return <div data-testid="healthy-child">ok</div>;
};

describe("AppErrorBoundary", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("catches a render error and shows the fallback UI", () => {
    render(
      <MemoryRouter initialEntries={["/foo"]}>
        <AppErrorBoundary>
          <ThrowOnRender shouldThrow />
        </AppErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /clear cache & reload/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign out & reset/i }),
    ).toBeInTheDocument();
  });

  it("resets the boundary when the route pathname changes", () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={["/foo"]}>
        <AppErrorBoundary>
          <ThrowOnRender shouldThrow />
        </AppErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    unmount();

    render(
      <MemoryRouter initialEntries={["/bar"]}>
        <AppErrorBoundary>
          <ThrowOnRender shouldThrow={false} />
        </AppErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("healthy-child")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
