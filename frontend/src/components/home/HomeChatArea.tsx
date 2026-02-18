import { useEffect } from "react";
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
import { useChat } from "@/contexts/ChatContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MessageContent } from "./MessageContent";
import { ReauthPrompt } from "@/components/chat/ReauthPrompt";

const HomeChatArea = () => {
  const {
    messages,
    newMessage,
    setNewMessage,
    isLoading,
    conversations,
    createNewChat,
    sendMessage,
    switchToConversation,
    handleKeyPress,
    updateChatContext,
  } = useChat();

  // Update chat context for Home page
  useEffect(() => {
    updateChatContext("Home");
  }, [updateChatContext]);

  return (
    <Card className="h-full flex flex-col bg-white border border-dashboard-gray-200">
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
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
                  message.role === "user"
                    ? "bg-dashboard-gray-100 text-dashboard-gray-900"
                    : "bg-brand-medium-blue text-white"
                }`}
              >
                <MessageContent
                  content={message.content}
                  isAssistant={message.role === "assistant"}
                />
              </div>
              {message.metadata?.requires_reauth && (
                <ReauthPrompt
                  service={message.metadata.service ?? "google-analytics"}
                />
              )}
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
