import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getSubscriptionPlans,
  type SubscriptionPlanDefinition,
} from "@/data/subscriptionPlansApi";

/**
 * Custom hook for managing subscription plans data
 * Provides caching, loading states, and error handling
 */
export function useSubscriptionPlans(enabled = true) {
  // In development, reduce cache time for easier testing
  const isDevelopment = import.meta.env.VITE_ENVIRONMENT === "development";
  const staleTime = isDevelopment ? 0 : 5 * 60 * 1000; // No caching in dev, 5 min in prod
  const gcTime = isDevelopment ? 0 : 10 * 60 * 1000; // No garbage collection time in dev

  const {
    data: plans = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["subscription-plans"],
    queryFn: getSubscriptionPlans,
    enabled,
    staleTime,
    gcTime,
    refetchOnWindowFocus: isDevelopment, // Refetch when window gains focus in dev
  });

  // Find the default plan
  const defaultPlan = plans.find((plan) => plan.is_default) || null;

  // Get plan by ID
  const getPlanById = (
    planId: string,
  ): SubscriptionPlanDefinition | undefined => {
    return plans.find((plan) => plan.plan_id === planId);
  };

  // Get plan by name
  const getPlanByName = (
    planName: string,
  ): SubscriptionPlanDefinition | undefined => {
    return plans.find((plan) => plan.plan_name === planName);
  };

  // Sort plans by price (ascending)
  const sortedPlans = [...plans].sort((a, b) => a.price - b.price);

  return {
    plans,
    sortedPlans,
    defaultPlan,
    isLoading,
    error,
    refetch,
    getPlanById,
    getPlanByName,
  };
}

/**
 * Hook for comparing two subscription plans
 */
export function usePlanComparison(
  currentPlanId: string | undefined,
  newPlanId: string | undefined,
) {
  const { plans } = useSubscriptionPlans();

  const currentPlan = plans.find((p) => p.plan_id === currentPlanId);
  const newPlan = plans.find((p) => p.plan_id === newPlanId);

  if (!currentPlan || !newPlan) {
    return null;
  }

  return {
    currentPlan,
    newPlan,
    priceDifference: newPlan.price - currentPlan.price,
    usersDifference:
      newPlan.features.max_users - currentPlan.features.max_users,
    reportsDifference:
      newPlan.features.max_reports - currentPlan.features.max_reports,
    isUpgrade: newPlan.price > currentPlan.price,
    isDowngrade: newPlan.price < currentPlan.price,
  };
}
