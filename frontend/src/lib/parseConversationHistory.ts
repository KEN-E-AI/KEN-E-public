import type { Artifact } from "./chatApi";

export type ParsedHistoryMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  chartArtifacts?: Artifact[];
  reasoning?: { thoughts: string[]; durationSeconds: number };
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
 *
 * An assistant event may also carry an `artifacts` array of persisted Vega-Lite
 * charts (re-attached server-side from GCS). These become `chartArtifacts` so a
 * reloaded conversation renders the same inline charts that streamed live.
 */
export function parseConversationHistory(raw: unknown): ParsedHistoryMessage[] {
  const history = raw as HistoryPayload;
  if (!history || (!history.messages && !history.events)) return [];

  const events = history.events || history.messages || [];

  return (
    events
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

        const chartArtifacts: Artifact[] | undefined = Array.isArray(
          event?.artifacts,
        )
          ? (event.artifacts as Artifact[])
          : undefined;

        const thoughts: string[] | undefined = Array.isArray(
          event?.reasoning?.thoughts,
        )
          ? event.reasoning.thoughts
          : undefined;

        const message: ParsedHistoryMessage = {
          id: `hist-${index}`,
          role: role === "user" ? ("user" as const) : ("assistant" as const),
          content,
          timestamp: new Date(event?.timestamp || Date.now()),
        };
        if (chartArtifacts && chartArtifacts.length > 0) {
          message.chartArtifacts = chartArtifacts;
        }
        if (thoughts && thoughts.length > 0) {
          message.reasoning = {
            thoughts,
            durationSeconds: Number(event?.reasoning?.durationSeconds) || 0,
          };
        }
        return message;
      })
      // Keep a message if it has rendered text OR carries charts — a chart-only
      // turn (empty text) must not be dropped.
      .filter(
        (msg) =>
          msg.content !== EMPTY ||
          (msg.chartArtifacts !== undefined && msg.chartArtifacts.length > 0),
      )
  );
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
