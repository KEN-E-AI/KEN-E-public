import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Opportunity {
  node_id: string;
  account_id: string;
  display_name: string;
  description: string;
  references: string[];
  strength_node_id: string;
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface OpportunityCreate {
  display_name: string;
  description: string;
  strength_node_id: string;
  references?: string[];
}

export interface OpportunityUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface OpportunityListResponse {
  opportunities: Opportunity[];
  total_count: number;
}

class OpportunityService {
  async list(
    accountId: AccountId,
    strengthNodeId?: string,
    skip = 0,
    limit = 1000,
  ): Promise<OpportunityListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/opportunities`,
      { params: { strength_node_id: strengthNodeId, skip, limit } },
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: OpportunityCreate,
  ): Promise<Opportunity> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/opportunities`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: OpportunityUpdate,
  ): Promise<Opportunity> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/opportunities/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/opportunities/${nodeId}`,
    );
  }
}

export const opportunityService = new OpportunityService();
