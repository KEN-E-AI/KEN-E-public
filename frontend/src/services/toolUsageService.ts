import { apiClient } from "./apiClient";

export type ToolBreakdown = {
  calls: number;
  success: number;
  failure: number;
  success_rate: number;
  avg_duration_ms: number | null;
};

export type UserBreakdown = {
  calls: number;
  success: number;
  failure: number;
  success_rate: number;
};

export type ToolUsageAggregation = {
  period_start: string;
  period_end: string;
  total_calls: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  avg_duration_ms: number | null;
  total_tokens: number;
  by_tool: Record<string, ToolBreakdown>;
  by_user: Record<string, UserBreakdown>;
  by_status: Record<string, number>;
};

export async function getToolUsage(
  days: number = 30,
): Promise<ToolUsageAggregation> {
  const response = await apiClient.get<ToolUsageAggregation>(
    `/api/v1/usage/tool-usage`,
    { params: { days } },
  );
  return response.data;
}
