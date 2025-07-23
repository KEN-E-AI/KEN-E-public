import { describe, test, expect, vi, beforeEach } from "vitest";
import axios from "axios";
import {
  getSubscriptionPlans,
  getDefaultPlan,
  getSubscriptionPlan,
} from "./subscriptionPlansApi";
import type { SubscriptionPlanDefinition } from "../types/subscription";

// Mock axios
vi.mock("axios");
const mockedAxios = vi.mocked(axios, true);

describe("subscriptionPlansApi", () => {
  // Use the actual environment variable value for testing
  const mockApiBaseUrl =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockPlanData: SubscriptionPlanDefinition = {
    plan_id: "test-plan",
    plan_name: "Test Plan",
    plan_description: "A test subscription plan",
    price: 99.99,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 10,
      max_reports: 100,
      features: ["Feature 1", "Feature 2", "Feature 3"],
    },
    is_default: false,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  describe("getSubscriptionPlans", () => {
    test("fetches subscription plans successfully", async () => {
      const mockResponse = { data: { plans: [mockPlanData] } };
      mockedAxios.get.mockResolvedValueOnce(mockResponse);

      const result = await getSubscriptionPlans();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${mockApiBaseUrl}/api/v1/subscription-plans`,
        { params: { active_only: true } },
      );
      expect(result).toEqual([mockPlanData]);
    });

    test("throws error when fetch fails", async () => {
      const mockError = new Error("Network error");
      mockedAxios.get.mockRejectedValueOnce(mockError);

      await expect(getSubscriptionPlans()).rejects.toThrow("Network error");
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${mockApiBaseUrl}/api/v1/subscription-plans`,
        { params: { active_only: true } },
      );
    });

    test("logs error to console when fetch fails", async () => {
      const consoleErrorSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mockError = new Error("Network error");
      mockedAxios.get.mockRejectedValueOnce(mockError);

      try {
        await getSubscriptionPlans();
      } catch (error) {
        // Expected to throw
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Failed to fetch subscription plans:",
        mockError,
      );
      consoleErrorSpy.mockRestore();
    });
  });

  describe("getDefaultPlan", () => {
    test("fetches default plan successfully", async () => {
      const defaultPlan = {
        ...mockPlanData,
        is_default: true,
        plan_id: "free-plan",
      };
      const mockResponse = { data: defaultPlan };
      mockedAxios.get.mockResolvedValueOnce(mockResponse);

      const result = await getDefaultPlan();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${mockApiBaseUrl}/api/v1/subscription-plans/default`,
      );
      expect(result).toEqual(defaultPlan);
    });

    test("throws error when fetch fails", async () => {
      const mockError = new Error("Not found");
      mockedAxios.get.mockRejectedValueOnce(mockError);

      await expect(getDefaultPlan()).rejects.toThrow("Not found");
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${mockApiBaseUrl}/api/v1/subscription-plans/default`,
      );
    });

    test("logs error to console when fetch fails", async () => {
      const consoleErrorSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mockError = new Error("Not found");
      mockedAxios.get.mockRejectedValueOnce(mockError);

      try {
        await getDefaultPlan();
      } catch (error) {
        // Expected to throw
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Failed to fetch default subscription plan:",
        mockError,
      );
      consoleErrorSpy.mockRestore();
    });
  });

  describe("getSubscriptionPlan", () => {
    test("fetches specific plan successfully", async () => {
      const mockResponse = { data: mockPlanData };
      mockedAxios.get.mockResolvedValueOnce(mockResponse);

      const result = await getSubscriptionPlan("test-plan");

      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${mockApiBaseUrl}/api/v1/subscription-plans/test-plan`,
      );
      expect(result).toEqual(mockPlanData);
    });

    test("throws error when fetch fails", async () => {
      const mockError = new Error("Plan not found");
      mockedAxios.get.mockRejectedValueOnce(mockError);

      await expect(getSubscriptionPlan("non-existent")).rejects.toThrow(
        "Plan not found",
      );
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${mockApiBaseUrl}/api/v1/subscription-plans/non-existent`,
      );
    });

    test("logs error to console with plan ID when fetch fails", async () => {
      const consoleErrorSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const mockError = new Error("Plan not found");
      mockedAxios.get.mockRejectedValueOnce(mockError);

      try {
        await getSubscriptionPlan("non-existent");
      } catch (error) {
        // Expected to throw
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Failed to fetch subscription plan non-existent:",
        mockError,
      );
      consoleErrorSpy.mockRestore();
    });
  });

  describe("environment configuration", () => {
    test("uses configured API URL from environment", async () => {
      const mockResponse = { data: { plans: [] } };
      mockedAxios.get.mockResolvedValueOnce(mockResponse);

      await getSubscriptionPlans();

      // Should use the actual environment URL
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/subscription-plans"),
        { params: { active_only: true } },
      );
    });
  });
});
