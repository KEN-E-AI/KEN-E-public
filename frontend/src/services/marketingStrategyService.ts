import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export type StrategyType =
  | "problem-awareness"
  | "brand-awareness"
  | "consideration"
  | "conversion"
  | "loyalty";

export interface MarketingStrategy {
  node_id: string;
  account_id: string;
  description: string;
  references?: string[];
  customer_profile_node_id?: string;
  product_category_node_id?: string;
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface MarketingStrategyUpdate {
  description?: string;
  references?: string[];
}

interface StrategyListResponse {
  problem_awareness_strategies?: MarketingStrategy[];
  brand_awareness_strategies?: MarketingStrategy[];
  consideration_strategies?: MarketingStrategy[];
  conversion_strategies?: MarketingStrategy[];
  loyalty_strategies?: MarketingStrategy[];
  total_count: number;
}

// Helper to extract strategies from response regardless of field name
function extractStrategies(
  response: StrategyListResponse,
): MarketingStrategy[] {
  return (
    response.problem_awareness_strategies ||
    response.brand_awareness_strategies ||
    response.consideration_strategies ||
    response.conversion_strategies ||
    response.loyalty_strategies ||
    []
  );
}

class MarketingStrategyService {
  private getEndpointPrefix(strategyType: StrategyType): string {
    const typeMap: Record<StrategyType, string> = {
      "problem-awareness": "problem-awareness-strategies",
      "brand-awareness": "brand-awareness-strategies",
      consideration: "consideration-strategies",
      conversion: "conversion-strategies",
      loyalty: "loyalty-strategies",
    };
    return typeMap[strategyType];
  }

  async listRollupStrategies(
    accountId: AccountId,
    strategyType: StrategyType,
    skip = 0,
    limit = 1000,
  ): Promise<{ strategies: MarketingStrategy[]; total_count: number }> {
    const endpoint = this.getEndpointPrefix(strategyType);
    const params = { skip, limit };

    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/rollup-${endpoint}`,
      { params },
    );
    const data = response.data as StrategyListResponse;
    return {
      strategies: extractStrategies(data),
      total_count: data.total_count,
    };
  }

  async listIndividualStrategies(
    accountId: AccountId,
    strategyType: StrategyType,
    skip = 0,
    limit = 1000,
  ): Promise<{ strategies: MarketingStrategy[]; total_count: number }> {
    const endpoint = this.getEndpointPrefix(strategyType);
    const params = { skip, limit };

    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/${endpoint}`,
      { params },
    );
    const data = response.data as StrategyListResponse;
    return {
      strategies: extractStrategies(data),
      total_count: data.total_count,
    };
  }

  async updateStrategy(
    accountId: AccountId,
    strategyType: StrategyType,
    nodeId: string,
    updates: MarketingStrategyUpdate,
  ): Promise<MarketingStrategy> {
    const endpoint = this.getEndpointPrefix(strategyType);

    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/${endpoint}/${nodeId}`,
      updates,
    );
    return response.data;
  }

  async deleteStrategy(
    accountId: AccountId,
    strategyType: StrategyType,
    nodeId: string,
  ): Promise<void> {
    const endpoint = this.getEndpointPrefix(strategyType);

    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/${endpoint}/${nodeId}`,
    );
  }
}

export const marketingStrategyService = new MarketingStrategyService();
