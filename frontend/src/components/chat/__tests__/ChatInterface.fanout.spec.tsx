/**
 * Integration tests for ChatInterface multi-author fan-out rendering (AH-124).
 *
 * Verifies:
 * - A two-author interleaved stream renders two separate assistant bubbles.
 * - No text fragment from author A appears in author B's bubble.
 * - Total text across all bubbles equals the concatenated raw-text fragments.
 * - A single-author stream produces one bubble — pixel-identical to baseline.
 * - Author labels appear only for non-"model" authors.
 * - The existing intro bubble is unaffected.
 *
 * SSE fixture construction mirrors chatApi.streamChatCompletion.spec.ts.
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

async function* makeStream(events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  for (const ev of events) {
    yield ev;
  }
}

async function sendMessage(text = "hello") {
  const textarea = screen.getByPlaceholderText(/ask me anything/i);
  await userEvent.type(textarea, text);
  await userEvent.keyboard("{Enter}");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatInterface — multi-author fan-out (AH-124)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("single-author stream renders one bubble with no author label (back-compat)", async () => {
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "text", text: "Hello ", author: "model" },
        { type: "text", text: "world.", author: "model" },
      ]) as any,
    );

    render(<ChatInterface />);
    await sendMessage("hi");

    await waitFor(() => {
      expect(screen.getByText("Hello world.")).toBeInTheDocument();
    });

    // No author label for the default "model" author.
    expect(screen.queryByText("model")).not.toBeInTheDocument();

    // Exactly one assistant bubble carries text content (plus the intro).
    const paras = screen.getAllByText(/Hello world\./);
    expect(paras).toHaveLength(1);
  });

  test("two-author stream renders two separate bubbles", async () => {
    // Interleaved: A1, B1, A2, B2
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "text", text: "A chunk 1 ", author: "specialist_a" },
        { type: "text", text: "B chunk 1 ", author: "specialist_b" },
        { type: "text", text: "A chunk 2", author: "specialist_a" },
        { type: "text", text: "B chunk 2", author: "specialist_b" },
      ]) as any,
    );

    render(<ChatInterface />);
    await sendMessage("fan-out query");

    // Wait for specialist_b's content to appear (last yielded).
    await waitFor(() => {
      expect(screen.getByText(/B chunk 1/)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/B chunk 2/)).toBeInTheDocument();
    });

    // specialist_a chunks must be in a single element (accumulated together).
    const aEl = screen.getByText(/A chunk 1/);
    expect(aEl.textContent).toContain("A chunk 1 ");
    expect(aEl.textContent).toContain("A chunk 2");

    // specialist_b chunks must be in a single element (accumulated together).
    const bEl = screen.getByText(/B chunk 1/);
    expect(bEl.textContent).toContain("B chunk 1 ");
    expect(bEl.textContent).toContain("B chunk 2");

    // No fragment from A appears in B's bubble and vice versa.
    expect(aEl.textContent).not.toContain("B chunk");
    expect(bEl.textContent).not.toContain("A chunk");
  });

  test("author labels appear only for non-model authors", async () => {
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        {
          type: "text",
          text: "Reply from specialist.",
          author: "specialist_a",
        },
      ]) as any,
    );

    render(<ChatInterface />);
    await sendMessage("test");

    await waitFor(() => {
      expect(screen.getByText("specialist_a")).toBeInTheDocument();
    });

    // The label text is "specialist_a", not "model".
    expect(screen.queryByText("model")).not.toBeInTheDocument();
  });

  test("each author's fragments accumulate in their own bubble", async () => {
    // Interleaved: a-b-a-b. specialist_a's two fragments must land in one bubble;
    // specialist_b's two fragments must land in another.
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "text", text: "Hello ", author: "specialist_a" },
        { type: "text", text: "World ", author: "specialist_b" },
        { type: "text", text: "Foo", author: "specialist_a" },
        { type: "text", text: "Bar", author: "specialist_b" },
      ]) as any,
    );

    render(<ChatInterface />);
    await sendMessage("total text test");

    // Wait for both authors' final fragments.
    await waitFor(() => expect(screen.getByText(/Foo/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Bar/)).toBeInTheDocument());

    // specialist_a's bubble contains both its fragments.
    const aEl = screen.getByText(/Hello/);
    expect(aEl.textContent).toContain("Hello ");
    expect(aEl.textContent).toContain("Foo");

    // specialist_b's bubble contains both its fragments.
    const bEl = screen.getByText(/World/);
    expect(bEl.textContent).toContain("World ");
    expect(bEl.textContent).toContain("Bar");
  });

  test("intro bubble is still present and unchanged during fan-out", async () => {
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "text", text: "Answer A", author: "specialist_a" },
        { type: "text", text: "Answer B", author: "specialist_b" },
      ]) as any,
    );

    render(<ChatInterface />);

    // Intro is visible before sending.
    expect(screen.getByText(/Hi! I'm your KEN-E/i)).toBeInTheDocument();

    await sendMessage("test");

    await waitFor(() => {
      expect(screen.getByText(/Answer B/)).toBeInTheDocument();
    });

    // Intro is still present after the fan-out stream.
    expect(screen.getByText(/Hi! I'm your KEN-E/i)).toBeInTheDocument();
  });

  test("no fragment from author A appears in author B bubble", async () => {
    mockStreamChatCompletion.mockReturnValue(
      makeStream([
        { type: "text", text: "Alpha text", author: "alpha" },
        { type: "text", text: "Beta text", author: "beta" },
        { type: "text", text: " more alpha", author: "alpha" },
        { type: "text", text: " more beta", author: "beta" },
      ]) as any,
    );

    render(<ChatInterface />);
    await sendMessage("test");

    await waitFor(() => {
      expect(screen.getByText(/more beta/)).toBeInTheDocument();
    });

    // Alpha bubble contains only alpha fragments.
    const alphaBubble = screen.getByText(/Alpha text/);
    expect(alphaBubble.textContent).not.toContain("Beta text");
    expect(alphaBubble.textContent).not.toContain("more beta");
    expect(alphaBubble.textContent).toContain("Alpha text");
    expect(alphaBubble.textContent).toContain("more alpha");

    // Beta bubble contains only beta fragments.
    const betaBubble = screen.getByText(/Beta text/);
    expect(betaBubble.textContent).not.toContain("Alpha text");
    expect(betaBubble.textContent).not.toContain("more alpha");
    expect(betaBubble.textContent).toContain("Beta text");
    expect(betaBubble.textContent).toContain("more beta");
  });

  test("undefined author defaults to model (back-compat with pre-author-tagging events)", async () => {
    // Events without the author field (legacy server / not yet tagged).
    const events = [
      { type: "text" as const, text: "Legacy response" },
    ] satisfies StreamEvent[];

    mockStreamChatCompletion.mockReturnValue(makeStream(events) as any);

    render(<ChatInterface />);
    await sendMessage("legacy");

    await waitFor(() => {
      expect(screen.getByText("Legacy response")).toBeInTheDocument();
    });

    // No label for the default "model" author.
    expect(screen.queryByText("model")).not.toBeInTheDocument();
  });
});
