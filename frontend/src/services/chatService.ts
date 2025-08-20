/**
 * Chat service for communicating with the Vertex AI Agent Engine via API.
 */

import axios from "axios";
import { auth } from "@/lib/firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  stream?: boolean;
  session_id?: string;
}

export interface ChatResponse {
  role: "assistant";
  content: string;
  session_id: string;
}

export interface ConversationInfo {
  session_id: string;
  conversation_name?: string;
  created_at: string;
  last_updated: string;
  message_count: number;
}

export interface ConversationListResponse {
  conversations: ConversationInfo[];
  total_count: number;
}

class ChatService {
  private apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000, // 30 second timeout for chat requests
  });

  constructor() {
    // Add auth interceptor
    this.apiClient.interceptors.request.use(async (config) => {
      try {
        const user = auth.currentUser;
        if (user) {
          const token = await user.getIdToken();
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.error("Failed to get auth token:", error);
      }
      return config;
    });

    // Add response interceptor for error handling
    this.apiClient.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error("Chat API error:", error);
        if (error.response?.status === 401) {
          // Handle unauthorized - could redirect to login
          console.error("Unauthorized chat request");
        }
        return Promise.reject(error);
      },
    );
  }

  /**
   * Send a chat message and get a response from the Agent Engine.
   */
  async sendMessage(
    messages: ChatMessage[],
    sessionId?: string,
  ): Promise<ChatResponse> {
    try {
      const request: ChatRequest = {
        messages,
        stream: false,
        session_id: sessionId || this.generateSessionId(),
      };

      const response = await this.apiClient.post<ChatResponse>(
        "/api/v1/chat/completions",
        request,
      );

      return response.data;
    } catch (error) {
      console.error("Error sending chat message:", error);

      // Return a fallback response
      return {
        role: "assistant",
        content:
          "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment.",
        session_id: sessionId || this.generateSessionId(),
      };
    }
  }

  /**
   * Stream a chat response from the Agent Engine.
   * This returns an async generator that yields chunks of the response.
   */
  async *streamMessage(
    messages: ChatMessage[],
    sessionId?: string,
  ): AsyncGenerator<string, void, unknown> {
    try {
      const request: ChatRequest = {
        messages,
        stream: true,
        session_id: sessionId || this.generateSessionId(),
      };

      const response = await this.apiClient.post(
        "/api/v1/chat/completions",
        request,
        {
          responseType: "stream",
          headers: {
            Accept: "text/plain",
          },
        },
      );

      const reader = response.data.getReader();
      const decoder = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6).trim();
              if (data === "[DONE]") {
                return;
              }
              if (data) {
                yield data;
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      console.error("Error streaming chat message:", error);
      yield "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment.";
    }
  }

  /**
   * Check if the chat service is healthy and available.
   */
  async checkHealth(): Promise<boolean> {
    try {
      const response = await this.apiClient.get("/api/v1/chat/health");
      return response.data.status === "healthy";
    } catch (error) {
      console.error("Chat health check failed:", error);
      return false;
    }
  }

  /**
   * Generate a unique session ID for conversation tracking.
   */
  private generateSessionId(): string {
    return `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Format messages for display in the UI.
   */
  formatMessage(content: string): string {
    // Basic formatting - could be enhanced with markdown parsing
    return content.trim();
  }

  /**
   * Validate if a message is appropriate (basic validation).
   */
  validateMessage(content: string): { valid: boolean; reason?: string } {
    if (!content.trim()) {
      return { valid: false, reason: "Message cannot be empty" };
    }

    if (content.length > 4000) {
      return {
        valid: false,
        reason: "Message is too long (max 4000 characters)",
      };
    }

    return { valid: true };
  }

  /**
   * Create a new conversation/chat session.
   */
  async createConversation(
    conversationName?: string,
  ): Promise<ConversationInfo> {
    try {
      const response = await this.apiClient.post<ConversationInfo>(
        "/api/v1/chat/conversations",
        { conversation_name: conversationName },
      );
      return response.data;
    } catch (error) {
      console.error("Error creating conversation:", error);
      throw new Error("Failed to create new conversation");
    }
  }

  /**
   * Get all conversations for the current user.
   */
  async getConversations(): Promise<ConversationInfo[]> {
    try {
      const response = await this.apiClient.get<ConversationListResponse>(
        "/api/v1/chat/conversations",
      );
      // API returns {conversations: ConversationInfo[], total_count: number}
      const data = response.data;
      if (data && Array.isArray(data.conversations)) {
        return data.conversations;
      }
      // Fallback: check if response.data is directly an array (for backward compatibility)
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      console.error("Error fetching conversations:", error);
      return [];
    }
  }

  /**
   * Update conversation metadata (like name).
   */
  async updateConversation(
    sessionId: string,
    conversationName: string,
  ): Promise<ConversationInfo> {
    try {
      const response = await this.apiClient.put<ConversationInfo>(
        `/api/v1/chat/conversations/${sessionId}`,
        { conversation_name: conversationName },
      );
      return response.data;
    } catch (error) {
      console.error("Error updating conversation:", error);
      throw new Error("Failed to update conversation");
    }
  }

  /**
   * Get conversation history (messages) for a specific session.
   */
  async getConversationHistory(sessionId: string): Promise<any> {
    try {
      const response = await this.apiClient.get(
        `/api/v1/chat/conversations/${sessionId}/history`,
      );
      return response.data;
    } catch (error) {
      console.error("Error fetching conversation history:", error);
      return null;
    }
  }

  /**
   * Delete a conversation and its associated session.
   */
  async deleteConversation(sessionId: string): Promise<boolean> {
    try {
      await this.apiClient.delete(`/api/v1/chat/conversations/${sessionId}`);
      return true;
    } catch (error) {
      console.error("Error deleting conversation:", error);
      return false;
    }
  }
}

// Export a singleton instance
export const chatService = new ChatService();
export default chatService;
