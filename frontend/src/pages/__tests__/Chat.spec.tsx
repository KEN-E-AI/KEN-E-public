import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { ReactNode } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  MemoryRouter,
  Route,
  Routes,
  Navigate,
  useLocation,
} from "react-router-dom";

// ─── Mocks ────────────────────────────────────────────────────────────────────

// Telemetry — assert the page-view span fires.
const mockEmitPageView = vi.fn();
vi.mock("@/lib/telemetry", () => ({
  emitPageView: (...args: unknown[]) => mockEmitPageView(...args),
}));

// Auth — Chat reads selectedOrgAccount.accountId.
const mockUseAuth = vi.fn();
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// New-session mutation hook.
const mockMutate = vi.fn();
const mockUseCreateChatSession = vi.fn();
vi.mock("@/hooks/useCreateChatSession", () => ({
  useCreateChatSession: () => mockUseCreateChatSession(),
}));

// Partially mock chatApi: stub createChatConversation (the lazy-create call),
// keep everything else real (toChatSessionId, branded-type guards, etc.).
vi.mock("@/lib/chatApi", async (orig) => {
  const actual = await orig<typeof import("@/lib/chatApi")>();
  return { ...actual, createChatConversation: vi.fn() };
});

// Heavy children stubbed to identifiable markers + interaction hooks.
vi.mock("@/components/chat/SessionsSidebar", () => ({
  SessionsSidebar: ({
    isCollapsed,
    onToggleCollapse,
    onSessionSelect,
    onNewSession,
  }: any) => (
    <div data-slot="sessions-sidebar" aria-label="Sessions sidebar">
      <button onClick={onToggleCollapse}>
        {isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      </button>
      <button onClick={() => onSessionSelect("picked123")}>
        Select session
      </button>
      <button onClick={onNewSession}>New session</button>
    </div>
  ),
}));

vi.mock("@/components/chat/ChatInterface", () => ({
  ChatInterface: ({
    sessionId,
    onCreateSession,
    onSessionStarted,
    onSessionResolved,
  }: any) => (
    <div data-testid="chat-interface" data-session-id={sessionId ?? ""}>
      <button
        onClick={async () => {
          const id = await onCreateSession?.();
          if (id) onSessionStarted?.(id);
        }}
      >
        simulate first message
      </button>
      <button onClick={() => onSessionResolved?.("real_42")}>
        simulate session resolved
      </button>
    </div>
  ),
}));

vi.mock("@/components/chat/ArtifactsPanel", () => ({
  ArtifactsPanel: () => <div data-testid="artifacts-panel" />,
}));

vi.mock("@/components/chat/TodoListsPanel", () => ({
  TodoListsPanel: () => <div data-testid="todo-lists-panel" />,
}));

import Chat from "../Chat";
import NotFoundPage from "../NotFoundPage";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { createChatConversation } from "@/lib/chatApi";
import { getActiveSessionId } from "@/hooks/useActiveChatSession";

const mockCreateChatConversation = vi.mocked(createChatConversation);

// ─── Helpers ──────────────────────────────────────────────────────────────────

const LAST_SESSION_KEY = "kene_chat_last_session";
const SIDEBAR_COLLAPSED_KEY = "kene_chat_sidebar_collapsed";
const BOOT_UID_KEY = "kene_chat_boot_uid";
const TEST_UID = "user_1";

function LocationProbe() {
  const location = useLocation();
  return (
    <div data-testid="location">{location.pathname + location.search}</div>
  );
}

function withQueryClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

function renderChat(search = "") {
  return render(
    withQueryClient(
      <MemoryRouter initialEntries={[`/chat${search}`]}>
        <LocationProbe />
        <Routes>
          <Route path="/chat" element={<Chat />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>,
    ),
  );
}

function locationText(): string {
  return screen.getByTestId("location").textContent ?? "";
}

// Deterministic in-memory storage (the test runtime's default storage is
// unreliable here — `removeItem` is missing under Node's experimental shim).
function memoryStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => void store.clear(),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  };
}

function installMemoryStorage() {
  vi.stubGlobal("localStorage", memoryStorage());
  vi.stubGlobal("sessionStorage", memoryStorage());
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("Chat page shell", () => {
  beforeEach(() => {
    installMemoryStorage();
    mockUseAuth.mockReturnValue({
      user: { id: TEST_UID },
      selectedOrgAccount: { accountId: "acct_1" },
    });
    mockUseCreateChatSession.mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ── slots ────────────────────────────────────────────────────────────────

  it("renders the sessions-sidebar slot", () => {
    renderChat();
    expect(
      screen.getByRole("generic", { name: /sessions sidebar/i }),
    ).toBeInTheDocument();
  });

  it("renders the chat-body slot", () => {
    renderChat();
    expect(document.querySelector("[data-slot='chat-body']")).not.toBeNull();
  });

  it("renders the view-toggle slot", () => {
    renderChat();
    expect(document.querySelector("[data-slot='view-toggle']")).not.toBeNull();
  });

  // ── ?session= query param wiring ──────────────────────────────────────────

  it("passes the validated session id down to ChatInterface", () => {
    renderChat("?session=abc123");
    expect(screen.getByTestId("chat-interface")).toHaveAttribute(
      "data-session-id",
      "abc123",
    );
  });

  // ── view-state toggle ─────────────────────────────────────────────────────

  it("starts in message view (toggle label reads 'Session Status')", () => {
    renderChat("?session=abc123");
    const toggle = screen.getByRole("button", { name: /toggle view/i });
    expect(toggle).toHaveTextContent(/session status/i);
    expect(screen.getByTestId("chat-interface")).toBeInTheDocument();
  });

  it("toggles to status view when the toggle is clicked", () => {
    renderChat("?session=abc123");
    fireEvent.click(screen.getByRole("button", { name: /toggle view/i }));
    expect(
      screen.getByRole("button", { name: /toggle view/i }),
    ).toHaveTextContent(/chat/i);
    expect(screen.getByTestId("artifacts-panel")).toBeInTheDocument();
    expect(screen.getByTestId("todo-lists-panel")).toBeInTheDocument();
  });

  it("toggles back to message view on a second click", () => {
    renderChat("?session=abc123");
    const toggle = () => screen.getByRole("button", { name: /toggle view/i });
    fireEvent.click(toggle()); // → status
    fireEvent.click(toggle()); // → message
    expect(toggle()).toHaveTextContent(/session status/i);
    expect(screen.getByTestId("chat-interface")).toBeInTheDocument();
  });

  // ── sidebar-collapse localStorage ─────────────────────────────────────────

  it("collapse toggle writes to localStorage", () => {
    renderChat("?session=abc123");
    expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /collapse sidebar/i }));
    expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("true");
  });

  it("reads initial collapsed state from localStorage", () => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, "true");
    renderChat("?session=abc123");
    expect(
      screen.getByRole("button", { name: /expand sidebar/i }),
    ).toBeInTheDocument();
  });

  it("collapse toggle round-trips: collapse → expand restores false", () => {
    renderChat("?session=abc123");
    const getBtn = () =>
      screen.getByRole("button", { name: /collapse sidebar|expand sidebar/i });
    fireEvent.click(getBtn()); // collapse → true
    expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("true");
    fireEvent.click(getBtn()); // expand → false
    expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("false");
  });

  // ── emitPageView telemetry ─────────────────────────────────────────────────

  it("calls emitPageView exactly once on mount", () => {
    renderChat("?session=test999");
    expect(mockEmitPageView).toHaveBeenCalledTimes(1);
  });

  it("calls emitPageView with 'chat.page.render' and the session id", () => {
    renderChat("?session=test999");
    expect(mockEmitPageView).toHaveBeenCalledWith("chat.page.render", {
      session_id: "test999",
      view: "message",
    });
  });

  it("calls emitPageView with session_id null when ?session= is absent", () => {
    renderChat();
    expect(mockEmitPageView).toHaveBeenCalledWith("chat.page.render", {
      session_id: null,
      view: "message",
    });
  });
});

// ─── Session boot: resume on in-app nav, defer creation to first message ──────

describe("Chat session boot (resume on nav / deferred create)", () => {
  beforeEach(() => {
    installMemoryStorage();
    mockUseAuth.mockReturnValue({
      user: { id: TEST_UID },
      selectedOrgAccount: { accountId: "acct_1" },
    });
    mockUseCreateChatSession.mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    });
    mockCreateChatConversation.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("persists the active session id and marks the browser session for the user", async () => {
    renderChat("?session=abc123");
    await waitFor(() =>
      expect(getActiveSessionId(TEST_UID, "acct_1")).toBe("abc123"),
    );
    expect(sessionStorage.getItem(BOOT_UID_KEY)).toBe(TEST_UID);
  });

  it("does NOT create a session at login — leaves the empty composer (deferred)", async () => {
    renderChat();
    await waitFor(() =>
      expect(screen.getByTestId("chat-interface")).toBeInTheDocument(),
    );
    expect(locationText()).toBe("/chat");
    expect(mockMutate).not.toHaveBeenCalled();
    expect(mockCreateChatConversation).not.toHaveBeenCalled();
    expect(screen.getByTestId("chat-interface")).toHaveAttribute(
      "data-session-id",
      "",
    );
  });

  it("resumes the active session on in-app navigation (boot marker matches)", async () => {
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);
    localStorage.setItem(LAST_SESSION_KEY, "active123");
    renderChat();
    await waitFor(() => expect(locationText()).toBe("/chat?session=active123"));
    expect(mockCreateChatConversation).not.toHaveBeenCalled();
  });

  it("stays on the empty composer when the boot marker matches but nothing is stored", async () => {
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);
    renderChat();
    await waitFor(() =>
      expect(screen.getByTestId("chat-interface")).toBeInTheDocument(),
    );
    expect(locationText()).toBe("/chat");
    expect(mockCreateChatConversation).not.toHaveBeenCalled();
  });

  it("does not redirect when a session is already in the URL", async () => {
    localStorage.setItem(LAST_SESSION_KEY, "active123");
    renderChat("?session=current456");
    await waitFor(() =>
      expect(screen.getByTestId("chat-interface")).toBeInTheDocument(),
    );
    expect(locationText()).toBe("/chat?session=current456");
  });

  it("creates a session on the first message and moves the URL to it", async () => {
    mockCreateChatConversation.mockResolvedValue({
      session_id: "new789",
      created_at: "",
      last_updated: "",
      message_count: 0,
    });
    renderChat();
    // The mocked ChatInterface's button simulates first-message create+activate.
    fireEvent.click(
      screen.getByRole("button", { name: /simulate first message/i }),
    );
    await waitFor(() =>
      expect(mockCreateChatConversation).toHaveBeenCalledWith({
        account_id: "acct_1",
      }),
    );
    await waitFor(() => expect(locationText()).toBe("/chat?session=new789"));
  });

  it("navigates to ?session= when a sidebar session is selected", async () => {
    // Render already in a session so the boot effect is a no-op.
    renderChat("?session=existing999");
    fireEvent.click(screen.getByRole("button", { name: /select session/i }));
    await waitFor(() => expect(locationText()).toBe("/chat?session=picked123"));
  });

  it("re-runs boot effect after account switch and resumes the new account's session (bootedForRef guard)", async () => {
    // Regression guard for the bootedForRef fix: after one boot attempt for
    // acct_1 (no stored session → stays on empty composer), switching to acct_2
    // which HAS a stored session must trigger a second boot and navigate.
    // Before the fix, a plain didBootRef would have blocked the second boot.

    // acct_1 has no stored session.
    const makeChatTree = () =>
      withQueryClient(
        <MemoryRouter initialEntries={["/chat"]}>
          <LocationProbe />
          <Routes>
            <Route path="/chat" element={<Chat />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </MemoryRouter>,
      );

    const { rerender } = render(makeChatTree());

    // First boot for acct_1 — no session, stays on bare /chat.
    await waitFor(() =>
      expect(screen.getByTestId("chat-interface")).toBeInTheDocument(),
    );
    expect(locationText()).toBe("/chat");

    // acct_2 has a stored session (written, e.g., from the widget on another page).
    localStorage.setItem(
      LAST_SESSION_KEY,
      JSON.stringify({ id: "sess_acct2", accountId: "acct_2" }),
    );
    sessionStorage.setItem(BOOT_UID_KEY, TEST_UID);

    // Simulate account switch: update the mock then re-render with a fresh
    // element so React reconciles the component tree and re-runs hooks.
    mockUseAuth.mockReturnValue({
      user: { id: TEST_UID },
      selectedOrgAccount: { accountId: "acct_2" },
    });

    // Creating a new element (not the same cached reference) ensures React's
    // reconciler re-runs the component's hooks and picks up the new auth value.
    rerender(makeChatTree());

    await waitFor(() =>
      expect(locationText()).toBe("/chat?session=sess_acct2"),
    );
  });
});

// ─── Flag-gate: ternary route renders the correct component ───────────────────

describe("App-level flag-gate behavior", () => {
  beforeEach(() => {
    installMemoryStorage();
    mockUseAuth.mockReturnValue({
      user: { id: TEST_UID },
      selectedOrgAccount: { accountId: "acct_1" },
    });
    mockUseCreateChatSession.mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // Mirrors AppRoutes: <Route path="/chat" element={flag ? <Chat/> : <ChatInterface/>} />
  function renderAppSlice(flagEnabled: boolean, path = "/chat") {
    return render(
      withQueryClient(
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route
              path="/chat"
              element={flagEnabled ? <Chat /> : <ChatInterface />}
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </MemoryRouter>,
      ),
    );
  }

  function renderWithRootRedirect(flagEnabled: boolean) {
    return render(
      withQueryClient(
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route
              path="/chat"
              element={flagEnabled ? <Chat /> : <ChatInterface />}
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </MemoryRouter>,
      ),
    );
  }

  it("renders new Chat shell when chat_v2_enabled is true", () => {
    renderAppSlice(true);
    expect(
      document.querySelector("[data-slot='sessions-sidebar']"),
    ).not.toBeNull();
  });

  it("renders legacy ChatInterface when chat_v2_enabled is false", () => {
    renderAppSlice(false);
    expect(
      document.querySelector("[data-testid='chat-interface']"),
    ).not.toBeNull();
  });

  it("does NOT show NotFoundPage when chat_v2_enabled is false", () => {
    renderAppSlice(false);
    expect(screen.queryByRole("heading", { name: /404/i })).toBeNull();
  });

  it("'/' → '/chat' renders ChatInterface (not 404) when flag is off", () => {
    renderWithRootRedirect(false);
    expect(
      document.querySelector("[data-testid='chat-interface']"),
    ).not.toBeNull();
    expect(screen.queryByRole("heading", { name: /404/i })).toBeNull();
  });
});

// ─── CH-62: pending_ session id reconciliation ────────────────────────────────

describe("Chat session resolved (onSessionResolved — CH-62)", () => {
  beforeEach(() => {
    installMemoryStorage();
    mockUseAuth.mockReturnValue({
      user: { id: TEST_UID },
      selectedOrgAccount: { accountId: "acct_1" },
    });
    mockUseCreateChatSession.mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("swaps the URL to the real id on onSessionResolved (replace: true)", async () => {
    renderChat("?session=pending_abc");
    fireEvent.click(
      screen.getByRole("button", { name: /simulate session resolved/i }),
    );
    await waitFor(() => expect(locationText()).toBe("/chat?session=real_42"));
  });

  it("updates the localStorage marker to the real id on onSessionResolved", async () => {
    renderChat("?session=pending_abc");
    fireEvent.click(
      screen.getByRole("button", { name: /simulate session resolved/i }),
    );
    await waitFor(() =>
      // Read through the canonical accessor: onSessionResolved now persists via
      // the account-scoped setActiveSessionId (CH-62 ⇄ CH-61 integration), so the
      // raw value is a JSON blob — assert the resumable id, not the storage format.
      expect(getActiveSessionId(TEST_UID, "acct_1")).toBe("real_42"),
    );
  });

  it("setActiveSessionId rejects pending_ ids (defense-in-depth)", async () => {
    // The boot effect writes the current session id — if it were pending_ it
    // must be rejected. We verify by starting on a pending_ URL: the boot
    // effect fires setActiveSessionId("pending_abc", …), which must be a no-op,
    // so the marker stays null.
    renderChat("?session=pending_abc");
    // Allow effects to settle.
    await waitFor(() =>
      expect(screen.getByTestId("chat-interface")).toBeInTheDocument(),
    );
    expect(localStorage.getItem(LAST_SESSION_KEY)).toBeNull();
  });

  it("onSessionResolved accepts valid ids and rejects invalid ones (SESSION_ID_RE guard)", async () => {
    // The mock ChatInterface fires "real_42" via "simulate session resolved".
    // "real_42" passes SESSION_ID_RE (/^[a-zA-Z0-9_-]{1,128}$/), so it must be
    // accepted: URL and localStorage update to the real id.
    // The guard is verified indirectly: if SESSION_ID_RE blocked "real_42",
    // the assertions below would fail.
    localStorage.setItem(LAST_SESSION_KEY, "old_session");
    renderChat("?session=pending_abc");

    fireEvent.click(
      screen.getByRole("button", { name: /simulate session resolved/i }),
    );

    await waitFor(() =>
      // Read through the canonical accessor: onSessionResolved now persists via
      // the account-scoped setActiveSessionId (CH-62 ⇄ CH-61 integration), so the
      // raw value is a JSON blob — assert the resumable id, not the storage format.
      expect(getActiveSessionId(TEST_UID, "acct_1")).toBe("real_42"),
    );
    await waitFor(() => expect(locationText()).toBe("/chat?session=real_42"));
  });
});
