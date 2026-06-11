import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Send, Sparkles, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ThinkingBlock } from "./ThinkingBlock";
import { ArtifactBlock } from "./ArtifactBlock";
import {
  getConversationHistory,
  isPendingSessionId,
  streamChatCompletion,
  StreamInterruptedError,
} from "@/lib/chatApi";
import type { Artifact, ChatMessage, StreamEvent } from "@/lib/chatApi";
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
import {
  parseConversationHistory,
  extractAnswerAfterLastUserMessage,
} from "@/lib/parseConversationHistory";
import { ChatMarkdown } from "./ChatMarkdown";
import {
  chatHistoryQueryKey,
  chatHistoryQueryOptions,
} from "@/hooks/useChatHistory";
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
  chartArtifacts?: Artifact[];
  author?: string;
  recoveryNotice?: string;
};

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

const INTRO_CONTENT =
  "Hi! I'm your KEN-E AI assistant. I can help you build marketing campaigns, analyze performance, create workflows, and manage your calendar. What would you like to work on?";

// Factory (not a shared constant) so each reset gets a fresh `timestamp` and a
// new object identity — reused by the initial state and by the session-switch
// reset below.
function makeIntroMessage(): Message {
  return {
    id: "intro",
    role: "assistant",
    content: INTRO_CONTENT,
    timestamp: new Date(),
  };
}

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
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<Message[]>(() => [
    makeIntroMessage(),
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
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  // Ref mirrors liveStatus so handleSend (a stable useCallback) can check
  // the current value without liveStatus appearing in its dep array.
  const liveStatusRef = useRef<string | null>(null);
  const [recoveryStatus, setRecoveryStatus] = useState<
    "idle" | "recovering" | "recovered" | "waiting" | "failed"
  >("idle");
  const recoveryPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const handleStopRef = useRef<() => void>(() => {});
  const latestAssistantRef = useRef<HTMLDivElement | null>(null);
  // Session ids created from within this component (first-message lazy create).
  // Their history must NOT be reloaded — the live turn is already in `messages`,
  // and a backend fetch could clobber the in-flight stream.
  const locallyCreatedRef = useRef<Set<string>>(new Set());
  // Monotonic turn counter, bumped at the start of every send. The history-load
  // effect captures its value at start and bails if it changed before the fetch
  // resolved — so a slow history fetch can never clobber a turn the user began
  // while it was in flight (open-session-then-send race).
  const turnSeqRef = useRef(0);

  const clearRecoveryPoll = useCallback(() => {
    if (recoveryPollRef.current !== null) {
      clearInterval(recoveryPollRef.current);
      recoveryPollRef.current = null;
    }
  }, []);

  // Cancel any in-flight stream and recovery poll when the component unmounts
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      clearRecoveryPoll();
    };
  }, [clearRecoveryPoll]);

  // Load prior messages when a session is opened or switched. Always resets the
  // view to the selected session so switching never leaves the previous
  // conversation on screen (CH Q4/Q5):
  //   - locally-created session with an in-flight stream → untouched (the live
  //     turn is already in `messages`; a fetch would clobber it);
  //   - no session, or a server-issued pending_ placeholder ("+ New Session")
  //     with no history yet → fresh intro, no fetch;
  //   - populated session → its history; empty session → fresh intro;
  //   - fetch error → fresh intro (never another session's stale messages).
  useEffect(() => {
    // Guard FIRST: the lazy-create / pending→real reconciliation paths add ids
    // to locallyCreatedRef (including pending_ ids), and those must not be
    // reloaded mid-stream.
    if (sessionId && locallyCreatedRef.current.has(sessionId)) return;
    if (!sessionId || isPendingSessionId(sessionId)) {
      setMessages([makeIntroMessage()]);
      return;
    }
    let cancelled = false;
    const seqAtStart = turnSeqRef.current;
    // Don't clobber a turn the user started after this effect began fetching.
    const superseded = () => cancelled || turnSeqRef.current !== seqAtStart;
    (async () => {
      try {
        // Cached/deduped via TanStack Query so the session-status toggle (which
        // remounts this component) and sidebar revisits reuse a recent fetch
        // instead of re-hitting Vertex. Each completed turn invalidates the key.
        const raw = await queryClient.fetchQuery(
          chatHistoryQueryOptions(sessionId),
        );
        if (superseded()) return;
        const parsed = parseConversationHistory(raw);
        setMessages(parsed.length > 0 ? parsed : [makeIntroMessage()]);
      } catch (err) {
        if (!superseded()) {
          console.error("Failed to load conversation history:", err);
          setMessages([makeIntroMessage()]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, queryClient]);

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

    // Cancel any recovery poll from a previous interrupted turn before starting
    // a new one, to prevent stale poll callbacks from overwriting the new turn's
    // in-flight bubbles (CH-71 High finding from code review).
    clearRecoveryPoll();

    // Mark a turn as started so an in-flight history fetch won't clobber it.
    turnSeqRef.current += 1;

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
    // Local accumulator mirrors liveThoughts so we can read the final value
    // inside setMessages without a stale closure.
    let collectedThoughts: string[] = [];
    // Multi-author fan-out: one bubble per distinct author seen in the turn.
    // Each entry holds the bubble's message ID and its accumulated text.
    // The first text event claims assistantId so the pre-created placeholder
    // is repurposed rather than left as a ghost.
    type BubbleState = { id: string; accumulated: string };
    const authorBubbleMap = new Map<string, BubbleState>();
    let firstTextAuthorSeen = false;
    // currentAssistantId tracks the most-recently updated bubble — used for
    // the stop/abort cleanup path and for attaching final reasoning.
    let currentAssistantId = assistantId;

    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        author: "model",
        timestamp: new Date(),
      },
    ]);

    let hasStreamedText = false;

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
        accountId ?? undefined,
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
        } else if (event.type === "status") {
          liveStatusRef.current = event.label;
          setLiveStatus(event.label);
        } else if (event.type === "reasoning") {
          collectedThoughts = [...collectedThoughts, event.text];
          liveThoughtsRef.current = collectedThoughts;
          setLiveThoughts(collectedThoughts);
        } else if (event.type === "artifacts") {
          // Attach artifacts to the last assistant bubble. The artifacts event
          // arrives once per turn just before [DONE]. AH-143: use targetId
          // fallback so supervisor turns (where currentAssistantId may be null
          // when the event fires) still attach to the correct bubble.
          if (event.artifacts.length > 0) {
            const targetId = currentAssistantId ?? assistantId;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === targetId
                  ? {
                      ...m,
                      chartArtifacts: [
                        ...(m.chartArtifacts ?? []),
                        ...(event.artifacts as Artifact[]),
                      ],
                    }
                  : m,
              ),
            );
          }
        } else if (event.type === "error") {
          liveStatusRef.current = null;
          setLiveStatus(null);
          if (hasStreamedText) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentAssistantId
                  ? {
                      ...m,
                      recoveryNotice:
                        "Answer received, but a follow-up step failed.",
                    }
                  : m,
              ),
            );
          } else {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentAssistantId
                  ? { ...m, content: event.message }
                  : m,
              ),
            );
          }
        } else {
          if (liveStatusRef.current !== null) {
            liveStatusRef.current = null;
            setLiveStatus(null);
          }
          const incomingAuthor = event.author ?? "model";
          if (!authorBubbleMap.has(incomingAuthor)) {
            // First time seeing this author in the turn.
            if (!firstTextAuthorSeen) {
              // Claim the pre-created placeholder bubble for this author.
              firstTextAuthorSeen = true;
              authorBubbleMap.set(incomingAuthor, {
                id: assistantId,
                accumulated: "",
              });
              if (incomingAuthor !== "model") {
                // Update the placeholder's author field.
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, author: incomingAuthor } : m,
                  ),
                );
              }
            } else {
              // Spawn a new bubble for this author.
              const newId = `asst-${crypto.randomUUID()}`;
              authorBubbleMap.set(incomingAuthor, {
                id: newId,
                accumulated: "",
              });
              setMessages((prev) => [
                ...prev,
                {
                  id: newId,
                  role: "assistant",
                  content: "",
                  author: incomingAuthor,
                  timestamp: new Date(),
                },
              ]);
            }
          }
          const bubble = authorBubbleMap.get(incomingAuthor)!;
          bubble.accumulated += event.text;
          hasStreamedText = true;
          currentAssistantId = bubble.id;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === bubble.id ? { ...m, content: bubble.accumulated } : m,
            ),
          );
        }
      }

      // Persist reasoning on the last in-flight bubble when thoughts were collected.
      const finalThoughts = collectedThoughts;
      const duration = Math.round((Date.now() - turnStartTime) / 1000);
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== currentAssistantId) return m;
          if (finalThoughts.length === 0) return m;
          return {
            ...m,
            reasoning: { thoughts: finalThoughts, durationSeconds: duration },
          };
        }),
      );
      liveStatusRef.current = null;
      setLiveStatus(null);
      setIsStreaming(false);
      // This turn added new messages (and possibly charts) the backend has now
      // persisted. Mark the cached history stale so the next mount (e.g. after
      // the session-status toggle) refetches the complete, chart-bearing turn.
      if (activeSessionId) {
        queryClient.invalidateQueries({
          queryKey: chatHistoryQueryKey(activeSessionId),
        });
      }
    } catch (err: unknown) {
      const name = (err as Error)?.name;
      liveStatusRef.current = null;
      setLiveStatus(null);

      if (name === "CanceledError" || name === "AbortError") {
        // handleStop already appended the stopped message; remove the ghost placeholder
        // (only the last in-flight bubble is a ghost — earlier finalized bubbles stay).
        setMessages((prev) => prev.filter((m) => m.id !== currentAssistantId));
        setIsStreaming(false);
        return;
      }

      if (err instanceof StreamInterruptedError) {
        const interruptedSessionId = err.sessionId;
        setIsStreaming(false);

        // #1 (CH-71): the turn this recovery belongs to. setIsStreaming(false)
        // above re-enables handleSend, so the user can start a new turn while a
        // recovery fetch is mid-flight; clearInterval stops future poll ticks but
        // cannot cancel a getConversationHistory awaited inside the current tick.
        // Each fetch result below is dropped if turnSeqRef has since advanced.
        const recoveryTurn = turnSeqRef.current;

        // #4 (CH-71): a null or pending_ placeholder id is unrecoverable — a
        // pending_ session does not exist server-side, so polling it would spin
        // for the full 5-minute budget. Surface a generic error instead.
        if (!interruptedSessionId || isPendingSessionId(interruptedSessionId)) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === currentAssistantId
                ? { ...m, content: "An error occurred. Please try again." }
                : m,
            ),
          );
          return;
        }

        // Drop the session from locallyCreatedRef so the history effect can fire.
        locallyCreatedRef.current.delete(interruptedSessionId);

        // Every bubble id created during this (now-interrupted) turn. Recovery
        // replaces all of them with a single recovered bubble so a multi-author
        // turn's partial bubbles don't linger beside the recovered answer.
        // #5 (CH-71) known limitation: extractAnswerAfterLastUserMessage returns
        // only the final assistant message, so a fan-out turn that produced
        // several specialist bubbles recovers just the last one. Acceptable for
        // a recovery path — not silent data loss; the full turn persists
        // server-side and renders in full on session reload.
        const turnBubbleIds = new Set<string>([
          assistantId,
          ...Array.from(authorBubbleMap.values()).map((b) => b.id),
        ]);
        const applyRecoveredAnswer = (content: string) => {
          setMessages((prev) => [
            ...prev.filter((m) => !turnBubbleIds.has(m.id)),
            {
              id: currentAssistantId,
              role: "assistant" as const,
              content,
              timestamp: new Date(),
              recoveryNotice: "Connection interrupted — recovered.",
            },
          ]);
          setRecoveryStatus("recovered");
        };

        setRecoveryStatus("recovering");
        try {
          // NB: getConversationHistory returns the raw { session_id, events }
          // payload — it MUST be parsed (parseConversationHistory), not treated
          // as a message array, and the answer is gated to post-date the user's
          // turn so a prior turn's answer is never shown as "recovered" (CH-71).
          const recovered = extractAnswerAfterLastUserMessage(
            await getConversationHistory(interruptedSessionId),
          );
          // #1: a new turn started while this fetch was in flight — drop the
          // stale result rather than write it into the new turn's bubbles.
          if (recoveryTurn !== turnSeqRef.current) return;
          if (recovered !== null) {
            applyRecoveredAnswer(recovered);
            return;
          }
        } catch {
          // History fetch failed; fall through to polling.
        }

        setRecoveryStatus("waiting");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === currentAssistantId
              ? {
                  ...m,
                  content:
                    "Connection interrupted — waiting for the agent to finish…",
                }
              : m,
          ),
        );

        let attempts = 0;
        const MAX_ATTEMPTS = 60;
        recoveryPollRef.current = setInterval(async () => {
          attempts += 1;
          try {
            const recovered = extractAnswerAfterLastUserMessage(
              await getConversationHistory(interruptedSessionId),
            );
            // #1: a new turn started while this tick's fetch was in flight —
            // drop the stale result (the new turn already cleared this poll).
            if (recoveryTurn !== turnSeqRef.current) return;
            if (recovered !== null) {
              clearRecoveryPoll();
              applyRecoveredAnswer(recovered);
              return;
            }
          } catch {
            // Ignore transient fetch errors; keep polling.
          }

          if (attempts >= MAX_ATTEMPTS) {
            clearRecoveryPoll();
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentAssistantId
                  ? {
                      ...m,
                      content:
                        "Recovery timed out — open the session from the sidebar to see the result if it arrives later.",
                    }
                  : m,
              ),
            );
            setRecoveryStatus("failed");
          }
        }, 5_000);

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
    accountId,
    onCreateSession,
    onSessionStarted,
    onSessionResolved,
    queryClient,
    clearRecoveryPoll,
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
                  onStop={handleStop}
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
              "resize-none rounded-[var(--radius-md)] text-base",
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
