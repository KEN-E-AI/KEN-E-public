import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import type { AccountId, MetricId } from "@/lib/branded-types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Types
interface Metric {
  id: MetricId;
  account_id: AccountId;
  d3_format: string;
  verbose_name: string;
  expression: string;
  metric_name: string;
  currency: string;
  account_components: string[];
  related_dataset_id: number;
  related_dataset_name: string;
  related_dataset_products: string[];
  description: string;
  below_zero: boolean;
  is_kpi: boolean;
}

interface MetricRequest {
  account_id: AccountId;
  metric_id?: MetricId;
  d3_format?: string;
  verbose_name?: string;
  expression?: string;
  metric_name?: string;
  currency?: string;
  account_components?: string[];
  related_dataset_id?: number;
  related_dataset_name?: string;
  related_dataset_products?: string[];
  description?: string;
  below_zero?: boolean;
  is_kpi?: boolean;
}

// Query keys factory
export const metricKeys = {
  all: ["metrics"] as const,
  lists: () => [...metricKeys.all, "list"] as const,
  list: (accountId: AccountId) => [...metricKeys.lists(), accountId] as const,
  details: () => [...metricKeys.all, "detail"] as const,
  detail: (id: MetricId) => [...metricKeys.details(), id] as const,
  kpis: (accountId: AccountId) =>
    [...metricKeys.list(accountId), "kpis"] as const,
};

// API functions
const getMetrics = async (accountId: AccountId): Promise<Metric[]> => {
  const { data } = await axios.get(
    `${API_BASE_URL}/api/v1/metrics?account_id=${accountId}`,
  );
  return data.metrics || [];
};

const createMetric = async (metric: MetricRequest): Promise<Metric> => {
  const { data } = await axios.post(`${API_BASE_URL}/api/v1/metrics`, metric);
  return data;
};

const updateMetric = async (metric: MetricRequest): Promise<Metric> => {
  const { data } = await axios.put(`${API_BASE_URL}/api/v1/metrics`, metric);
  return data;
};

const deleteMetric = async (
  accountId: AccountId,
  metricId: MetricId,
): Promise<void> => {
  await axios.delete(
    `${API_BASE_URL}/api/v1/metrics?account_id=${accountId}&metric_id=${metricId}`,
  );
};

// Queries
export const useMetrics = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId ? metricKeys.list(accountId) : ["metrics-disabled"],
    queryFn: async () => {
      if (!accountId) return [];
      return getMetrics(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export const useKPIMetrics = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId ? metricKeys.kpis(accountId) : ["kpis-disabled"],
    queryFn: async () => {
      if (!accountId) return [];
      const metrics = await getMetrics(accountId);
      return metrics.filter((m) => m.is_kpi);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

// Mutations
export const useCreateMetric = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMetric,
    onSuccess: (newMetric) => {
      // Invalidate and refetch metrics list
      queryClient.invalidateQueries({
        queryKey: metricKeys.list(newMetric.account_id),
      });
    },
    onError: (error) => {
      console.error("[useCreateMetric] Error:", error);
    },
  });
};

export const useUpdateMetric = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateMetric,
    onSuccess: (updatedMetric) => {
      // Invalidate lists and specific metric
      queryClient.invalidateQueries({
        queryKey: metricKeys.list(updatedMetric.account_id),
      });
      if (updatedMetric.id) {
        queryClient.invalidateQueries({
          queryKey: metricKeys.detail(updatedMetric.id),
        });
      }
    },
    onError: (error) => {
      console.error("[useUpdateMetric] Error:", error);
    },
  });
};

export const useDeleteMetric = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      metricId,
    }: {
      accountId: AccountId;
      metricId: MetricId;
    }) => {
      return deleteMetric(accountId, metricId);
    },
    onSuccess: (_, { accountId }) => {
      // Invalidate and refetch metrics list
      queryClient.invalidateQueries({
        queryKey: metricKeys.list(accountId),
      });
    },
    onError: (error) => {
      console.error("[useDeleteMetric] Error:", error);
    },
  });
};
