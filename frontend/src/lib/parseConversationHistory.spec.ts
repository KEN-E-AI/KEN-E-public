import { describe, it, expect } from "vitest";
import { parseConversationHistory } from "./parseConversationHistory";

describe("parseConversationHistory", () => {
  it("returns [] for null, undefined, and payloads without messages/events", () => {
    expect(parseConversationHistory(null)).toEqual([]);
    expect(parseConversationHistory(undefined)).toEqual([]);
    expect(parseConversationHistory({})).toEqual([]);
    expect(parseConversationHistory("garbage")).toEqual([]);
  });

  it("maps the ADK part-list content shape and reads role from content", () => {
    const result = parseConversationHistory({
      events: [
        {
          content: { role: "user", parts: [{ text: "hello" }] },
          timestamp: "2026-05-28T10:00:00.000Z",
        },
        {
          content: { role: "model", parts: [{ text: "hi there" }] },
          timestamp: "2026-05-28T10:00:01.000Z",
        },
      ],
    });

    expect(result).toEqual([
      {
        id: "hist-0",
        role: "user",
        content: "hello",
        timestamp: new Date("2026-05-28T10:00:00.000Z"),
      },
      {
        id: "hist-1",
        role: "assistant",
        content: "hi there",
        timestamp: new Date("2026-05-28T10:00:01.000Z"),
      },
    ]);
  });

  it("falls back to parts[0].content when text is absent", () => {
    const [msg] = parseConversationHistory({
      events: [{ content: { parts: [{ content: "from-content" }] } }],
    });
    expect(msg.content).toBe("from-content");
  });

  it("maps a plain-string content shape using the top-level role", () => {
    const [msg] = parseConversationHistory({
      events: [{ content: "plain text", role: "user" }],
    });
    expect(msg).toMatchObject({ role: "user", content: "plain text" });
  });

  it("maps the nested { text } content shape", () => {
    const [msg] = parseConversationHistory({
      events: [{ content: { text: "nested text" } }],
    });
    expect(msg.content).toBe("nested text");
  });

  it("reads from the `messages` key when `events` is absent", () => {
    const result = parseConversationHistory({
      messages: [{ content: "via messages", role: "assistant" }],
    });
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe("via messages");
  });

  it("filters out entries that resolve to an empty message", () => {
    const result = parseConversationHistory({
      events: [
        { content: { parts: [{ text: "keep" }] } },
        { content: {} },
        { content: { parts: [] } },
      ],
    });
    expect(result.map((m) => m.content)).toEqual(["keep"]);
  });

  it("defaults role to assistant and timestamp to a Date when missing", () => {
    const [msg] = parseConversationHistory({
      events: [{ content: "no role no time" }],
    });
    expect(msg.role).toBe("assistant");
    expect(msg.timestamp).toBeInstanceOf(Date);
  });
});
