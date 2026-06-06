import axios from "axios";
import type { Brand, AccountId } from "@/lib/branded-types";
import api from "@/lib/api";
import { auth } from "@/lib/firebase";

// ─── Branded types ────────────────────────────────────────────────────────────

export type ChatSessionId = Brand<string, "ChatSessionId">;
export type ChatArtifactId = Brand<string, "ChatArtifactId">;

export const isChatSessionId = (value: string): value is ChatSessionId =>
  value.length > 0;

export const toChatSessionId = (value: string): ChatSessionId => {
  if (!isChatSessionId(value)) {
    throw new Error(`Invalid ChatSessionId: ${value}`);
  }
  return value as ChatSessionId;
};

export const tryChatSessionId = (value: string): ChatSessionId | undefined =>
  isChatSessionId(value) ? (value as ChatSessionId) : undefined;

// Sentinel for optimistic placeholder rows created by useCreateChatSession.
// The colon deliberately violates Chat.tsx's SESSION_ID_RE so a click that
// races onSuccess cannot produce a routable `/chat?session=optimistic:...`
// URL — the page treats the param as invalid and falls back to "no session".
export const OPTIMISTIC_SESSION_ID_PREFIX = "optimistic:" as const;

export const isOptimisticSessionId = (id: string): boolean =>
  id.startsWith(OPTIMISTIC_SESSION_ID_PREFIX);

// Server-issued placeholder id returned by POST /conversations while the real
// ADK session is created in the background (~3.8s). A pending_ id is valid only
// for the single /completions call that resolves it to the real id; it is never
// persisted to the chat_sessions side-table, so any other endpoint keyed on it
// (mark-read, etc.) 404s until resolution. Callers must skip those requests for
// pending ids. See chat.py resolve_pending_session + useActiveChatSession.
export const PENDING_SESSION_ID_PREFIX = "pending_" as const;

export const isPendingSessionId = (id: string): boolean =>
  id.startsWith(PENDING_SESSION_ID_PREFIX);

export type ChatCategoryId = Brand<string, "ChatCategoryId">;

export const isChatCategoryId = (value: string): value is ChatCategoryId =>
  value.length > 0;

export const toChatCategoryId = (value: string): ChatCategoryId => {
  if (!isChatCategoryId(value)) {
    throw new Error(`Invalid ChatCategoryId: ${value}`);
  }
  return value as ChatCategoryId;
};

export const tryChatCategoryId = (value: string): ChatCategoryId | undefined =>
  isChatCategoryId(value) ? (value as ChatCategoryId) : undefined;

// ─── Legacy wire-protocol types — authoritative definition ───────────────────

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
};

export type ChatRequest = {
  messages: ChatMessage[];
  stream?: boolean;
  session_id?: string;
  account_id?: string;
};

export type ChatResponse = {
  role: "assistant";
  content: string;
  session_id: string;
  metadata?: { requires_reauth?: boolean; service?: string };
};

export type ConversationInfo = {
  session_id: string;
  conversation_name?: string;
  created_at: string;
  last_updated: string;
  message_count: number;
  preview?: string;
};

export type ConversationListResponse = {
  conversations: ConversationInfo[];
  total_count: number;
};

// ─── PRD §4.1 sidebar types ───────────────────────────────────────────────────

export type ChatSessionSidebarItem = {
  session_id: ChatSessionId;
  title: string | null;
  category_id: ChatCategoryId | null;
  category_name: string | null;
  last_message_preview: string | null;
  updated_at: string;
  created_at: string;
  is_agent_running: boolean;
  last_agent_message_at: string | null;
  last_viewed_at: string | null;
};

export type ListChatSessionsRequest = {
  cursor?: string | null;
  category_id?: ChatCategoryId;
  query?: string;
  limit?: number;
  account_id?: AccountId | null;
};

export type ListChatSessionsResponse = {
  items: ChatSessionSidebarItem[];
  next_cursor: string | null;
};

export type MarkReadRequest = {
  session_id: ChatSessionId;
};

// ─── Status derivation (PRD §4.2) ────────────────────────────────────────────

export function deriveSessionStatus(
  item: Pick<
    ChatSessionSidebarItem,
    "is_agent_running" | "last_agent_message_at" | "last_viewed_at"
  >,
): "active" | "needs-review" | "idle" {
  if (item.is_agent_running) return "active";
  if (
    item.last_agent_message_at &&
    (!item.last_viewed_at || item.last_agent_message_at > item.last_viewed_at)
  )
    return "needs-review";
  return "idle";
}

// ─── Todo lists types ────────────────────────────────────────────────────────

export type TodoItemView = {
  item_id: string;
  text: string;
  completed: boolean;
  completed_at: string | null;
};

export type TodoListView = {
  list_id: string;
  title: string;
  is_current: boolean;
  created_at: string;
  items: TodoItemView[];
};

export type ListTodosResponse = {
  todo_lists: TodoListView[];
};

// ─── Artifact types (CH-PRD-05 §4.3) ─────────────────────────────────────────

export type ChatArtifactIndex = {
  artifact_id: ChatArtifactId;
  session_id: ChatSessionId;
  filename: string;
  mime_type: string;
  size_bytes: number;
  version: number;
  gcs_path: string;
  created_by_tool: string | null;
  created_at: string;
};

export type ListArtifactsResponseItem = {
  artifact_index: ChatArtifactIndex;
  signed_url: string;
  signed_url_expires_at: string;
};

export type ListArtifactsResponse = {
  items: ListArtifactsResponseItem[];
};

// ─── Categories types (CH-PRD-03 §4.1) ───────────────────────────────────────

export type ChatCategory = {
  category_id: ChatCategoryId;
  name: string;
  created_at: string;
  updated_at: string;
};

export type DeleteCategoryResponse = {
  sessions_reassigned: number;
};

/**
 * Thrown by createChatCategory when the server returns 409 (casefold dedup
 * conflict). Carries the existing category id so callers can surface it without
 * re-parsing the raw AxiosError response body. `existingCategoryId` is null
 * when the server 409 response does not include a parseable ID.
 */
export class CategoryExistsError extends Error {
  constructor(
    public readonly existingCategoryId: ChatCategoryId | null,
    public readonly attemptedName: string,
  ) {
    super(
      existingCategoryId
        ? `Category "${attemptedName}" already exists as id "${existingCategoryId}"`
        : `Category "${attemptedName}" already exists`,
    );
    this.name = "CategoryExistsError";
  }
}

// ─── API client functions ─────────────────────────────────────────────────────

const CHAT_BASE = "/api/v1/chat";
const COMPLETION_TIMEOUT = 1_800_000; // 30 minutes — matches legacy chatService timeout

/**
 * GET /api/v1/chat/conversations (extended — cursor + filters)
 * Returns the PRD §4.1 paginated shape.
 */
export async function listChatSessions(
  params: ListChatSessionsRequest = {},
): Promise<ListChatSessionsResponse> {
  const query: Record<string, string | number> = {};
  if (params.cursor != null) query["cursor"] = params.cursor;
  if (params.category_id != null) query["category_id"] = params.category_id;
  if (params.query != null) query["query"] = params.query;
  if (params.limit != null) query["limit"] = params.limit;
  if (params.account_id != null) query["account_id"] = params.account_id;
  const { data } = await api.get<ListChatSessionsResponse>(
    `${CHAT_BASE}/conversations`,
    { params: query },
  );
  return data;
}

/**
 * GET /api/v1/chat/conversations (legacy un-paginated shape)
 * Preserved so chatService.getConversations() can delegate here.
 */
export async function listChatConversationsLegacy(): Promise<ConversationListResponse> {
  const { data } = await api.get<ConversationListResponse>(
    `${CHAT_BASE}/conversations`,
  );
  return data;
}

/**
 * POST /api/v1/chat/conversations/{session_id}/mark-read
 *
 * No-ops (returns null) for pending_ placeholder ids: they are not persisted to
 * the side-table, so the request would 404. The hook-level guard normally skips
 * these before we get here; this is belt-and-braces. Returning null lets callers
 * distinguish "skipped" from a real { last_viewed_at } response.
 */
export async function markRead(
  sessionId: ChatSessionId,
): Promise<{ last_viewed_at: string } | null> {
  if (isPendingSessionId(sessionId)) return null;
  const { data } = await api.post<{ last_viewed_at: string }>(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}/mark-read`,
  );
  return data;
}

/**
 * POST /api/v1/chat/conversations
 */
export async function createChatConversation(req: {
  conversation_name?: string;
  account_id?: string;
}): Promise<ConversationInfo> {
  const { data } = await api.post<ConversationInfo>(
    `${CHAT_BASE}/conversations`,
    req,
  );
  return data;
}

/**
 * PUT /api/v1/chat/conversations/{session_id}
 */
export async function updateChatConversation(
  sessionId: string,
  conversationName: string,
): Promise<ConversationInfo> {
  const { data } = await api.put<ConversationInfo>(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}`,
    { conversation_name: conversationName },
  );
  return data;
}

/**
 * DELETE /api/v1/chat/conversations/{session_id}
 */
export async function deleteChatConversation(sessionId: string): Promise<void> {
  await api.delete(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}`,
  );
}

/**
 * GET /api/v1/chat/conversations/{session_id}/history
 */
export async function getConversationHistory(
  sessionId: string,
): Promise<unknown> {
  const { data } = await api.get(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}/history`,
  );
  return data;
}

/**
 * POST /api/v1/chat/completions (non-streaming)
 */
export async function postChatCompletion(
  messages: ChatMessage[],
  sessionId?: string,
  accountId?: string,
): Promise<ChatResponse> {
  const request: ChatRequest = {
    messages,
    stream: false,
    session_id: sessionId,
    account_id: accountId,
  };
  const { data } = await api.post<ChatResponse>(
    `${CHAT_BASE}/completions`,
    request,
    { timeout: COMPLETION_TIMEOUT },
  );
  return data;
}

/**
 * Discriminated-union event emitted by streamChatCompletion.
 * - "text": a fragment of the assistant's answer text.
 * - "reasoning": a fragment of the model's reasoning (thought) text.
 * - "session": a one-time event carrying the real session id when a pending_
 *   placeholder has been resolved server-side (CH-62).
 * Unknown SSE event types are silently dropped.
 */
export type StreamEvent =
  | { type: "text"; text: string; author?: string }
  | { type: "reasoning"; text: string; author?: string }
  | { type: "session"; sessionId: string };

/**
 * POST /api/v1/chat/completions (streaming SSE)
 * Async generator yielding discriminated StreamEvent objects.
 *
 * Wire protocol:
 *   - Answer text:   `data: <text>\n\n`           (default SSE channel)
 *   - Reasoning:     `event: reasoning\n`
 *                    `data: {"text":"...","seq":N}\n\n`
 *   - Stream end:    `data: [DONE]\n\n`
 *
 * Backward-compatible: a pre-CH-60 server that emits only default `data:`
 * lines works identically — only "text" events are produced.
 */
export async function* streamChatCompletion(
  messages: ChatMessage[],
  sessionId?: string,
  accountId?: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent, void, unknown> {
  const request: ChatRequest = {
    messages,
    stream: true,
    session_id: sessionId,
    account_id: accountId,
  };

  // Native Fetch — axios `responseType: "stream"` is Node-only, so the
  // browser path needs `response.body.getReader()` directly. Auth + base URL
  // are injected manually since fetch bypasses the axios interceptor.
  const token = await auth.currentUser?.getIdToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  const url = `${baseUrl}${CHAT_BASE}/completions`;

  const timeoutSignal = AbortSignal.timeout(COMPLETION_TIMEOUT);
  const combinedSignal = signal
    ? AbortSignal.any([signal, timeoutSignal])
    : timeoutSignal;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
    signal: combinedSignal,
  });

  if (!response.ok || !response.body) {
    throw new Error(
      `Chat completion request failed: ${response.status} ${response.statusText}`,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  // Buffer carries an incomplete trailing line across reads so an SSE line
  // split across TCP packets isn't silently dropped.
  let buffer = "";
  // Per-event accumulation. Per the SSE spec, an event is a run of field lines
  // terminated by a blank line, and consecutive `data:` lines are concatenated
  // with "\n" to form the payload. The backend emits one `data:` line per line
  // of a multi-line fragment (SSE-injection safety), so this join is what
  // restores embedded newlines — without it, line and paragraph breaks in the
  // streamed answer collapse (the message bubble renders `whitespace-pre-wrap`).
  let currentEvent = "message";
  let currentAuthor = "model";
  let dataLines: string[] = [];

  // Build the StreamEvent for a completed event block, or null when it should
  // be dropped (unknown event type, malformed reasoning JSON).
  const buildEvent = (
    eventType: string,
    data: string,
    author: string,
  ): StreamEvent | null => {
    if (eventType === "session") {
      try {
        const parsed = JSON.parse(data) as { session_id: string };
        if (typeof parsed.session_id !== "string" || !parsed.session_id) {
          return null;
        }
        return { type: "session", sessionId: parsed.session_id };
      } catch {
        // Malformed session JSON — drop silently (CH-62).
        console.debug(
          "[streamChatCompletion] malformed session payload:",
          data,
        );
        return null;
      }
    }
    if (eventType === "reasoning") {
      try {
        const parsed = JSON.parse(data) as {
          text: string;
          seq: number;
          author?: string;
        };
        return {
          type: "reasoning",
          text: parsed.text,
          author: parsed.author ?? author,
        };
      } catch {
        // Malformed reasoning JSON — drop silently, no UI noise.
        console.debug(
          "[streamChatCompletion] malformed reasoning payload:",
          data,
        );
        return null;
      }
    }
    if (eventType === "message") {
      return { type: "text", text: data, author };
    }
    // Unknown event types (e.g. "event: ping") — dropped.
    return null;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line === "") {
          // Blank line: event boundary — dispatch the accumulated event.
          if (dataLines.length > 0) {
            const data = dataLines.join("\n");
            dataLines = [];
            if (data === "[DONE]") {
              return;
            }
            // Handle author sidecar: update tracking state, do not yield.
            if (currentEvent === "author") {
              if (data.trim()) {
                currentAuthor = data.trim();
              }
              currentEvent = "message";
              continue;
            }
            const event = buildEvent(currentEvent, data, currentAuthor);
            if (event) {
              yield event;
            }
          }
          currentEvent = "message";
        } else if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          // Do NOT trim — leading/trailing spaces and empty data lines are
          // meaningful and must round-trip into the joined payload.
          dataLines.push(line.slice(6));
        }
        // Other SSE fields (comments ":", "id:", "retry:") are ignored.
      }
    }

    // Flush an event left unterminated by a final blank line (server closed
    // the stream without the trailing "\n\n").
    if (buffer.startsWith("data: ")) {
      dataLines.push(buffer.slice(6));
    }
    if (dataLines.length > 0) {
      const data = dataLines.join("\n");
      if (data !== "[DONE]") {
        if (currentEvent === "author") {
          if (data.trim()) {
            currentAuthor = data.trim();
          }
        } else {
          const event = buildEvent(currentEvent, data, currentAuthor);
          if (event) {
            yield event;
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * GET /api/v1/chat/conversations/{session_id}/todos
 */
export async function listTodoLists(
  sessionId: ChatSessionId,
): Promise<ListTodosResponse> {
  const { data } = await api.get<ListTodosResponse>(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}/todos`,
  );
  return data;
}

/**
 * GET /api/v1/chat/conversations/{session_id}/artifacts
 */
export async function listArtifacts(
  sessionId: ChatSessionId,
): Promise<ListArtifactsResponse> {
  const { data } = await api.get<ListArtifactsResponse>(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}/artifacts`,
  );
  return data;
}

/**
 * GET /api/v1/chat/categories
 * Gated by chat_categories_enabled flag; caller must check the flag before calling.
 */
export async function listChatCategories(): Promise<ChatCategory[]> {
  const { data } = await api.get<ChatCategory[]>(`${CHAT_BASE}/categories`);
  return data;
}

/**
 * POST /api/v1/chat/categories
 * Creates a new category. Throws CategoryExistsError on 409 (casefold dedup conflict).
 */
export async function createChatCategory(name: string): Promise<ChatCategory> {
  try {
    const { data } = await api.post<ChatCategory>(`${CHAT_BASE}/categories`, {
      name,
    });
    return data;
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      const rawId: unknown = err.response?.data?.detail?.existing_category_id;
      const existingId =
        typeof rawId === "string" ? (tryChatCategoryId(rawId) ?? null) : null;
      if (rawId !== undefined && existingId === null) {
        console.warn(
          "createChatCategory: 409 response missing or malformed existing_category_id; CategoryExistsError.existingCategoryId will be null. rawId=",
          rawId,
        );
      }
      throw new CategoryExistsError(existingId, name);
    }
    throw err;
  }
}

/**
 * DELETE /api/v1/chat/categories/{id}
 * Deletes a category and bulk-clears it from affected sessions.
 */
export async function deleteChatCategory(
  id: ChatCategoryId,
): Promise<DeleteCategoryResponse> {
  const { data } = await api.delete<DeleteCategoryResponse>(
    `${CHAT_BASE}/categories/${encodeURIComponent(id)}`,
  );
  return data;
}

/**
 * PUT /api/v1/chat/conversations/{session_id}/category
 * Assigns or clears a session's category. Pass null to unassign.
 */
export async function assignSessionCategory(
  sessionId: ChatSessionId,
  categoryId: ChatCategoryId | null,
): Promise<void> {
  await api.put(
    `${CHAT_BASE}/conversations/${encodeURIComponent(sessionId)}/category`,
    { category_id: categoryId },
  );
}

/**
 * GET /api/v1/chat/health
 */
export async function chatHealth(): Promise<{ status: string }> {
  const { data } = await api.get<{ status: string }>(`${CHAT_BASE}/health`);
  return data;
}
