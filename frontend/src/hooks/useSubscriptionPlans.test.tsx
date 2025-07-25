import { describe, test, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useSubscriptionPlans,
  usePlanComparison,
} from "./useSubscriptionPlans";
import * as subscriptionApi from "@/data/subscriptionPlansApi";
import type { SubscriptionPlanDefinition } from "@/types/subscription";

// Mock the API module
vi.mock("@/data/subscriptionPlansApi");

const mockPlans: SubscriptionPlanDefinition[] = [
  {
    plan_id: "free-plan",
    plan_name: "Free Plan",
    plan_description: "Basic features",
    price: 0,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 1,
      max_reports: 10,
      features: ["Basic Reports"],
    },
    is_default: true,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    plan_id: "starter-plan",
    plan_name: "Starter Plan",
    plan_description: "For small teams",
    price: 49,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 5,
      max_reports: 50,
      features: ["Advanced Reports"],
    },
    is_default: false,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    plan_id: "pro-plan",
    plan_name: "Professional Plan",
    plan_description: "For growing teams",
    price: 149,
    currency: "USD",
    billing_cycle: "monthly",
    features: {
      max_users: 20,
      max_reports: 200,
      features: ["Premium Reports"],
    },
    is_default: false,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useSubscriptionPlans", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(subscriptionApi.getSubscriptionPlans).mockResolvedValue(
      mockPlans,
    );
  });

  test("fetches and returns subscription plans", async () => {
    const { result } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.plans).toEqual(mockPlans);
    expect(result.current.error).toBeNull();
  });

  test("identifies default plan correctly", async () => {
    const { result } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.defaultPlan).toEqual(mockPlans[0]);
    expect(result.current.defaultPlan?.is_default).toBe(true);
  });

  test("sorts plans by price", async () => {
    const { result } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const prices = result.current.sortedPlans.map((p) => p.price);
    expect(prices).toEqual([0, 49, 149]);
  });

  test("getPlanById returns correct plan", async () => {
    const { result } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const plan = result.current.getPlanById("starter-plan");
    expect(plan?.plan_name).toBe("Starter Plan");
  });

  test("getPlanByName returns correct plan", async () => {
    const { result } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const plan = result.current.getPlanByName("Professional Plan");
    expect(plan?.plan_id).toBe("pro-plan");
  });

  test("handles API error", async () => {
    const mockError = new Error("API Error");
    vi.mocked(subscriptionApi.getSubscriptionPlans).mockRejectedValue(
      mockError,
    );

    const { result } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe(mockError);
    expect(result.current.plans).toEqual([]);
  });

  test("respects enabled parameter", async () => {
    const { result } = renderHook(() => useSubscriptionPlans(false), {
      wrapper: createWrapper(),
    });

    // Should not start loading when disabled
    expect(result.current.isLoading).toBe(false);
    expect(subscriptionApi.getSubscriptionPlans).not.toHaveBeenCalled();
  });
});

describe("usePlanComparison", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(subscriptionApi.getSubscriptionPlans).mockResolvedValue(
      mockPlans,
    );
  });

  test("compares plans correctly", async () => {
    const { result: plansResult } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(plansResult.current.isLoading).toBe(false);
    });

    const { result } = renderHook(
      () => usePlanComparison("free-plan", "starter-plan"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current).not.toBeNull();
    });

    expect(result.current?.currentPlan.plan_id).toBe("free-plan");
    expect(result.current?.newPlan.plan_id).toBe("starter-plan");
    expect(result.current?.priceDifference).toBe(49);
    expect(result.current?.usersDifference).toBe(4);
    expect(result.current?.reportsDifference).toBe(40);
    expect(result.current?.isUpgrade).toBe(true);
    expect(result.current?.isDowngrade).toBe(false);
  });

  test("identifies downgrade correctly", async () => {
    const { result: plansResult } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(plansResult.current.isLoading).toBe(false);
    });

    const { result } = renderHook(
      () => usePlanComparison("pro-plan", "starter-plan"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current).not.toBeNull();
    });

    expect(result.current?.isUpgrade).toBe(false);
    expect(result.current?.isDowngrade).toBe(true);
    expect(result.current?.priceDifference).toBe(-100);
  });

  test("returns null for invalid plan IDs", async () => {
    const { result: plansResult } = renderHook(() => useSubscriptionPlans(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(plansResult.current.isLoading).toBe(false);
    });

    const { result } = renderHook(
      () => usePlanComparison("invalid-plan", "starter-plan"),
      { wrapper: createWrapper() },
    );

    expect(result.current).toBeNull();
  });

  test("returns null when plans are undefined", () => {
    const { result } = renderHook(
      () => usePlanComparison(undefined, undefined),
      { wrapper: createWrapper() },
    );

    expect(result.current).toBeNull();
  });
});
