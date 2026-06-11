import { describe, it, expect } from "vitest";
import {
  parseConversationHistory,
  extractAnswerAfterLastUserMessage,
} from "./parseConversationHistory";

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

  const _chart = {
    type: "visualization",
    spec: { mark: "line", title: "Sessions" },
    metadata: {
      chart_type_suggestion: "line",
      title: "Sessions",
      data_source: "agent",
    },
  };

  it("attaches re-served charts to the assistant message as chartArtifacts", () => {
    const [msg] = parseConversationHistory({
      events: [
        {
          content: { role: "model", parts: [{ text: "here is your chart" }] },
          artifacts: [_chart],
        },
      ],
    });
    expect(msg.chartArtifacts).toEqual([_chart]);
  });

  it("keeps a chart-only turn even when its text is empty", () => {
    const result = parseConversationHistory({
      events: [{ content: {}, artifacts: [_chart] }],
    });
    expect(result).toHaveLength(1);
    expect(result[0].chartArtifacts).toEqual([_chart]);
  });

  it("omits chartArtifacts when no artifacts are present", () => {
    const [msg] = parseConversationHistory({
      events: [{ content: { parts: [{ text: "no charts" }] } }],
    });
    expect(msg.chartArtifacts).toBeUndefined();
  });

  it("restores reasoning thoughts so the thinking block re-renders", () => {
    const [msg] = parseConversationHistory({
      events: [
        {
          content: { role: "model", parts: [{ text: "the answer" }] },
          reasoning: { thoughts: ["step one", "step two"], durationSeconds: 4 },
        },
      ],
    });
    expect(msg.reasoning).toEqual({
      thoughts: ["step one", "step two"],
      durationSeconds: 4,
    });
  });

  it("omits reasoning when none is present", () => {
    const [msg] = parseConversationHistory({
      events: [{ content: { parts: [{ text: "no thoughts" }] } }],
    });
    expect(msg.reasoning).toBeUndefined();
  });
});

describe("extractAnswerAfterLastUserMessage (CH-71 recovery)", () => {
  it("returns the assistant answer that follows the last user message", () => {
    const answer = extractAnswerAfterLastUserMessage({
      events: [
        { content: { role: "user", parts: [{ text: "Q1" }] } },
        { content: { role: "model", parts: [{ text: "A1" }] } },
        { content: { role: "user", parts: [{ text: "Q2" }] } },
        { content: { role: "model", parts: [{ text: "A2" }] } },
      ],
    });
    expect(answer).toBe("A2");
  });

  it("returns null when the current turn has no answer yet (last message is the user's)", () => {
    // The prior turn's answer (A1) must NOT be returned — it pre-dates the
    // current user turn (Q2). This is the stale-answer guard.
    const answer = extractAnswerAfterLastUserMessage({
      events: [
        { content: { role: "user", parts: [{ text: "Q1" }] } },
        { content: { role: "model", parts: [{ text: "A1" }] } },
        { content: { role: "user", parts: [{ text: "Q2" }] } },
      ],
    });
    expect(answer).toBeNull();
  });

  it("returns the answer for a first turn with no prior history", () => {
    const answer = extractAnswerAfterLastUserMessage({
      events: [
        { content: { role: "user", parts: [{ text: "Only question" }] } },
        { content: { role: "model", parts: [{ text: "Only answer" }] } },
      ],
    });
    expect(answer).toBe("Only answer");
  });

  it("does not throw on the raw { session_id, events } dict (the shape that broke the old cast)", () => {
    // Regression: the endpoint returns an object, not an array. The previous
    // recovery code did (raw as []).slice() and threw TypeError on this.
    expect(() =>
      extractAnswerAfterLastUserMessage({ session_id: "s", events: [] }),
    ).not.toThrow();
    expect(
      extractAnswerAfterLastUserMessage({ session_id: "s", events: [] }),
    ).toBeNull();
  });

  it("returns null for empty / malformed payloads", () => {
    expect(extractAnswerAfterLastUserMessage(null)).toBeNull();
    expect(extractAnswerAfterLastUserMessage(undefined)).toBeNull();
    expect(extractAnswerAfterLastUserMessage({})).toBeNull();
    expect(extractAnswerAfterLastUserMessage([])).toBeNull();
  });
});
