import { useState, useCallback, useEffect } from "react";
import {
  Plus,
  Mic,
  Share2,
  ChevronDown,
  Mail,
  MessageSquare,
  Save,
  FileAudio,
  AudioWaveform,
  Wrench,
} from "lucide-react";
import {
  chatService,
  type ChatMessage,
  type ConversationInfo,
} from "@/services/chatService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
}

const initialMessages: Message[] = [
  {
    id: "1",
    content: "Oh?",
    isUser: true,
    timestamp: "Nov 30, 2023, 9:41 AM",
  },
  {
    id: "2",
    content: "Cool",
    isUser: true,
    timestamp: "",
  },
  {
    id: "3",
    content: "How does it work?",
    isUser: true,
    timestamp: "",
  },
  {
    id: "4",
    content: "No honestly I'm thinking of a career pivot",
    isUser: false,
    timestamp: "",
  },
  {
    id: "5",
    content: "Welcome to KEN-E, your marketing intelligence assistant!",
    isUser: false,
    timestamp: "",
  },
  {
    id: "6",
    content:
      "I can help you analyze your marketing performance, understand customer insights, and optimize your strategies. What would you like to explore today?",
    isUser: false,
    timestamp: "",
  },
  {
    id: "7",
    content: "Show me the latest performance metrics",
    isUser: true,
    timestamp: "",
  },
  {
    id: "8",
    content: "I think I get it",
    isUser: true,
    timestamp: "",
  },
  {
    id: "9",
    content: "Let me know if you need help with anything specific!",
    isUser: false,
    timestamp: "",
  },
];

const HomeChatArea = () => {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [newMessage, setNewMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [currentConversation, setCurrentConversation] =
    useState<ConversationInfo | null>(null);

  // Load conversations on component mount
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const userConversations = await chatService.getConversations();
        // Ensure we always set an array, even if API returns unexpected data
        setConversations(
          Array.isArray(userConversations) ? userConversations : [],
        );

        // If no current session, create a new one or use the most recent
        if (
          !sessionId &&
          Array.isArray(userConversations) &&
          userConversations.length > 0
        ) {
          const mostRecent = userConversations[0]; // API returns sorted by last_updated
          setCurrentConversation(mostRecent);
          setSessionId(mostRecent.session_id);
        }
      } catch (error) {
        console.error("Failed to load conversations:", error);
        // Set empty array on error to prevent crashes
        setConversations([]);
      }
    };

    loadConversations();
  }, [sessionId]);

  // Create a new chat conversation
  const createNewChat = useCallback(async () => {
    try {
      setIsLoading(true);
      const newConversation = await chatService.createConversation("New Chat");

      // Update conversations list
      setConversations((prev) => [newConversation, ...prev]);

      // Switch to the new conversation
      setCurrentConversation(newConversation);
      setSessionId(newConversation.session_id);

      // Clear current messages to start fresh
      setMessages([
        {
          id: "1",
          content:
            "Hello! I'm KEN-E, your marketing intelligence assistant. How can I help you today?",
          isUser: false,
          timestamp: new Date().toLocaleString(),
        },
      ]);
    } catch (error) {
      console.error("Failed to create new chat:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Switch to an existing conversation
  const switchToConversation = useCallback(
    async (conversation: ConversationInfo) => {
      try {
        setIsLoading(true);
        setCurrentConversation(conversation);
        setSessionId(conversation.session_id);

        // Load actual conversation history from ADK session service
        const history = await chatService.getConversationHistory(
          conversation.session_id,
        );

        if (history && (history.messages || history.events)) {
          // Convert ADK session data to our Message format
          const events = history.events || history.messages || [];
          const loadedMessages: Message[] = events.map(
            (event: any, index: number) => {
              // Handle ADK event format: event.content.parts[].text
              let content = "Empty message";
              let role = "assistant";

              if (
                event.content &&
                event.content.parts &&
                event.content.parts.length > 0
              ) {
                // Extract text from first part
                content =
                  event.content.parts[0].text ||
                  event.content.parts[0].content ||
                  "Empty message";
                role = event.content.role || event.role || "assistant";
              } else if (event.content) {
                // Simple content format
                content =
                  event.content.text || event.content || "Empty message";
                role = event.role || "assistant";
              }

              return {
                id: `${index}`,
                content: content,
                isUser: role === "user",
                timestamp: event.timestamp || "",
              };
            },
          );
          setMessages(loadedMessages);
        } else {
          // Fallback if no history available
          setMessages([
            {
              id: "1",
              content: `Resumed conversation: ${conversation.conversation_name || "Untitled Chat"}`,
              isUser: false,
              timestamp: new Date().toLocaleString(),
            },
          ]);
        }
      } catch (error) {
        console.error("Failed to load conversation history:", error);
        // Fallback on error
        setMessages([
          {
            id: "1",
            content: `Error loading conversation history. Starting fresh chat.`,
            isUser: false,
            timestamp: new Date().toLocaleString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const sendMessage = useCallback(async () => {
    if (!newMessage.trim() || isLoading) return;

    // Validate message
    const validation = chatService.validateMessage(newMessage);
    if (!validation.valid) {
      console.error("Invalid message:", validation.reason);
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content: newMessage,
      isUser: true,
      timestamp: "",
    };

    setMessages((prev) => [...prev, userMessage]);
    setNewMessage("");
    setIsLoading(true);

    try {
      // Convert messages to ChatMessage format
      const chatMessages: ChatMessage[] = [...messages, userMessage].map(
        (msg) => ({
          role: msg.isUser ? "user" : "assistant",
          content: msg.content,
          timestamp: msg.timestamp,
        }),
      );

      // Get response from Agent Engine
      const response = await chatService.sendMessage(chatMessages, sessionId);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response.content,
        isUser: false,
        timestamp: "",
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);

      // Add error message
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content:
          "I'm sorry, I'm having trouble processing your request. Please try again.",
        isUser: false,
        timestamp: "",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [newMessage, messages, isLoading, sessionId]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Card className="h-[calc(100vh-200px)] flex flex-col bg-white border border-dashboard-gray-200">
      {/* Chat Controls */}
      <div className="p-4 border-b border-dashboard-gray-200">
        <div className="flex flex-col sm:flex-row gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex items-center justify-between w-full"
              >
                <span>Resume Conversation</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-full">
              {!Array.isArray(conversations) || conversations.length === 0 ? (
                <DropdownMenuItem disabled>
                  No previous conversations
                </DropdownMenuItem>
              ) : (
                conversations.slice(0, 5).map((conversation) => (
                  <DropdownMenuItem
                    key={conversation.session_id}
                    onClick={() => switchToConversation(conversation)}
                    className="cursor-pointer"
                  >
                    {conversation.conversation_name ||
                      `Chat ${conversation.session_id.slice(-8)}`}
                    <span className="ml-auto text-xs text-gray-500">
                      {new Date(conversation.last_updated).toLocaleDateString()}
                    </span>
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="flex gap-2 w-full sm:w-auto">
            <Button
              size="sm"
              className="bg-brand-medium-blue hover:bg-brand-dark-blue flex-1 sm:flex-none"
              onClick={createNewChat}
              disabled={isLoading}
            >
              New Chat
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-9 w-9 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900"
                >
                  <Share2 className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                  <Mail className="h-4 w-4" />
                  Share chat by email
                </DropdownMenuItem>
                <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                  <MessageSquare className="h-4 w-4" />
                  Share chat on Slack
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((message, index) => (
          <div key={message.id}>
            {/* Show timestamp for first message */}
            {index === 0 && message.timestamp && (
              <div className="text-center text-sm text-dashboard-gray-500 mb-4">
                {message.timestamp}
              </div>
            )}

            <div
              className={`flex ${
                message.isUser ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
                  message.isUser
                    ? "bg-dashboard-gray-100 text-dashboard-gray-900"
                    : "bg-brand-medium-blue text-white"
                }`}
              >
                <p className="text-sm leading-relaxed">{message.content}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Message Input */}
      <div className="p-4 border-t border-dashboard-gray-200 bg-white">
        <div className="flex flex-col gap-3">
          {/* Input Row */}
          <div className="border border-[#CBD5E1] rounded-md p-2">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              {/* Input Field Row */}
              <div className="flex-1">
                <Input
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyDown={handleKeyPress}
                  placeholder="What would you like to discuss?"
                  className="w-full border-0 focus:ring-0 focus:border-0 shadow-none"
                  disabled={isLoading}
                />
              </div>

              {/* Buttons Row - Desktop: inline, Mobile: separate row */}
              <div className="flex items-center gap-1 sm:gap-0">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900 flex flex-col"
                >
                  <Mic className="h-5 w-5 mx-auto" />
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900 flex flex-col mr-2"
                  title="Enable voice mode"
                >
                  <AudioWaveform className="h-5 w-5" />
                </Button>

                <Button
                  onClick={sendMessage}
                  disabled={!newMessage.trim() || isLoading}
                  size="sm"
                  className="bg-brand-medium-blue hover:bg-brand-dark-blue text-white px-4"
                >
                  {isLoading ? "..." : "Send"}
                </Button>
              </div>
            </div>
          </div>

          {/* Action Button Row - Visible on All Screens */}
          <div className="flex items-center gap-2 justify-start">
            <Button
              variant="outline"
              size="sm"
              className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900"
              title="Upload a file"
            >
              <Plus className="h-5 w-5" />
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900"
                  title="Select a tool"
                >
                  <Wrench className="h-5 w-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                  Explain a change to a metric
                </DropdownMenuItem>
                <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                  Create a chart
                </DropdownMenuItem>
                <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                  Draft content
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default HomeChatArea;
