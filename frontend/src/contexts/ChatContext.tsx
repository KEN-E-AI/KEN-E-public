import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import {
  chatService,
  type ChatMessage,
  type ConversationInfo,
} from "@/services/chatService";
import { useAuth } from "./AuthContext";

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  metadata?: { requires_reauth?: boolean; service?: string };
}

interface ChatContextType {
  messages: DisplayMessage[];
  newMessage: string;
  isLoading: boolean;
  sessionId: string | null;
  conversations: ConversationInfo[];
  currentConversation: ConversationInfo | null;
  currentTab: string;
  setNewMessage: (message: string) => void;
  sendMessage: () => Promise<void>;
  createNewChat: () => Promise<void>;
  switchToConversation: (conversation: ConversationInfo) => Promise<void>;
  handleKeyPress: (e: React.KeyboardEvent) => void;
  updateChatContext: (selectedTab: string) => void;
}

export const ChatContext = createContext<ChatContextType | undefined>(
  undefined,
);

export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
};

interface ChatProviderProps {
  children: ReactNode;
}

export const ChatProvider = ({ children }: ChatProviderProps) => {
  const { selectedOrgAccount, isAuthenticated } = useAuth();
  const [currentTab, setCurrentTab] = useState("Awareness");
  const [newMessage, setNewMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [currentConversation, setCurrentConversation] =
    useState<ConversationInfo | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      id: "1",
      role: "assistant",
      content: `Hello! I'm here to help with your ${currentTab} strategy. What would you like to discuss?`,
      timestamp: new Date().toISOString(),
    },
  ]);

  // Track previous account to detect switches
  const prevAccountIdRef = useRef(selectedOrgAccount?.accountId);

  // Reset chat session when the selected account changes
  useEffect(() => {
    const prevAccountId = prevAccountIdRef.current;
    const currentAccountId = selectedOrgAccount?.accountId;
    prevAccountIdRef.current = currentAccountId;

    if (
      prevAccountId &&
      currentAccountId &&
      prevAccountId !== currentAccountId
    ) {
      setSessionId(null);
      setCurrentConversation(null);
      setMessages([
        {
          id: "1",
          role: "assistant",
          content: `Hello! I'm here to help with your ${currentTab} strategy. What would you like to discuss?`,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  }, [selectedOrgAccount?.accountId, currentTab]);

  // Load conversations and check for recoverable sessions when authenticated or account changes
  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    const loadConversations = async () => {
      try {
        const userConversations = await chatService.getConversations();
        setConversations(
          Array.isArray(userConversations) ? userConversations : [],
        );

        // Auto-resume: load most recent conversation with full message history
        if (
          !sessionId &&
          Array.isArray(userConversations) &&
          userConversations.length > 0
        ) {
          const mostRecent = userConversations[0];
          await switchToConversation(mostRecent);
        }
      } catch (error) {
        console.error("Failed to load conversations:", error);
        setConversations([]);
      }
    };

    loadConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, selectedOrgAccount?.accountId]); // Re-run when auth state or account changes

  // Create a new chat conversation
  const createNewChat = useCallback(async () => {
    try {
      setIsLoading(true);
      const newConversation = await chatService.createConversation(
        "Dashboard Chat",
        selectedOrgAccount?.accountId,
      );

      setConversations((prev) => [newConversation, ...prev]);
      setCurrentConversation(newConversation);
      setSessionId(newConversation.session_id);

      setMessages([
        {
          id: "1",
          role: "assistant",
          content: `Hello! I'm here to help with your ${currentTab} strategy. What would you like to discuss?`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (error) {
      console.error("Failed to create new chat:", error);
    } finally {
      setIsLoading(false);
    }
  }, [currentTab, selectedOrgAccount]);

  // Switch to an existing conversation
  const switchToConversation = useCallback(
    async (conversation: ConversationInfo) => {
      try {
        setIsLoading(true);
        setCurrentConversation(conversation);
        setSessionId(conversation.session_id);

        const history = await chatService.getConversationHistory(
          conversation.session_id,
        );

        if (history && (history.messages || history.events)) {
          const events = history.events || history.messages || [];
          const loadedMessages: DisplayMessage[] = events
            .map((event: any, index: number) => {
              let content = "Empty message";
              let role = "assistant";

              if (event.content?.parts?.length > 0) {
                content =
                  event.content.parts[0].text ||
                  event.content.parts[0].content ||
                  "Empty message";
                role = event.content.role || event.role || "assistant";
              } else if (typeof event.content === "string") {
                content = event.content || "Empty message";
                role = event.role || "assistant";
              } else if (event.content) {
                content = String(event.content.text || "Empty message");
                role = event.role || "assistant";
              }

              return {
                id: `${index}`,
                role:
                  role === "user" ? ("user" as const) : ("assistant" as const),
                content,
                timestamp: new Date(
                  event.timestamp || Date.now(),
                ).toISOString(),
              };
            })
            .filter((msg) => msg.content !== "Empty message");
          setMessages(loadedMessages);
        } else {
          setMessages([
            {
              id: "1",
              role: "assistant",
              content: `Resumed conversation: ${conversation.conversation_name || "Untitled Chat"} for ${currentTab}`,
              timestamp: new Date().toISOString(),
            },
          ]);
        }
      } catch (error) {
        console.error("Failed to load conversation history:", error);
        setMessages([
          {
            id: "1",
            role: "assistant",
            content: `Error loading conversation history. Starting fresh chat for ${currentTab}.`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [currentTab],
  );

  // Send new chat message
  const sendMessage = useCallback(async () => {
    if (!newMessage.trim() || isLoading) return;

    const validation = chatService.validateMessage(newMessage);
    if (!validation.valid) {
      console.error("Invalid message:", validation.reason);
      return;
    }

    const userMessage = {
      id: Date.now().toString(),
      role: "user" as const,
      content: newMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setNewMessage("");
    setIsLoading(true);

    try {
      const chatMessages: ChatMessage[] = [...messages, userMessage].map(
        (msg) => ({
          role: msg.role,
          content: msg.content,
        }),
      );

      const response = await chatService.sendMessage(
        chatMessages,
        sessionId,
        selectedOrgAccount?.accountId,
      );

      // Sync session ID if the backend resolved a pending/new session
      if (response.session_id && response.session_id !== sessionId) {
        setSessionId(response.session_id);
      }

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant" as const,
        content: response.content,
        timestamp: new Date().toISOString(),
        metadata: response.metadata,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);

      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant" as const,
        content:
          "I'm sorry, I'm having trouble processing your request. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [newMessage, messages, isLoading, sessionId, selectedOrgAccount]);

  // Handle key press for chat input
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Update chat context when tab changes
  const updateChatContext = useCallback((selectedTab: string) => {
    setCurrentTab(selectedTab);
  }, []);

  const value = {
    messages,
    newMessage,
    isLoading,
    sessionId,
    conversations,
    currentConversation,
    currentTab,
    setNewMessage,
    sendMessage,
    createNewChat,
    switchToConversation,
    handleKeyPress,
    updateChatContext,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};
