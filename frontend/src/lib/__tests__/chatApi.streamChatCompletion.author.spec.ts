/**
 * Unit tests for streamChatCompletion's author-tracking SSE parser.
 *
 * The backend emits `event: author\ndata: <name>\n\n` immediately before a
 * text frame when the author changes. These tests verify:
 *   - Default author "model" is attached to all text events when no sidecar is present.
 *   - Author sidecar correctly updates currentAuthor for subsequent events.
 *   - Author persists across multiple frames until the next sidecar.
 *   - Switching authors via a second sidecar works correctly.
 *   - Reasoning events use the author from the JSON payload when present.
 *   - Reasoning events fall back to currentAuthor when JSON has no author key.
 *   - Empty/whitespace-only author sidecars are treated as no-ops.
 *   - Session events are unaffected by author tracking.
 *
 * References: AH-124 Task 3.
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import type { StreamEvent } from "../chatApi";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a ReadableStream from a raw SSE string. */
function sseStream(raw: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(raw));
      controller.close();
    },
  });
}

/** Collect all StreamEvents from the generator into an array. */
async function collectEvents(
  gen: AsyncGenerator<StreamEvent>,
): Promise<StreamEvent[]> {
  const results: StreamEvent[] = [];
  for await (const ev of gen) {
    results.push(ev);
  }
  return results;
}

// ---------------------------------------------------------------------------
// Mock firebase auth and fetch so we can drive the generator with fake streams
// ---------------------------------------------------------------------------

vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: { getIdToken: async () => "fake-token" },
  },
}));

/** Drive streamChatCompletion with a pre-built SSE string. */
async function driveStream(raw: string): Promise<StreamEvent[]> {
  const { streamChatCompletion } = await import("../chatApi");

  const stream = sseStream(raw);

  vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: true,
    status: 200,
    body: stream,
  } as unknown as Response);

  const gen = streamChatCompletion([{ role: "user", content: "hi" }]);
  return collectEvents(gen);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("streamChatCompletion — author tracking", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  test("single author stream has author model on all text events", async () => {
    const events = await driveStream(
      "data: hello\n\ndata: world\n\ndata: [DONE]\n\n",
    );
    expect(events).toEqual([
      { type: "text", text: "hello", author: "model" },
      { type: "text", text: "world", author: "model" },
    ]);
  });

  test("author sidecar updates currentAuthor for subsequent text events", async () => {
    const events = await driveStream(
      "event: author\ndata: specialist_a\n\ndata: hello\n\ndata: [DONE]\n\n",
    );
    expect(events).toEqual([
      { type: "text", text: "hello", author: "specialist_a" },
    ]);
  });

  test("author persists across multiple frames", async () => {
    const events = await driveStream(
      "event: author\ndata: specialist_a\n\n" +
        "data: frame one\n\n" +
        "data: frame two\n\n" +
        "data: frame three\n\n" +
        "data: [DONE]\n\n",
    );
    expect(events).toEqual([
      { type: "text", text: "frame one", author: "specialist_a" },
      { type: "text", text: "frame two", author: "specialist_a" },
      { type: "text", text: "frame three", author: "specialist_a" },
    ]);
  });

  test("author switches back on second sidecar", async () => {
    const events = await driveStream(
      "event: author\ndata: specialist_a\n\n" +
        "data: from a\n\n" +
        "event: author\ndata: specialist_b\n\n" +
        "data: from b\n\n" +
        "data: [DONE]\n\n",
    );
    expect(events).toEqual([
      { type: "text", text: "from a", author: "specialist_a" },
      { type: "text", text: "from b", author: "specialist_b" },
    ]);
  });

  test("reasoning event uses author from JSON payload", async () => {
    const payload = JSON.stringify({
      text: "thinking",
      seq: 0,
      author: "specialist_a",
    });
    const events = await driveStream(
      `event: reasoning\ndata: ${payload}\n\ndata: [DONE]\n\n`,
    );
    expect(events).toEqual([
      { type: "reasoning", text: "thinking", author: "specialist_a" },
    ]);
  });

  test("reasoning without author field uses currentAuthor", async () => {
    const payload = JSON.stringify({ text: "inference step", seq: 0 });
    const events = await driveStream(
      "event: author\ndata: specialist_a\n\n" +
        `event: reasoning\ndata: ${payload}\n\n` +
        "data: [DONE]\n\n",
    );
    expect(events).toEqual([
      { type: "reasoning", text: "inference step", author: "specialist_a" },
    ]);
  });

  test("empty or whitespace-only author sidecar is no-op", async () => {
    const events = await driveStream(
      "event: author\ndata: \n\n" + "data: plain\n\n" + "data: [DONE]\n\n",
    );
    // Author should remain "model" since the sidecar payload was whitespace-only.
    expect(events).toEqual([{ type: "text", text: "plain", author: "model" }]);
  });

  test("session events are unaffected by author tracking", async () => {
    const sessionPayload = JSON.stringify({ session_id: "real_42" });
    const events = await driveStream(
      "event: author\ndata: specialist_a\n\n" +
        `event: session\ndata: ${sessionPayload}\n\n` +
        "data: answer\n\n" +
        "data: [DONE]\n\n",
    );
    expect(events).toEqual([
      { type: "session", sessionId: "real_42" },
      { type: "text", text: "answer", author: "specialist_a" },
    ]);
    // session event must NOT have an author field
    const sessionEvent = events[0];
    expect("author" in sessionEvent).toBe(false);
  });
});
