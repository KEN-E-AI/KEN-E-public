import type { Brand } from "@/lib/branded-types";
import api from "@/lib/api";
import { auth } from "@/lib/firebase";

// ─── Branded types ────────────────────────────────────────────────────────────

export type ChatSessionId = Brand<string, "ChatSessionId">;

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
 */
export async function markRead(
  sessionId: ChatSessionId,
): Promise<{ last_viewed_at: string }> {
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
 * POST /api/v1/chat/completions (streaming SSE)
 * Async generator yielding raw SSE data-line payloads.
 */
export async function* streamChatCompletion(
  messages: ChatMessage[],
  sessionId?: string,
  accountId?: string,
  signal?: AbortSignal,
): AsyncGenerator<string, void, unknown> {
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

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "[DONE]") {
            return;
          }
          if (data) {
            yield data;
          }
        }
      }
    }

    if (buffer.startsWith("data: ")) {
      const data = buffer.slice(6).trim();
      if (data && data !== "[DONE]") {
        yield data;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * GET /api/v1/chat/health
 */
export async function chatHealth(): Promise<{ status: string }> {
  const { data } = await api.get<{ status: string }>(`${CHAT_BASE}/health`);
  return data;
}
