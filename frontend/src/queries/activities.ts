import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import type { AccountId, ActivityId, ActivityLogId } from "@/lib/branded-types";
import type {
  Activity,
  ActivityLog,
  ActivityRequest,
  ActivityLogRequest,
  HolidaySyncResponse,
} from "@/types/activities";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Query keys factory
export const activityKeys = {
  all: ["activities"] as const,
  lists: () => [...activityKeys.all, "list"] as const,
  list: (accountId: AccountId) => [...activityKeys.lists(), accountId] as const,
  details: () => [...activityKeys.all, "detail"] as const,
  detail: (id: ActivityId) => [...activityKeys.details(), id] as const,
  logs: (activityId: ActivityId) =>
    [...activityKeys.detail(activityId), "logs"] as const,
};

// API functions
const getActivities = async (accountId: AccountId): Promise<Activity[]> => {
  const { data } = await axios.get(
    `${API_BASE_URL}/api/v1/activities?account_id=${accountId}`,
  );
  return data.activities || [];
};

const createActivity = async (activity: ActivityRequest): Promise<Activity> => {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/activities`,
    activity,
  );
  return data;
};

const updateActivity = async (activity: ActivityRequest): Promise<Activity> => {
  const { data } = await axios.put(
    `${API_BASE_URL}/api/v1/activities`,
    activity,
  );
  return data;
};

const deleteActivity = async (
  accountId: AccountId,
  activityId: ActivityId,
): Promise<void> => {
  await axios.delete(
    `${API_BASE_URL}/api/v1/activities?account_id=${accountId}&activity_id=${activityId}`,
  );
};

const createActivityLog = async (
  log: ActivityLogRequest,
): Promise<ActivityLog> => {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/activity-logs`,
    log,
  );
  return data;
};

const updateActivityLog = async (
  log: ActivityLogRequest,
): Promise<ActivityLog> => {
  const { data } = await axios.put(`${API_BASE_URL}/api/v1/activity-logs`, log);
  return data;
};

const deleteActivityLog = async (
  accountId: AccountId,
  activityId: ActivityId,
  activityLogId: ActivityLogId,
): Promise<void> => {
  await axios.delete(
    `${API_BASE_URL}/api/v1/activity-logs?account_id=${accountId}&activity_id=${activityId}&activity_log_id=${activityLogId}`,
  );
};

const syncHolidayActivityLogs = async (
  accountId: AccountId,
): Promise<HolidaySyncResponse> => {
  const { data } = await axios.post<HolidaySyncResponse>(
    `${API_BASE_URL}/api/v1/activities/logs/sync?account_id=${accountId}`,
  );
  return data;
};

// Queries
export const useActivities = (accountId: AccountId | null) => {
  return useQuery({
    queryKey: accountId
      ? activityKeys.list(accountId)
      : ["activities-disabled"],
    queryFn: async () => {
      if (!accountId) return [];
      return getActivities(accountId);
    },
    enabled: !!accountId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export const useActivity = (activityId: ActivityId | null) => {
  return useQuery({
    queryKey: activityId
      ? activityKeys.detail(activityId)
      : ["activity-disabled"],
    queryFn: async () => {
      if (!activityId) return null;
      // In a real implementation, we'd have a getActivity endpoint
      // For now, we'll return null
      return null;
    },
    enabled: !!activityId,
  });
};

// Mutations
export const useCreateActivity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createActivity,
    onSuccess: (newActivity) => {
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(newActivity.account_id),
      });
    },
    onError: (error) => {
      console.error("[useCreateActivity] Error:", error);
    },
  });
};

export const useUpdateActivity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateActivity,
    onSuccess: (updatedActivity) => {
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(updatedActivity.account_id),
      });
      if (updatedActivity.id) {
        queryClient.invalidateQueries({
          queryKey: activityKeys.detail(updatedActivity.id),
        });
      }
    },
    onError: (error) => {
      console.error("[useUpdateActivity] Error:", error);
    },
  });
};

export const useDeleteActivity = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      activityId,
    }: {
      accountId: AccountId;
      activityId: ActivityId;
    }) => {
      return deleteActivity(accountId, activityId);
    },
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(accountId),
      });
    },
    onError: (error) => {
      console.error("[useDeleteActivity] Error:", error);
    },
  });
};

// Activity Log mutations
export const useCreateActivityLog = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createActivityLog,
    onSuccess: (newLog, variables) => {
      if (variables.activity_id) {
        queryClient.invalidateQueries({
          queryKey: activityKeys.logs(variables.activity_id),
        });
      }
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(newLog.account_id),
      });
    },
    onError: (error) => {
      console.error("[useCreateActivityLog] Error:", error);
    },
  });
};

export const useUpdateActivityLog = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateActivityLog,
    onSuccess: (updatedLog, variables) => {
      if (variables.activity_id) {
        queryClient.invalidateQueries({
          queryKey: activityKeys.logs(variables.activity_id),
        });
      }
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(updatedLog.account_id),
      });
    },
    onError: (error) => {
      console.error("[useUpdateActivityLog] Error:", error);
    },
  });
};

export const useDeleteActivityLog = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      accountId,
      activityId,
      activityLogId,
    }: {
      accountId: AccountId;
      activityId: ActivityId;
      activityLogId: ActivityLogId;
    }) => {
      return deleteActivityLog(accountId, activityId, activityLogId);
    },
    onSuccess: (_, { accountId, activityId }) => {
      queryClient.invalidateQueries({
        queryKey: activityKeys.logs(activityId),
      });
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(accountId),
      });
    },
    onError: (error) => {
      console.error("[useDeleteActivityLog] Error:", error);
    },
  });
};

// Sync holiday activity logs mutation
export const useSyncHolidayActivityLogs = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (accountId: AccountId) => {
      return syncHolidayActivityLogs(accountId);
    },
    onSuccess: (data, accountId) => {
      // Invalidate activities list to refresh the holiday logs
      queryClient.invalidateQueries({
        queryKey: activityKeys.list(accountId),
      });
      console.log("[useSyncHolidayActivityLogs] Sync completed:", data);
    },
    onError: (error) => {
      console.error("[useSyncHolidayActivityLogs] Error:", error);
    },
  });
};
