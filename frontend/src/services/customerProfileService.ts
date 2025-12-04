import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";

export interface CustomerProfile {
  node_id: string;
  account_id: string;
  display_name: string;
  description: string;
  references: string[];
  created_time: string;
  last_modified: string;
  created_by?: string;
  last_modified_by?: string;
}

export interface CustomerProfileCreate {
  display_name: string;
  description: string;
  references?: string[];
}

export interface CustomerProfileUpdate {
  display_name?: string;
  description?: string;
  references?: string[];
}

interface CustomerProfileListResponse {
  customer_profiles: CustomerProfile[];
  total_count: number;
}

class CustomerProfileService {
  async list(
    accountId: AccountId,
    skip = 0,
    limit = 1000,
  ): Promise<CustomerProfileListResponse> {
    const params = { skip, limit };

    const response = await api.get(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles`,
      { params },
    );
    return response.data;
  }

  async create(
    accountId: AccountId,
    data: CustomerProfileCreate,
  ): Promise<CustomerProfile> {
    const response = await api.post(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles`,
      data,
    );
    return response.data;
  }

  async update(
    accountId: AccountId,
    nodeId: string,
    data: CustomerProfileUpdate,
  ): Promise<CustomerProfile> {
    const response = await api.patch(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles/${nodeId}`,
      data,
    );
    return response.data;
  }

  async delete(accountId: AccountId, nodeId: string): Promise<void> {
    await api.delete(
      `/api/v1/knowledge-graph/${accountId}/customer-profiles/${nodeId}`,
    );
  }
}

export const customerProfileService = new CustomerProfileService();
