import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface CompetitorTactic {
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

export interface CompetitorTacticCreate {
  display_name: string;
  description: string;
  references?: string[];
  competitor_node_id: string;
}

export interface CompetitorTacticUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface CompetitorTacticListResponse {
  tactics: CompetitorTactic[];
  total_count: number;
}

class CompetitorTacticService {
  async list(
    accountId: AccountId,
    competitorId?: string,
    skip = 0,
    limit = 1000
  ): Promise<CompetitorTacticListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/competitor-tactics`,
      { params: { competitor_node_id: competitorId, skip, limit } }
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: CompetitorTacticCreate
  ): Promise<CompetitorTactic> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/competitor-tactics`,
      data
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: CompetitorTacticUpdate
  ): Promise<CompetitorTactic> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/competitor-tactics/${nodeId}`,
      data
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/competitor-tactics/${nodeId}`
    );
  }
}

export const competitorTacticService = new CompetitorTacticService();
