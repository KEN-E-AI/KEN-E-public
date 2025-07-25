import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import type {
  AccountId,
  ActivityId,
  MetricId,
  ActivityLogId,
  InsightId,
  IntuitionId,
} from "@/lib/branded-types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Types
type RelationshipType =
  | "INFLUENCE_CONFIRMED"
  | "NO_INFLUENCE_CONFIRMED"
  | "INFLUENCE_LIKELY";
type DirectionType = "positive" | "negative";

interface Insight {
  activity_id: ActivityId;
  metric_id: MetricId;
  activity_log_id: ActivityLogId;
  relationship_type: RelationshipType;
  direction?: DirectionType;
  metric_verbose_name: string;
  related_dataset_products: string[];
  evidence?: any;
  activity_description: string;
}

interface Intuition {
  activity_id: ActivityId;
  metric_id: MetricId;
  direction: DirectionType;
}

interface InsightRequest {
  account_id: AccountId;
  activity_id?: ActivityId;
  metric_id?: MetricId;
  activity_log_id?: ActivityLogId;
  relationship_type?: RelationshipType;
  direction?: DirectionType;
  metric_verbose_name?: string;
  related_dataset_products?: string[];
  evidence?: any;
  activity_description?: string;
}

interface IntuitionRequest {
  account_id: AccountId;
  activity_id?: ActivityId;
  metric_id?: MetricId;
  direction?: DirectionType;
}

interface InsightSearchRequest {
  account_id: AccountId;
  metric_id: MetricId;
  activity_id: ActivityId;
  evaluation_date_start: string;
  evaluation_date_end: string;
  comparison_date_start: string;
  comparison_date_end: string;
  direction: DirectionType;
}

// Query keys factory
export const insightKeys = {
  all: ["insights"] as const,
  lists: () => [...insightKeys.all, "list"] as const,
  list: (accountId: AccountId) => [...insightKeys.lists(), accountId] as const,
  search: (params: InsightSearchRequest) =>
    [...insightKeys.all, "search", params] as const,
};

export const intuitionKeys = {
  all: ["intuitions"] as const,
  lists: () => [...intuitionKeys.all, "list"] as const,
  list: (accountId: AccountId) =>
    [...intuitionKeys.lists(), accountId] as const,
};

// API functions
const getInsights = async (
  accountId: AccountId,
): Promise<{ insights: Insight[]; intuitions: Intuition[] }> => {
  const { data } = await axios.get(
    `${API_BASE_URL}/api/v1/insights?account_id=${accountId}`,
  );
  return {
    insights: data.insights || [],
    intuitions: data.intuitions || [],
  };
};

const searchInsights = async (
  params: InsightSearchRequest,
): Promise<Insight[]> => {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/insights/search`,
    params,
  );
  return data.insights || [];
};

const createInsight = async (insight: InsightRequest): Promise<Insight> => {
  const { data } = await axios.post(`${API_BASE_URL}/api/v1/insights`, insight);
  return data;
};

const updateInsight = async (insight: InsightRequest): Promise<Insight> => {
  const { data } = await axios.put(`${API_BASE_URL}/api/v1/insights`, insight);
  return data;
};

const deleteInsight = async (
  accountId: AccountId,
  activityId: ActivityId,
  metricId: MetricId,
  activityLogId: ActivityLogId,
): Promise<void> => {
  await axios.delete(
    `${API_BASE_URL}/api/v1/insights?account_id=${accountId}&activity_id=${activityId}&metric_id=${metricId}&activity_log_id=${activityLogId}`,
  );
};

const createIntuition = async (
  intuition: IntuitionRequest,
): Promise<Intuition> => {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/intuitions`,
    intuition,
  );
  return data;
};

const updateIntuition = async (
  intuition: IntuitionRequest,
): Promise<Intuition> => {
  const { data } = await axios.put(
    `${API_BASE_URL}/api/v1/intuitions`,
    intuition,
  );
  return data;
};

const deleteIntuition = async (
  accountId: AccountId,
  activityId: ActivityId,
  metricId: MetricId,
): Promise<void> => {
  await axios.delete(
    `${API_BASE_URL}/api/v1/intuitions?account_id=${accountId}&activity_id=${activityId}&metric_id=${metricId}`,
  );
};

// Queries
export const useInsights = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId ? insightKeys.list(accountId) : ["insights-disabled"],
    queryFn: async () => {
      if (!accountId) return { insights: [], intuitions: [] };
      return getInsights(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export const useSearchInsights = (params: InsightSearchRequest | null) => {
  return useQuery({
    queryKey: params
      ? insightKeys.search(params)
      : ["insights-search-disabled"],
    queryFn: async () => {
      if (!params) return [];
      return searchInsights(params);
    },
    enabled: !!params,
  });
};

export const useIntuitions = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? intuitionKeys.list(accountId)
      : ["intuitions-disabled"],
    queryFn: async () => {
      if (!accountId) return [];
      const { intuitions } = await getInsights(accountId);
      return intuitions;
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

// Mutations
export const useCreateInsight = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createInsight,
    onSuccess: (_, variables) => {
      if (variables.account_id) {
        queryClient.invalidateQueries({
          queryKey: insightKeys.list(variables.account_id),
        });
      }
    },
    onError: (error) => {
      console.error("[useCreateInsight] Error:", error);
    },
  });
};

export const useUpdateInsight = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateInsight,
    onSuccess: (_, variables) => {
      if (variables.account_id) {
        queryClient.invalidateQueries({
          queryKey: insightKeys.list(variables.account_id),
        });
      }
    },
    onError: (error) => {
      console.error("[useUpdateInsight] Error:", error);
    },
  });
};

export const useDeleteInsight = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      activityId,
      metricId,
      activityLogId,
    }: {
      accountId: AccountId;
      activityId: ActivityId;
      metricId: MetricId;
      activityLogId: ActivityLogId;
    }) => {
      return deleteInsight(accountId, activityId, metricId, activityLogId);
    },
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({
        queryKey: insightKeys.list(accountId),
      });
    },
    onError: (error) => {
      console.error("[useDeleteInsight] Error:", error);
    },
  });
};

export const useCreateIntuition = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createIntuition,
    onSuccess: (_, variables) => {
      if (variables.account_id) {
        queryClient.invalidateQueries({
          queryKey: intuitionKeys.list(variables.account_id),
        });
        queryClient.invalidateQueries({
          queryKey: insightKeys.list(variables.account_id),
        });
      }
    },
    onError: (error) => {
      console.error("[useCreateIntuition] Error:", error);
    },
  });
};

export const useUpdateIntuition = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateIntuition,
    onSuccess: (_, variables) => {
      if (variables.account_id) {
        queryClient.invalidateQueries({
          queryKey: intuitionKeys.list(variables.account_id),
        });
        queryClient.invalidateQueries({
          queryKey: insightKeys.list(variables.account_id),
        });
      }
    },
    onError: (error) => {
      console.error("[useUpdateIntuition] Error:", error);
    },
  });
};

export const useDeleteIntuition = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      activityId,
      metricId,
    }: {
      accountId: AccountId;
      activityId: ActivityId;
      metricId: MetricId;
    }) => {
      return deleteIntuition(accountId, activityId, metricId);
    },
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({
        queryKey: intuitionKeys.list(accountId),
      });
      queryClient.invalidateQueries({
        queryKey: insightKeys.list(accountId),
      });
    },
    onError: (error) => {
      console.error("[useDeleteIntuition] Error:", error);
    },
  });
};
