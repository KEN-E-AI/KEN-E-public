import { describe, it, expect, vi, beforeEach , type Mocked} from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import axios from "axios";
import type { ReactNode } from "react";
import {
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
import {
  toAccountId,
  toActivityId,
  toActivityLogId,
} from "@/lib/branded-types";

// Mock axios
vi.mock("axios");
const mockedAxios = axios as Mocked<typeof axios>;

// Test data
const testAccountId = toAccountId("acc_test123");
const testActivityId = toActivityId("activity_test123");
const testActivityLogId = toActivityLogId("activitylog_test123");

const testActivityLog = {
  id: testActivityLogId,
  account_id: testAccountId,
  start_date: "2024-01-01",
  end_date: "2024-01-31",
  description: "Test log description",
  evidence: { data: "test" },
};

const testActivity = {
  id: testActivityId,
  account_id: testAccountId,
  activity_name: "Test Activity",
  activity_description: "Test activity description",
  expected_impact: "High",
  internal: false,
  known_activity: true,
  logs: [testActivityLog],
};

describe("Activity Query Hooks", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const createWrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe("activityKeys", () => {
    it("generates correct query keys", () => {
      expect(activityKeys.all).toEqual(["activities"]);
      expect(activityKeys.lists()).toEqual(["activities", "list"]);
      expect(activityKeys.list(testAccountId)).toEqual([
        "activities",
        "list",
        testAccountId,
      ]);
      expect(activityKeys.details()).toEqual(["activities", "detail"]);
      expect(activityKeys.detail(testActivityId)).toEqual([
        "activities",
        "detail",
        testActivityId,
      ]);
      expect(activityKeys.logs(testActivityId)).toEqual([
        "activities",
        "detail",
        testActivityId,
        "logs",
      ]);
    });
  });

  describe("useActivities", () => {
    it("fetches activities for an account", async () => {
      const mockActivities = [testActivity];
      mockedAxios.get.mockResolvedValueOnce({
        data: { activities: mockActivities },
      });

      const { result } = renderHook(() => useActivities(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockActivities);
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/activities?account_id=${testAccountId}`,
        ),
      );
    });

    it("returns empty array when accountId is null", async () => {
      const { result } = renderHook(() => useActivities(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toEqual([]);
      expect(result.current.isSuccess).toBe(true);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it("handles API errors gracefully", async () => {
      const errorMessage = "Network error";
      mockedAxios.get.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useActivities(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe("useActivity", () => {
    it("returns null when activityId is null", async () => {
      const { result } = renderHook(() => useActivity(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toBeNull();
      expect(result.current.isSuccess).toBe(true);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it("fetches single activity when implemented", async () => {
      // Currently returns null as noted in implementation
      const { result } = renderHook(() => useActivity(testActivityId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toBeNull();
    });
  });

  describe("useCreateActivity", () => {
    it("creates an activity successfully", async () => {
      const newActivity = { ...testActivity };
      mockedAxios.post.mockResolvedValueOnce({ data: newActivity });

      const { result } = renderHook(() => useCreateActivity(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        activity_name: "New Activity",
        activity_description: "New description",
        expected_impact: "Medium",
        internal: true,
        known_activity: false,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(newActivity);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/activities"),
        expect.objectContaining({
          account_id: testAccountId,
          activity_name: "New Activity",
        }),
      );
    });

    it("invalidates queries on successful creation", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedAxios.post.mockResolvedValueOnce({ data: testActivity });

      const { result } = renderHook(() => useCreateActivity(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        activity_name: "New Activity",
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: activityKeys.list(testAccountId),
      });
    });
  });

  describe("useUpdateActivity", () => {
    it("updates an activity successfully", async () => {
      const updatedActivity = {
        ...testActivity,
        activity_name: "Updated Activity",
      };
      mockedAxios.put.mockResolvedValueOnce({ data: updatedActivity });

      const { result } = renderHook(() => useUpdateActivity(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        activity_id: testActivityId,
        activity_name: "Updated Activity",
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(updatedActivity);
      expect(mockedAxios.put).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/activities"),
        expect.objectContaining({
          activity_id: testActivityId,
          activity_name: "Updated Activity",
        }),
      );
    });

    it("invalidates queries on successful update", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedAxios.put.mockResolvedValueOnce({ data: testActivity });

      const { result } = renderHook(() => useUpdateActivity(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        activity_id: testActivityId,
        activity_name: "Updated Activity",
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: activityKeys.list(testAccountId),
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: activityKeys.detail(testActivityId),
      });
    });
  });

  describe("useDeleteActivity", () => {
    it("deletes an activity successfully", async () => {
      mockedAxios.delete.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useDeleteActivity(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        accountId: testAccountId,
        activityId: testActivityId,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedAxios.delete).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/activities?account_id=${testAccountId}&activity_id=${testActivityId}`,
        ),
      );
    });

    it("invalidates queries on successful deletion", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedAxios.delete.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useDeleteActivity(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        accountId: testAccountId,
        activityId: testActivityId,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: activityKeys.list(testAccountId),
      });
    });
  });

  describe("Activity Log Mutations", () => {
    describe("useCreateActivityLog", () => {
      it("creates an activity log successfully", async () => {
        const newLog = { ...testActivityLog };
        mockedAxios.post.mockResolvedValueOnce({ data: newLog });

        const { result } = renderHook(() => useCreateActivityLog(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          start_date: "2024-02-01",
          end_date: "2024-02-28",
          description: "New log",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(newLog);
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/activity-logs"),
          expect.objectContaining({
            account_id: testAccountId,
            activity_id: testActivityId,
          }),
        );
      });

      it("invalidates queries on successful creation", async () => {
        const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
        mockedAxios.post.mockResolvedValueOnce({ data: testActivityLog });

        const { result } = renderHook(() => useCreateActivityLog(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          start_date: "2024-02-01",
          end_date: "2024-02-28",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: activityKeys.logs(testActivityId),
        });
        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: activityKeys.list(testAccountId),
        });
      });
    });

    describe("useUpdateActivityLog", () => {
      it("updates an activity log successfully", async () => {
        const updatedLog = { ...testActivityLog, description: "Updated log" };
        mockedAxios.put.mockResolvedValueOnce({ data: updatedLog });

        const { result } = renderHook(() => useUpdateActivityLog(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          activity_log_id: testActivityLogId,
          description: "Updated log",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(updatedLog);
        expect(mockedAxios.put).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/activity-logs"),
          expect.objectContaining({
            activity_log_id: testActivityLogId,
            description: "Updated log",
          }),
        );
      });
    });

    describe("useDeleteActivityLog", () => {
      it("deletes an activity log successfully", async () => {
        mockedAxios.delete.mockResolvedValueOnce({ data: {} });

        const { result } = renderHook(() => useDeleteActivityLog(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          accountId: testAccountId,
          activityId: testActivityId,
          activityLogId: testActivityLogId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(mockedAxios.delete).toHaveBeenCalledWith(
          expect.stringContaining(
            `/api/v1/activity-logs?account_id=${testAccountId}&activity_id=${testActivityId}&activity_log_id=${testActivityLogId}`,
          ),
        );
      });

      it("invalidates queries on successful deletion", async () => {
        const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
        mockedAxios.delete.mockResolvedValueOnce({ data: {} });

        const { result } = renderHook(() => useDeleteActivityLog(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          accountId: testAccountId,
          activityId: testActivityId,
          activityLogId: testActivityLogId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: activityKeys.logs(testActivityId),
        });
        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: activityKeys.list(testAccountId),
        });
      });
    });
  });
});
