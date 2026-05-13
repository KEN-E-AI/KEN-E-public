// TODO(CH-PRD-02): replace stub with real chat session integration.
// Visual shell ported from docs/figma-export/src/app/components/ChatInterface.tsx so
// CH-PRD-02 can replace internals (message state, sessionStorage persistence, mock
// thinking blocks, artifact rendering, real handlers) in place without moving the
// file. Lives in components/chat/ alongside SessionsSidebar.
//
// The stub renders the figma's intro greeting plus a disabled input row. It accepts
// the figma's prop signature (sessionId, compact) so consumers (Phase 2.3 LayoutC's
// Mini Chat Widget) compile and render correctly until the real implementation lands.

import { Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatInterfaceProps {
  sessionId?: string;
  compact?: boolean;
}

const STUB_INTRO =
  "Hi! I'm your KEN-E AI assistant. I can help you build marketing campaigns, analyze performance, create workflows, and manage your calendar. What would you like to work on?";

export function ChatInterface({
  sessionId: _sessionId,
  compact: _compact = false,
}: ChatInterfaceProps) {
  return (
    <div
      data-testid="chat-interface"
      className="flex flex-col flex-1 min-h-0 bg-[var(--color-bg-primary)]"
    >
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="space-y-4 p-6">
          <div className="flex justify-start">
            <div className="max-w-[80%] space-y-2">
              <div
                className="rounded-[var(--radius-lg)] px-5 py-4 bg-[var(--color-bg-elevated)] border-2 border-[var(--color-border-default)]"
                style={{
                  transitionTimingFunction: "var(--ease-default)",
                  transitionDuration: "var(--duration-fast)",
                }}
              >
                <p className="text-base whitespace-pre-wrap leading-relaxed">
                  {STUB_INTRO}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        className="shrink-0 p-6"
        style={{
          borderTop: "2px dashed var(--color-border-default)",
        }}
      >
        <div className="flex gap-3">
          <Textarea
            placeholder="Ask me anything about your marketing campaigns..."
            disabled
            aria-label="Chat input (disabled in stub)"
            className="min-h-[3.75rem] resize-none rounded-[var(--radius-md)]"
          />
          <Button
            disabled
            size="icon"
            aria-label="Send message"
            className="shrink-0 size-[3.75rem]"
          >
            <Send className="size-5" />
          </Button>
        </div>
        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-3 flex items-center gap-2">
          <Sparkles className="size-3" />
          Chat is disabled in the layout stub. Replaced by the real
          implementation in CH-PRD-02.
        </p>
      </div>
    </div>
  );
}
