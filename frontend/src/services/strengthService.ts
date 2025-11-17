import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface Strength {
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

export interface StrengthCreate {
  display_name: string;
  description: string;
}

export interface StrengthUpdate {
  display_name?: string;
  description?: string;
}

interface StrengthListResponse {
  strengths: Strength[];
  total_count: number;
}

class StrengthService {
  async list(
    accountId: AccountId,
    skip = 0,
    limit = 1000,
  ): Promise<StrengthListResponse> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/strengths`,
      { params: { skip, limit } },
    );
    return response.data;
  }

  async create(accountId: AccountId, data: StrengthCreate): Promise<Strength> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/strengths`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: StrengthUpdate,
  ): Promise<Strength> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/strengths/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/strengths/${nodeId}`,
    );
  }
}

export const strengthService = new StrengthService();
