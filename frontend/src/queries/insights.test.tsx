import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import axios from "axios";
import type { ReactNode } from "react";
import {
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
import {
  toAccountId,
  toActivityId,
  toMetricId,
  toActivityLogId,
} from "@/lib/branded-types";

// Mock axios
vi.mock("axios");
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Test data
const testAccountId = toAccountId("acc_test123");
const testActivityId = toActivityId("activity_test123");
const testMetricId = toMetricId("metric_test123");
const testActivityLogId = toActivityLogId("activitylog_test123");

const testInsight = {
  activity_id: testActivityId,
  metric_id: testMetricId,
  activity_log_id: testActivityLogId,
  relationship_type: "INFLUENCE_CONFIRMED" as const,
  direction: "positive" as const,
  metric_verbose_name: "Test Metric",
  related_dataset_products: ["product1"],
  evidence: { data: "test" },
  activity_description: "Test activity",
};

const testIntuition = {
  activity_id: testActivityId,
  metric_id: testMetricId,
  direction: "positive" as const,
};

const testSearchParams = {
  account_id: testAccountId,
  metric_id: testMetricId,
  activity_id: testActivityId,
  evaluation_date_start: "2024-01-01",
  evaluation_date_end: "2024-01-31",
  comparison_date_start: "2023-12-01",
  comparison_date_end: "2023-12-31",
  direction: "positive" as const,
};

describe("Insight Query Hooks", () => {
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

  describe("Query Keys", () => {
    it("generates correct insight query keys", () => {
      expect(insightKeys.all).toEqual(["insights"]);
      expect(insightKeys.lists()).toEqual(["insights", "list"]);
      expect(insightKeys.list(testAccountId)).toEqual([
        "insights",
        "list",
        testAccountId,
      ]);
      expect(insightKeys.search(testSearchParams)).toEqual([
        "insights",
        "search",
        testSearchParams,
      ]);
    });

    it("generates correct intuition query keys", () => {
      expect(intuitionKeys.all).toEqual(["intuitions"]);
      expect(intuitionKeys.lists()).toEqual(["intuitions", "list"]);
      expect(intuitionKeys.list(testAccountId)).toEqual([
        "intuitions",
        "list",
        testAccountId,
      ]);
    });
  });

  describe("useInsights", () => {
    it("fetches insights and intuitions for an account", async () => {
      const mockData = {
        insights: [testInsight],
        intuitions: [testIntuition],
      };
      mockedAxios.get.mockResolvedValueOnce({ data: mockData });

      const { result } = renderHook(() => useInsights(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockData);
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining(`/api/v1/insights?account_id=${testAccountId}`),
      );
    });

    it("returns empty arrays when accountId is null", async () => {
      const { result } = renderHook(() => useInsights(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toEqual({ insights: [], intuitions: [] });
      expect(result.current.isSuccess).toBe(true);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it("handles API errors gracefully", async () => {
      const errorMessage = "Network error";
      mockedAxios.get.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useInsights(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });

    it("returns empty arrays when API returns no data", async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useInsights(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual({ insights: [], intuitions: [] });
    });
  });

  describe("useSearchInsights", () => {
    it("searches insights with parameters", async () => {
      const mockInsights = [testInsight];
      mockedAxios.post.mockResolvedValueOnce({
        data: { insights: mockInsights },
      });

      const { result } = renderHook(() => useSearchInsights(testSearchParams), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockInsights);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/insights/search"),
        testSearchParams,
      );
    });

    it("returns empty array when params is null", async () => {
      const { result } = renderHook(() => useSearchInsights(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toEqual([]);
      expect(result.current.isSuccess).toBe(true);
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    it("returns empty array when API returns no insights", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useSearchInsights(testSearchParams), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([]);
    });
  });

  describe("useIntuitions", () => {
    it("fetches intuitions for an account", async () => {
      const mockIntuitions = [testIntuition];
      mockedAxios.get.mockResolvedValueOnce({
        data: { insights: [], intuitions: mockIntuitions },
      });

      const { result } = renderHook(() => useIntuitions(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockIntuitions);
    });
  });

  describe("Insight Mutations", () => {
    describe("useCreateInsight", () => {
      it("creates an insight successfully", async () => {
        mockedAxios.post.mockResolvedValueOnce({ data: testInsight });

        const { result } = renderHook(() => useCreateInsight(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          metric_id: testMetricId,
          activity_log_id: testActivityLogId,
          relationship_type: "INFLUENCE_CONFIRMED",
          direction: "positive",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(testInsight);
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/insights"),
          expect.objectContaining({
            account_id: testAccountId,
            activity_id: testActivityId,
            metric_id: testMetricId,
          }),
        );
      });

      it("invalidates queries on successful creation", async () => {
        const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
        mockedAxios.post.mockResolvedValueOnce({ data: testInsight });

        const { result } = renderHook(() => useCreateInsight(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          metric_id: testMetricId,
          activity_log_id: testActivityLogId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: insightKeys.list(testAccountId),
        });
      });
    });

    describe("useUpdateInsight", () => {
      it("updates an insight successfully", async () => {
        const updatedInsight = {
          ...testInsight,
          relationship_type: "INFLUENCE_LIKELY" as const,
        };
        mockedAxios.put.mockResolvedValueOnce({ data: updatedInsight });

        const { result } = renderHook(() => useUpdateInsight(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          metric_id: testMetricId,
          activity_log_id: testActivityLogId,
          relationship_type: "INFLUENCE_LIKELY",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(updatedInsight);
      });
    });

    describe("useDeleteInsight", () => {
      it("deletes an insight successfully", async () => {
        mockedAxios.delete.mockResolvedValueOnce({ data: {} });

        const { result } = renderHook(() => useDeleteInsight(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          accountId: testAccountId,
          activityId: testActivityId,
          metricId: testMetricId,
          activityLogId: testActivityLogId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(mockedAxios.delete).toHaveBeenCalledWith(
          expect.stringContaining(
            `/api/v1/insights?account_id=${testAccountId}&activity_id=${testActivityId}&metric_id=${testMetricId}&activity_log_id=${testActivityLogId}`,
          ),
        );
      });

      it("invalidates queries on successful deletion", async () => {
        const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
        mockedAxios.delete.mockResolvedValueOnce({ data: {} });

        const { result } = renderHook(() => useDeleteInsight(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          accountId: testAccountId,
          activityId: testActivityId,
          metricId: testMetricId,
          activityLogId: testActivityLogId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: insightKeys.list(testAccountId),
        });
      });
    });
  });

  describe("Intuition Mutations", () => {
    describe("useCreateIntuition", () => {
      it("creates an intuition successfully", async () => {
        mockedAxios.post.mockResolvedValueOnce({ data: testIntuition });

        const { result } = renderHook(() => useCreateIntuition(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          metric_id: testMetricId,
          direction: "positive",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(testIntuition);
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining("/api/v1/intuitions"),
          expect.objectContaining({
            account_id: testAccountId,
            activity_id: testActivityId,
            metric_id: testMetricId,
            direction: "positive",
          }),
        );
      });

      it("invalidates both insights and intuitions queries", async () => {
        const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
        mockedAxios.post.mockResolvedValueOnce({ data: testIntuition });

        const { result } = renderHook(() => useCreateIntuition(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          metric_id: testMetricId,
          direction: "positive",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: intuitionKeys.list(testAccountId),
        });
        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: insightKeys.list(testAccountId),
        });
      });
    });

    describe("useUpdateIntuition", () => {
      it("updates an intuition successfully", async () => {
        const updatedIntuition = {
          ...testIntuition,
          direction: "negative" as const,
        };
        mockedAxios.put.mockResolvedValueOnce({ data: updatedIntuition });

        const { result } = renderHook(() => useUpdateIntuition(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          account_id: testAccountId,
          activity_id: testActivityId,
          metric_id: testMetricId,
          direction: "negative",
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(updatedIntuition);
      });
    });

    describe("useDeleteIntuition", () => {
      it("deletes an intuition successfully", async () => {
        mockedAxios.delete.mockResolvedValueOnce({ data: {} });

        const { result } = renderHook(() => useDeleteIntuition(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          accountId: testAccountId,
          activityId: testActivityId,
          metricId: testMetricId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(mockedAxios.delete).toHaveBeenCalledWith(
          expect.stringContaining(
            `/api/v1/intuitions?account_id=${testAccountId}&activity_id=${testActivityId}&metric_id=${testMetricId}`,
          ),
        );
      });

      it("invalidates both insights and intuitions queries", async () => {
        const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
        mockedAxios.delete.mockResolvedValueOnce({ data: {} });

        const { result } = renderHook(() => useDeleteIntuition(), {
          wrapper: createWrapper,
        });

        result.current.mutate({
          accountId: testAccountId,
          activityId: testActivityId,
          metricId: testMetricId,
        });

        await waitFor(() => {
          expect(result.current.isSuccess).toBe(true);
        });

        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: intuitionKeys.list(testAccountId),
        });
        expect(invalidateQueriesSpy).toHaveBeenCalledWith({
          queryKey: insightKeys.list(testAccountId),
        });
      });
    });
  });
});
