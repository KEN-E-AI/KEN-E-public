import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { emitPageView } from "@/lib/telemetry";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { SessionsSidebar } from "@/components/chat/SessionsSidebar";
import { useAuth } from "@/contexts/AuthContext";
import { useCreateChatSession } from "@/hooks/useCreateChatSession";
import { CHAT_SESSIONS_QUERY_KEY } from "@/hooks/useChatSessions";
import { createChatConversation, toChatSessionId } from "@/lib/chatApi";
import { ArtifactsPanel } from "@/components/chat/ArtifactsPanel";
import { TodoListsPanel } from "@/components/chat/TodoListsPanel";
import {
  getActiveSessionId,
  setActiveSessionId,
  SESSION_ID_RE,
} from "@/hooks/useActiveChatSession";

type ViewState = "message" | "status";

const SIDEBAR_COLLAPSED_KEY = "kene_chat_sidebar_collapsed";

function readSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
}

function writeSidebarCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  } catch {
    // localStorage unavailable (e.g. private browsing with storage blocked) — ignore
  }
}

export default function Chat() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rawSession = searchParams.get("session");
  const sessionId =
    rawSession && SESSION_ID_RE.test(rawSession) ? rawSession : null;

  const { user, selectedOrgAccount } = useAuth();
  const accountId = selectedOrgAccount?.accountId ?? null;
  const createSession = useCreateChatSession();
  const queryClient = useQueryClient();

  const [viewState, setViewState] = useState<ViewState>("message");
  const [sidebarCollapsed, setSidebarCollapsed] =
    useState<boolean>(readSidebarCollapsed);
  const isFirstRender = useRef(true);
  // Keyed on "userId:accountId" so the boot runs once per (user, account) pair —
  // switching accounts triggers a fresh resume attempt while still preventing
  // spurious re-runs within the same session. Plain boolean ref was insufficient
  // once accountId was added to the effect's dep array.
  const bootedForRef = useRef<string | null>(null);

  // Persist sidebar collapse state across hard refreshes.
  // Skip the initial render — the value was just read from localStorage,
  // so writing it back would convert a missing key to an explicit "false".
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    writeSidebarCollapsed(sidebarCollapsed);
  }, [sidebarCollapsed]);

  // Remember the active session (for in-login resume) and mark this browser
  // session as belonging to the current user.
  useEffect(() => {
    if (sessionId && user && accountId) {
      setActiveSessionId(sessionId, user.id, accountId);
    }
  }, [sessionId, user, accountId]);

  // When the user lands on a bare /chat (no ?session=) and is navigating within
  // the same login, resume the active session. A new login / fresh browser
  // session is left on the empty composer — no session is created until the
  // first message is sent (see onCreateSession below), so we don't accumulate
  // empty "Untitled" sessions on every visit.
  // Runs once per (user, account) pair — bootedForRef tracks the key so that
  // switching accounts triggers a fresh resume attempt for the new account.
  useEffect(() => {
    if (rawSession || !user) return;

    const key = accountId ? `${user.id}:${accountId}` : user.id;
    if (bootedForRef.current === key) return;
    // Mark immediately so the effect does not re-fire if no stored session is
    // found (prevents a loop when no session exists for the current account).
    bootedForRef.current = key;

    const stored = getActiveSessionId(user.id, accountId ?? undefined);
    if (stored) {
      // getActiveSessionId already validates via SESSION_ID_RE internally.
      navigate(`/chat?session=${encodeURIComponent(stored)}`, {
        replace: true,
      });
    }
  }, [rawSession, user, accountId, navigate]);

  // Lazily create a session on the first message (ChatInterface calls this when
  // it has no sessionId). Creates the side-table row and returns the new id
  // WITHOUT navigating, so ChatInterface can guard its history-load before the
  // URL changes; onSessionStarted then moves the URL to ?session=<id>.
  const onCreateSession = useCallback(async (): Promise<string | null> => {
    if (!accountId) return null;
    try {
      const info = await createChatConversation({ account_id: accountId });
      const id = info?.session_id;
      if (!id || !SESSION_ID_RE.test(id)) return null;
      queryClient.invalidateQueries({ queryKey: [CHAT_SESSIONS_QUERY_KEY] });
      return id;
    } catch {
      return null;
    }
  }, [accountId, queryClient]);

  const onSessionStarted = useCallback(
    (id: string) => {
      if (!SESSION_ID_RE.test(id)) return; // defence-in-depth: reject invalid ids
      navigate(`/chat?session=${encodeURIComponent(id)}`, { replace: true });
    },
    [navigate],
  );

  // Called mid-stream when a pending_ session id resolves to the real Vertex id.
  // Swaps the URL and the durable resume marker so that any future resume
  // (tab reload, mini-widget, sidebar navigation) finds the real session (CH-62).
  const onSessionResolved = useCallback(
    (realId: string) => {
      // Apply the same format guard used at every other id entry point so an
      // unexpected server value cannot pollute the URL or localStorage (CH-62).
      if (!SESSION_ID_RE.test(realId)) return;
      navigate(`/chat?session=${encodeURIComponent(realId)}`, {
        replace: true,
      });
      // Persist through the shared active-session store so the mini-widget
      // (which reads getActiveSessionId) resumes the reconciled real id —
      // account-scoped to match the boot effect. The pending_ guard lives in
      // setActiveSessionId (CH-62 ⇄ CH-61 integration).
      if (user) setActiveSessionId(realId, user.id, accountId ?? undefined);
    },
    [navigate, user, accountId],
  );

  // Emit the page-view telemetry span once on mount.
  useEffect(() => {
    emitPageView("chat.page.render", {
      session_id: sessionId,
      view: viewState,
    });
    // Intentionally empty dep array — fires once on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Left: Sessions sidebar */}
      <SessionsSidebar
        accountId={accountId}
        currentSessionId={sessionId ? toChatSessionId(sessionId) : null}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        onSessionSelect={(id) => {
          const params = new URLSearchParams({ session: id });
          navigate(`/chat?${params}`);
        }}
        onNewSession={() =>
          createSession.mutate({ account_id: accountId ?? undefined })
        }
        isNewSessionPending={createSession.isPending}
      />

      {/* Right: Main content area */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        {/* Header: view-toggle button */}
        <div
          data-slot="view-toggle"
          className="mx-6 mt-6 mb-2 flex items-center"
        >
          <Button
            variant="outline"
            aria-label="Toggle view"
            onClick={() =>
              setViewState((v) => (v === "message" ? "status" : "message"))
            }
            className="gap-2 rounded-[var(--radius-pill)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-5 py-2.5 text-[var(--text-body-sm)] font-bold text-[var(--color-text-tertiary)] hover:border-[var(--color-teal-300)] hover:text-[var(--color-teal-500)] hover:-translate-y-0.5 transition-all"
            style={{
              transitionTimingFunction: "var(--ease-bounce)",
              transitionDuration: "var(--duration-default)",
            }}
          >
            <ArrowLeftRight className="size-4" />
            {viewState === "message" ? "Session Status" : "Chat"}
          </Button>
        </div>

        {/* Body slot — CH-23 (ChatInterface) or CH-PRD-04 (SessionStatusView) */}
        <div
          data-slot="chat-body"
          className="flex-1 min-h-0 overflow-hidden px-6 flex flex-col"
        >
          {viewState === "message" ? (
            <ChatInterface
              sessionId={sessionId ?? undefined}
              onCreateSession={onCreateSession}
              onSessionStarted={onSessionStarted}
              onSessionResolved={onSessionResolved}
            />
          ) : (
            // TODO: replace this placeholder with the full SessionStatusView once it ships (CH-PRD-04); ArtifactsPanel and TodoListsPanel will move into that surface.
            <div className="overflow-y-auto h-full space-y-4 py-2">
              <ArtifactsPanel
                sessionId={sessionId ? toChatSessionId(sessionId) : null}
              />
              <TodoListsPanel
                sessionId={sessionId ? toChatSessionId(sessionId) : null}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
