import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeftRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { emitPageView } from "@/lib/telemetry";

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
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session");

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
      {/* Left: Sessions sidebar slot — CH-25 mounts here */}
      <div data-slot="sessions-sidebar" aria-label="Sessions sidebar">
        {/* CH-25: SessionsSidebar */}
      </div>

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

          {/* Sidebar collapse toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSidebarCollapsed((c) => !c)}
            aria-label={
              sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
            }
            className="ml-2"
          >
            {sidebarCollapsed ? "›" : "‹"}
          </Button>
        </div>

        {/* Body slot — CH-23 (ChatInterface) or CH-PRD-04 (SessionStatusView) */}
        <div
          data-slot="chat-body"
          className="flex-1 min-h-0 overflow-hidden px-6 flex flex-col"
        >
          {viewState === "message" ? (
            sessionId ? (
              <p className="text-sm text-[var(--color-text-secondary)] mt-4">
                Session: {sessionId}
              </p>
            ) : (
              <p className="text-sm text-[var(--color-text-secondary)] mt-4">
                Start a new session…
              </p>
            )
          ) : (
            // CH-PRD-04 SessionStatusView placeholder
            <p className="text-sm text-[var(--color-text-secondary)] mt-4">
              Session status — coming soon
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
