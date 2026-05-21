import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  isChatSessionId,
  toChatSessionId,
  tryChatSessionId,
  isChatCategoryId,
  toChatCategoryId,
  tryChatCategoryId,
  deriveSessionStatus,
  listChatSessions,
  listChatConversationsLegacy,
  markRead,
  createChatConversation,
  updateChatConversation,
  deleteChatConversation,
  getConversationHistory,
  postChatCompletion,
  streamChatCompletion,
  chatHealth,
  toChatSessionId as mkSessionId,
  toChatCategoryId as mkCategoryId,
} from "./chatApi";

// ─── Mock the shared axios instance ──────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from "@/lib/api";

const mockApi = api as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── ChatSessionId branded type ───────────────────────────────────────────────

describe("isChatSessionId", () => {
  it("returns true for non-empty strings", () => {
    expect(isChatSessionId("abc123")).toBe(true);
    expect(isChatSessionId("pending_uuid-123")).toBe(true);
  });

  it("returns false for empty string", () => {
    expect(isChatSessionId("")).toBe(false);
  });
});

describe("toChatSessionId", () => {
  it("returns branded ChatSessionId for valid string", () => {
    const id = toChatSessionId("session_abc");
    expect(id).toBe("session_abc");
  });

  it("throws for empty string", () => {
    expect(() => toChatSessionId("")).toThrow("Invalid ChatSessionId");
  });
});

describe("tryChatSessionId", () => {
  it("returns the id for non-empty strings", () => {
    expect(tryChatSessionId("session_xyz")).toBe("session_xyz");
  });

  it("returns undefined for empty string", () => {
    expect(tryChatSessionId("")).toBeUndefined();
  });
});

// ─── ChatCategoryId branded type ──────────────────────────────────────────────

describe("isChatCategoryId", () => {
  it("returns true for non-empty strings", () => {
    expect(isChatCategoryId("cat_001")).toBe(true);
  });

  it("returns false for empty string", () => {
    expect(isChatCategoryId("")).toBe(false);
  });
});

describe("toChatCategoryId", () => {
  it("returns branded ChatCategoryId for valid string", () => {
    const id = toChatCategoryId("cat_abc");
    expect(id).toBe("cat_abc");
  });

  it("throws for empty string", () => {
    expect(() => toChatCategoryId("")).toThrow("Invalid ChatCategoryId");
  });
});

describe("tryChatCategoryId", () => {
  it("returns the id for non-empty strings", () => {
    expect(tryChatCategoryId("cat_xyz")).toBe("cat_xyz");
  });

  it("returns undefined for empty string", () => {
    expect(tryChatCategoryId("")).toBeUndefined();
  });
});

// ─── deriveSessionStatus ─────────────────────────────────────────────────────

describe("deriveSessionStatus", () => {
  it("returns 'active' when is_agent_running is true", () => {
    expect(
      deriveSessionStatus({
        is_agent_running: true,
        last_agent_message_at: "2026-05-01T10:00:00Z",
        last_viewed_at: "2026-05-01T10:05:00Z",
      }),
    ).toBe("active");
  });

  it("returns 'needs-review' when agent stopped and message not yet viewed", () => {
    expect(
      deriveSessionStatus({
        is_agent_running: false,
        last_agent_message_at: "2026-05-01T10:05:00Z",
        last_viewed_at: "2026-05-01T10:00:00Z",
      }),
    ).toBe("needs-review");
  });

  it("returns 'needs-review' when last_viewed_at is null and agent replied", () => {
    expect(
      deriveSessionStatus({
        is_agent_running: false,
        last_agent_message_at: "2026-05-01T10:05:00Z",
        last_viewed_at: null,
      }),
    ).toBe("needs-review");
  });

  it("returns 'idle' when agent stopped and message viewed after", () => {
    expect(
      deriveSessionStatus({
        is_agent_running: false,
        last_agent_message_at: "2026-05-01T10:00:00Z",
        last_viewed_at: "2026-05-01T10:05:00Z",
      }),
    ).toBe("idle");
  });

  it("returns 'idle' when no agent message has arrived", () => {
    expect(
      deriveSessionStatus({
        is_agent_running: false,
        last_agent_message_at: null,
        last_viewed_at: null,
      }),
    ).toBe("idle");
  });
});

// ─── listChatSessions ─────────────────────────────────────────────────────────

describe("listChatSessions", () => {
  it("calls GET /api/v1/chat/conversations with no params by default", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { items: [], next_cursor: null },
    });
    await listChatSessions();
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/conversations", {
      params: {},
    });
  });

  it("passes cursor query param", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { items: [], next_cursor: null },
    });
    await listChatSessions({ cursor: "opaque_cursor_abc" });
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/conversations", {
      params: { cursor: "opaque_cursor_abc" },
    });
  });

  it("passes category_id query param", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { items: [], next_cursor: null },
    });
    await listChatSessions({ category_id: mkCategoryId("cat_01") });
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/conversations", {
      params: { category_id: "cat_01" },
    });
  });

  it("passes query param for search", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { items: [], next_cursor: null },
    });
    await listChatSessions({ query: "Q3 campaign" });
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/conversations", {
      params: { query: "Q3 campaign" },
    });
  });

  it("passes limit param", async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { items: [], next_cursor: null },
    });
    await listChatSessions({ limit: 50 });
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/conversations", {
      params: { limit: 50 },
    });
  });

  it("returns response data", async () => {
    const fixture = {
      items: [
        {
          session_id: mkSessionId("s1"),
          title: "Q3 Calendar",
          category_id: null,
          category_name: null,
          last_message_preview: "Help me build...",
          updated_at: "2026-05-01T10:00:00Z",
          created_at: "2026-05-01T09:00:00Z",
          is_agent_running: false,
          last_agent_message_at: "2026-05-01T10:00:00Z",
          last_viewed_at: null,
        },
      ],
      next_cursor: "cursor_xyz",
    };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listChatSessions();
    expect(result).toEqual(fixture);
  });
});

// ─── listChatConversationsLegacy ──────────────────────────────────────────────

describe("listChatConversationsLegacy", () => {
  it("calls GET /api/v1/chat/conversations without params", async () => {
    const fixture = { conversations: [], total_count: 0 };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listChatConversationsLegacy();
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/conversations");
    expect(result).toEqual(fixture);
  });
});

// ─── markRead ─────────────────────────────────────────────────────────────────

describe("markRead", () => {
  it("calls POST /api/v1/chat/conversations/{id}/mark-read", async () => {
    const fixture = { last_viewed_at: "2026-05-01T10:00:00Z" };
    mockApi.post.mockResolvedValueOnce({ data: fixture });
    const result = await markRead(mkSessionId("session_abc"));
    expect(mockApi.post).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/session_abc/mark-read",
    );
    expect(result).toEqual(fixture);
  });
});

// ─── createChatConversation ───────────────────────────────────────────────────

describe("createChatConversation", () => {
  it("calls POST /api/v1/chat/conversations with body", async () => {
    const fixture = {
      session_id: "sess_1",
      created_at: "2026-05-01T09:00:00Z",
      last_updated: "2026-05-01T09:00:00Z",
      message_count: 0,
    };
    mockApi.post.mockResolvedValueOnce({ data: fixture });
    const result = await createChatConversation({
      conversation_name: "New chat",
      account_id: "acc_01",
    });
    expect(mockApi.post).toHaveBeenCalledWith("/api/v1/chat/conversations", {
      conversation_name: "New chat",
      account_id: "acc_01",
    });
    expect(result).toEqual(fixture);
  });
});

// ─── updateChatConversation ───────────────────────────────────────────────────

describe("updateChatConversation", () => {
  it("calls PUT /api/v1/chat/conversations/{id} with body", async () => {
    const fixture = {
      session_id: "sess_1",
      conversation_name: "Renamed",
      created_at: "2026-05-01T09:00:00Z",
      last_updated: "2026-05-01T10:00:00Z",
      message_count: 2,
    };
    mockApi.put.mockResolvedValueOnce({ data: fixture });
    const result = await updateChatConversation("sess_1", "Renamed");
    expect(mockApi.put).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess_1",
      { conversation_name: "Renamed" },
    );
    expect(result).toEqual(fixture);
  });
});

// ─── deleteChatConversation ───────────────────────────────────────────────────

describe("deleteChatConversation", () => {
  it("calls DELETE /api/v1/chat/conversations/{id}", async () => {
    mockApi.delete.mockResolvedValueOnce({ data: undefined });
    await deleteChatConversation("sess_1");
    expect(mockApi.delete).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess_1",
    );
  });
});

// ─── getConversationHistory ───────────────────────────────────────────────────

describe("getConversationHistory", () => {
  it("calls GET /api/v1/chat/conversations/{id}/history", async () => {
    const fixture = { events: [] };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await getConversationHistory("sess_1");
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess_1/history",
    );
    expect(result).toEqual(fixture);
  });
});

// ─── postChatCompletion ───────────────────────────────────────────────────────

describe("postChatCompletion", () => {
  it("calls POST /api/v1/chat/completions with correct body and 30-min timeout", async () => {
    const fixture = {
      role: "assistant" as const,
      content: "Hello!",
      session_id: "sess_1",
    };
    mockApi.post.mockResolvedValueOnce({ data: fixture });
    const messages = [{ role: "user" as const, content: "Hi" }];
    const result = await postChatCompletion(messages, "sess_1", "acc_01");
    expect(mockApi.post).toHaveBeenCalledWith(
      "/api/v1/chat/completions",
      { messages, stream: false, session_id: "sess_1", account_id: "acc_01" },
      { timeout: 1_800_000 },
    );
    expect(result).toEqual(fixture);
  });
});

// ─── streamChatCompletion ─────────────────────────────────────────────────────

describe("streamChatCompletion", () => {
  it("yields data payloads from SSE lines and stops at [DONE]", async () => {
    const sseChunk = "data: chunk1\n\ndata: chunk2\n\ndata: [DONE]\n\n";
    const encoder = new TextEncoder();
    const encoded = encoder.encode(sseChunk);

    // Fake reader: returns encoded bytes on first read, then done
    const fakeReader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: encoded })
        .mockResolvedValueOnce({ done: true, value: undefined }),
      releaseLock: vi.fn(),
    };

    mockApi.post.mockResolvedValueOnce({
      data: { getReader: () => fakeReader },
    });

    const messages = [{ role: "user" as const, content: "Stream this" }];
    const chunks: string[] = [];
    for await (const chunk of streamChatCompletion(messages)) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual(["chunk1", "chunk2"]);
    expect(fakeReader.releaseLock).toHaveBeenCalled();
  });
});

// ─── chatHealth ───────────────────────────────────────────────────────────────

describe("chatHealth", () => {
  it("calls GET /api/v1/chat/health and returns data", async () => {
    const fixture = { status: "healthy" };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await chatHealth();
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/health");
    expect(result).toEqual(fixture);
  });
});
