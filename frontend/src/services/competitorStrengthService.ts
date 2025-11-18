import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface CompetitorStrength {
  node_id: string;
  account_id: string;
  display_name: string;
  description: string;
  references: string[];
  competitor_node_id: string;
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}

export interface CompetitorStrengthCreate {
  display_name: string;
  description: string;
  references?: string[];
  competitor_node_id: string;
}

export interface CompetitorStrengthUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface CompetitorStrengthListResponse {
  strengths: CompetitorStrength[];
  total_count: number;
}

class CompetitorStrengthService {
  async list(
    accountId: AccountId,
    competitorId?: string,
    skip = 0,
    limit = 1000
  ): Promise<CompetitorStrengthListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/competitor-strengths`,
      { params: { competitor_node_id: competitorId, skip, limit } }
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: CompetitorStrengthCreate
  ): Promise<CompetitorStrength> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/competitor-strengths`,
      data
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: CompetitorStrengthUpdate
  ): Promise<CompetitorStrength> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/competitor-strengths/${nodeId}`,
      data
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/competitor-strengths/${nodeId}`
    );
  }
}

export const competitorStrengthService = new CompetitorStrengthService();
