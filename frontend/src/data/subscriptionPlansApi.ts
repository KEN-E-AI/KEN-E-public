import axios from "axios";
import type {
  SubscriptionPlanDefinition,
  SubscriptionPlanFeatures,
} from "../types/subscription";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type { SubscriptionPlanDefinition, SubscriptionPlanFeatures };

export async function getSubscriptionPlans(): Promise<
  SubscriptionPlanDefinition[]
> {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/subscription-plans`,
      {
        params: { active_only: true },
      },
    );
    return response.data.plans;
  } catch (error) {
    console.error("Failed to fetch subscription plans:", error);
    throw error;
  }
}

export async function getDefaultPlan(): Promise<SubscriptionPlanDefinition> {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/subscription-plans/default`,
    );
    return response.data;
  } catch (error) {
    console.error("Failed to fetch default subscription plan:", error);
    throw error;
  }
}

export async function getSubscriptionPlan(
  planId: string,
): Promise<SubscriptionPlanDefinition> {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/subscription-plans/${planId}`,
    );
    return response.data;
  } catch (error) {
    console.error(`Failed to fetch subscription plan ${planId}:`, error);
    throw error;
  }
}
