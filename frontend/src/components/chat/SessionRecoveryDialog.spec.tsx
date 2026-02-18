import { describe, test, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionRecoveryDialog } from "./SessionRecoveryDialog";
import type { RecoverableSessionInfo } from "@/services/chatService";

const mockSessions: RecoverableSessionInfo[] = [
  {
    session_id: "sess-001",
    conversation_name: "Marketing Analysis",
    last_updated: new Date().toISOString(),
    message_count: 12,
    preview: "What are the latest trends in...",
  },
  {
    session_id: "sess-002",
    conversation_name: "Analytics Report",
    last_updated: new Date(Date.now() - 3_600_000).toISOString(),
    message_count: 5,
  },
];

describe("SessionRecoveryDialog", () => {
  test("renders recoverable sessions list", () => {
    render(
      <SessionRecoveryDialog
        open={true}
        sessions={mockSessions}
        onRecover={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Resume a previous conversation?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Marketing Analysis")).toBeInTheDocument();
    expect(screen.getByText("Analytics Report")).toBeInTheDocument();
    expect(screen.getByText("12 messages")).toBeInTheDocument();
    expect(screen.getByText("5 messages")).toBeInTheDocument();
  });

  test("clicking session calls onRecover with session id", () => {
    const onRecover = vi.fn();
    render(
      <SessionRecoveryDialog
        open={true}
        sessions={mockSessions}
        onRecover={onRecover}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Marketing Analysis"));
    expect(onRecover).toHaveBeenCalledWith("sess-001");
  });

  test("Start Fresh button dismisses dialog", () => {
    const onDismiss = vi.fn();
    render(
      <SessionRecoveryDialog
        open={true}
        sessions={mockSessions}
        onRecover={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByText("Start Fresh"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("shows preview text when available", () => {
    render(
      <SessionRecoveryDialog
        open={true}
        sessions={mockSessions}
        onRecover={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(
      screen.getByText("What are the latest trends in..."),
    ).toBeInTheDocument();
  });
});
