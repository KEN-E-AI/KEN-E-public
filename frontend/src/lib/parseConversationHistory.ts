export type ParsedHistoryMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
};

type HistoryPayload = {
  messages?: unknown[];
  events?: unknown[];
} | null;

const EMPTY = "Empty message";

/**
 * Maps the untyped `GET /conversations/{id}/history` payload into display
 * messages. The backend returns either an `events` or a `messages` array, and
 * each entry's content takes one of three shapes (ADK part list, plain string,
 * or a `{ text }` object) — all handled here.
 */
export function parseConversationHistory(raw: unknown): ParsedHistoryMessage[] {
  const history = raw as HistoryPayload;
  if (!history || (!history.messages && !history.events)) return [];

  const events = history.events || history.messages || [];

  return events
    .map((event: any, index: number) => {
      let content = EMPTY;
      let role = "assistant";

      if (event?.content?.parts?.length > 0) {
        content =
          event.content.parts[0].text ||
          event.content.parts[0].content ||
          EMPTY;
        role = event.content.role || event.role || "assistant";
      } else if (typeof event?.content === "string") {
        content = event.content || EMPTY;
        role = event.role || "assistant";
      } else if (event?.content) {
        content = String(event.content.text || EMPTY);
        role = event.role || "assistant";
      }

      return {
        id: `hist-${index}`,
        role: role === "user" ? ("user" as const) : ("assistant" as const),
        content,
        timestamp: new Date(event?.timestamp || Date.now()),
      };
    })
    .filter((msg) => msg.content !== EMPTY);
}

/**
 * Stream-death recovery (CH-71): from the raw `GET .../history` payload, return
 * the answer that belongs to the just-interrupted turn — the last assistant
 * message that appears *after* the final user message in persisted history.
 *
 * Returns `null` when the engine has not yet persisted an answer for the current
 * turn (so the caller keeps polling). The "after the last user message" gate is
 * what prevents a *prior* turn's answer being shown as the recovered result when
 * the current turn's answer has not landed yet. Timestamps aren't used because
 * the ADK event timestamp (epoch seconds) is not reliably comparable to the
 * client clock here.
 */
export function extractAnswerAfterLastUserMessage(raw: unknown): string | null {
  const parsed = parseConversationHistory(raw);
  let lastUserIdx = -1;
  for (let i = parsed.length - 1; i >= 0; i--) {
    if (parsed[i].role === "user") {
      lastUserIdx = i;
      break;
    }
  }
  for (let i = parsed.length - 1; i > lastUserIdx; i--) {
    if (parsed[i].role === "assistant") return parsed[i].content;
  }
  return null;
}
