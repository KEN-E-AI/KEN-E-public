import { describe, test, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionExpiredDialog } from "./SessionExpiredDialog";

describe("SessionExpiredDialog", () => {
  test("displays expired message when open", () => {
    render(
      <SessionExpiredDialog
        open={true}
        onRecover={vi.fn()}
        onStartNew={vi.fn()}
      />,
    );

    expect(screen.getByText("Session Expired")).toBeInTheDocument();
    expect(screen.getByText(/expired due to inactivity/)).toBeInTheDocument();
    expect(screen.getByText(/preserved for up to 7 days/)).toBeInTheDocument();
  });

  test("Recover Session button calls onRecover", () => {
    const onRecover = vi.fn();
    render(
      <SessionExpiredDialog
        open={true}
        onRecover={onRecover}
        onStartNew={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Recover Session"));
    expect(onRecover).toHaveBeenCalledTimes(1);
  });

  test("Start New Chat button calls onStartNew", () => {
    const onStartNew = vi.fn();
    render(
      <SessionExpiredDialog
        open={true}
        onRecover={vi.fn()}
        onStartNew={onStartNew}
      />,
    );

    fireEvent.click(screen.getByText("Start New Chat"));
    expect(onStartNew).toHaveBeenCalledTimes(1);
  });

  test("not rendered when open is false", () => {
    render(
      <SessionExpiredDialog
        open={false}
        onRecover={vi.fn()}
        onStartNew={vi.fn()}
      />,
    );

    expect(screen.queryByText("Session Expired")).not.toBeInTheDocument();
  });
});
