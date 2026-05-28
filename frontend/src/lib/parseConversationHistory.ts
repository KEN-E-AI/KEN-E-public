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
