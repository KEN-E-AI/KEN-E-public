import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Send, Sparkles, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ThinkingBlock } from "./ThinkingBlock";
import { ArtifactBlock } from "./ArtifactBlock";
import { Settings2 } from "lucide-react";
import { ChatArtifactRenderer } from "./ChatArtifactRenderer";
import { ChartSettingsPopover } from "./ChartSettingsPopover";
import type { ArtifactConfig } from "./ChartSettingsPopover";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { AccountId } from "@/lib/branded-types";
import { ChatMarkdown } from "./ChatMarkdown";
import { useOrgStatus } from "@/hooks/useOrgStatus";
import { useMarkRead } from "@/hooks/useMarkRead";
import { cn } from "@/lib/utils";
import type { Artifact } from "@/lib/chatApi";
import { useChatStream } from "@/contexts/ChatStreamContext";
import type { Message } from "@/contexts/ChatStreamContext";

type TextSize = "small" | "medium" | "large";

type ChatInterfaceProps = {
  sessionId?: string;
  // Account the chat turn is scoped to. Forwarded to streamChatCompletion so the
  // completion request carries account_id — without it the backend can't write
  // the side-table title (renders "Untitled session") or its stop-stamp.
  accountId?: AccountId | null;
  // Lazily create a session on the first message when there is no sessionId.
  // Returns the new session id (without navigating) or null on failure.
  onCreateSession?: () => Promise<string | null>;
  // Called after a session is created so the parent can move the URL to it.
  onSessionStarted?: (id: string) => void;
  // Called when a pending_ session id resolves to the real id mid-stream.
  // The parent should swap the URL (?session=) and the resume marker (CH-62).
  onSessionResolved?: (realId: string) => void;
  compact?: boolean;
};

const TEXT_SIZE_CLASSES: Record<TextSize, string> = {
  small: "text-sm",
  medium: "text-base",
  large: "text-lg",
};

function ChartArtifactItem({ artifact }: { artifact: Artifact }) {
  const [config, setConfig] = useState<ArtifactConfig>({});

  const handleChange = useCallback((patch: Partial<ArtifactConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
  }, []);

  return (
    <Popover>
      <div className="relative group" data-testid="chart-artifact-item">
        <ChatArtifactRenderer
          artifact={artifact}
          viewOverride={config.viewOverride}
          color={config.color}
          showDataLabels={config.showDataLabels}
        />
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="Chart settings"
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)]"
          >
            <Settings2 className="size-3.5" />
          </button>
        </PopoverTrigger>
      </div>
      <PopoverContent align="end" className="w-[12.5rem] p-2">
        <ChartSettingsPopover config={config} onChange={handleChange} />
      </PopoverContent>
    </Popover>
  );
}

export function ChatInterface({
  sessionId,
  accountId,
  onCreateSession,
  onSessionStarted,
  onSessionResolved,
  compact = false,
}: ChatInterfaceProps) {
  const stream = useChatStream(sessionId ?? null);
  const { messages, isStreaming, liveThoughts, liveStatus, recoveryStatus } =
    stream;

  const [input, setInput] = useState("");
  const [chatTextSize, setChatTextSize] = useState<TextSize>("medium");
  const scrollRef = useRef<HTMLDivElement>(null);
  const latestAssistantRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("kene-chat-text-size");
      if (saved === "small" || saved === "medium" || saved === "large") {
        setChatTextSize(saved);
      }
    } catch {
      // sandboxed environment
    }
  }, []);

  useEffect(() => {
    const handler = (e: CustomEvent<unknown>) => {
      const detail = e.detail;
      if (detail === "small" || detail === "medium" || detail === "large") {
        setChatTextSize(detail);
      }
    };
    window.addEventListener(
      "kene-chat-text-size-change",
      handler as EventListener,
    );
    return () =>
      window.removeEventListener(
        "kene-chat-text-size-change",
        handler as EventListener,
      );
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isStreaming]);

  useEffect(() => {
    if (!isStreaming) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        stream.stop();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isStreaming, stream]);

  const { status: orgStatus } = useOrgStatus();
  const isOrgInactive = orgStatus.startsWith("inactive_");

  const lastAssistantIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant" && messages[i].id !== "intro") {
        return i;
      }
    }
    return -1;
  }, [messages]);

  useMarkRead({
    sessionId: sessionId ?? null,
    latestMessageRef: latestAssistantRef,
    latestMessageId:
      lastAssistantIndex >= 0 ? messages[lastAssistantIndex].id : null,
  });

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || isOrgInactive) return;
    setInput("");
    stream.send(trimmed, {
      onCreateSession,
      onSessionStarted,
      onSessionResolved,
      accountId,
      isOrgInactive,
    });
  }, [
    input,
    isStreaming,
    isOrgInactive,
    stream,
    onCreateSession,
    onSessionStarted,
    onSessionResolved,
    accountId,
  ]);

  const handleRetry = useCallback(
    (stoppedId: string) => {
      const idx = messages.findIndex((m) => m.id === stoppedId);
      if (idx < 1) return;
      let userMsg: Message | undefined;
      for (let i = idx - 1; i >= 0; i--) {
        if (messages[i].role === "user") {
          userMsg = messages[i];
          break;
        }
      }
      if (!userMsg) return;
      setInput(userMsg.content);
      stream.retry(stoppedId);
    },
    [messages, stream],
  );

  const textSizeClass = TEXT_SIZE_CLASSES[chatTextSize];

  // CH-71: announce stream-death recovery transitions to assistive tech. The
  // recovery messages are rendered visibly in the bubble; this mirrors them
  // into a polite live region so screen-reader users hear the reconnect /
  // recovered / timed-out outcome (the visible bubble swap alone is silent).
  const recoveryAnnouncement =
    recoveryStatus === "recovering"
      ? "Reconnecting to recover your answer…"
      : recoveryStatus === "waiting"
        ? "Connection interrupted. Waiting for the agent to finish…"
        : recoveryStatus === "recovered"
          ? "Your answer was recovered."
          : recoveryStatus === "failed"
            ? "Recovery timed out."
            : "";

  return (
    <div
      data-testid="chat-interface"
      className="flex flex-col flex-1 min-h-0 bg-[var(--color-bg-primary)]"
    >
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        data-testid="recovery-announcer"
      >
        {recoveryAnnouncement}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto" ref={scrollRef}>
        <div className={cn("space-y-4", compact ? "p-4" : "p-6")}>
          {messages.map((message, index) => (
            <div key={message.id} className="flex justify-start">
              <div
                className={compact ? "max-w-full" : "max-w-[80%]"}
                ref={
                  index === lastAssistantIndex ? latestAssistantRef : undefined
                }
                data-testid={
                  index === lastAssistantIndex
                    ? "latest-assistant-message"
                    : undefined
                }
              >
                {message.role === "user" ? (
                  // User prompt: the question carries the visual weight, as a
                  // neutral elevated card (border only in light mode).
                  <div className="rounded-[var(--radius-lg)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] dark:border-transparent px-5 py-4">
                    <p
                      className={cn(
                        textSizeClass,
                        "whitespace-pre-wrap leading-relaxed",
                      )}
                    >
                      {message.content}
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Author label — shown only for non-default (non-"model") specialist authors */}
                    {message.author && message.author !== "model" && (
                      <p className="text-xs text-muted-foreground mb-1 px-1">
                        {message.author}
                      </p>
                    )}
                    {/* Reasoning, demoted to an inline line, grouped with the response it produced */}
                    {message.reasoning && (
                      <div className="mb-2">
                        <ThinkingBlock
                          isThinking={false}
                          thoughts={message.reasoning.thoughts}
                          durationSeconds={message.reasoning.durationSeconds}
                        />
                      </div>
                    )}
                    {/* Assistant response: plain, document-like text — no card.
                        Rendered as markdown (the agent emits **bold**, lists,
                        headings, tables) instead of raw text. */}
                    <div className="px-1 py-1">
                      {message.recoveryNotice && (
                        <p className="text-[11px] text-[var(--color-text-tertiary)] italic mb-1">
                          {message.recoveryNotice}
                        </p>
                      )}
                      <ChatMarkdown
                        content={message.content}
                        className={cn(textSizeClass, "leading-relaxed")}
                      />
                      {message.artifacts && message.artifacts.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {message.artifacts.map((a) => (
                            <ArtifactBlock
                              key={a.filename}
                              filename={a.filename}
                              mime_type={a.mime_type}
                            />
                          ))}
                        </div>
                      )}
                      {message.chartArtifacts &&
                        message.chartArtifacts.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {message.chartArtifacts.map((artifact, idx) => (
                              <ChartArtifactItem
                                key={`${message.id}-chart-${idx}`}
                                artifact={artifact}
                              />
                            ))}
                          </div>
                        )}
                      {message.stopped && (
                        <button
                          onClick={() => handleRetry(message.id)}
                          disabled={isStreaming}
                          className="flex items-center gap-1.5 px-3 py-1.5 mt-1 rounded-[var(--radius-md)] text-[var(--text-caption)] text-[var(--color-text-secondary)] hover:text-[var(--color-violet-500)] hover:bg-[var(--color-violet-500)]/10 border border-[var(--color-border-default)] hover:border-[var(--color-violet-500)]/40 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none"
                        >
                          <RotateCcw className="size-3" />
                          <span>Retry</span>
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}

          {isStreaming && (
            <div className="flex justify-start">
              <div className={compact ? "max-w-full" : "max-w-[80%]"}>
                <ThinkingBlock
                  isThinking={true}
                  thoughts={liveThoughts}
                  onStop={stream.stop}
                  currentStatusLabel={liveStatus ?? undefined}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div
        className={cn("shrink-0", compact ? "p-4" : "p-6")}
        style={{ borderTop: "2px dashed var(--color-border-default)" }}
      >
        <div className="flex gap-3">
          <Textarea
            placeholder={
              isStreaming
                ? "Waiting for response..."
                : "Ask me anything about your marketing campaigns..."
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            className={cn(
              "resize-none rounded-[var(--radius-md)]",
              compact ? "min-h-[2.5rem]" : "min-h-[3.75rem]",
            )}
            disabled={isStreaming || isOrgInactive}
            aria-label="Chat input"
          />
          <Button
            onClick={handleSend}
            size="icon"
            className={cn("shrink-0", compact ? "size-11" : "size-[3.75rem]")}
            disabled={isStreaming || isOrgInactive}
            aria-label="Send message"
          >
            {isStreaming ? (
              <Loader2 className="size-5 animate-spin" />
            ) : (
              <Send className="size-5" />
            )}
          </Button>
        </div>
        {!compact && (
          <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-3 flex items-center gap-2">
            <Sparkles className="size-3" />
            {isOrgInactive
              ? "Your subscription is inactive. Please update your billing."
              : "Tip: Ask me to create campaigns, analyze data, or set up automations"}
          </p>
        )}
      </div>
    </div>
  );
}
