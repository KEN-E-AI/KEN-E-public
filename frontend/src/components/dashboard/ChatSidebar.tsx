import { useState } from "react";
import {
  Send,
  Mic,
  Paperclip,
  User,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  BarChart3,
  Activity,
  Lightbulb,
  Building,
  Users,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
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
  pageType?: "dashboard" | "knowledge-base";
  selectedKnowledgePage?: string;
  onKnowledgePageChange?: (page: string) => void;
}

const agents = [
  { id: "ken-e", name: "KEN-E", description: "Marketing Assistant" },
  { id: "ann-e", name: "ANN-E", description: "Data Analyst" },
  { id: "lib-e", name: "LIB-E", description: "Knowledge Base Librarian" },
  { id: "con-e", name: "CON-E", description: "Content Creator" }
];

const knowledgeBaseItems = [
  { id: "metrics", name: "Metrics", icon: BarChart3 },
  { id: "activities", name: "Activities", icon: Activity },
  { id: "insights", name: "Insights", icon: Lightbulb },
  { id: "account-overview", name: "Account Overview", icon: Building },
  { id: "customers", name: "Customers", icon: Users },
  { id: "competitors", name: "Competitors", icon: TrendingUp },
];

const ChatSidebar = ({
  selectedTab = "Awareness",
  selectedChannel = "Overview",
  selectedTactic = "",
  isCollapsed = false,
  onToggleCollapse = () => {},
  pageType = "dashboard",
  selectedKnowledgePage = "metrics",
  onKnowledgePageChange = () => {},
}: ChatSidebarProps) => {
  const [selectedAgent, setSelectedAgent] = useState("ken-e");
  const [message, setMessage] = useState("");
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

  return (
    <div
      className={`fixed left-0 top-0 h-full border-r bg-white border-dashboard-gray-200 flex flex-col z-30 transition-all duration-300 ${isCollapsed ? "w-16" : "w-80 md:w-80"}`}
    >
      {/* Collapse Toggle Button */}
      <div className="absolute top-4 right-2 z-10">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className="p-1 h-8 w-8 hover:bg-dashboard-gray-100"
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Collapsed State - Show only icon */}
      {isCollapsed ? (
        <div className="flex flex-col items-center justify-start pt-16 p-2">
          {pageType === "knowledge-base" ? (
            <div className="w-8 h-8 bg-dashboard-gray-800 rounded-sm flex items-center justify-center mb-4">
              <BarChart3 className="h-4 w-4 text-white" />
            </div>
          ) : (
            <div className="w-8 h-8 bg-dashboard-gray-800 rounded-sm flex items-center justify-center mb-4">
              <span className="text-white text-xs font-medium">
                {currentAgent?.name.split("-")[0] || "KE"}
              </span>
            </div>
          )}
        </div>
      ) : (
        /* Expanded Content */
        <>
          {pageType === "knowledge-base" ? (
            /* Knowledge Base Content */
            <div className="py-6 px-4 pt-16">
              {/* Header */}
              <div className="mb-6">
                <h1 className="text-xl font-semibold text-dashboard-gray-900">
                  Knowledge Base
                </h1>
              </div>

              {/* Navigation */}
              <nav className="space-y-2">
                {knowledgeBaseItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Button
                      key={item.id}
                      variant={
                        selectedKnowledgePage === item.id ? "default" : "ghost"
                      }
                      className={cn(
                        "w-full h-10 justify-start gap-3 px-3 transition-all duration-200",
                        selectedKnowledgePage === item.id
                          ? "bg-dashboard-gray-800 text-white hover:bg-dashboard-gray-700"
                          : "text-dashboard-gray-600 hover:bg-dashboard-gray-50",
                      )}
                      onClick={() => onKnowledgePageChange(item.id)}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.name}</span>
                    </Button>
                  );
                })}
              </nav>
            </div>
          ) : (
            /* Dashboard Chat Content */
            <>
              {/* Header */}
              <div className="p-4 border-b border-dashboard-gray-200 mt-7">
                <div className="mb-3"></div>

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
                      <DropdownMenuItem>
                        Budget Optimization Talk
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
                    New
                  </Button>
                </div>

                {/* Agent Selection */}
                <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                  <SelectTrigger className="w-full">
                    <SelectValue>
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-dashboard-gray-800 rounded-sm flex items-center justify-center">
                          <span className="text-white text-xs font-medium">
                            {currentAgent?.name.split("-")[0] || "KE"}
                          </span>
                        </div>
                        <div className="text-left">
                          <div className="font-medium">
                            {currentAgent?.name}
                          </div>
                          <div className="text-xs text-dashboard-gray-600">
                            {currentAgent?.description}
                          </div>
                        </div>
                      </div>
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 bg-dashboard-gray-800 rounded-sm flex items-center justify-center">
                            <span className="text-white text-xs font-medium">
                              {agent.name.split("-")[0]}
                            </span>
                          </div>
                          <div>
                            <div className="font-medium">{agent.name}</div>
                            <div className="text-xs text-dashboard-gray-600">
                              {agent.description}
                            </div>
                          </div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                      <div className="w-6 h-6 bg-dashboard-gray-800 rounded-sm flex items-center justify-center flex-shrink-0 mt-1">
                        <span className="text-white text-xs font-medium">
                          {currentAgent?.name.split("-")[0]}
                        </span>
                      </div>
                    )}
                    <div
                      className={cn(
                        "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                        msg.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-dashboard-gray-100 text-dashboard-gray-900",
                      )}
                    >
                      {msg.content}
                    </div>
                    {msg.role === "user" && (
                      <div className="w-6 h-6 bg-blue-600 rounded-sm flex items-center justify-center flex-shrink-0 mt-1">
                        <User className="h-3 w-3 text-white" />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Message Input */}
              <div className="p-4 border-t border-dashboard-gray-200">
                <div className="flex gap-2 mb-2">
                  <Textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask me anything about your marketing performance..."
                    className="flex-1 resize-none min-h-[80px]"
                    rows={3}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="p-2">
                      <Paperclip className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" className="p-2">
                      <Mic className="h-4 w-4" />
                    </Button>
                  </div>
                  <Button
                    onClick={handleSendMessage}
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700"
                    disabled={!message.trim()}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
};

export default ChatSidebar;
