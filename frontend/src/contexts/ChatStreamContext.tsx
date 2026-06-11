import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getConversationHistory,
  isPendingSessionId,
  streamChatCompletion,
  StreamInterruptedError,
} from "@/lib/chatApi";
import type { Artifact, ChatMessage } from "@/lib/chatApi";
import type { AccountId } from "@/lib/branded-types";
import {
  parseConversationHistory,
  extractAnswerAfterLastUserMessage,
} from "@/lib/parseConversationHistory";
import {
  chatHistoryQueryKey,
  chatHistoryQueryOptions,
} from "@/hooks/useChatHistory";
import { useAuth } from "@/contexts/AuthContext";

// ─── Public types ─────────────────────────────────────────────────────────────

export type MessageArtifact = {
  filename: string;
  mime_type?: string;
};

export type Message = {
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

export type SendOptions = {
  onCreateSession?: () => Promise<string | null>;
  onSessionStarted?: (id: string) => void;
  onSessionResolved?: (realId: string) => void;
  accountId?: AccountId | null;
  isOrgInactive?: boolean;
};

// ─── Internal turn state ──────────────────────────────────────────────────────

type RecoveryStatus =
  | "idle"
  | "recovering"
  | "recovered"
  | "waiting"
  | "failed";
type StreamStatus = "idle" | "streaming" | "recovering" | "waiting" | "failed";

type TurnState = {
  messages: Message[];
  status: StreamStatus;
  liveThoughts: string[];
  liveStatus: string | null;
  thinkingStartTime: number;
  abortController: AbortController | null;
  turnSeq: number;
  locallyCreated: Set<string>;
  recoveryPollRef: ReturnType<typeof setInterval> | null;
  recoveryStatus: RecoveryStatus;
};

function makeDefaultTurnState(): TurnState {
  return {
    messages: [makeIntroMessage()],
    status: "idle",
    liveThoughts: [],
    liveStatus: null,
    thinkingStartTime: 0,
    abortController: null,
    turnSeq: 0,
    locallyCreated: new Set(),
    recoveryPollRef: null,
    recoveryStatus: "idle",
  };
}

// ─── Intro message factory ────────────────────────────────────────────────────

const INTRO_CONTENT =
  "Hi! I'm your KEN-E AI assistant. I can help you build marketing campaigns, analyze performance, create workflows, and manage your calendar. What would you like to work on?";

function makeIntroMessage(): Message {
  return {
    id: "intro",
    role: "assistant",
    content: INTRO_CONTENT,
    timestamp: new Date(),
  };
}

// ─── Context shape ────────────────────────────────────────────────────────────

type ChatStreamContextValue = {
  getState: (key: string) => TurnState;
  send: (key: string, input: string, opts: SendOptions) => void;
  stop: (key: string) => void;
  retry: (key: string, stoppedId: string) => void;
  subscribe: (key: string) => void;
  unsubscribe: (key: string) => void;
  loadHistoryIfNeeded: (key: string) => void;
  // version changes on every state mutation to trigger consumer re-renders
  version: number;
};

const ChatStreamContext = createContext<ChatStreamContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ChatStreamProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { user, selectedOrgAccount } = useAuth();
  const accountId = selectedOrgAccount?.accountId ?? null;

  // Force re-renders via a counter. Every time we mutate the Map we bump this.
  const [version, forceUpdate] = useReducer((x: number) => x + 1, 0);

  const mapRef = useRef<Map<string, TurnState>>(new Map());
  const refCountRef = useRef<Map<string, number>>(new Map());

  // Track the previous accountId to detect changes
  const prevAccountIdRef = useRef<typeof accountId>(null);

  // Global set of session IDs created from within this provider (lazy create /
  // pending→real reconciliation). Prevents the history-load effect from firing
  // for in-flight or just-completed streams. This set is NEVER cleared after
  // stream completion — it persists for the provider lifecycle so that a fast
  // rerender (e.g. onSessionStarted triggers prop change) cannot race the stream
  // completion and clobber in-flight bubbles. Cleared only on account switch or
  // sign-out.
  const globalLocallyCreatedRef = useRef<Set<string>>(new Set());
  // Declared here (before the effects that reference it) so the reference is
  // always defined when the auth-teardown and account-isolation effects run.
  const historyLoadedRef = useRef<Set<string>>(new Set());

  function getOrCreate(key: string): TurnState {
    if (!mapRef.current.has(key)) {
      mapRef.current.set(key, makeDefaultTurnState());
    }
    return mapRef.current.get(key)!;
  }

  function setState(key: string, updater: (prev: TurnState) => TurnState) {
    const prev = mapRef.current.get(key) ?? makeDefaultTurnState();
    mapRef.current.set(key, updater(prev));
    forceUpdate();
  }

  // ─── Auth teardown: abort all on sign-out ────────────────────────────────
  const prevUserRef = useRef(user);
  useEffect(() => {
    const prevUser = prevUserRef.current;
    prevUserRef.current = user;
    if (prevUser && !user) {
      // User signed out — abort all running streams
      for (const [key, state] of mapRef.current.entries()) {
        if (state.abortController) {
          state.abortController.abort();
        }
        if (state.recoveryPollRef !== null) {
          clearInterval(state.recoveryPollRef);
        }
        mapRef.current.delete(key);
      }
      globalLocallyCreatedRef.current.clear();
      historyLoadedRef.current.clear();
      forceUpdate();
    }
  }, [user]);

  // ─── Account isolation: evict map on accountId change ───────────────────
  useEffect(() => {
    const prevAccountId = prevAccountIdRef.current;
    prevAccountIdRef.current = accountId;

    if (prevAccountId && accountId && prevAccountId !== accountId) {
      // Account switched — evict all entries
      for (const [key, state] of mapRef.current.entries()) {
        if (state.abortController) {
          state.abortController.abort();
        }
        if (state.recoveryPollRef !== null) {
          clearInterval(state.recoveryPollRef);
        }
        mapRef.current.delete(key);
      }
      globalLocallyCreatedRef.current.clear();
      historyLoadedRef.current.clear();
      forceUpdate();
    }
  }, [accountId]);

  // ─── reKey: atomically move a TurnState from one key to another ──────────
  // Called when the session id becomes known mid-stream (onCreateSession or
  // a "session" SSE event), so the state is findable by the real id that the
  // subscriber's useChatStream(sessionId) will use after the URL updates.
  function reKey(oldKey: string, newKey: string) {
    if (oldKey === newKey) return;
    const state = mapRef.current.get(oldKey);
    if (state) {
      mapRef.current.set(newKey, state);
      mapRef.current.delete(oldKey);
    }
    // Transfer refcount so the existing subscriber count is preserved.
    const count = refCountRef.current.get(oldKey) ?? 0;
    if (count > 0) {
      refCountRef.current.set(newKey, count);
    }
    refCountRef.current.delete(oldKey);
    // NOTE: historyLoadedRef and globalLocallyCreatedRef are NOT transferred
    // here — they are keyed by the real session id and managed by the callers.
  }

  // ─── subscribe / unsubscribe ─────────────────────────────────────────────

  function subscribe(key: string) {
    const count = refCountRef.current.get(key) ?? 0;
    refCountRef.current.set(key, count + 1);

    if (count === 0) {
      // Ensure TurnState exists.
      getOrCreate(key);
      // History load is triggered by loadHistoryIfNeeded (called from
      // useChatStream's effect), not here, so that the caller's effect runs
      // after pending microtasks from waitFor have flushed — matching the
      // original ChatInterface.tsx useEffect([sessionId]) timing.
    }
  }

  function loadHistoryIfNeeded(key: string) {
    if (!key || isPendingSessionId(key)) return;
    // Blocked if either guard is present (locally created OR already loaded).
    // globalLocallyCreatedRef: set when onCreateSession/session SSE creates a
    //   real session id from within this provider. Cleared by eviction.
    // historyLoadedRef: set inside loadHistory to prevent duplicate fetches.
    //   Cleared by eviction.
    if (globalLocallyCreatedRef.current.has(key)) return;
    if (historyLoadedRef.current.has(key)) return;
    loadHistory(key);
  }

  function unsubscribe(key: string) {
    const count = refCountRef.current.get(key) ?? 1;
    const next = Math.max(0, count - 1);
    refCountRef.current.set(key, next);

    if (next === 0) {
      // Schedule eviction in a microtask
      queueMicrotask(() => {
        const currentCount = refCountRef.current.get(key) ?? 0;
        if (currentCount > 0) return; // A new subscriber appeared
        const state = mapRef.current.get(key);
        if (!state) return;
        // Only evict idle entries
        if (state.status === "idle") {
          mapRef.current.delete(key);
          refCountRef.current.delete(key);
          // Clear both guards on eviction so that history CAN reload if the
          // user comes back to this session later (after it was evicted).
          globalLocallyCreatedRef.current.delete(key);
          historyLoadedRef.current.delete(key);
          // No forceUpdate needed — no subscribers to re-render
        }
      });
    }
  }

  // ─── History load ─────────────────────────────────────────────────────────

  function loadHistory(sessionId: string) {
    if (!sessionId) return;
    // Already initiated or in-progress
    if (historyLoadedRef.current.has(sessionId)) return;

    const state = mapRef.current.get(sessionId);
    if (!state) return;

    // Don't reload if locally created (stream in-flight or just completed)
    if (state.locallyCreated.has(sessionId)) return;

    historyLoadedRef.current.add(sessionId);

    // Capture current turnSeq to detect superseding
    const seqAtStart = state.turnSeq;
    const superseded = () => {
      const current = mapRef.current.get(sessionId);
      return !current || current.turnSeq !== seqAtStart;
    };

    (async () => {
      try {
        const raw = await queryClient.fetchQuery(
          chatHistoryQueryOptions(sessionId),
        );
        if (superseded()) return;
        const parsed = parseConversationHistory(raw);
        setState(sessionId, (s) => ({
          ...s,
          messages: parsed.length > 0 ? parsed : [makeIntroMessage()],
        }));
      } catch (err) {
        if (!superseded()) {
          console.error("Failed to load conversation history:", err);
          setState(sessionId, (s) => ({
            ...s,
            messages: [makeIntroMessage()],
          }));
        }
      }
    })();
  }

  // ─── stop ─────────────────────────────────────────────────────────────────

  function stop(key: string) {
    const state = mapRef.current.get(key);
    if (!state) return;

    state.abortController?.abort();
    const duration = Math.round((Date.now() - state.thinkingStartTime) / 1000);
    // Read partial thoughts from the current state
    const partialThoughts = mapRef.current.get(key)?.liveThoughts ?? [];
    const stoppedMsg: Message = {
      id: `stopped-${crypto.randomUUID()}`,
      role: "assistant",
      content: "Generation was stopped by the user.",
      timestamp: new Date(),
      stopped: true,
      reasoning: { thoughts: partialThoughts, durationSeconds: duration },
    };

    setState(key, (s) => ({
      ...s,
      abortController: null,
      messages: [...s.messages, stoppedMsg],
      status: "idle",
      liveThoughts: [],
      liveStatus: null,
    }));
  }

  // ─── retry ────────────────────────────────────────────────────────────────

  function retry(key: string, stoppedId: string) {
    setState(key, (s) => ({
      ...s,
      messages: s.messages.filter((m) => m.id !== stoppedId),
    }));
  }

  // ─── send ─────────────────────────────────────────────────────────────────

  function send(key: string, input: string, opts: SendOptions) {
    const trimmed = input.trim();
    if (!trimmed || opts.isOrgInactive) return;

    // Ensure the key exists in the map (may be "" for no-session)
    const state = getOrCreate(key);
    if (state.status === "streaming") return;

    // Cancel any stale recovery poll
    if (state.recoveryPollRef !== null) {
      clearInterval(state.recoveryPollRef);
    }

    // Bump turn sequence
    const newTurnSeq = state.turnSeq + 1;

    const userMsg: Message = {
      id: `user-${crypto.randomUUID()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    // Build history snapshot before mutating state
    const history: ChatMessage[] = [...state.messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const assistantId = `asst-${crypto.randomUUID()}`;
    const turnStartTime = Date.now();
    const controller = new AbortController();

    setState(key, (s) => ({
      ...s,
      messages: [
        ...s.messages,
        userMsg,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          author: "model",
          timestamp: new Date(),
        },
      ],
      status: "streaming",
      thinkingStartTime: turnStartTime,
      liveThoughts: [],
      liveStatus: null,
      abortController: controller,
      turnSeq: newTurnSeq,
      recoveryPollRef: null,
      recoveryStatus: "idle",
    }));

    // Run the async stream logic
    runStream(
      key,
      history,
      assistantId,
      controller,
      turnStartTime,
      newTurnSeq,
      opts,
    );
  }

  // ─── runStream ────────────────────────────────────────────────────────────

  async function runStream(
    key: string,
    history: ChatMessage[],
    assistantId: string,
    controller: AbortController,
    turnStartTime: number,
    turnSeq: number,
    opts: SendOptions,
  ) {
    const {
      onCreateSession,
      onSessionStarted,
      onSessionResolved,
      accountId: optsAccountId,
    } = opts;

    // activeKey tracks the current Map key for this stream. It starts as `key`
    // (the caller's key: "" for no-session, or the real session id for existing
    // sessions). When onCreateSession resolves a real id or a "session" SSE
    // event reconciles pending_→real, we call reKey() and update activeKey so
    // all subsequent setState calls land under the real id. Without this, the
    // TurnState would stay under "" while ChatInterface re-renders with
    // sessionId=realId and getState(realId) returns default state.
    let activeKey = key;

    // Per-turn local accumulators (closure variables, not React state)
    let collectedThoughts: string[] = [];
    type BubbleState = { id: string; accumulated: string };
    const authorBubbleMap = new Map<string, BubbleState>();
    let firstTextAuthorSeen = false;
    let currentAssistantId = assistantId;
    let hasStreamedText = false;

    // Closes over `activeKey` (let) — always checks the current key.
    const isSuperseded = () => {
      const s = mapRef.current.get(activeKey);
      return !s || s.turnSeq !== turnSeq;
    };

    try {
      // Determine active session id from the key.
      // An empty key or a pending-prefixed key means no server session yet.
      let activeSessionId: string | undefined =
        key && !isPendingSessionId(key) ? key : undefined;

      if (!activeSessionId && onCreateSession) {
        const newId = await onCreateSession();
        if (!newId) throw new Error("SESSION_CREATE_FAILED");

        // Re-key BEFORE calling onSessionStarted so that when navigation fires
        // and ChatInterface re-renders with sessionId=newId, getState(newId)
        // finds the in-flight TurnState rather than returning default state.
        reKey(activeKey, newId);
        activeKey = newId;

        // Guard: mark the new id as locally created before navigating so the
        // history-load effect (which fires when sessionId prop changes) doesn't
        // clobber the in-flight stream.
        globalLocallyCreatedRef.current.add(newId);
        historyLoadedRef.current.add(newId);
        setState(activeKey, (s) => {
          const newSet = new Set(s.locallyCreated);
          newSet.add(newId);
          return { ...s, locallyCreated: newSet };
        });
        activeSessionId = newId;
        if (!isSuperseded()) onSessionStarted?.(newId);
      }

      for await (const event of streamChatCompletion(
        history,
        activeSessionId,
        (optsAccountId ?? undefined) as string | undefined,
        controller.signal,
      )) {
        if (isSuperseded()) break;

        if (event.type === "session") {
          const realId = event.sessionId;
          // Re-key BEFORE calling onSessionResolved so navigation finds the
          // TurnState under the real id.
          if (activeKey !== realId) {
            reKey(activeKey, realId);
            activeKey = realId;
          }
          // Guard real id before parent navigates
          globalLocallyCreatedRef.current.add(realId);
          historyLoadedRef.current.add(realId);
          setState(activeKey, (s) => {
            const newSet = new Set(s.locallyCreated);
            newSet.add(realId);
            return { ...s, locallyCreated: newSet };
          });
          activeSessionId = realId;
          onSessionResolved?.(realId);
        } else if (event.type === "status") {
          setState(activeKey, (s) => ({ ...s, liveStatus: event.label }));
        } else if (event.type === "reasoning") {
          collectedThoughts = [...collectedThoughts, event.text];
          const snapshot = collectedThoughts;
          setState(activeKey, (s) => ({
            ...s,
            liveThoughts: snapshot,
          }));
        } else if (event.type === "artifacts") {
          if (event.artifacts.length > 0) {
            const targetId = currentAssistantId ?? assistantId;
            setState(activeKey, (s) => ({
              ...s,
              messages: s.messages.map((m) =>
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
            }));
          }
        } else if (event.type === "error") {
          if (hasStreamedText) {
            setState(activeKey, (s) => ({
              ...s,
              liveStatus: null,
              messages: s.messages.map((m) =>
                m.id === currentAssistantId
                  ? {
                      ...m,
                      recoveryNotice:
                        "Answer received, but a follow-up step failed.",
                    }
                  : m,
              ),
            }));
          } else {
            setState(activeKey, (s) => ({
              ...s,
              liveStatus: null,
              messages: s.messages.map((m) =>
                m.id === currentAssistantId
                  ? { ...m, content: event.message }
                  : m,
              ),
            }));
          }
        } else {
          // Text event
          // Clear liveStatus on first text event
          if (mapRef.current.get(activeKey)?.liveStatus !== null) {
            setState(activeKey, (s) => ({ ...s, liveStatus: null }));
          }

          const incomingAuthor = event.author ?? "model";
          if (!authorBubbleMap.has(incomingAuthor)) {
            if (!firstTextAuthorSeen) {
              firstTextAuthorSeen = true;
              authorBubbleMap.set(incomingAuthor, {
                id: assistantId,
                accumulated: "",
              });
              if (incomingAuthor !== "model") {
                // Update placeholder's author field
                setState(activeKey, (s) => ({
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === assistantId ? { ...m, author: incomingAuthor } : m,
                  ),
                }));
              }
            } else {
              // Spawn a new bubble for this author
              const newId = `asst-${crypto.randomUUID()}`;
              authorBubbleMap.set(incomingAuthor, {
                id: newId,
                accumulated: "",
              });
              setState(activeKey, (s) => ({
                ...s,
                messages: [
                  ...s.messages,
                  {
                    id: newId,
                    role: "assistant",
                    content: "",
                    author: incomingAuthor,
                    timestamp: new Date(),
                  },
                ],
              }));
            }
          }

          const bubble = authorBubbleMap.get(incomingAuthor)!;
          bubble.accumulated += event.text;
          hasStreamedText = true;
          currentAssistantId = bubble.id;

          const bubbleId = bubble.id;
          const accumulated = bubble.accumulated;
          setState(activeKey, (s) => ({
            ...s,
            messages: s.messages.map((m) =>
              m.id === bubbleId ? { ...m, content: accumulated } : m,
            ),
          }));
        }
      }

      if (isSuperseded()) return;

      // Persist reasoning on final bubble
      const finalThoughts = collectedThoughts;
      const duration = Math.round((Date.now() - turnStartTime) / 1000);
      setState(activeKey, (s) => ({
        ...s,
        status: "idle",
        liveStatus: null,
        liveThoughts: [],
        abortController: null,
        messages: s.messages.map((m) => {
          if (m.id !== currentAssistantId) return m;
          if (finalThoughts.length === 0) return m;
          return {
            ...m,
            reasoning: { thoughts: finalThoughts, durationSeconds: duration },
          };
        }),
      }));

      // Invalidate history cache so next open gets fresh data
      if (activeSessionId) {
        queryClient.invalidateQueries({
          queryKey: chatHistoryQueryKey(activeSessionId),
        });
        // historyLoadedRef and globalLocallyCreatedRef are intentionally NOT
        // cleared here. They persist until the session is evicted + re-subscribed
        // (in subscribe(), where wasEvicted=true clears them). This prevents a
        // race between stream completion and a fast rerender (e.g., the parent
        // calling onSessionStarted immediately) from triggering a history reload
        // that would clobber the in-flight or just-completed turn.
      }
    } catch (err: unknown) {
      if (isSuperseded()) return;

      const name = (err as Error)?.name;

      if (name === "CanceledError" || name === "AbortError") {
        // handleStop already appended the stopped message; remove the ghost placeholder
        setState(activeKey, (s) => ({
          ...s,
          status: "idle",
          liveStatus: null,
          abortController: null,
          messages: s.messages.filter((m) => m.id !== currentAssistantId),
        }));
        return;
      }

      if (err instanceof StreamInterruptedError) {
        const interruptedSessionId = err.sessionId;

        setState(activeKey, (s) => ({
          ...s,
          status: "idle",
          liveStatus: null,
          abortController: null,
        }));

        const recoveryTurn = turnSeq;

        if (!interruptedSessionId || isPendingSessionId(interruptedSessionId)) {
          setState(activeKey, (s) => ({
            ...s,
            messages: s.messages.map((m) =>
              m.id === currentAssistantId
                ? { ...m, content: "An error occurred. Please try again." }
                : m,
            ),
          }));
          return;
        }

        // Drop from locallyCreated so history effect can fire after recovery
        setState(activeKey, (s) => {
          const newSet = new Set(s.locallyCreated);
          newSet.delete(interruptedSessionId);
          return { ...s, locallyCreated: newSet };
        });

        const turnBubbleIds = new Set<string>([
          assistantId,
          ...Array.from(authorBubbleMap.values()).map((b) => b.id),
        ]);

        const applyRecoveredAnswer = (content: string) => {
          if (isSuperseded()) return;
          const currentTurnSeq = mapRef.current.get(activeKey)?.turnSeq;
          if (currentTurnSeq !== recoveryTurn) return;
          setState(activeKey, (s) => ({
            ...s,
            recoveryStatus: "recovered",
            messages: [
              ...s.messages.filter((m) => !turnBubbleIds.has(m.id)),
              {
                id: currentAssistantId,
                role: "assistant" as const,
                content,
                timestamp: new Date(),
                recoveryNotice: "Connection interrupted — recovered.",
              },
            ],
          }));
        };

        setState(activeKey, (s) => ({
          ...s,
          recoveryStatus: "recovering",
          status: "recovering",
        }));

        try {
          const recovered = extractAnswerAfterLastUserMessage(
            await getConversationHistory(interruptedSessionId),
          );
          if (isSuperseded()) return;
          const currentTurnSeq = mapRef.current.get(activeKey)?.turnSeq;
          if (currentTurnSeq !== recoveryTurn) return;
          if (recovered !== null) {
            applyRecoveredAnswer(recovered);
            return;
          }
        } catch {
          // History fetch failed; fall through to polling
        }

        if (isSuperseded()) return;
        const currentTurnSeqCheck = mapRef.current.get(activeKey)?.turnSeq;
        if (currentTurnSeqCheck !== recoveryTurn) return;

        setState(activeKey, (s) => ({
          ...s,
          recoveryStatus: "waiting",
          status: "waiting",
          messages: s.messages.map((m) =>
            m.id === currentAssistantId
              ? {
                  ...m,
                  content:
                    "Connection interrupted — waiting for the agent to finish…",
                }
              : m,
          ),
        }));

        let attempts = 0;
        const MAX_ATTEMPTS = 60;
        const pollId = setInterval(async () => {
          attempts += 1;

          if (isSuperseded()) {
            clearInterval(pollId);
            return;
          }
          const currentTurnSeqPoll = mapRef.current.get(activeKey)?.turnSeq;
          if (currentTurnSeqPoll !== recoveryTurn) {
            clearInterval(pollId);
            return;
          }

          try {
            const recovered = extractAnswerAfterLastUserMessage(
              await getConversationHistory(interruptedSessionId),
            );
            if (isSuperseded()) return;
            const currentTurnSeqAfterFetch =
              mapRef.current.get(activeKey)?.turnSeq;
            if (currentTurnSeqAfterFetch !== recoveryTurn) return;
            if (recovered !== null) {
              clearInterval(pollId);
              setState(activeKey, (s) => ({ ...s, recoveryPollRef: null }));
              applyRecoveredAnswer(recovered);
              return;
            }
          } catch {
            // Ignore transient fetch errors
          }

          if (attempts >= MAX_ATTEMPTS) {
            clearInterval(pollId);
            setState(activeKey, (s) => {
              if (s.turnSeq !== recoveryTurn) return s;
              return {
                ...s,
                recoveryPollRef: null,
                recoveryStatus: "failed",
                status: "failed",
                messages: s.messages.map((m) =>
                  m.id === currentAssistantId
                    ? {
                        ...m,
                        content:
                          "Recovery timed out — open the session from the sidebar to see the result if it arrives later.",
                      }
                    : m,
                ),
              };
            });
          }
        }, 5_000);

        setState(activeKey, (s) => ({ ...s, recoveryPollRef: pollId }));
        return;
      }

      const message =
        (err as Error)?.message === "SESSION_CREATE_FAILED"
          ? "Couldn't start a new session. Please try again."
          : "An error occurred. Please try again.";

      setState(activeKey, (s) => ({
        ...s,
        status: "idle",
        liveStatus: null,
        abortController: null,
        messages: s.messages.map((m) =>
          m.id === assistantId ? { ...m, content: message } : m,
        ),
      }));
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const value: ChatStreamContextValue = useMemo(
    () => ({
      getState: (key: string) =>
        mapRef.current.get(key) ?? makeDefaultTurnState(),
      send,
      stop,
      retry,
      subscribe,
      unsubscribe,
      loadHistoryIfNeeded,
      version,
    }),
    // Re-create the value object only when state actually mutates (version bump).
    // The action functions (send, stop, etc.) are redefined on every render but
    // operate on stable refs — capturing them fresh here ensures they see up-to-date
    // closure state on the render that triggered the version bump.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [version],
  );

  return (
    <ChatStreamContext.Provider value={value}>
      {children}
    </ChatStreamContext.Provider>
  );
}

// ─── useChatStream ────────────────────────────────────────────────────────────

export type UseChatStreamResult = {
  messages: Message[];
  isStreaming: boolean;
  liveThoughts: string[];
  liveStatus: string | null;
  recoveryStatus: RecoveryStatus;
  send: (input: string, opts: SendOptions) => void;
  stop: () => void;
  retry: (stoppedId: string) => void;
};

export function useChatStream(sessionId: string | null): UseChatStreamResult {
  const ctx = useContext(ChatStreamContext);
  if (!ctx) {
    throw new Error("useChatStream must be used within a ChatStreamProvider");
  }

  // The key used for this session. Empty string = no session yet.
  const key = sessionId ?? "";

  // Subscribe on mount / key change, unsubscribe on cleanup
  useEffect(() => {
    ctx.subscribe(key);
    return () => {
      ctx.unsubscribe(key);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Load prior history when a session key is set or changes. Runs AFTER the
  // component renders and after pending microtasks (from act/waitFor) have
  // flushed — same timing as the original ChatInterface.tsx useEffect([sessionId]).
  // The provider's loadHistoryIfNeeded guards against locally-created sessions.
  useEffect(() => {
    ctx.loadHistoryIfNeeded(key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Stable action refs — only recreated when ctx (version bump) or key changes.
  const send = useCallback(
    (input: string, opts: SendOptions) => ctx.send(key, input, opts),
    [ctx, key],
  );
  const stop = useCallback(() => ctx.stop(key), [ctx, key]);
  const retry = useCallback(
    (stoppedId: string) => ctx.retry(key, stoppedId),
    [ctx, key],
  );

  // Read state — ctx.version causes re-render on provider mutation
  const state = ctx.getState(key);

  return {
    messages: state.messages,
    isStreaming: state.status === "streaming",
    liveThoughts: state.liveThoughts,
    liveStatus: state.liveStatus,
    recoveryStatus: state.recoveryStatus,
    send,
    stop,
    retry,
  };
}
