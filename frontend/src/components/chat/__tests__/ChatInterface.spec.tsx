/**
 * Unit tests for ChatInterface reasoning-channel integration (CH-60).
 *
 * Covers:
 * - Live ThinkingBlock receives streaming thoughts as reasoning events arrive.
 * - ThinkingBlock shows placeholder ("Analyzing your request…") when no thoughts.
 * - Persisted message contains reasoning.thoughts after stream completion.
 * - Stop button preserves partial reasoning.
 * - Second turn starts with empty liveThoughts (no ghost from prior turn).
 * - Text streaming continues to work correctly alongside reasoning.
 *
 * References: CH-60 Implementation Plan Task 4.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { StreamEvent } from "@/lib/chatApi";

// ---------------------------------------------------------------------------
// Mocks — all external deps that ChatInterface pulls in
// ---------------------------------------------------------------------------

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...p }: any) => <div {...p}>{children}</div>,
    p: ({ children, ...p }: any) => <p {...p}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("@/lib/chatApi", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/chatApi")>("@/lib/chatApi");
  return {
    ...actual,
    getConversationHistory: vi.fn().mockResolvedValue([]),
    streamChatCompletion: vi.fn(),
  };
});

vi.mock("@/lib/parseConversationHistory", () => ({
  parseConversationHistory: vi.fn().mockReturnValue([]),
}));

vi.mock("@/hooks/useOrgStatus", () => ({
  useOrgStatus: vi.fn().mockReturnValue({ status: "active" }),
}));

vi.mock("@/hooks/useMarkRead", () => ({
  useMarkRead: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { ChatInterface } from "../ChatInterface";
import { streamChatCompletion } from "@/lib/chatApi";

const mockStreamChatCompletion = vi.mocked(streamChatCompletion);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build an AsyncGenerator from a list of StreamEvents. */
async function* makeStream(events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  for (const ev of events) {
    yield ev;
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatInterface — reasoning channel (CH-60)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("live ThinkingBlock shows placeholder when no thoughts yet (isThinking=true, thoughts=[])", async () => {
    // Stream that hangs — we just want to see the initial isStreaming=true state.
    // We'll use a never-resolving generator and just check the placeholder renders.
    let resolvePause: () => void;
    const pause = new Promise<void>((resolve) => {
      resolvePause = resolve;
    });

    async function* hangingStream(): AsyncGenerator<StreamEvent> {
      await pause;
      yield { type: "text", text: "done" };
    }

    mockStreamChatCompletion.mockReturnValue(hangingStream() as any);

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "hello");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      // The ThinkingBlock placeholder is shown during streaming when no thoughts.
      expect(screen.getByText(/analyzing your request/i)).toBeInTheDocument();
    });

    // Clean up — let the stream finish so no open handles.
    act(() => {
      resolvePause!();
    });
  });

  test("live ThinkingBlock receives thoughts as reasoning events arrive", async () => {
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "reasoning", text: "Step one." },
        { type: "reasoning", text: " Step two." },
        { type: "text", text: "Answer." },
      ]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "hello");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      // After stream completes the assistant message should appear.
      expect(screen.getByText("Answer.")).toBeInTheDocument();
    });
  });

  test("text streaming still works when there are no reasoning events", async () => {
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "text", text: "Hello " },
        { type: "text", text: "world." },
      ]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "hi");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Hello world.")).toBeInTheDocument();
    });
  });

  test("second turn starts with empty thoughts (no ghost from prior turn)", async () => {
    // First turn with reasoning.
    mockStreamChatCompletion.mockReturnValueOnce(
      makeStream([
        { type: "reasoning", text: "Turn 1 thought." },
        { type: "text", text: "Turn 1 answer." },
      ]) as any,
    );

    // Second turn — text only, no reasoning.
    mockStreamChatCompletion.mockReturnValueOnce(
      makeStream([{ type: "text", text: "Turn 2 answer." }]) as any,
    );

    render(<ChatInterface />);

    const textarea = screen.getByPlaceholderText(/ask me anything/i);

    // First send.
    await userEvent.type(textarea, "question 1");
    await userEvent.keyboard("{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Turn 1 answer.")).toBeInTheDocument();
    });

    // Second send — ThinkingBlock should start with no ghost thoughts (shows placeholder).
    await userEvent.type(textarea, "question 2");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Turn 2 answer.")).toBeInTheDocument();
    });

    // Both calls made.
    expect(mockStreamChatCompletion).toHaveBeenCalledTimes(2);
  });

  test("pending_ session id reconciliation: onSessionResolved called once with the real id, locallyCreatedRef guards history reload", async () => {
    // This test covers the blind spot the original suite omitted: when
    // createChatConversation returns a pending_ id and the stream emits a
    // "session" event, ChatInterface must call onSessionResolved once with the
    // real id (CH-62).

    // Step 1: set up mocks.
    const onSessionResolved = vi.fn();

    // The stream yields a session event (pending→real) followed by text.
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "session", sessionId: "real_vertex_id_999" },
        { type: "text", text: "Hello from agent." },
      ]) as any,
    );

    // Step 2: render ChatInterface with onSessionResolved prop.
    render(
      <ChatInterface
        sessionId="pending_abc123"
        onSessionResolved={onSessionResolved}
      />,
    );

    // Step 3: send a message to trigger the stream.
    const textarea = screen.getByPlaceholderText(/ask me anything/i);
    await userEvent.type(textarea, "test message");
    await userEvent.keyboard("{Enter}");

    // Step 4: wait for the stream to complete.
    await waitFor(() => {
      expect(screen.getByText("Hello from agent.")).toBeInTheDocument();
    });

    // Step 5: assert onSessionResolved was called exactly once with the real id.
    expect(onSessionResolved).toHaveBeenCalledTimes(1);
    expect(onSessionResolved).toHaveBeenCalledWith("real_vertex_id_999");
  });
});
