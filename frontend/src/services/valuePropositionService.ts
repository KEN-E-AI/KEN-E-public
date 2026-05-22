import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface ValueProposition {
  node_id: string;
  account_id: string;
  display_name: string;
  description: string;
  references: string[];
  parent_node_id?: string;
  parent_node_type?: string;
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface ValuePropositionCreate {
  display_name: string;
  description: string;
  parent_node_id: string;
  parent_node_type:
    | "Account"
    | "ProductCategory"
    | "Product"
    | "Competitor"
    | "SubstituteProduct";
  references?: string[];
}

export interface ValuePropositionUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface ValuePropositionListResponse {
  value_propositions: ValueProposition[];
  total_count: number;
}

class ValuePropositionService {
  async list(
    accountId: AccountId,
    parentNodeId?: string,
    skip = 0,
    limit = 1000,
  ): Promise<ValuePropositionListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/value-propositions`,
      { params: { parent_node_id: parentNodeId, skip, limit } },
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: ValuePropositionCreate,
  ): Promise<ValueProposition> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/value-propositions`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: ValuePropositionUpdate,
  ): Promise<ValueProposition> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/value-propositions/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/value-propositions/${nodeId}`,
    );
  }
}

export const valuePropositionService = new ValuePropositionService();
