/**
 * ChatInterface tests for server-side error events (CH-79).
 *
 * Covers three acceptance criteria:
 * - AC1: Empty-bubble hard failure — when an error event arrives before any
 *   text has been streamed, the bubble content is replaced with the error
 *   message and the recovery-poll interval is NOT started.
 * - AC2: Post-answer benign failure — when text has already been streamed and
 *   an error event then arrives, the answer is preserved and a recoveryNotice
 *   banner is shown. No recovery-poll interval is started.
 * - AC3: Regression guard — a true stream-death (StreamInterruptedError)
 *   still triggers the existing setRecoveryStatus("recovering") path, which
 *   sets up a setInterval poll.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { StreamEvent } from "@/lib/chatApi";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...p }: any) => <div {...p}>{children}</div>,
    p: ({ children, ...p }: any) => <p {...p}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("@/lib/chatApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/chatApi")>();
  return {
    ...actual,
    streamChatCompletion: vi.fn(),
    getConversationHistory: vi.fn(),
  };
});

vi.mock("@/hooks/useOrgStatus", () => ({
  useOrgStatus: vi.fn().mockReturnValue({ status: "active" }),
}));

vi.mock("@/hooks/useMarkRead", () => ({
  useMarkRead: vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn().mockReturnValue({
    user: null,
    selectedOrgAccount: null,
    isAuthenticated: false,
  }),
}));

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import { ChatInterface } from "../ChatInterface";
import { ChatStreamProvider } from "@/contexts/ChatStreamContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  streamChatCompletion,
  getConversationHistory,
  StreamInterruptedError,
} from "@/lib/chatApi";

const mockStream = vi.mocked(streamChatCompletion);
const mockHistory = vi.mocked(getConversationHistory);

// ---------------------------------------------------------------------------
// Generator helpers
// ---------------------------------------------------------------------------

/** Yields each event in order, then returns (no throw). */
function eventStream(events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  return (async function* () {
    for (const ev of events) {
      yield ev;
    }
  })();
}

/** Throws the given error immediately without yielding any events. */
function dyingStream(err: Error): AsyncGenerator<StreamEvent> {
  return (async function* () {
    throw err;
  })();
}

// ---------------------------------------------------------------------------
// Interaction helper
// ---------------------------------------------------------------------------

async function sendMessage(text = "test question") {
  const textarea = screen.getByPlaceholderText(/ask me anything/i);
  await userEvent.type(textarea, text);
  await userEvent.keyboard("{Enter}");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatInterface — server-side error events (CH-79)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Restore real timers if any individual test installed fake ones.
    vi.useRealTimers();
  });

  test("AC1: empty-bubble hard failure — error message replaces bubble content, no recovery poll", async () => {
    // Stream yields only an error event (no prior text): the pre-created
    // placeholder bubble must be updated with the error message directly.
    mockStream.mockReturnValue(
      eventStream([{ type: "error", message: "Server failure." }]) as any,
    );

    // Collect the interval delays that were registered (userEvent internally
    // calls setInterval with 50ms for its pointer simulation; the recovery poll
    // uses 5000ms). We only care that the 5000ms poll was never started.
    const recoveryPollIntervals: number[] = [];
    const origSetInterval = global.setInterval.bind(global);
    vi.spyOn(global, "setInterval").mockImplementation(
      (fn: TimerHandler, delay?: number, ...args: unknown[]) => {
        if (delay === 5000) recoveryPollIntervals.push(delay);
        return origSetInterval(fn, delay, ...args);
      },
    );

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <ChatStreamProvider>
          <ChatInterface />
        </ChatStreamProvider>
      </QueryClientProvider>,
    );
    await sendMessage();

    // The error message must appear in the assistant bubble.
    await waitFor(() => {
      expect(screen.getByText("Server failure.")).toBeInTheDocument();
    });

    // The recovery notice should NOT appear when the bubble was empty.
    expect(
      screen.queryByText(/Answer received, but a follow-up step failed\./),
    ).not.toBeInTheDocument();

    // The recovery poll (5000ms interval) must not have been started.
    expect(recoveryPollIntervals).toHaveLength(0);
  });

  test("AC2: post-answer benign failure — answer preserved, recoveryNotice shown, no recovery poll", async () => {
    // Stream yields real text first, then an error event. The answer must
    // remain visible and a recoveryNotice banner must appear.
    mockStream.mockReturnValue(
      eventStream([
        { type: "text", text: "The answer.", author: "model" },
        { type: "error", message: "Server failure." },
      ]) as any,
    );

    // See AC1 comment — track only the 5000ms recovery poll interval.
    const recoveryPollIntervals: number[] = [];
    const origSetInterval = global.setInterval.bind(global);
    vi.spyOn(global, "setInterval").mockImplementation(
      (fn: TimerHandler, delay?: number, ...args: unknown[]) => {
        if (delay === 5000) recoveryPollIntervals.push(delay);
        return origSetInterval(fn, delay, ...args);
      },
    );

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <ChatStreamProvider>
          <ChatInterface />
        </ChatStreamProvider>
      </QueryClientProvider>,
    );
    await sendMessage();

    // The original answer text must still be visible.
    await waitFor(() => {
      expect(screen.getByText("The answer.")).toBeInTheDocument();
    });

    // The recovery notice must be rendered.
    expect(
      screen.getByText(/Answer received, but a follow-up step failed\./),
    ).toBeInTheDocument();

    // The recovery poll (5000ms interval) must not have been started.
    expect(recoveryPollIntervals).toHaveLength(0);
  });

  test("AC3 (regression): true stream-death (StreamInterruptedError) still triggers recovery poll", async () => {
    // A stream that dies without [DONE] must still invoke the existing
    // recovery flow, which eventually calls setInterval for the 5s poll.
    mockStream.mockReturnValue(
      dyingStream(new StreamInterruptedError("no_done", "sess-reg-1")) as any,
    );

    // getConversationHistory is called in the immediate recovery attempt.
    // Returning only the user event (no model answer yet) keeps the component
    // in "waiting" state so the 5000ms poll is actually created.
    mockHistory.mockResolvedValue({
      session_id: "sess-reg-1",
      events: [
        { content: { role: "user", parts: [{ text: "test question" }] } },
      ],
    } as unknown as never);

    // Track only the 5000ms recovery poll interval.
    const recoveryPollIntervals: number[] = [];
    const origSetInterval = global.setInterval.bind(global);
    vi.spyOn(global, "setInterval").mockImplementation(
      (fn: TimerHandler, delay?: number, ...args: unknown[]) => {
        if (delay === 5000) recoveryPollIntervals.push(delay);
        return origSetInterval(fn, delay, ...args);
      },
    );

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <ChatStreamProvider>
          <ChatInterface />
        </ChatStreamProvider>
      </QueryClientProvider>,
    );
    await sendMessage();

    // Wait until the immediate recovery attempt finishes and the component
    // transitions to the "waiting" polling state, which registers the 5000ms poll.
    await waitFor(() => {
      expect(recoveryPollIntervals).toHaveLength(1);
    });
  });
});
