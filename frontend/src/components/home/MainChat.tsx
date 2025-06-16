import { useState } from "react";
import { Plus, Mic, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
    content: "This is the main chat template",
    isUser: false,
    timestamp: "",
  },
  {
    id: "6",
    content:
      "You just edit any text to type in the conversation you want to show, and delete any bubbles you don't want to use",
    isUser: false,
    timestamp: "",
  },
  {
    id: "7",
    content: "Hmmm",
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
    content: "Will head to the Help Center if I have more questions tho",
    isUser: true,
    timestamp: "",
  },
];

const MainChat = () => {
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
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((message, index) => (
          <div key={message.id}>
            {/* Show timestamp for first message */}
            {index === 0 && message.timestamp && (
              <div className="text-center text-sm text-gray-500 mb-4">
                {message.timestamp}
              </div>
            )}

            <div
              className={`flex ${
                message.isUser ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                  message.isUser
                    ? "bg-gray-200 text-gray-900"
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
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            className="flex-shrink-0 h-10 w-10 p-0"
          >
            <Plus className="h-5 w-5" />
          </Button>

          <div className="flex-1">
            <Input
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Enter your message"
              className="w-full"
            />
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <Button variant="ghost" size="sm" className="h-10 w-10 p-0">
              <Mic className="h-5 w-5" />
            </Button>

            <Button variant="ghost" size="sm" className="h-10 w-10 p-0">
              <Share2 className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MainChat;
