import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
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

  it("resets the boundary when the route pathname changes (in-place navigation)", () => {
    // Capture navigate from inside the router so we can drive navigation
    // without unmounting the tree.
    let navigateFn: ReturnType<typeof useNavigate> | undefined;
    const NavigationCapture = () => {
      navigateFn = useNavigate();
      return null;
    };

    // Ref-controlled thrower: still alive after the key-forced remount, but
    // won't throw once we flip the ref before navigating.
    const shouldThrowRef = { current: true };
    const ConditionalThrower = () => {
      if (shouldThrowRef.current) throw new Error("test error");
      return <div data-testid="healthy-child">ok</div>;
    };

    render(
      <MemoryRouter initialEntries={["/foo"]}>
        <NavigationCapture />
        <AppErrorBoundary>
          <ConditionalThrower />
        </AppErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Allow the re-mounted child to render cleanly after the key change
    shouldThrowRef.current = false;

    // Navigate within the same mounted tree — location.pathname changes →
    // AppErrorBoundaryInner gets a new key → fresh mount with no error state
    act(() => navigateFn!("/bar"));

    expect(screen.getByTestId("healthy-child")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
