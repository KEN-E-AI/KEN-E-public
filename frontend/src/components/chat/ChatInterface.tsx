import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Send, Sparkles, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ThinkingBlock } from "./ThinkingBlock";
import { ArtifactBlock } from "./ArtifactBlock";
import { getConversationHistory, streamChatCompletion } from "@/lib/chatApi";
import type { ChatMessage, StreamEvent } from "@/lib/chatApi";
import { parseConversationHistory } from "@/lib/parseConversationHistory";
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

const INTRO_CONTENT =
  "Hi! I'm your KEN-E AI assistant. I can help you build marketing campaigns, analyze performance, create workflows, and manage your calendar. What would you like to work on?";

const TEXT_SIZE_CLASSES: Record<TextSize, string> = {
  small: "text-sm",
  medium: "text-base",
  large: "text-lg",
};

export function ChatInterface({
  sessionId,
  onCreateSession,
  onSessionStarted,
  onSessionResolved,
  compact = false,
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
  // Reasoning fragments accumulated during the live turn. Reset at the start of
  // each handleSend so a new turn never shows thoughts from a prior turn.
  const [liveThoughts, setLiveThoughts] = useState<string[]>([]);
  // Ref mirrors liveThoughts so handleStop (a stale closure) can read the
  // current value without being recreated on every reasoning event.
  const liveThoughtsRef = useRef<string[]>([]);
  const [chatTextSize, setChatTextSize] = useState<TextSize>("medium");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const handleStopRef = useRef<() => void>(() => {});
  const latestAssistantRef = useRef<HTMLDivElement | null>(null);
  // Session ids created from within this component (first-message lazy create).
  // Their history must NOT be reloaded — the live turn is already in `messages`,
  // and a backend fetch could clobber the in-flight stream.
  const locallyCreatedRef = useRef<Set<string>>(new Set());

  // Cancel any in-flight stream when the component unmounts
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // Load prior messages when a session is opened or switched. Keeps the intro
  // for an ephemeral (no sessionId) or brand-new (empty history) conversation.
  useEffect(() => {
    if (!sessionId) return;
    if (locallyCreatedRef.current.has(sessionId)) return; // just created here
    let cancelled = false;
    (async () => {
      try {
        const raw = await getConversationHistory(sessionId);
        if (cancelled) return;
        const parsed = parseConversationHistory(raw);
        if (parsed.length > 0) setMessages(parsed);
      } catch (err) {
        if (!cancelled)
          console.error("Failed to load conversation history:", err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

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
    // Read partial reasoning via ref so this stale closure always sees the
    // latest thoughts even though it can't depend on liveThoughts state.
    const partialThoughts = liveThoughtsRef.current;
    const stoppedMsg: Message = {
      id: `stopped-${crypto.randomUUID()}`,
      role: "assistant",
      content: "Generation was stopped by the user.",
      timestamp: new Date(),
      stopped: true,
      reasoning: { thoughts: partialThoughts, durationSeconds: duration },
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
    // Capture start time in a local variable to avoid the stale-closure problem:
    // setThinkingStartTime is async, so reading `thinkingStartTime` from the
    // closure at stream-end would give the prior turn's value.
    const turnStartTime = Date.now();
    setThinkingStartTime(turnStartTime);
    // Reset reasoning for this new turn.
    setLiveThoughts([]);
    liveThoughtsRef.current = [];

    const controller = new AbortController();
    abortRef.current = controller;

    const assistantId = `asst-${crypto.randomUUID()}`;
    let accumulated = "";
    // Local accumulator mirrors liveThoughts so we can read the final value
    // inside setMessages without a stale closure.
    let collectedThoughts: string[] = [];

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
      // First message with no session → create one now (deferred creation).
      // Guard the new id against the history-load effect BEFORE navigating, so
      // the in-flight stream below isn't clobbered by a backend history fetch.
      let activeSessionId = sessionId;
      if (!activeSessionId && onCreateSession) {
        const newId = await onCreateSession();
        if (!newId) throw new Error("SESSION_CREATE_FAILED");
        locallyCreatedRef.current.add(newId);
        activeSessionId = newId;
        onSessionStarted?.(newId);
      }

      for await (const event of streamChatCompletion(
        history,
        activeSessionId,
        undefined,
        controller.signal,
      )) {
        if (event.type === "session") {
          // Guard the real id before the parent navigates to it, so the
          // history-load effect (which fires when sessionId prop changes)
          // doesn't clobber the in-flight stream — same defense as the
          // lazy-create path above (CH-62).
          locallyCreatedRef.current.add(event.sessionId);
          activeSessionId = event.sessionId;
          onSessionResolved?.(event.sessionId);
        } else if (event.type === "reasoning") {
          collectedThoughts = [...collectedThoughts, event.text];
          liveThoughtsRef.current = collectedThoughts;
          setLiveThoughts(collectedThoughts);
        } else {
          accumulated += event.text;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: accumulated } : m,
            ),
          );
        }
      }

      // Persist reasoning on the completed message when thoughts were collected.
      const finalThoughts = collectedThoughts;
      const duration = Math.round((Date.now() - turnStartTime) / 1000);
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId) return m;
          if (finalThoughts.length === 0) return m;
          return {
            ...m,
            reasoning: { thoughts: finalThoughts, durationSeconds: duration },
          };
        }),
      );
      setIsStreaming(false);
    } catch (err: unknown) {
      const name = (err as Error)?.name;
      if (name === "CanceledError" || name === "AbortError") {
        // handleStop already appended the stopped message; remove the ghost placeholder
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        return;
      }
      const message =
        (err as Error)?.message === "SESSION_CREATE_FAILED"
          ? "Couldn't start a new session. Please try again."
          : "An error occurred. Please try again.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: message } : m,
        ),
      );
      setIsStreaming(false);
    }
  }, [
    input,
    isStreaming,
    isOrgInactive,
    messages,
    sessionId,
    onCreateSession,
    onSessionStarted,
    onSessionResolved,
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
        <div className={cn("space-y-4", compact ? "p-4" : "p-6")}>
          {messages.map((message, index) => (
            <div key={message.id} className="flex justify-start">
              <div
                className={cn(
                  compact ? "max-w-full" : "max-w-[80%]",
                  "space-y-2",
                )}
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
              <div className={compact ? "max-w-full" : "max-w-[80%]"}>
                <ThinkingBlock
                  isThinking={true}
                  thoughts={liveThoughts}
                  onStop={handleStop}
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
