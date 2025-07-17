import { useState } from "react";
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

  const sendNewMessage = () => {
    if (newMessage.trim()) {
      const message = {
        id: Date.now().toString(),
        role: "user" as const,
        content: newMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, message]);
      setNewMessage("");

      // Simulate assistant response
      setTimeout(() => {
        const response = {
          id: (Date.now() + 1).toString(),
          role: "assistant" as const,
          content: "I understand your question. Let me help you with that...",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, response]);
      }, 1000);
    }
  };

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
      {/* Header with toggle button */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-dashboard-gray-200">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className="h-8 w-8 p-0"
          aria-label="Toggle chat sidebar"
        >
          {isCollapsed ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
        {!isCollapsed && (
          <h2 className="text-lg font-semibold text-dashboard-gray-900 flex-1 text-center">
            Chat
          </h2>
        )}
        {!isCollapsed && <div className="w-8" />} {/* Spacer for balance */}
      </div>

      {/* Collapsed State - Show only icon */}
      {isCollapsed ? (
        <div className="flex flex-col items-center justify-start pt-4 p-2">
          <MessageSquare className="w-5 h-5 text-gray-600" />
        </div>
      ) : (
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
                  <DropdownMenuItem>
                    Marketing Strategy Discussion
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    Campaign Performance Review
                  </DropdownMenuItem>
                  <DropdownMenuItem>Data Analysis Session</DropdownMenuItem>
                  <DropdownMenuItem>Budget Optimization Talk</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                size="sm"
                className="bg-brand-medium-blue hover:bg-brand-medium-blue/90"
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
                      onKeyPress={handleNewKeyPress}
                      placeholder="What would you like to discuss?"
                      className="w-full border-0 focus:ring-0 focus:border-0 shadow-none"
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
                      disabled={!newMessage.trim()}
                      size="sm"
                      className="bg-brand-medium-blue hover:bg-brand-medium-blue/90 text-white px-4"
                    >
                      Send
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
