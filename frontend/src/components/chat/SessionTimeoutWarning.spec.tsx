import { describe, test, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionTimeoutWarning } from "./SessionTimeoutWarning";

describe("SessionTimeoutWarning", () => {
  test("displays remaining time in countdown format", () => {
    render(
      <SessionTimeoutWarning
        open={true}
        remainingSeconds={300}
        onExtend={vi.fn()}
        onEndSession={vi.fn()}
      />,
    );

    expect(screen.getByText("Session Expiring Soon")).toBeInTheDocument();
    expect(screen.getByText("5:00")).toBeInTheDocument();
  });

  test("I'm still here button calls onExtend", () => {
    const onExtend = vi.fn();
    render(
      <SessionTimeoutWarning
        open={true}
        remainingSeconds={120}
        onExtend={onExtend}
        onEndSession={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("I'm still here"));
    expect(onExtend).toHaveBeenCalledTimes(1);
  });

  test("End Session button calls onEndSession", () => {
    const onEndSession = vi.fn();
    render(
      <SessionTimeoutWarning
        open={true}
        remainingSeconds={120}
        onExtend={vi.fn()}
        onEndSession={onEndSession}
      />,
    );

    fireEvent.click(screen.getByText("End Session"));
    expect(onEndSession).toHaveBeenCalledTimes(1);
  });

  test("not rendered when open is false", () => {
    render(
      <SessionTimeoutWarning
        open={false}
        remainingSeconds={120}
        onExtend={vi.fn()}
        onEndSession={vi.fn()}
      />,
    );

    expect(screen.queryByText("Session Expiring Soon")).not.toBeInTheDocument();
  });
});
