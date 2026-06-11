/**
 * Unit tests for streamChatCompletion's error-event SSE parser (CH-79).
 *
 * Covers:
 * - AC1: error frame before DONE yields { type: "error", message } and the
 *   generator completes cleanly (no StreamInterruptedError thrown).
 * - AC2: malformed error payload (non-JSON) is silently dropped; generator
 *   completes cleanly.
 * - AC3 (back-compat): a pre-CH-79 stream (text + DONE) continues to produce
 *   only { type: "text" } events — no regressions.
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
// Mock firebase auth so we can drive the generator with fake streams
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

describe("streamChatCompletion — error event parser (CH-79)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  test("AC1: error frame before DONE yields { type: 'error', message } and completes without throwing", async () => {
    // AC maps to: CH-79 §7 AC-1 — server-side error frame surfaced to consumer.
    // The generator must yield exactly one error event and then return cleanly
    // (not throw StreamInterruptedError, which would trigger the recovery flow).
    const events = await driveStream(
      'event: error\ndata: {"message":"foo"}\n\ndata: [DONE]\n\n',
    );

    expect(events).toEqual([{ type: "error", message: "foo" }]);
  });

  test("AC2: malformed error payload (non-JSON) is silently dropped; generator completes", async () => {
    // AC maps to: CH-79 §7 AC-2 — robustness against a broken error payload.
    // No events should be yielded and the generator must not throw.
    const events = await driveStream(
      "event: error\ndata: not-json\n\ndata: [DONE]\n\n",
    );

    expect(events).toEqual([]);
  });

  test("AC3 (back-compat): pre-CH-79 stream (text + DONE) produces only text events", async () => {
    // AC maps to: CH-79 §7 AC-3 — no regression for streams that predate this feature.
    const events = await driveStream("data: Hello world\n\ndata: [DONE]\n\n");

    expect(events).toEqual([
      { type: "text", text: "Hello world", author: "model" },
    ]);
    expect(events.some((e) => e.type === "error")).toBe(false);
  });
});
