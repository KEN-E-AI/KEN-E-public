import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Risk {
  node_id: string;
  account_id: string;
  display_name: string;
  description: string;
  references: string[];
  weakness_node_id?: string; // For business SWOT
  strength_node_id?: string; // For competitive (CompetitorStrength)
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface RiskCreate {
  display_name: string;
  description: string;
  weakness_node_id?: string; // For business SWOT
  strength_node_id?: string; // For competitive (CompetitorStrength)
  references?: string[];
}

export interface RiskUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface RiskListResponse {
  risks: Risk[];
  total_count: number;
}

class RiskService {
  async list(
    accountId: AccountId,
    weaknessNodeId?: string,
    strengthNodeId?: string,
    skip = 0,
    limit = 1000,
  ): Promise<RiskListResponse> {
    const params: Record<string, any> = { skip, limit };
    if (weaknessNodeId) params.weakness_node_id = weaknessNodeId;
    if (strengthNodeId) params.strength_node_id = strengthNodeId;

    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/risks`,
      { params },
    );
    return response.data;
  }

  async create(accountId: AccountId, data: RiskCreate): Promise<Risk> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/risks`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: RiskUpdate,
  ): Promise<Risk> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/risks/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(`/api/v1/knowledge-graph/${accountId}/risks/${nodeId}`);
  }
}

export const riskService = new RiskService();
