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
  listTodoLists,
  listArtifacts,
  listChatCategories,
  createChatCategory,
  deleteChatCategory,
  assignSessionCategory,
  CategoryExistsError,
  toChatSessionId as mkSessionId,
  toChatCategoryId as mkCategoryId,
} from "./chatApi";
import type { StreamEvent } from "./chatApi";

// ─── Mock the shared axios instance ──────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

// streamChatCompletion uses native fetch + Firebase token directly (axios
// `responseType: "stream"` is Node-only, see chatApi.ts). Stub the auth
// module so getIdToken resolves without a real Firebase init.
vi.mock("@/lib/firebase", () => ({
  auth: {
    currentUser: {
      getIdToken: vi.fn().mockResolvedValue("test-token"),
    },
  },
}));

import api from "@/lib/api";

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const mockFetch = global.fetch as ReturnType<typeof vi.fn>;

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

  it("runtime shape: items[0].is_agent_running is a boolean and deriveSessionStatus works", async () => {
    const fixture = {
      items: [
        {
          session_id: mkSessionId("s1"),
          title: "Revenue Q3",
          category_id: null,
          category_name: null,
          last_message_preview: "Analyse trends",
          updated_at: "2026-05-21T12:00:00Z",
          created_at: "2026-05-21T11:00:00Z",
          is_agent_running: false,
          last_agent_message_at: "2026-05-21T11:55:00Z",
          last_viewed_at: null,
        },
      ],
      next_cursor: null,
    };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listChatSessions();
    const item = result.items[0];
    expect(typeof item.is_agent_running).toBe("boolean");
    // is_agent_running=false + last_agent_message_at set + last_viewed_at=null → "needs-review"
    expect(deriveSessionStatus(item)).toBe("needs-review");
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
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseChunk));
        controller.close();
      },
    });
    mockFetch.mockResolvedValueOnce(
      new Response(body, {
        status: 200,
        headers: { "Content-Type": "text/plain" },
      }),
    );

    const messages = [{ role: "user" as const, content: "Stream this" }];
    const events: StreamEvent[] = [];
    for await (const event of streamChatCompletion(messages)) {
      events.push(event);
    }

    expect(events).toEqual([
      { type: "text", text: "chunk1" },
      { type: "text", text: "chunk2" },
    ]);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/chat/completions"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        }),
        body: expect.stringContaining("Stream this"),
      }),
    );
  });

  it("reassembles SSE lines that span chunk boundaries", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        const enc = new TextEncoder();
        // "data: hello" is split mid-line across two reads.
        controller.enqueue(enc.encode("data: hel"));
        controller.enqueue(enc.encode("lo\n\ndata: [DONE]\n\n"));
        controller.close();
      },
    });
    mockFetch.mockResolvedValueOnce(new Response(body, { status: 200 }));

    const events: StreamEvent[] = [];
    for await (const event of streamChatCompletion([
      { role: "user" as const, content: "split" },
    ])) {
      events.push(event);
    }
    expect(events).toEqual([{ type: "text", text: "hello" }]);
  });

  it("throws when fetch is invoked with an aborted signal", async () => {
    const controller = new AbortController();
    controller.abort();

    mockFetch.mockImplementation((_url: string, init: RequestInit) => {
      if (init.signal?.aborted) {
        return Promise.reject(
          new DOMException("The user aborted a request.", "AbortError"),
        );
      }
      return Promise.resolve(new Response());
    });

    await expect(async () => {
      for await (const _ of streamChatCompletion(
        [{ role: "user" as const, content: "abort me" }],
        undefined,
        undefined,
        controller.signal,
      )) {
        // should not reach here
      }
    }).rejects.toThrow();

    const callArgs = mockFetch.mock.calls[0];
    const initArg = callArgs[1] as RequestInit;
    expect(initArg.signal?.aborted).toBe(true);
  });

  it("throws when the response is non-OK", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response("server error", { status: 500, statusText: "Internal" }),
    );

    await expect(async () => {
      for await (const _ of streamChatCompletion([
        { role: "user" as const, content: "boom" },
      ])) {
        // should not reach here
      }
    }).rejects.toThrow(/500/);
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

// ─── listTodoLists ────────────────────────────────────────────────────────────

describe("listTodoLists", () => {
  it("calls GET /api/v1/chat/conversations/{id}/todos and returns data", async () => {
    const fixture = {
      todo_lists: [
        {
          list_id: "list_1",
          title: "Q3 Campaign Tasks",
          is_current: true,
          created_at: "2026-05-01T09:00:00Z",
          items: [
            {
              item_id: "item_1",
              text: "Analyse performance data",
              completed: true,
              completed_at: "2026-05-01T10:00:00Z",
            },
            {
              item_id: "item_2",
              text: "Draft recommendations",
              completed: false,
              completed_at: null,
            },
          ],
        },
      ],
    };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listTodoLists(mkSessionId("session_abc"));
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/session_abc/todos",
    );
    expect(result).toEqual(fixture);
  });

  it("URL-encodes session IDs that contain special characters (AC-10)", async () => {
    mockApi.get.mockResolvedValueOnce({ data: { todo_lists: [] } });
    // A session ID containing a forward-slash must be percent-encoded in the URL path.
    await listTodoLists("sess/abc" as ReturnType<typeof mkSessionId>);
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess%2Fabc/todos",
    );
  });
});

// ─── listArtifacts ────────────────────────────────────────────────────────────

describe("listArtifacts", () => {
  it("calls GET /api/v1/chat/conversations/{id}/artifacts and returns data", async () => {
    const fixture = {
      items: [
        {
          artifact_index: {
            artifact_id: "artifact_abc123",
            session_id: "session_abc",
            filename: "campaign-report.pdf",
            mime_type: "application/pdf",
            size_bytes: 204800,
            version: 0,
            gcs_path: "gs://bucket/app/user/session/file/0",
            created_by_tool: "generate_report",
            created_at: "2026-05-01T09:00:00Z",
          },
          signed_url: "https://storage.googleapis.com/bucket/signed?token=abc",
          signed_url_expires_at: "2026-05-01T10:00:00Z",
        },
      ],
    };
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listArtifacts(mkSessionId("session_abc"));
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/session_abc/artifacts",
    );
    expect(result).toEqual(fixture);
  });

  it("URL-encodes session IDs that contain special characters (AC-12)", async () => {
    mockApi.get.mockResolvedValueOnce({ data: { items: [] } });
    await listArtifacts("sess/abc" as ReturnType<typeof mkSessionId>);
    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess%2Fabc/artifacts",
    );
  });
});

// ─── listChatCategories ───────────────────────────────────────────────────────

describe("listChatCategories", () => {
  it("calls GET /api/v1/chat/categories and returns data", async () => {
    const fixture = [
      {
        category_id: mkCategoryId("cat_01"),
        name: "Campaign Planning",
        created_at: "2026-05-01T09:00:00Z",
        updated_at: "2026-05-01T09:00:00Z",
      },
    ];
    mockApi.get.mockResolvedValueOnce({ data: fixture });
    const result = await listChatCategories();
    expect(mockApi.get).toHaveBeenCalledWith("/api/v1/chat/categories");
    expect(result).toEqual(fixture);
  });
});

// ─── createChatCategory ───────────────────────────────────────────────────────

describe("createChatCategory", () => {
  it("calls POST /api/v1/chat/categories with the name and returns the created category", async () => {
    const fixture = {
      category_id: mkCategoryId("cat_01"),
      name: "Q3 Campaigns",
      created_at: "2026-05-01T09:00:00Z",
      updated_at: "2026-05-01T09:00:00Z",
    };
    mockApi.post.mockResolvedValueOnce({ data: fixture });
    const result = await createChatCategory("Q3 Campaigns");
    expect(mockApi.post).toHaveBeenCalledWith("/api/v1/chat/categories", {
      name: "Q3 Campaigns",
    });
    expect(result).toEqual(fixture);
  });

  it("throws CategoryExistsError with existing id on 409", async () => {
    const axiosError = {
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          detail: {
            error: "category_exists",
            existing_category_id: "cat_42",
          },
        },
      },
    };
    mockApi.post.mockRejectedValueOnce(axiosError);

    let caught: unknown;
    try {
      await createChatCategory("q3 campaigns");
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(CategoryExistsError);
    const typedErr = caught as CategoryExistsError;
    expect(typedErr.existingCategoryId).toBe("cat_42");
    expect(typedErr.attemptedName).toBe("q3 campaigns");
  });

  it("rethrows non-409 AxiosErrors unchanged", async () => {
    const axiosError = Object.assign(
      new Error("Request failed with status code 500"),
      {
        isAxiosError: true,
        response: { status: 500, data: { detail: "Internal Server Error" } },
      },
    );
    mockApi.post.mockRejectedValueOnce(axiosError);

    await expect(createChatCategory("Q3")).rejects.not.toBeInstanceOf(
      CategoryExistsError,
    );
  });

  it("gracefully handles 409 with missing detail.existing_category_id — existingCategoryId is null", async () => {
    const axiosError = Object.assign(new Error("Conflict"), {
      isAxiosError: true,
      response: { status: 409, data: {} },
    });
    mockApi.post.mockRejectedValueOnce(axiosError);

    let caught: unknown;
    try {
      await createChatCategory("Q3");
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(CategoryExistsError);
    expect((caught as CategoryExistsError).existingCategoryId).toBeNull();
  });

  it("warns when 409 carries a non-string existing_category_id (server contract violation)", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const axiosError = Object.assign(new Error("Conflict"), {
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: { existing_category_id: 42 } },
      },
    });
    mockApi.post.mockRejectedValueOnce(axiosError);

    let caught: unknown;
    try {
      await createChatCategory("Q3");
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(CategoryExistsError);
    expect((caught as CategoryExistsError).existingCategoryId).toBeNull();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("missing or malformed existing_category_id"),
      42,
    );
    warnSpy.mockRestore();
  });
});

// ─── deleteChatCategory ───────────────────────────────────────────────────────

describe("deleteChatCategory", () => {
  it("calls DELETE /api/v1/chat/categories/{id} and returns sessions_reassigned", async () => {
    const fixture = { sessions_reassigned: 5 };
    mockApi.delete.mockResolvedValueOnce({ data: fixture });
    const result = await deleteChatCategory(mkCategoryId("cat_01"));
    expect(mockApi.delete).toHaveBeenCalledWith(
      "/api/v1/chat/categories/cat_01",
    );
    expect(result).toEqual(fixture);
  });

  it("URL-encodes category IDs that contain special characters", async () => {
    mockApi.delete.mockResolvedValueOnce({ data: { sessions_reassigned: 0 } });
    await deleteChatCategory("cat/special" as ReturnType<typeof mkCategoryId>);
    expect(mockApi.delete).toHaveBeenCalledWith(
      "/api/v1/chat/categories/cat%2Fspecial",
    );
  });
});

// ─── assignSessionCategory ────────────────────────────────────────────────────

describe("assignSessionCategory", () => {
  it("calls PUT /api/v1/chat/conversations/{session_id}/category with category_id", async () => {
    mockApi.put.mockResolvedValueOnce({ data: { status: "ok" } });
    await assignSessionCategory(mkSessionId("sess_01"), mkCategoryId("cat_01"));
    expect(mockApi.put).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess_01/category",
      { category_id: "cat_01" },
    );
  });

  it("sends category_id: null to clear a session's category", async () => {
    mockApi.put.mockResolvedValueOnce({ data: { status: "ok" } });
    await assignSessionCategory(mkSessionId("sess_01"), null);
    expect(mockApi.put).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess_01/category",
      { category_id: null },
    );
  });

  it("URL-encodes session IDs that contain special characters", async () => {
    mockApi.put.mockResolvedValueOnce({ data: { status: "ok" } });
    await assignSessionCategory(
      "sess/special" as ReturnType<typeof mkSessionId>,
      mkCategoryId("cat_01"),
    );
    expect(mockApi.put).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/sess%2Fspecial/category",
      { category_id: "cat_01" },
    );
  });

  it("returns void on success", async () => {
    mockApi.put.mockResolvedValueOnce({ data: { status: "ok" } });
    const result = await assignSessionCategory(
      mkSessionId("sess_01"),
      mkCategoryId("cat_01"),
    );
    expect(result).toBeUndefined();
  });
});
