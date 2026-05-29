/**
 * Unit tests for streamChatCompletion's discriminated-union SSE parser.
 *
 * We test the parser logic by constructing ReadableStream byte sequences
 * that represent different SSE wire formats and asserting the correct
 * StreamEvent objects are yielded.
 *
 * References: CH-60 Implementation Plan Task 3.
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

/** Drive streamChatCompletion with a pre-built ReadableStream body. */
async function driveStream(raw: string): Promise<StreamEvent[]> {
  // We import inside the test so the vi.mock above is already in place.
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

describe("streamChatCompletion — SSE parser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the module registry so each test gets a clean import.
    vi.resetModules();
  });

  test("plain data line yields text event", async () => {
    const events = await driveStream("data: hello\n\ndata: [DONE]\n\n");
    expect(events).toEqual([{ type: "text", text: "hello" }]);
  });

  test("event: reasoning + data yields reasoning event", async () => {
    const payload = JSON.stringify({ text: "step 1", seq: 0 });
    const events = await driveStream(
      `event: reasoning\ndata: ${payload}\n\ndata: [DONE]\n\n`,
    );
    expect(events).toEqual([{ type: "reasoning", text: "step 1" }]);
  });

  test("unknown event type is silently dropped", async () => {
    const events = await driveStream(
      "event: unknown\ndata: x\n\ndata: answer\n\ndata: [DONE]\n\n",
    );
    // Only the default "answer" text line should survive; unknown event dropped.
    expect(events).toEqual([{ type: "text", text: "answer" }]);
  });

  test("malformed reasoning JSON is silently dropped (no throw)", async () => {
    const events = await driveStream(
      "event: reasoning\ndata: NOT_JSON\n\ndata: [DONE]\n\n",
    );
    expect(events).toEqual([]);
  });

  test("[DONE] terminates the stream", async () => {
    const events = await driveStream(
      "data: before\n\ndata: [DONE]\n\ndata: after\n\n",
    );
    // "after" should not appear — generator returned on [DONE]
    expect(events).toEqual([{ type: "text", text: "before" }]);
  });

  test("interleaved text and reasoning events in order", async () => {
    const r0 = JSON.stringify({ text: "thinking…", seq: 0 });
    const r1 = JSON.stringify({ text: "more thoughts", seq: 1 });
    const raw =
      `data: Hi. \n\n` +
      `event: reasoning\ndata: ${r0}\n\n` +
      `data: Let me \n\n` +
      `event: reasoning\ndata: ${r1}\n\n` +
      `data: answer.\n\n` +
      `data: [DONE]\n\n`;

    const events = await driveStream(raw);

    expect(events).toEqual([
      { type: "text", text: "Hi. " },
      { type: "reasoning", text: "thinking…" },
      { type: "text", text: "Let me " },
      { type: "reasoning", text: "more thoughts" },
      { type: "text", text: "answer." },
    ]);
  });

  test("event type resets to default after each blank-line boundary", async () => {
    const r0 = JSON.stringify({ text: "reason", seq: 0 });
    // After reasoning event, next data line should be text (no lingering "reasoning" type)
    const raw =
      `event: reasoning\ndata: ${r0}\n\n` +
      `data: plain text\n\n` +
      `data: [DONE]\n\n`;

    const events = await driveStream(raw);
    expect(events).toEqual([
      { type: "reasoning", text: "reason" },
      { type: "text", text: "plain text" },
    ]);
  });

  test("multi-line text event joins data lines with newlines (SSE §9.2.6)", async () => {
    // The backend splits a multi-line text fragment into one `data:` line per
    // line; the client must rejoin them with "\n" so embedded newlines survive.
    const events = await driveStream(
      "data: line one\ndata: line two\n\ndata: [DONE]\n\n",
    );
    expect(events).toEqual([{ type: "text", text: "line one\nline two" }]);
  });

  test("blank data lines round-trip a paragraph break", async () => {
    // A pure "\n\n" fragment is emitted as three empty `data:` lines and must
    // reconstruct as "\n\n", not collapse to nothing.
    const events = await driveStream(
      "data: para one\ndata: \ndata: para two\n\ndata: [DONE]\n\n",
    );
    expect(events).toEqual([{ type: "text", text: "para one\n\npara two" }]);
  });

  test("multi-line text split across reads still joins correctly", async () => {
    // The two `data:` lines of one event arrive in separate stream reads; the
    // event boundary (blank line) is what dispatches, so they must still join.
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("data: first\n"));
        controller.enqueue(encoder.encode("data: second\n\n"));
        controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        controller.close();
      },
    });
    const { streamChatCompletion } = await import("../chatApi");
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: stream,
    } as unknown as Response);

    const events = await collectEvents(
      streamChatCompletion([{ role: "user", content: "hi" }]),
    );
    expect(events).toEqual([{ type: "text", text: "first\nsecond" }]);
  });
});
