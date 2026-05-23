import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes, Navigate } from "react-router-dom";

// ─── Mocks ────────────────────────────────────────────────────────────────────

// Stub the telemetry helper so tests don't write to console and
// can assert the function was called.
const mockEmitPageView = vi.fn();
vi.mock("@/lib/telemetry", () => ({
  emitPageView: (...args: unknown[]) => mockEmitPageView(...args),
}));

// Mock useFeatureFlag so we can flip flag state per test.
const mockUseFeatureFlag = vi.fn(() => ({
  enabled: false,
  reason: "default" as const,
  isLoading: false,
}));
vi.mock("@/contexts/FeatureFlagsContext", () => ({
  // mockUseFeatureFlag is typed by vi.fn() with 0 args; the key is
  // ignored because the mock returns the same value for every flag.
  useFeatureFlag: (_key: string) => mockUseFeatureFlag(),
  FeatureFlagsProvider: ({ children }: { children: React.ReactNode }) =>
    children,
  useFeatureFlagsContext: vi.fn(),
  FeatureFlagsContext: {},
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

import Chat from "../Chat";
import NotFoundPage from "../NotFoundPage";
import { ChatInterface } from "@/components/chat/ChatInterface";

/**
 * Renders Chat inside a MemoryRouter at `/chat` with optional query params.
 */
function renderChat(search = "") {
  const path = `/chat${search}`;
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/chat" element={<Chat />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ─── localStorage helpers ─────────────────────────────────────────────────────

function clearLocalStorage() {
  localStorage.removeItem("kene_chat_sidebar_collapsed");
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("Chat page shell", () => {
  beforeEach(() => {
    clearLocalStorage();
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearLocalStorage();
  });

  // ── AC-1a: renders inside a router without throwing ───────────────────────

  it("renders the sessions-sidebar slot", () => {
    renderChat();
    expect(
      screen.getByRole("generic", { name: /sessions sidebar/i }),
    ).toBeInTheDocument();
  });

  it("renders the chat-body slot", () => {
    renderChat();
    const slot = document.querySelector("[data-slot='chat-body']");
    expect(slot).not.toBeNull();
  });

  it("renders the view-toggle slot", () => {
    renderChat();
    const slot = document.querySelector("[data-slot='view-toggle']");
    expect(slot).not.toBeNull();
  });

  // ── ?session= query param wiring ──────────────────────────────────────────

  it("shows empty-state copy when session param is absent", () => {
    renderChat();
    expect(screen.getByText(/start a new session/i)).toBeInTheDocument();
  });

  it("shows the session ID when ?session= param is present", () => {
    renderChat("?session=abc123");
    expect(screen.getByText(/session: abc123/i)).toBeInTheDocument();
  });

  // ── view-state toggle ─────────────────────────────────────────────────────

  it("starts in message view (toggle button label is 'Session Status')", () => {
    renderChat();
    expect(
      screen.getByRole("button", { name: /session status/i }),
    ).toBeInTheDocument();
  });

  it("toggles to status view when button is clicked", () => {
    renderChat();
    const toggleBtn = screen.getByRole("button", { name: /session status/i });
    fireEvent.click(toggleBtn);
    // Button label flips; status placeholder visible
    expect(screen.getByRole("button", { name: /^chat$/i })).toBeInTheDocument();
    expect(
      screen.getByText(/session status — coming soon/i),
    ).toBeInTheDocument();
  });

  it("toggles back to message view on a second click", () => {
    renderChat();
    const getToggle = () =>
      screen.getByRole("button", { name: /session status|^chat$/i });
    fireEvent.click(getToggle()); // → status
    fireEvent.click(getToggle()); // → message
    expect(
      screen.getByRole("button", { name: /session status/i }),
    ).toBeInTheDocument();
  });

  // ── localStorage persistence ──────────────────────────────────────────────

  it("collapse toggle writes to localStorage", () => {
    renderChat();
    const collapseBtn = screen.getByRole("button", {
      name: /collapse sidebar/i,
    });
    expect(localStorage.getItem("kene_chat_sidebar_collapsed")).toBeNull();
    fireEvent.click(collapseBtn);
    expect(localStorage.getItem("kene_chat_sidebar_collapsed")).toBe("true");
  });

  it("reads initial collapsed state from localStorage", () => {
    localStorage.setItem("kene_chat_sidebar_collapsed", "true");
    renderChat();
    // When collapsed, button label should be "Expand sidebar"
    expect(
      screen.getByRole("button", { name: /expand sidebar/i }),
    ).toBeInTheDocument();
  });

  it("collapse toggle round-trips: collapse → expand restores false", () => {
    renderChat();
    const getCollapseBtn = () =>
      screen.getByRole("button", { name: /collapse sidebar|expand sidebar/i });
    fireEvent.click(getCollapseBtn()); // collapse → true
    expect(localStorage.getItem("kene_chat_sidebar_collapsed")).toBe("true");
    fireEvent.click(getCollapseBtn()); // expand → false
    expect(localStorage.getItem("kene_chat_sidebar_collapsed")).toBe("false");
  });

  // ── emitPageView telemetry ─────────────────────────────────────────────────

  it("calls emitPageView exactly once on mount", () => {
    renderChat("?session=test999");
    expect(mockEmitPageView).toHaveBeenCalledTimes(1);
  });

  it("calls emitPageView with 'chat.page.render' event and correct props", () => {
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

// ─── Flag-gate integration: ternary route renders correct component ───────────

describe("App-level flag-gate behavior", () => {
  beforeEach(() => {
    mockUseFeatureFlag.mockReturnValue({
      enabled: false,
      reason: "default",
      isLoading: false,
    });
    vi.clearAllMocks();
  });

  /**
   * Mirrors the AppRoutes ternary:
   *   <Route path="/chat" element={isChatV2Enabled ? <Chat /> : <ChatInterface />} />
   */
  function renderAppSlice(flagEnabled: boolean, path = "/chat") {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/chat"
            element={flagEnabled ? <Chat /> : <ChatInterface />}
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  /**
   * Mirrors the top-level redirect + ternary chat route to verify
   * "/" → "/chat" lands on ChatInterface (not 404) when flag is off.
   */
  function renderWithRootRedirect(flagEnabled: boolean) {
    return render(
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
