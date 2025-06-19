import { useState } from "react";
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

  const sendMessage = () => {
    if (newMessage.trim()) {
      const message: Message = {
        id: Date.now().toString(),
        content: newMessage,
        isUser: true,
        timestamp: "",
      };
      setMessages([...messages, message]);
      setNewMessage("");

      // Simulate assistant response
      setTimeout(() => {
        const response: Message = {
          id: (Date.now() + 1).toString(),
          content: "I understand your question. Let me help you with that...",
          isUser: false,
          timestamp: "",
        };
        setMessages((prev) => [...prev, response]);
      }, 1000);
    }
  };

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
              <DropdownMenuItem>Marketing Strategy Discussion</DropdownMenuItem>
              <DropdownMenuItem>Campaign Performance Review</DropdownMenuItem>
              <DropdownMenuItem>Data Analysis Session</DropdownMenuItem>
              <DropdownMenuItem>Customer Insights Review</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="flex gap-2 w-full sm:w-auto">
            <Button
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 flex-1 sm:flex-none"
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
                    : "bg-blue-600 text-white"
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
                  onKeyPress={handleKeyPress}
                  placeholder="What would you like to discuss?"
                  className="w-full border-0 focus:ring-0 focus:border-0 shadow-none"
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
                  disabled={!newMessage.trim()}
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4"
                >
                  Send
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
