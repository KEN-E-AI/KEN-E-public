import { describe, it, expect, vi, beforeEach } from "vitest";
import type { StreamEvent } from "@/lib/chatApi";

vi.mock("@/lib/firebase", () => ({
  auth: { currentUser: { getIdToken: async () => "test-token" } },
}));

function makeStream(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
}

function makeFetch(body: ReadableStream<Uint8Array>): typeof globalThis.fetch {
  return vi.fn().mockResolvedValue({
    ok: true,
    body,
    status: 200,
    statusText: "OK",
  });
}

async function driveStream(frames: string[]): Promise<StreamEvent[]> {
  const { streamChatCompletion } = await import("@/lib/chatApi");
  globalThis.fetch = makeFetch(makeStream(frames));
  const events: StreamEvent[] = [];
  for await (const e of streamChatCompletion([
    { role: "user", content: "hi" },
  ])) {
    events.push(e);
  }
  return events;
}

describe("streamChatCompletion status events", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("yields status event from event: status frame", async () => {
    const events = await driveStream([
      'event: status\ndata: {"label":"Creating visualization…","seq":0}\n\n',
      "data: [DONE]\n\n",
    ]);

    const statusEvent = events.find((e) => e.type === "status");
    expect(statusEvent).toBeDefined();
    expect((statusEvent as { type: "status"; label: string }).label).toBe(
      "Creating visualization…",
    );
  });

  it("yields status event with author when non-model", async () => {
    const events = await driveStream([
      'event: status\ndata: {"label":"Running GA report…","seq":0,"author":"ga_specialist"}\n\n',
      "data: [DONE]\n\n",
    ]);

    const statusEvent = events.find((e) => e.type === "status") as {
      type: "status";
      label: string;
      author?: string;
    };
    expect(statusEvent?.author).toBe("ga_specialist");
  });

  it("drops malformed status JSON silently", async () => {
    const events = await driveStream([
      "event: status\ndata: not-json\n\n",
      "data: [DONE]\n\n",
    ]);

    expect(events.filter((e) => e.type === "status")).toHaveLength(0);
  });

  it("heartbeat ping frames do not produce events", async () => {
    const events = await driveStream([
      ": ping 12345\n\n",
      "data: Hello\n\n",
      "data: [DONE]\n\n",
    ]);

    expect(events.filter((e) => e.type === "text")).toHaveLength(1);
    expect(events.length).toBe(1);
  });

  it("clean stream end (with [DONE]) does not throw", async () => {
    await expect(async () => {
      await driveStream(["data: Answer\n\n", "data: [DONE]\n\n"]);
    }).not.toThrow();
  });

  it("stream end without [DONE] throws StreamInterruptedError(no_done)", async () => {
    const { StreamInterruptedError } = await import("@/lib/chatApi");
    const { streamChatCompletion } = await import("@/lib/chatApi");
    globalThis.fetch = makeFetch(makeStream(["data: Partial answer\n\n"]));

    await expect(async () => {
      for await (const _ of streamChatCompletion([
        { role: "user", content: "hi" },
      ])) {
        // consume
      }
    }).rejects.toBeInstanceOf(StreamInterruptedError);
  });
});
