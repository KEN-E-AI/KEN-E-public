import { useState, useCallback, useEffect } from "react";
import {
  chatService,
  type ChatMessage,
  type ConversationInfo,
} from "@/services/chatService";
import {
  Send,
  Mic,
  Paperclip,
  User,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Plus,
  AudioWaveform,
  Wrench,
  Mail,
  MessageSquare,
  Share2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatSidebarProps {
  selectedTab?: string;
  selectedChannel?: string;
  selectedTactic?: string;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

const agents = [
  { id: "ken-e", name: "KEN-E", description: "Marketing Assistant" },
  { id: "sarah", name: "Sarah", description: "Data Analyst" },
  { id: "alex", name: "Alex", description: "Growth Strategist" },
];

const ChatSidebar = ({
  selectedTab = "Awareness",
  selectedChannel = "Overview",
  selectedTactic = "",
  isCollapsed = false,
  onToggleCollapse = () => {},
}: ChatSidebarProps) => {
  const [selectedAgent, setSelectedAgent] = useState("ken-e");
  const [message, setMessage] = useState("");
  const [newMessage, setNewMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [currentConversation, setCurrentConversation] =
    useState<ConversationInfo | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      role: "assistant",
      content: `Hello! I'm here to help with your ${selectedTab} strategy${
        selectedChannel !== "Overview" ? ` for ${selectedChannel}` : ""
      }${selectedTactic ? ` - ${selectedTactic}` : ""}. What would you like to discuss?`,
      timestamp: new Date(),
    },
  ]);

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
      const newConversation =
        await chatService.createConversation("Dashboard Chat");

      // Update conversations list
      setConversations((prev) => [newConversation, ...prev]);

      // Switch to the new conversation
      setCurrentConversation(newConversation);
      setSessionId(newConversation.session_id);

      // Clear current messages to start fresh
      setMessages([
        {
          id: "1",
          role: "assistant",
          content: `Hello! I'm here to help with your ${selectedTab} strategy${
            selectedChannel !== "Overview" ? ` for ${selectedChannel}` : ""
          }${selectedTactic ? ` - ${selectedTactic}` : ""}. What would you like to discuss?`,
          timestamp: new Date(),
        },
      ]);
    } catch (error) {
      console.error("Failed to create new chat:", error);
    } finally {
      setIsLoading(false);
    }
  }, [selectedTab, selectedChannel, selectedTactic]);

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
          // Convert ADK session data to our ChatMessage format
          const events = history.events || history.messages || [];
          const loadedMessages: ChatMessage[] = events.map(
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
                role: role === "user" ? "user" : "assistant",
                content: content,
                timestamp: new Date(event.timestamp || Date.now()),
              };
            },
          );
          setMessages(loadedMessages);
        } else {
          // Fallback if no history available
          setMessages([
            {
              id: "1",
              role: "assistant",
              content: `Resumed conversation: ${conversation.conversation_name || "Untitled Chat"} for ${selectedTab}`,
              timestamp: new Date(),
            },
          ]);
        }
      } catch (error) {
        console.error("Failed to load conversation history:", error);
        // Fallback on error
        setMessages([
          {
            id: "1",
            role: "assistant",
            content: `Error loading conversation history. Starting fresh chat for ${selectedTab}.`,
            timestamp: new Date(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [selectedTab],
  );

  const handleSendMessage = () => {
    if (!message.trim()) return;

    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: message,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setMessage("");

    // Simulate assistant response
    setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `I understand you're asking about "${message}". Let me analyze your ${selectedTab} performance${
          selectedChannel !== "Overview" ? ` for ${selectedChannel}` : ""
        } and provide some insights...`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    }, 1000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const currentAgent = agents.find((agent) => agent.id === selectedAgent);

  const sendNewMessage = useCallback(async () => {
    if (!newMessage.trim() || isLoading) return;

    // Validate message
    const validation = chatService.validateMessage(newMessage);
    if (!validation.valid) {
      console.error("Invalid message:", validation.reason);
      return;
    }

    const userMessage = {
      id: Date.now().toString(),
      role: "user" as const,
      content: newMessage,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setNewMessage("");
    setIsLoading(true);

    try {
      // Convert messages to ChatMessage format for the service
      const chatMessages: ChatMessage[] = [...messages, userMessage].map(
        (msg) => ({
          role: msg.role,
          content: msg.content,
        }),
      );

      // Get response from Agent Engine
      const response = await chatService.sendMessage(chatMessages, sessionId);

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant" as const,
        content: response.content,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);

      // Add error message
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant" as const,
        content:
          "I'm sorry, I'm having trouble processing your request. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [newMessage, messages, isLoading, sessionId]);

  const handleNewKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendNewMessage();
    }
  };

  return (
    <div
      className={`fixed right-0 top-0 h-full border-l bg-white border-dashboard-gray-200 flex flex-col z-30 transition-all duration-300 ${isCollapsed ? "w-16" : "w-80 md:w-80"}`}
    >
      {/* Header */}
      {isCollapsed ? (
        <div className="h-16 flex items-center justify-center border-b border-dashboard-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-10 w-10 p-0"
            aria-label="Toggle chat sidebar"
          >
            <MessageSquare className="h-5 w-5" />
          </Button>
        </div>
      ) : (
        <div className="h-16 flex items-center justify-between px-4 border-b border-dashboard-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-8 w-8 p-0"
            aria-label="Toggle chat sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <h2 className="text-lg font-semibold text-dashboard-gray-900 flex-1 text-center">
            Chat
          </h2>
          <div className="w-8" /> {/* Spacer for balance */}
        </div>
      )}

      {/* Main Content */}
      {!isCollapsed && (
        <>
          {/* Header */}
          <div className="p-4 border-b border-dashboard-gray-200">
            {/* Chat Controls */}
            <div className="flex gap-2 mb-4">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="flex-1">
                    <span className="lg:mr-auto">Resume Conversation</span>
                    <ChevronDown className="ml-2 h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-56">
                  {!Array.isArray(conversations) ||
                  conversations.length === 0 ? (
                    <DropdownMenuItem disabled>
                      No previous conversations
                    </DropdownMenuItem>
                  ) : (
                    conversations.slice(0, 4).map((conversation) => (
                      <DropdownMenuItem
                        key={conversation.session_id}
                        onClick={() => switchToConversation(conversation)}
                        className="cursor-pointer"
                      >
                        {conversation.conversation_name ||
                          `Chat ${conversation.session_id.slice(-6)}`}
                      </DropdownMenuItem>
                    ))
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                size="sm"
                className="bg-brand-medium-blue hover:bg-brand-medium-blue/90"
                onClick={createNewChat}
                disabled={isLoading}
              >
                New
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
                    Share chat by Slack
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex gap-3",
                  msg.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                {msg.role === "assistant" && (
                  <div className="w-6 h-6 rounded-sm flex items-center justify-center flex-shrink-0 mt-1 overflow-hidden">
                    <img
                      src="https://cdn.builder.io/api/v1/assets/c9d6292aa8bc48fc881c52163e11eef1/headshot-1-1-modified-178e67?format=webp&width=800"
                      alt="KEN-E Assistant"
                      className="w-full h-full object-cover rounded-sm"
                    />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                    msg.role === "user"
                      ? "bg-brand-medium-blue text-white"
                      : "bg-dashboard-gray-100 text-dashboard-gray-900",
                  )}
                >
                  {msg.content}
                </div>
                {msg.role === "user" && (
                  <div className="w-6 h-6 bg-brand-medium-blue rounded-sm flex items-center justify-center flex-shrink-0 mt-1">
                    <User className="h-3 w-3 text-white" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* New Message Input Section */}
          <div className="p-4 border-t border-dashboard-gray-200">
            <div className="space-y-3">
              {/* Input Container */}
              <div className="border border-[#CBD5E1] rounded-md p-2">
                <div className="flex flex-col gap-2">
                  {/* Input Field Row */}
                  <div className="flex-1">
                    <Input
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyDown={handleNewKeyPress}
                      placeholder="What would you like to discuss?"
                      className="w-full border-0 focus:ring-0 focus:border-0 shadow-none"
                      disabled={isLoading}
                    />
                  </div>

                  {/* Buttons Row */}
                  <div className="flex items-center gap-1">
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
                      onClick={sendNewMessage}
                      disabled={!newMessage.trim() || isLoading}
                      size="sm"
                      className="bg-brand-medium-blue hover:bg-brand-medium-blue/90 text-white px-4"
                    >
                      {isLoading ? "..." : "Send"}
                    </Button>
                  </div>
                </div>
              </div>

              {/* Action Button Row */}
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
        </>
      )}
    </div>
  );
};

export default ChatSidebar;
