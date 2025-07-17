import { useState } from "react";
import { Mic, Paperclip, Send, Plus, FileText, X, Minimize2 } from "lucide-react";
import { ImageWithFallback } from './figma/ImageWithFallback';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
}

export function ChatWindow() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: "Hello! I'm here to help with your Anthropic Console. What would you like to discuss?",
      sender: 'assistant',
      timestamp: new Date()
    }
  ]);
  const [isMinimized, setIsMinimized] = useState(false);

  const handleSendMessage = () => {
    if (message.trim()) {
      const newMessage: Message = {
        id: Date.now().toString(),
        text: message,
        sender: 'user',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, newMessage]);
      setMessage("");
      
      // Simulate assistant response
      setTimeout(() => {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: "I understand you're asking about: " + message + ". How can I help you with that?",
          sender: 'assistant',
          timestamp: new Date()
        };
        setMessages(prev => [...prev, assistantMessage]);
      }, 1000);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (isMinimized) {
    return (
      <div className="w-12 h-12 bg-blue-600 rounded-full fixed bottom-4 right-4 flex items-center justify-center cursor-pointer shadow-lg z-50" onClick={() => setIsMinimized(false)}>
        <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center">
          <span className="text-blue-600 text-xs">💬</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col h-screen">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-white text-xs">A</span>
            </div>
            <div>
              <h3 className="text-sm text-gray-900">Assistant</h3>
              <p className="text-xs text-gray-500">Online</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsMinimized(true)}
              className="p-1 hover:bg-gray-200 rounded"
            >
              <Minimize2 className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex items-start gap-2 max-w-[85%] ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}>
              {msg.sender === 'assistant' && (
                <div className="w-6 h-6 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-xs">A</span>
                </div>
              )}
              <div
                className={`p-3 rounded-lg text-sm ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {msg.text}
              </div>
              {msg.sender === 'user' && (
                <div className="w-6 h-6 bg-gray-400 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-xs">U</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex items-end gap-2 mb-2">
          <div className="flex-1 relative">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              className="w-full p-2 pr-20 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              rows={1}
              style={{ minHeight: '36px', maxHeight: '100px' }}
            />
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex items-center gap-1">
              <button className="text-gray-400 hover:text-gray-600 transition-colors p-1">
                <Paperclip className="w-4 h-4" />
              </button>
              <button className="text-gray-400 hover:text-gray-600 transition-colors p-1">
                <Mic className="w-4 h-4" />
              </button>
            </div>
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!message.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white p-2 rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex items-center gap-1">
          <button className="text-gray-400 hover:text-gray-600 transition-colors p-1 hover:bg-gray-100 rounded">
            <Plus className="w-4 h-4" />
          </button>
          <button className="text-gray-400 hover:text-gray-600 transition-colors p-1 hover:bg-gray-100 rounded">
            <FileText className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}