import api from "@/lib/api";
import type { AccountId } from "@/lib/branded-types";
import type {
  MonitoringTopics,
  CompetitorEntry,
  CustomerProfileEntry,
} from "@/types/monitoring";

interface UpdateCompetitorKeywordsRequest {
  account_id: string;
  competitor_index: number;
  node_id?: string;
  name?: string;
  website?: string;
  keywords?: string[];
}

interface UpdateCustomerProfileKeywordsRequest {
  account_id: string;
  customer_profile_index: number;
  node_id?: string;
  keywords?: string[];
}

class MonitoringTopicsService {
  async getMonitoringTopics(accountId: AccountId): Promise<MonitoringTopics> {
    const response = await api.get(`/api/v1/monitoring-topics/${accountId}`);
    return response.data.data;
  }

  async addCompetitorKeywords(
    accountId: AccountId,
    data: CompetitorEntry,
  ): Promise<void> {
    await api.post(`/api/v1/monitoring-topics/${accountId}/competitors`, {
      account_id: accountId,
      competitor_entry: data,
    });
  }

  async updateCompetitorKeywords(
    accountId: AccountId,
    competitorIndex: number,
    data: Partial<CompetitorEntry>,
  ): Promise<void> {
    const request: UpdateCompetitorKeywordsRequest = {
      account_id: accountId,
      competitor_index: competitorIndex,
      ...data,
    };
    await api.put(
      `/api/v1/monitoring-topics/${accountId}/competitors/${competitorIndex}`,
      request,
    );
  }

  async deleteCompetitorKeywords(
    accountId: AccountId,
    competitorIndex: number,
  ): Promise<void> {
    await api.delete(
      `/api/v1/monitoring-topics/${accountId}/competitors/${competitorIndex}`,
      {
        params: { account_id: accountId },
      },
    );
  }

  async addCustomerProfileKeywords(
    accountId: AccountId,
    data: CustomerProfileEntry,
  ): Promise<void> {
    await api.post(`/api/v1/monitoring-topics/${accountId}/customer-profiles`, {
      account_id: accountId,
      customer_profile_entry: data,
    });
  }

  async updateCustomerProfileKeywords(
    accountId: AccountId,
    customerProfileIndex: number,
    data: Partial<CustomerProfileEntry>,
  ): Promise<void> {
    const request: UpdateCustomerProfileKeywordsRequest = {
      account_id: accountId,
      customer_profile_index: customerProfileIndex,
      ...data,
    };
    await api.put(
      `/api/v1/monitoring-topics/${accountId}/customer-profiles/${customerProfileIndex}`,
      request,
    );
  }

  async deleteCustomerProfileKeywords(
    accountId: AccountId,
    customerProfileIndex: number,
  ): Promise<void> {
    await api.delete(
      `/api/v1/monitoring-topics/${accountId}/customer-profiles/${customerProfileIndex}`,
      {
        params: { account_id: accountId },
      },
    );
  }
}

export const monitoringTopicsService = new MonitoringTopicsService();
