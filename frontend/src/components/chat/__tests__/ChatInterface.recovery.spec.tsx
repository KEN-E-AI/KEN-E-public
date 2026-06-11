/**
 * Stream-death recovery tests (CH-71, workstream C).
 *
 * Two layers:
 * 1. StreamInterruptedError class shape (cheap guards on the typed error).
 * 2. Render-level recovery flow — drives streamChatCompletion to throw
 *    StreamInterruptedError and asserts the component pulls the persisted
 *    answer out of GET /conversations/{id}/history and renders it. This is the
 *    layer that exercises the real failure that shipped: the endpoint returns a
 *    { session_id, events } dict, so the recovery path MUST parse it (not treat
 *    it as a message array) and must only surface an answer that post-dates the
 *    interrupted turn.
 */

import { describe, it, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { StreamEvent } from "@/lib/chatApi";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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

// NB: parseConversationHistory / extractAnswerAfterLastUserMessage are NOT
// mocked — the recovery flow's correctness depends on the real parsing of the
// raw history payload, which is exactly what regressed.

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

import { ChatInterface } from "../ChatInterface";
import { ChatStreamProvider } from "@/contexts/ChatStreamContext";
import {
  streamChatCompletion,
  getConversationHistory,
  StreamInterruptedError,
} from "@/lib/chatApi";

const mockStream = vi.mocked(streamChatCompletion);
const mockHistory = vi.mocked(getConversationHistory);

// An async generator that throws after yielding nothing — models a stream that
// dies without [DONE].
function dyingStream(err: Error): AsyncGenerator<StreamEvent> {
  return (async function* () {
    throw err;
  })();
}

// A clean stream that yields one text fragment then completes.
function textStream(text: string): AsyncGenerator<StreamEvent> {
  return (async function* () {
    yield { type: "text", text, author: "model" };
  })();
}

// A manually-resolvable promise, for controlling when a mocked fetch settles.
function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

async function sendMessage(text = "long-running question") {
  const textarea = screen.getByPlaceholderText(/ask me anything/i);
  await userEvent.type(textarea, text);
  await userEvent.keyboard("{Enter}");
}

describe("StreamInterruptedError (class shape)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carries reason and sessionId", () => {
    const err = new StreamInterruptedError("no_done", "sess-1");
    expect(err.reason).toBe("no_done");
    expect(err.sessionId).toBe("sess-1");
    expect(err.name).toBe("StreamInterruptedError");
    expect(err instanceof Error).toBe(true);
    expect(err.message).toBe("Stream interrupted: no_done");
  });

  it("allows a null sessionId", () => {
    expect(new StreamInterruptedError("no_done", null).sessionId).toBeNull();
  });

  it("is distinct from an AbortError", () => {
    const err = new DOMException("user cancelled", "AbortError");
    expect(err instanceof StreamInterruptedError).toBe(false);
  });
});

describe("ChatInterface — stream-death recovery flow", () => {
  beforeEach(() => vi.clearAllMocks());

  test("recovers and renders the persisted answer when the stream dies without [DONE]", async () => {
    mockStream.mockReturnValue(
      dyingStream(new StreamInterruptedError("no_done", "sess-1")) as any,
    );
    // Raw endpoint payload shape: { session_id, events: [...] } — an object,
    // not an array. The answer post-dates the user's turn.
    mockHistory.mockResolvedValue({
      session_id: "sess-1",
      events: [
        {
          content: { role: "user", parts: [{ text: "long-running question" }] },
        },
        {
          content: {
            role: "model",
            parts: [{ text: "The recovered answer." }],
          },
        },
      ],
    } as unknown as never);

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

    await waitFor(() => {
      expect(screen.getByText("The recovered answer.")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Connection interrupted — recovered\./),
    ).toBeInTheDocument();
    // #1: the recovery outcome is announced to assistive tech via the live region.
    expect(screen.getByTestId("recovery-announcer")).toHaveTextContent(
      "Your answer was recovered.",
    );
  });

  test("does not surface a prior turn's answer as recovered (waits instead)", async () => {
    mockStream.mockReturnValue(
      dyingStream(
        new StreamInterruptedError("silence_timeout", "sess-2"),
      ) as any,
    );
    // Current turn's answer not persisted yet — last event is the user message;
    // the only assistant message ("Stale prior answer") pre-dates this turn.
    mockHistory.mockResolvedValue({
      session_id: "sess-2",
      events: [
        { content: { role: "user", parts: [{ text: "Prev question" }] } },
        { content: { role: "model", parts: [{ text: "Stale prior answer" }] } },
        {
          content: { role: "user", parts: [{ text: "long-running question" }] },
        },
      ],
    } as unknown as never);

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

    // #1: wait on the live-region announcement (unambiguous; the visible bubble
    // carries near-identical "waiting…" copy, so a text query would match both).
    await waitFor(() => {
      expect(screen.getByTestId("recovery-announcer")).toHaveTextContent(
        "Waiting for the agent to finish",
      );
    });
    // The waiting copy is also shown in the assistant bubble.
    expect(
      screen.getByText(/Connection interrupted — waiting/i),
    ).toBeInTheDocument();
    // The stale prior answer must never be shown as the recovered result.
    expect(screen.queryByText("Stale prior answer")).not.toBeInTheDocument();
    expect(screen.queryByText(/— recovered\./)).not.toBeInTheDocument();
  });

  test("a null sessionId surfaces a generic error, not the recovery flow", async () => {
    mockStream.mockReturnValue(
      dyingStream(new StreamInterruptedError("no_done", null)) as any,
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

    await waitFor(() => {
      expect(
        screen.getByText(/An error occurred\. Please try again\./),
      ).toBeInTheDocument();
    });
    expect(mockHistory).not.toHaveBeenCalled();
  });

  test("#4: a pending_ placeholder sessionId surfaces a generic error, never polls", async () => {
    mockStream.mockReturnValue(
      dyingStream(
        new StreamInterruptedError("no_done", "pending_abc123"),
      ) as any,
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

    await waitFor(() => {
      expect(
        screen.getByText(/An error occurred\. Please try again\./),
      ).toBeInTheDocument();
    });
    // A pending_ session does not exist server-side — recovery must not fetch it.
    expect(mockHistory).not.toHaveBeenCalled();
  });

  test("#1: a stale recovery refetch is dropped once a new turn has started", async () => {
    const histDeferred = deferred<unknown>();
    // Turn 1 dies → recovery's immediate refetch awaits this controllable fetch.
    mockHistory.mockReturnValueOnce(histDeferred.promise as never);
    mockStream
      .mockReturnValueOnce(
        dyingStream(new StreamInterruptedError("no_done", "sess-1")) as any,
      )
      // Turn 2 streams a clean answer.
      .mockReturnValueOnce(textStream("New turn answer") as any);

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
    await sendMessage("first question");
    // Recovery is now blocked on the in-flight history fetch.
    await waitFor(() => expect(mockHistory).toHaveBeenCalledTimes(1));

    // User starts a new turn while turn 1's recovery fetch is still pending.
    await sendMessage("second question");
    await waitFor(() =>
      expect(screen.getByText("New turn answer")).toBeInTheDocument(),
    );

    // Now turn 1's refetch resolves with a (stale) answer for the first turn.
    histDeferred.resolve({
      session_id: "sess-1",
      events: [
        { content: { role: "user", parts: [{ text: "first question" }] } },
        {
          content: {
            role: "model",
            parts: [{ text: "STALE recovered answer" }],
          },
        },
      ],
    });
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(2));

    // The stale result must be dropped (turnSeq advanced) — never written into
    // the new turn. The new turn's answer remains intact.
    expect(
      screen.queryByText("STALE recovered answer"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("New turn answer")).toBeInTheDocument();
  });
});
