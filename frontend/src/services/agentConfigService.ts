/**
 * Agent configuration service for managing strategy agent configs in Firestore.
 */

import axios from "axios";
import { auth } from "@/lib/firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

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

    // Add response interceptor
    this.apiClient.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error("Agent config API error:", error);
        return Promise.reject(error);
      },
    );
  }

  /**
   * Get list of all agent config IDs.
   */
  async listConfigs(): Promise<string[]> {
    try {
      const response = await this.apiClient.get<string[]>(
        "/api/v1/agent-configs/",
      );
      return response.data;
    } catch (error) {
      console.error("Error listing agent configs:", error);
      throw new Error("Failed to list agent configs");
    }
  }

  /**
   * Get a specific agent configuration.
   */
  async getConfig(configId: string): Promise<AgentConfig> {
    try {
      const response = await this.apiClient.get<AgentConfig>(
        `/api/v1/agent-configs/${configId}`,
      );
      return response.data;
    } catch (error) {
      console.error(`Error getting config ${configId}:`, error);
      throw new Error(`Failed to get config: ${configId}`);
    }
  }

  /**
   * Update an agent configuration.
   */
  async updateConfig(
    configId: string,
    update: AgentConfigUpdate,
  ): Promise<AgentConfig> {
    try {
      const response = await this.apiClient.put<AgentConfig>(
        `/api/v1/agent-configs/${configId}`,
        update,
      );
      return response.data;
    } catch (error) {
      console.error(`Error updating config ${configId}:`, error);
      throw new Error(`Failed to update config: ${configId}`);
    }
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
  ): Record<string, { researcher: string; formatter: string }> {
    const categories: Record<
      string,
      { researcher: string; formatter: string }
    > = {};

    for (const id of configIds) {
      if (id.includes("business")) {
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
