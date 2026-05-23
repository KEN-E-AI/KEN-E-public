import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Send, Sparkles, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ThinkingBlock } from "./ThinkingBlock";
import { ArtifactBlock } from "./ArtifactBlock";
import { streamChatCompletion } from "@/lib/chatApi";
import type { ChatMessage } from "@/lib/chatApi";
import { useOrgStatus } from "@/hooks/useOrgStatus";
import { useMarkRead } from "@/hooks/useMarkRead";
import { cn } from "@/lib/utils";

type TextSize = "small" | "medium" | "large";

type MessageArtifact = {
  filename: string;
  mime_type?: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  stopped?: boolean;
  reasoning?: { thoughts: string[]; durationSeconds: number };
  artifacts?: MessageArtifact[];
};

type ChatInterfaceProps = {
  sessionId?: string;
  // TODO(CH-PRD-XX): compact mode is reserved for the mini-widget in LayoutC
  compact?: boolean;
};

const INTRO_CONTENT =
  "Hi! I'm your KEN-E AI assistant. I can help you build marketing campaigns, analyze performance, create workflows, and manage your calendar. What would you like to work on?";

const TEXT_SIZE_CLASSES: Record<TextSize, string> = {
  small: "text-sm",
  medium: "text-base",
  large: "text-lg",
};

export function ChatInterface({
  sessionId,
  compact: _compact = false,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: "intro",
      role: "assistant",
      content: INTRO_CONTENT,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingStartTime, setThinkingStartTime] = useState(0);
  const [chatTextSize, setChatTextSize] = useState<TextSize>("medium");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const handleStopRef = useRef<() => void>(() => {});
  const latestAssistantRef = useRef<HTMLDivElement | null>(null);

  // Cancel any in-flight stream when the component unmounts
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

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
        handleStopRef.current();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isStreaming]);

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

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    const duration = Math.round((Date.now() - thinkingStartTime) / 1000);
    const stoppedMsg: Message = {
      id: `stopped-${crypto.randomUUID()}`,
      role: "assistant",
      content: "Generation was stopped by the user.",
      timestamp: new Date(),
      stopped: true,
      reasoning: { thoughts: [], durationSeconds: duration },
    };
    setMessages((prev) => [...prev, stoppedMsg]);
    setIsStreaming(false);
  }, [thinkingStartTime]);

  useEffect(() => {
    handleStopRef.current = handleStop;
  }, [handleStop]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || isOrgInactive) return;

    const userMsg: Message = {
      id: `user-${crypto.randomUUID()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    // Build history before any state mutations to avoid stale closure issues
    const history: ChatMessage[] = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);
    setThinkingStartTime(Date.now());

    const controller = new AbortController();
    abortRef.current = controller;

    const assistantId = `asst-${crypto.randomUUID()}`;
    let accumulated = "";

    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
      },
    ]);

    try {
      for await (const chunk of streamChatCompletion(
        history,
        sessionId,
        undefined,
        controller.signal,
      )) {
        accumulated += chunk;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: accumulated } : m,
          ),
        );
      }
      setIsStreaming(false);
    } catch (err: unknown) {
      const name = (err as Error)?.name;
      if (name === "CanceledError" || name === "AbortError") {
        // handleStop already appended the stopped message; remove the ghost placeholder
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        return;
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: "An error occurred. Please try again." }
            : m,
        ),
      );
      setIsStreaming(false);
    }
  }, [input, isStreaming, isOrgInactive, messages, sessionId]);

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
      setMessages((prev) => prev.filter((m) => m.id !== stoppedId));
    },
    [messages],
  );

  const textSizeClass = TEXT_SIZE_CLASSES[chatTextSize];

  return (
    <div
      data-testid="chat-interface"
      className="flex flex-col flex-1 min-h-0 bg-[var(--color-bg-primary)]"
    >
      <div className="flex-1 min-h-0 overflow-y-auto" ref={scrollRef}>
        <div className="space-y-4 p-6">
          {messages.map((message, index) => (
            <div key={message.id} className="flex justify-start">
              <div
                className="max-w-[80%] space-y-2"
                ref={
                  index === lastAssistantIndex ? latestAssistantRef : undefined
                }
                data-testid={
                  index === lastAssistantIndex
                    ? "latest-assistant-message"
                    : undefined
                }
              >
                {message.reasoning && (
                  <ThinkingBlock
                    isThinking={false}
                    thoughts={message.reasoning.thoughts}
                    durationSeconds={message.reasoning.durationSeconds}
                  />
                )}
                {message.artifacts?.map((a) => (
                  <ArtifactBlock
                    key={a.filename}
                    filename={a.filename}
                    mime_type={a.mime_type}
                  />
                ))}
                <div
                  className={cn(
                    "rounded-[var(--radius-lg)] px-5 py-4 transition-all",
                    message.role === "user"
                      ? "bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]"
                      : "bg-[var(--color-bg-elevated)] border-2 border-[var(--color-border-default)]",
                  )}
                  style={{
                    transitionTimingFunction: "var(--ease-default)",
                    transitionDuration: "var(--duration-fast)",
                  }}
                >
                  <p
                    className={cn(
                      textSizeClass,
                      "whitespace-pre-wrap leading-relaxed",
                    )}
                  >
                    {message.content}
                  </p>
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
              </div>
            </div>
          ))}

          {isStreaming && (
            <div className="flex justify-start">
              <div className="max-w-[80%]">
                <ThinkingBlock
                  isThinking={true}
                  thoughts={[]}
                  onStop={handleStop}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div
        className="shrink-0 p-6"
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
            className="min-h-[3.75rem] resize-none rounded-[var(--radius-md)]"
            disabled={isStreaming || isOrgInactive}
            aria-label="Chat input"
          />
          <Button
            onClick={handleSend}
            size="icon"
            className="shrink-0 size-[3.75rem]"
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
        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-3 flex items-center gap-2">
          <Sparkles className="size-3" />
          {isOrgInactive
            ? "Your subscription is inactive. Please update your billing."
            : "Tip: Ask me to create campaigns, analyze data, or set up automations"}
        </p>
      </div>
    </div>
  );
}
