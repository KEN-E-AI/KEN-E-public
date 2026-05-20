/**
 * Chat service for communicating with the Vertex AI Agent Engine via API.
 *
 * This module delegates all API calls to `@/lib/chatApi`. The class shape,
 * singleton export, and type re-exports are preserved so existing callers
 * (ChatContext.tsx) require no edits in this PR.
 *
 * Deletion of this file is deferred to the CH-PRD-02 follow-up PR (AC-15)
 * once all callers migrate directly to `@/lib/chatApi`.
 */

// Re-export legacy types so `import { type ChatMessage, type ConversationInfo }
// from "@/services/chatService"` in ChatContext.tsx continues to resolve.
export type {
  ChatMessage,
  ChatRequest,
  ChatResponse,
  ConversationInfo,
  ConversationListResponse,
} from "@/lib/chatApi";

import {
  postChatCompletion,
  streamChatCompletion,
  chatHealth,
  createChatConversation,
  listChatConversationsLegacy,
  updateChatConversation,
  getConversationHistory,
  deleteChatConversation,
} from "@/lib/chatApi";
import type {
  ChatMessage,
  ChatResponse,
  ConversationInfo,
} from "@/lib/chatApi";

class ChatService {
  /**
   * Send a chat message and get a response from the Agent Engine.
   */
  async sendMessage(
    messages: ChatMessage[],
    sessionId?: string,
    accountId?: string,
  ): Promise<ChatResponse> {
    try {
      return await postChatCompletion(messages, sessionId, accountId);
    } catch (error) {
      console.error("Error sending chat message:", error);
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
    accountId?: string,
  ): AsyncGenerator<string, void, unknown> {
    try {
      yield* streamChatCompletion(messages, sessionId, accountId);
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
      const result = await chatHealth();
      return result.status === "healthy";
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
    accountId?: string,
  ): Promise<ConversationInfo> {
    try {
      return await createChatConversation({
        conversation_name: conversationName,
        account_id: accountId,
      });
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
      const data = await listChatConversationsLegacy();
      if (data && Array.isArray(data.conversations)) {
        return data.conversations;
      }
      return [];
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
      return await updateChatConversation(sessionId, conversationName);
    } catch (error) {
      console.error("Error updating conversation:", error);
      throw new Error("Failed to update conversation");
    }
  }

  /**
   * Get conversation history (messages) for a specific session.
   */
  async getConversationHistory(sessionId: string): Promise<unknown> {
    try {
      return await getConversationHistory(sessionId);
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
      await deleteChatConversation(sessionId);
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
