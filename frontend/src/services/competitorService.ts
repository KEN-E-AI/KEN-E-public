import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Competitor {
  node_id: string;
  account_id: string;
  display_name: string;
  description: string;
  references: string[];
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}

export interface CompetitorCreate {
  display_name: string;
  description: string;
  references?: string[];
}

export interface CompetitorUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface CompetitorListResponse {
  competitors: Competitor[];
  total_count: number;
}

class CompetitorService {
  async list(
    accountId: AccountId,
    skip = 0,
    limit = 1000
  ): Promise<CompetitorListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/competitors`,
      { params: { skip, limit } }
    );
    return response.data;
  }

  async get(accountId: AccountId, nodeId: string): Promise<Competitor> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/competitors/${nodeId}`
    );
    return response.data;
  }

  async create(accountId: AccountId, data: CompetitorCreate): Promise<Competitor> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/competitors`,
      data
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: CompetitorUpdate
  ): Promise<Competitor> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/competitors/${nodeId}`,
      data
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/competitors/${nodeId}`
    );
  }
}

export const competitorService = new CompetitorService();
