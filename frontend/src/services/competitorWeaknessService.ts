import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface CompetitorWeakness {
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

export interface CompetitorWeaknessCreate {
  display_name: string;
  description: string;
  references?: string[];
  competitor_node_id: string;
}

export interface CompetitorWeaknessUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface CompetitorWeaknessListResponse {
  weaknesses: CompetitorWeakness[];
  total_count: number;
}

class CompetitorWeaknessService {
  async list(
    accountId: AccountId,
    competitorId?: string,
    skip = 0,
    limit = 1000,
  ): Promise<CompetitorWeaknessListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/competitor-weaknesses`,
      { params: { competitor_node_id: competitorId, skip, limit } },
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: CompetitorWeaknessCreate,
  ): Promise<CompetitorWeakness> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/competitor-weaknesses`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: CompetitorWeaknessUpdate,
  ): Promise<CompetitorWeakness> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/competitor-weaknesses/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/competitor-weaknesses/${nodeId}`,
    );
  }
}

export const competitorWeaknessService = new CompetitorWeaknessService();
