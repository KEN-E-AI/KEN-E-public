import { describe, it, expect, vi, beforeEach , type Mocked} from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import axios from "axios";
import type { ReactNode } from "react";
import {
  metricKeys,
  useMetrics,
  useKPIMetrics,
  useCreateMetric,
  useUpdateMetric,
  useDeleteMetric,
} from "./metrics";
import { toAccountId, toMetricId } from "@/lib/branded-types";

// Mock axios
vi.mock("axios");
const mockedAxios = axios as Mocked<typeof axios>;

// Test data
const testAccountId = toAccountId("acc_test123");
const testMetricId = toMetricId("metric_test123");
const testMetric = {
  id: testMetricId,
  account_id: testAccountId,
  d3_format: ".2f",
  verbose_name: "Test Metric",
  expression: "sum(value)",
  metric_name: "test_metric",
  currency: "USD",
  account_components: ["revenue"],
  related_dataset_id: 1,
  related_dataset_name: "Test Dataset",
  related_dataset_products: ["product1"],
  description: "Test metric description",
  below_zero: false,
  is_kpi: false,
};

const testKPIMetric = {
  ...testMetric,
  id: toMetricId("metric_kpi123"),
  verbose_name: "KPI Metric",
  is_kpi: true,
};

describe("Metric Query Hooks", () => {
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

  describe("metricKeys", () => {
    it("generates correct query keys", () => {
      expect(metricKeys.all).toEqual(["metrics"]);
      expect(metricKeys.lists()).toEqual(["metrics", "list"]);
      expect(metricKeys.list(testAccountId)).toEqual([
        "metrics",
        "list",
        testAccountId,
      ]);
      expect(metricKeys.details()).toEqual(["metrics", "detail"]);
      expect(metricKeys.detail(testMetricId)).toEqual([
        "metrics",
        "detail",
        testMetricId,
      ]);
      expect(metricKeys.kpis(testAccountId)).toEqual([
        "metrics",
        "list",
        testAccountId,
        "kpis",
      ]);
    });
  });

  describe("useMetrics", () => {
    it("fetches metrics for an account", async () => {
      const mockMetrics = [testMetric, testKPIMetric];
      mockedAxios.get.mockResolvedValueOnce({
        data: { metrics: mockMetrics },
      });

      const { result } = renderHook(() => useMetrics(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockMetrics);
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining(`/api/v1/metrics?account_id=${testAccountId}`),
      );
    });

    it("returns empty array when accountId is null", async () => {
      const { result } = renderHook(() => useMetrics(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toEqual([]);
      expect(result.current.isSuccess).toBe(true);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it("handles API errors gracefully", async () => {
      const errorMessage = "Network error";
      mockedAxios.get.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useMetrics(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });

    it("returns empty array when API returns no metrics", async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useMetrics(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([]);
    });
  });

  describe("useKPIMetrics", () => {
    it("fetches and filters KPI metrics", async () => {
      const mockMetrics = [testMetric, testKPIMetric];
      mockedAxios.get.mockResolvedValueOnce({
        data: { metrics: mockMetrics },
      });

      const { result } = renderHook(() => useKPIMetrics(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([testKPIMetric]);
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining(`/api/v1/metrics?account_id=${testAccountId}`),
      );
    });

    it("returns empty array when no KPI metrics exist", async () => {
      mockedAxios.get.mockResolvedValueOnce({
        data: { metrics: [testMetric] }, // No KPI metrics
      });

      const { result } = renderHook(() => useKPIMetrics(testAccountId), {
        wrapper: createWrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([]);
    });

    it("returns empty array when accountId is null", async () => {
      const { result } = renderHook(() => useKPIMetrics(null), {
        wrapper: createWrapper,
      });

      expect(result.current.data).toEqual([]);
      expect(result.current.isSuccess).toBe(true);
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });
  });

  describe("useCreateMetric", () => {
    it("creates a metric successfully", async () => {
      const newMetric = { ...testMetric };
      mockedAxios.post.mockResolvedValueOnce({ data: newMetric });

      const { result } = renderHook(() => useCreateMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        verbose_name: "New Metric",
        metric_name: "new_metric",
        expression: "sum(value)",
        d3_format: ".2f",
        currency: "USD",
        is_kpi: false,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(newMetric);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/metrics"),
        expect.objectContaining({
          account_id: testAccountId,
          verbose_name: "New Metric",
        }),
      );
    });

    it("invalidates queries on successful creation", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedAxios.post.mockResolvedValueOnce({ data: testMetric });

      const { result } = renderHook(() => useCreateMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        verbose_name: "New Metric",
        metric_name: "new_metric",
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: metricKeys.list(testAccountId),
      });
    });

    it("handles creation errors", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const errorMessage = "Creation failed";
      mockedAxios.post.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useCreateMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        verbose_name: "New Metric",
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
      expect(consoleSpy).toHaveBeenCalledWith(
        "[useCreateMetric] Error:",
        expect.any(Error),
      );

      consoleSpy.mockRestore();
    });
  });

  describe("useUpdateMetric", () => {
    it("updates a metric successfully", async () => {
      const updatedMetric = { ...testMetric, verbose_name: "Updated Metric" };
      mockedAxios.put.mockResolvedValueOnce({ data: updatedMetric });

      const { result } = renderHook(() => useUpdateMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        metric_id: testMetricId,
        verbose_name: "Updated Metric",
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(updatedMetric);
      expect(mockedAxios.put).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/metrics"),
        expect.objectContaining({
          metric_id: testMetricId,
          verbose_name: "Updated Metric",
        }),
      );
    });

    it("invalidates queries on successful update", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedAxios.put.mockResolvedValueOnce({ data: testMetric });

      const { result } = renderHook(() => useUpdateMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        account_id: testAccountId,
        metric_id: testMetricId,
        verbose_name: "Updated Metric",
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: metricKeys.list(testAccountId),
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: metricKeys.detail(testMetricId),
      });
    });
  });

  describe("useDeleteMetric", () => {
    it("deletes a metric successfully", async () => {
      mockedAxios.delete.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useDeleteMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        accountId: testAccountId,
        metricId: testMetricId,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockedAxios.delete).toHaveBeenCalledWith(
        expect.stringContaining(
          `/api/v1/metrics?account_id=${testAccountId}&metric_id=${testMetricId}`,
        ),
      );
    });

    it("invalidates queries on successful deletion", async () => {
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedAxios.delete.mockResolvedValueOnce({ data: {} });

      const { result } = renderHook(() => useDeleteMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        accountId: testAccountId,
        metricId: testMetricId,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: metricKeys.list(testAccountId),
      });
    });

    it("handles deletion errors", async () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const errorMessage = "Deletion failed";
      mockedAxios.delete.mockRejectedValueOnce(new Error(errorMessage));

      const { result } = renderHook(() => useDeleteMetric(), {
        wrapper: createWrapper,
      });

      result.current.mutate({
        accountId: testAccountId,
        metricId: testMetricId,
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error?.message).toBe(errorMessage);
      expect(consoleSpy).toHaveBeenCalledWith(
        "[useDeleteMetric] Error:",
        expect.any(Error),
      );

      consoleSpy.mockRestore();
    });
  });
});
