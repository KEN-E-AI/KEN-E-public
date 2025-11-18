import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface CompetitiveEnvironment {
  node_id: string;
  account_id: string;
  description: string;
  created_time: string;
  last_modified: string;
  created_by: string;
  last_modified_by: string;
  embedding?: number[];
}

export interface CompetitiveEnvironmentUpdate {
  description?: string;
}

class CompetitiveEnvironmentService {
  async get(accountId: AccountId): Promise<CompetitiveEnvironment> {
    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/competitive-environment`
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    data: CompetitiveEnvironmentUpdate
  ): Promise<CompetitiveEnvironment> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/competitive-environment`,
      data
    );
    return response.data;
  }
}

export const competitiveEnvironmentService =
  new CompetitiveEnvironmentService();
