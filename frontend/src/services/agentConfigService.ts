/**
 * Agent configuration service for managing strategy agent configs in Firestore.
 */

import axios, { AxiosError } from "axios";
import { auth } from "@/lib/firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * Custom error class for agent config service operations.
 */
export class AgentConfigServiceError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: unknown,
  ) {
    super(message);
    this.name = "AgentConfigServiceError";
  }
}

export interface AgentConfigMetadata {
  version: string;
  variant_name: string;
  experiment_id: string;
  created_at: string;
  updated_at: string;
  updated_by: string;
  notes: string;
}

export interface GenerateContentConfig {
  temperature: number;
  max_output_tokens: number;
}

export interface AgentConfig {
  name: string;
  model: string;
  description: string;
  instruction: string;
  generate_content_config: GenerateContentConfig;
  metadata: AgentConfigMetadata;
}

export interface AgentConfigUpdate {
  instruction?: string;
  model?: string;
  description?: string;
  temperature?: number;
  max_output_tokens?: number;
  version?: string;
  variant_name?: string;
  experiment_id?: string;
  updated_by: string;
  notes?: string;
}

class AgentConfigService {
  private apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
  });

  private maxRetries = 3;
  private retryDelay = 1000;

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

    // Add response interceptor with retry logic
    this.apiClient.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const config = error.config;
        const retryCount = (config as any).__retryCount || 0;

        // Don't retry on client errors (4xx) except 429 (rate limit)
        if (
          error.response &&
          error.response.status >= 400 &&
          error.response.status < 500 &&
          error.response.status !== 429
        ) {
          console.error("Agent config API error:", error);
          throw new AgentConfigServiceError(
            (error.response.data as any)?.detail || "Request failed",
            error.response.status,
            error,
          );
        }

        // Retry on server errors (5xx), 429 (rate limit), or network errors
        if (retryCount < this.maxRetries) {
          (config as any).__retryCount = retryCount + 1;

          // Exponential backoff
          const delay = this.retryDelay * Math.pow(2, retryCount);
          await new Promise((resolve) => setTimeout(resolve, delay));

          console.log(
            `Retrying request (attempt ${retryCount + 1}/${this.maxRetries})`,
          );
          return this.apiClient(config!);
        }

        console.error("Agent config API error after retries:", error);
        throw new AgentConfigServiceError(
          "Request failed after retries",
          error.response?.status,
          error,
        );
      },
    );
  }

  /**
   * Get list of all agent config IDs.
   * Automatically retries on network/server errors.
   */
  async listConfigs(): Promise<string[]> {
    const response = await this.apiClient.get<string[]>(
      "/api/v1/agent-configs/",
    );
    return response.data;
  }

  /**
   * Get a specific agent configuration.
   * Automatically retries on network/server errors.
   */
  async getConfig(configId: string): Promise<AgentConfig> {
    const response = await this.apiClient.get<AgentConfig>(
      `/api/v1/agent-configs/${configId}`,
    );
    return response.data;
  }

  /**
   * Update an agent configuration.
   * Automatically retries on network/server errors.
   */
  async updateConfig(
    configId: string,
    update: AgentConfigUpdate,
  ): Promise<AgentConfig> {
    const response = await this.apiClient.put<AgentConfig>(
      `/api/v1/agent-configs/${configId}`,
      update,
    );
    return response.data;
  }

  /**
   * Helper to parse agent name from config ID.
   * Example: "business_researcher" -> "Business Researcher"
   */
  formatAgentName(configId: string): string {
    return configId
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  /**
   * Helper to categorize configs by strategy type.
   */
  categorizeConfigs(
    configIds: string[],
  ): Record<
    string,
    { researcher?: string; formatter?: string; chatbot?: string }
  > {
    const categories: Record<
      string,
      { researcher?: string; formatter?: string; chatbot?: string }
    > = {};

    for (const id of configIds) {
      if (id === "ken_e_chatbot") {
        // Special handling for chatbot config
        if (!categories.chatbot) categories.chatbot = {};
        categories.chatbot.chatbot = id;
      } else if (id.includes("business")) {
        if (!categories.business)
          categories.business = { researcher: "", formatter: "" };
        if (id.includes("researcher")) categories.business.researcher = id;
        else categories.business.formatter = id;
      } else if (id.includes("competitive")) {
        if (!categories.competitive)
          categories.competitive = { researcher: "", formatter: "" };
        if (id.includes("researcher")) categories.competitive.researcher = id;
        else categories.competitive.formatter = id;
      } else if (id.includes("marketing")) {
        if (!categories.marketing)
          categories.marketing = { researcher: "", formatter: "" };
        if (id.includes("researcher")) categories.marketing.researcher = id;
        else categories.marketing.formatter = id;
      } else if (id.includes("brand")) {
        if (!categories.brand)
          categories.brand = { researcher: "", formatter: "" };
        if (id.includes("researcher")) categories.brand.researcher = id;
        else categories.brand.formatter = id;
      }
    }

    return categories;
  }
}

// Export singleton instance
export const agentConfigService = new AgentConfigService();
export default agentConfigService;
