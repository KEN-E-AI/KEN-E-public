import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { ThemeProvider, useTheme } from "./ThemeProvider";

function ToggleConsumer() {
  const { mode, toggle } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <button onClick={toggle}>toggle</button>
    </div>
  );
}

function SetModeConsumer({ next }: { next: "light" | "dark" }) {
  const { mode, setMode } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <button onClick={() => setMode(next)}>set</button>
    </div>
  );
}

function OutsideConsumer() {
  const { mode } = useTheme();
  return <span data-testid="mode">{mode}</span>;
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("toggle flips .dark class on <html>", () => {
    render(
      <ThemeProvider>
        <ToggleConsumer />
      </ThemeProvider>,
    );

    expect(document.documentElement.classList.contains("dark")).toBe(false);

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "toggle" }));
    });

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("reads initial mode from localStorage", () => {
    localStorage.setItem("kene-theme", "dark");

    render(
      <ThemeProvider>
        <ToggleConsumer />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("mode").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("persists mode across remount", () => {
    const { unmount } = render(
      <ThemeProvider>
        <SetModeConsumer next="dark" />
      </ThemeProvider>,
    );

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "set" }));
    });

    unmount();

    render(
      <ThemeProvider>
        <ToggleConsumer />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("mode").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("useTheme outside provider returns safe fallback without throwing", () => {
    expect(() => {
      render(<OutsideConsumer />);
    }).not.toThrow();

    expect(screen.getByTestId("mode").textContent).toBe("light");
  });
});
