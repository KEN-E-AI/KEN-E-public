import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Weakness {
  node_id: string;
  display_name: string;
  description: string;
  account_id?: string;
  created_at?: string;
  updated_at?: string;
  created_time?: string;
  last_modified?: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface WeaknessCreate {
  display_name: string;
  description: string;
}

export interface WeaknessUpdate {
  display_name?: string;
  description?: string;
}

interface WeaknessListResponse {
  weaknesses: Weakness[];
  total_count: number;
}

class WeaknessService {
  async list(
    accountId: AccountId,
    skip = 0,
    limit = 1000,
  ): Promise<WeaknessListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/weaknesses`,
      { params: { skip, limit } },
    );
    return response.data;
  }

  async create(accountId: AccountId, data: WeaknessCreate): Promise<Weakness> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/weaknesses`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: WeaknessUpdate,
  ): Promise<Weakness> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/weaknesses/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/weaknesses/${nodeId}`,
    );
  }
}

export const weaknessService = new WeaknessService();
