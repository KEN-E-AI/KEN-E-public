import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Sparkles, Loader2, RotateCcw, Settings2 } from 'lucide-react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { ThinkingBlock } from './ThinkingBlock';
import { ArtifactRenderer } from './dashboard/ArtifactRenderer';
import type { DashboardArtifactPayload } from './dashboard/artifactTypes';
import { TileSettingsPopover, type ArtifactConfig } from './dashboard/TileSettingsPopover';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  stopped?: boolean;
  reasoning?: {
    thoughts: string[];
    durationSeconds: number;
  };
  artifacts?: DashboardArtifactPayload[];
}

const VIZ_KEYWORDS = /\b(chart|graph|visualiz|plot|trend|breakdown|show me)\b/i;

function buildMockVisualization(prompt: string): DashboardArtifactPayload {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
  const values = months.map(() => Math.round(40 + Math.random() * 60));
  return {
    type: 'visualization',
    title: 'Campaign performance',
    spec: {
      $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
      description: prompt.slice(0, 80),
      data: { values: months.map((m, i) => ({ month: m, value: values[i] })) },
      mark: 'bar',
      encoding: {
        x: { field: 'month', type: 'ordinal', title: 'Month' },
        y: { field: 'value', type: 'quantitative', title: 'Conversions' },
      },
    },
  };
}

function ChatArtifact({ artifact }: { artifact: DashboardArtifactPayload }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 480, height: 260 });
  const [config, setConfig] = useState<ArtifactConfig>({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  const configurable = artifact.type === 'visualization';

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      setSize({ width: Math.max(240, w), height: 260 });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className="group relative rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-primary)] p-3"
      style={{ height: size.height }}
    >
      {configurable && (
        <div
          className={`absolute top-1.5 right-1.5 z-10 transition-opacity ${
            settingsOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}
        >
          <div className="relative">
            <button
              onClick={() => setSettingsOpen((o) => !o)}
              className="p-1 rounded bg-[var(--color-bg-secondary)]/90 backdrop-blur-sm border border-[var(--color-border-default)] hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)]"
              title="Configure visualization"
            >
              <Settings2 className="size-3" />
            </button>
            {settingsOpen && (
              <TileSettingsPopover
                config={config}
                onChange={(patch) => setConfig((prev) => ({ ...prev, ...patch }))}
                onClose={() => setSettingsOpen(false)}
              />
            )}
          </div>
        </div>
      )}
      <ArtifactRenderer
        artifact={artifact}
        viewOverride={config.viewOverride}
        color={config.color}
        showDataLabels={config.showDataLabels}
        width={size.width}
        height={size.height - 24}
      />
    </div>
  );
}

interface ChatInterfaceProps {
  sessionId?: string;
  compact?: boolean;
}

export function ChatInterface({ sessionId, compact = false }: ChatInterfaceProps) {
  const initialMessages: Message[] = [
    {
      id: '1',
      role: 'assistant',
      content: 'Hi! I\'m your KEN-E AI assistant. I can help you build marketing campaigns, analyze performance, create workflows, and manage your calendar. What would you like to work on?',
      timestamp: new Date()
    }
  ];

  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [currentThoughts, setCurrentThoughts] = useState<string[]>([]);
  const [thinkingStartTime, setThinkingStartTime] = useState<number>(0);
  const [chatTextSize, setChatTextSize] = useState<'small' | 'medium' | 'large'>('medium');
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const pendingTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Stable ref for handleStop so the Escape listener never has a stale closure
  const handleStopRef = useRef<() => void>(() => {});

  // Load chat text size from localStorage on mount
  useEffect(() => {
    try {
      const savedSize = localStorage.getItem('kene-chat-text-size') as 'small' | 'medium' | 'large';
      if (savedSize) {
        setChatTextSize(savedSize);
      }
    } catch {
      // localStorage may not be available in sandboxed environments
    }
  }, []);

  // Listen for text size changes from settings
  useEffect(() => {
    const handleTextSizeChange = (e: CustomEvent<'small' | 'medium' | 'large'>) => {
      setChatTextSize(e.detail);
    };
    
    window.addEventListener('kene-chat-text-size-change', handleTextSizeChange as EventListener);
    return () => {
      window.removeEventListener('kene-chat-text-size-change', handleTextSizeChange as EventListener);
    };
  }, []);

  // Restore messages and draft input from sessionStorage on mount
  useEffect(() => {
    try {
      const savedMessages = sessionStorage.getItem('kene-chat-messages');
      if (savedMessages) {
        try {
          const parsed = JSON.parse(savedMessages);
          // Convert timestamp strings back to Date objects
          const messagesWithDates = parsed.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }));
          setMessages(messagesWithDates);
        } catch (e) {
          console.error('Failed to parse saved messages:', e);
        }
      }

      const savedDraft = sessionStorage.getItem('kene-chat-draft');
      if (savedDraft) {
        setInput(savedDraft);
      }
    } catch {
      // sessionStorage may not be available in sandboxed environments
    }
  }, []);

  // Save messages to sessionStorage whenever they change
  useEffect(() => {
    try {
      sessionStorage.setItem('kene-chat-messages', JSON.stringify(messages));
    } catch {
      // sessionStorage may not be available in sandboxed environments
    }
  }, [messages]);

  // Save draft input to sessionStorage whenever it changes
  useEffect(() => {
    try {
      if (input) {
        sessionStorage.setItem('kene-chat-draft', input);
      } else {
        sessionStorage.removeItem('kene-chat-draft');
      }
    } catch {
      // sessionStorage may not be available in sandboxed environments
    }
  }, [input]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, isThinking, currentThoughts]);

  const handleSend = () => {
    if (!input.trim() || isThinking) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages([...messages, newMessage]);
    setInput('');
    setIsThinking(true);
    setCurrentThoughts([]);
    setThinkingStartTime(Date.now());

    // Clear any leftover timers
    pendingTimersRef.current.forEach(clearTimeout);
    pendingTimersRef.current = [];

    // Simulate streamed reasoning steps
    const reasoningSteps = [
      'Understanding the user\'s request and context...',
      'Checking campaign data and recent performance metrics...',
      'Identifying relevant marketing channels and audience segments...',
      'Formulating recommendations based on historical patterns...',
      'Preparing a comprehensive response with actionable next steps...',
    ];

    reasoningSteps.forEach((step, index) => {
      const id = setTimeout(() => {
        setCurrentThoughts(prev => [...prev, step]);
      }, 600 + index * 800);
      pendingTimersRef.current.push(id);
    });

    // Simulate AI response after reasoning completes
    const totalDelay = 600 + reasoningSteps.length * 800 + 400;
    const startTime = Date.now();
    const promptText = input;
    const responseId = setTimeout(() => {
      const duration = Math.round((Date.now() - startTime) / 1000);
      const wantsViz = VIZ_KEYWORDS.test(promptText);
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: wantsViz
          ? 'Here\'s a quick look at the trend you asked about. Let me know if you\'d like to slice it differently or pin it to a dashboard.'
          : 'I understand. Let me help you with that. I\'m analyzing your request and will create the necessary updates across your marketing platform...',
        timestamp: new Date(),
        reasoning: {
          thoughts: reasoningSteps,
          durationSeconds: duration,
        },
        artifacts: wantsViz ? [buildMockVisualization(promptText)] : undefined,
      };
      setMessages(prev => [...prev, aiResponse]);
      setIsThinking(false);
      setCurrentThoughts([]);
      pendingTimersRef.current = [];
    }, totalDelay);
    pendingTimersRef.current.push(responseId);
  };

  const handleStop = useCallback(() => {
    // Cancel all pending timers
    pendingTimersRef.current.forEach(clearTimeout);
    pendingTimersRef.current = [];

    const duration = Math.round((Date.now() - thinkingStartTime) / 1000);

    // Add a stopped message with whatever thoughts were collected
    const stoppedResponse: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: 'Generation was stopped by the user.',
      timestamp: new Date(),
      stopped: true,
      reasoning: currentThoughts.length > 0
        ? { thoughts: currentThoughts, durationSeconds: duration }
        : undefined,
    };
    setMessages(prev => [...prev, stoppedResponse]);
    setIsThinking(false);
    setCurrentThoughts([]);
  }, [thinkingStartTime, currentThoughts]);

  // Keep ref in sync
  useEffect(() => {
    handleStopRef.current = handleStop;
  }, [handleStop]);

  // Escape key listener to stop generation
  useEffect(() => {
    if (!isThinking) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleStopRef.current();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isThinking]);

  // Retry: find the user message right before the stopped message and re-send it
  const handleRetry = (stoppedMessageId: string) => {
    const index = messages.findIndex(m => m.id === stoppedMessageId);
    if (index < 1) return;

    // Walk backwards to find the preceding user message
    let userMessage: Message | undefined;
    for (let i = index - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMessage = messages[i];
        break;
      }
    }
    if (!userMessage) return;

    // Remove the stopped assistant message
    const cleaned = messages.filter(m => m.id !== stoppedMessageId);
    setMessages(cleaned);

    // Re-trigger a send with the same user content
    setIsThinking(true);
    setCurrentThoughts([]);
    setThinkingStartTime(Date.now());

    pendingTimersRef.current.forEach(clearTimeout);
    pendingTimersRef.current = [];

    const reasoningSteps = [
      'Re-analyzing the original request...',
      'Checking campaign data and recent performance metrics...',
      'Identifying relevant marketing channels and audience segments...',
      'Formulating recommendations based on historical patterns...',
      'Preparing a comprehensive response with actionable next steps...',
    ];

    reasoningSteps.forEach((step, index) => {
      const id = setTimeout(() => {
        setCurrentThoughts(prev => [...prev, step]);
      }, 600 + index * 800);
      pendingTimersRef.current.push(id);
    });

    const totalDelay = 600 + reasoningSteps.length * 800 + 400;
    const startTime = Date.now();
    const responseId = setTimeout(() => {
      const duration = Math.round((Date.now() - startTime) / 1000);
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I understand. Let me help you with that. I\'m analyzing your request and will create the necessary updates across your marketing platform...',
        timestamp: new Date(),
        reasoning: {
          thoughts: reasoningSteps,
          durationSeconds: duration,
        },
      };
      setMessages(prev => [...prev, aiResponse]);
      setIsThinking(false);
      setCurrentThoughts([]);
      pendingTimersRef.current = [];
    }, totalDelay);
    pendingTimersRef.current.push(responseId);
  };

  // Get text size class based on preference
  const getTextSizeClass = () => {
    switch (chatTextSize) {
      case 'small':
        return 'text-sm';
      case 'large':
        return 'text-lg';
      default:
        return 'text-base';
    }
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-[var(--color-bg-primary)]">
      <div className="flex-1 min-h-0 overflow-y-auto" ref={scrollContainerRef}>
        <div className="space-y-4 p-6">
          {messages.map(message => (
            <div
              key={message.id}
              className="flex justify-start"
            >
              {message.role === 'user' ? (
                <div className="max-w-[80%]">
                  {/* User prompt: the question carries the visual weight, as a neutral card */}
                  <div className="rounded-[var(--radius-lg)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] dark:border-transparent px-5 py-4">
                    <p className={`${getTextSizeClass()} whitespace-pre-wrap leading-relaxed`}>{message.content}</p>
                  </div>
                </div>
              ) : (
                <div className="max-w-[80%]">
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
                  {/* Assistant response: plain, document-like text — no card */}
                  <div className="px-1 py-1">
                    <p className={`${getTextSizeClass()} whitespace-pre-wrap leading-relaxed`}>{message.content}</p>

                    {message.artifacts && message.artifacts.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {message.artifacts.map((a, i) => (
                          <ChatArtifact key={i} artifact={a} />
                        ))}
                      </div>
                    )}

                    {/* Retry button for stopped messages */}
                    {message.stopped && (
                      <button
                        onClick={() => handleRetry(message.id)}
                        disabled={isThinking}
                        className="flex items-center gap-1.5 px-3 py-1.5 mt-1 rounded-[var(--radius-md)] text-[var(--text-caption)] text-[var(--color-text-secondary)] hover:text-[var(--color-violet-500)] hover:bg-[var(--color-violet-500)]/10 border border-[var(--color-border-default)] hover:border-[var(--color-violet-500)]/40 transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none"
                      >
                        <RotateCcw className="size-3" />
                        <span>Retry</span>
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Live Thinking Indicator */}
          {isThinking && (
            <div className="flex justify-start">
              <div className="max-w-[80%]">
                <ThinkingBlock
                  isThinking={true}
                  thoughts={currentThoughts}
                  onStop={handleStop}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div 
        className="shrink-0 p-6"
        style={{
          borderTop: '2px dashed var(--color-border-default)',
        }}
      >
        <div className="flex gap-3">
          <Textarea
            placeholder={isThinking ? "Waiting for response..." : "Ask me anything about your marketing campaigns..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            className="min-h-[3.75rem] resize-none rounded-[var(--radius-md)]"
            disabled={isThinking}
          />
          <Button onClick={handleSend} size="icon" className="shrink-0 size-[3.75rem]" disabled={isThinking}>
            {isThinking ? <Loader2 className="size-5 animate-spin" /> : <Send className="size-5" />}
          </Button>
        </div>
        <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-3 flex items-center gap-2">
          <Sparkles className="size-3" />
          Tip: Ask me to create campaigns, analyze data, or set up automations
        </p>
      </div>
    </div>
  );
}