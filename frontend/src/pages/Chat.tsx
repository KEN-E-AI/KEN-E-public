import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeftRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { emitPageView } from "@/lib/telemetry";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { SessionsSidebar } from "@/components/chat/SessionsSidebar";
import { useAuth } from "@/contexts/AuthContext";
import { useCreateChatSession } from "@/hooks/useCreateChatSession";
import { toChatSessionId } from "@/lib/chatApi";
import { TodoListsPanel } from "@/components/chat/TodoListsPanel";

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

const SESSION_ID_RE = /^[a-zA-Z0-9_-]{1,128}$/;

export default function Chat() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rawSession = searchParams.get("session");
  const sessionId =
    rawSession && SESSION_ID_RE.test(rawSession) ? rawSession : null;

  const { selectedOrgAccount } = useAuth();
  const accountId = selectedOrgAccount?.accountId ?? null;
  const createSession = useCreateChatSession();

  const [viewState, setViewState] = useState<ViewState>("message");
  const [sidebarCollapsed, setSidebarCollapsed] =
    useState<boolean>(readSidebarCollapsed);
  const isFirstRender = useRef(true);

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
            <ChatInterface sessionId={sessionId ?? undefined} />
          ) : (
            // TODO: replace this placeholder with the full SessionStatusView once it ships; TodoListsPanel will move into that surface.
            <TodoListsPanel
              sessionId={sessionId ? toChatSessionId(sessionId) : null}
            />
          )}
        </div>
      </div>
    </div>
  );
}
