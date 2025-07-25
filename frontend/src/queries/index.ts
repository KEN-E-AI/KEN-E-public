/**
 * Central export for all React Query hooks
 *
 * This file re-exports all query hooks to provide a single
 * import point for components that need data fetching.
 */

// Account queries
export {
  accountKeys,
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from "./accounts";

// Metric queries
export {
  metricKeys,
  useMetrics,
  useKPIMetrics,
  useCreateMetric,
  useUpdateMetric,
  useDeleteMetric,
} from "./metrics";

// Activity queries
export {
  activityKeys,
  useActivities,
  useActivity,
  useCreateActivity,
  useUpdateActivity,
  useDeleteActivity,
  useCreateActivityLog,
  useUpdateActivityLog,
  useDeleteActivityLog,
} from "./activities";

// Insight and Intuition queries
export {
  insightKeys,
  intuitionKeys,
  useInsights,
  useSearchInsights,
  useIntuitions,
  useCreateInsight,
  useUpdateInsight,
  useDeleteInsight,
  useCreateIntuition,
  useUpdateIntuition,
  useDeleteIntuition,
} from "./insights";
