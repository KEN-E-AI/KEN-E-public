import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface SubstituteProduct {
  node_id: string;
  account_id: string;
  product_name: string;
  description: string;
  references: string[];
  product_detail_page?: string;
  competitor_node_id: string;
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}

export interface SubstituteProductCreate {
  product_name: string;
  description: string;
  references?: string[];
  product_detail_page?: string;
  competitor_node_id: string;
}

export interface SubstituteProductUpdate {
  product_name?: string;
  description?: string;
  references?: string[];
  product_detail_page?: string;
}

interface SubstituteProductListResponse {
  products: SubstituteProduct[];
  total_count: number;
}

class SubstituteProductService {
  async list(
    accountId: AccountId,
    competitorId?: string,
    skip = 0,
    limit = 1000
  ): Promise<SubstituteProductListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/substitute-products`,
      { params: { competitor_node_id: competitorId, skip, limit } }
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: SubstituteProductCreate
  ): Promise<SubstituteProduct> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/substitute-products`,
      data
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: SubstituteProductUpdate
  ): Promise<SubstituteProduct> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/substitute-products/${nodeId}`,
      data
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/substitute-products/${nodeId}`
    );
  }
}

export const substituteProductService = new SubstituteProductService();
