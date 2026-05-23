import { PRODUCT_INTEGRATIONS } from "@/data/productIntegrations";
import {
  ValidationResult,
  PRODUCT_INTEGRATION_LIMITS,
  INTEGRATION_CONFLICTS,
  INTEGRATION_PREREQUISITES,
} from "@/types/validation";

/**
 * Validates product integration selections
 */
export const validateProductIntegrations = (
  integrations: string[],
): ValidationResult => {
  // Since integrations are now managed through modals and not actually added to a list,
  // we don't need any validation. Return valid with no errors or warnings.
  return {
    isValid: true,
    errors: [],
    warnings: [],
  };
};

/**
 * Get product integration validation rules
 */
export const getProductIntegrationRules = () => ({
  maxIntegrations: PRODUCT_INTEGRATION_LIMITS.MAX_INTEGRATIONS,
  recommendedIntegrations: PRODUCT_INTEGRATION_LIMITS.RECOMMENDED_INTEGRATIONS,
  allowedIntegrations: PRODUCT_INTEGRATIONS.map((int) => int.id),
  availableIntegrations: PRODUCT_INTEGRATIONS.filter(
    (int) => int.status === "available",
  ).map((int) => int.id),
  conflicts: INTEGRATION_CONFLICTS,
  prerequisites: INTEGRATION_PREREQUISITES,
});

/**
 * Check if a product integration is valid and available
 */
export const isValidProductIntegration = (integrationId: string): boolean => {
  const integration = PRODUCT_INTEGRATIONS.find(
    (int) => int.id === integrationId,
  );
  return integration !== undefined && integration.status === "available";
};

/**
 * Check if a product integration exists (even if not available)
 */
export const productIntegrationExists = (integrationId: string): boolean => {
  return PRODUCT_INTEGRATIONS.some((int) => int.id === integrationId);
};

/**
 * Get conflicts for a specific integration
 */
export const getIntegrationConflicts = (integrationId: string): string[] => {
  return INTEGRATION_CONFLICTS[integrationId] || [];
};

/**
 * Get prerequisites for a specific integration
 */
export const getIntegrationPrerequisites = (
  integrationId: string,
): string[] => {
  return INTEGRATION_PREREQUISITES[integrationId] || [];
};

/**
 * Remove invalid, duplicate, and conflicting integrations
 */
export const sanitizeProductIntegrations = (
  integrations: string[],
): string[] => {
  const availableIntegrationIds = PRODUCT_INTEGRATIONS.filter(
    (int) => int.status === "available",
  ).map((int) => int.id);

  // Remove duplicates and invalid integrations
  const uniqueValidIntegrations = Array.from(
    new Set(integrations.filter((id) => availableIntegrationIds.includes(id))),
  );

  // Remove conflicts (keep first occurrence)
  const conflictFreeIntegrations: string[] = [];
  for (const integration of uniqueValidIntegrations) {
    const conflicts = INTEGRATION_CONFLICTS[integration] || [];
    const hasExistingConflict = conflictFreeIntegrations.some((existing) =>
      conflicts.includes(existing),
    );

    if (!hasExistingConflict) {
      conflictFreeIntegrations.push(integration);
    }
  }

  // Respect max limit
  return conflictFreeIntegrations.slice(
    0,
    PRODUCT_INTEGRATION_LIMITS.MAX_INTEGRATIONS,
  );
};

/**
 * Suggest integrations based on current selections
 */
export const suggestComplementaryIntegrations = (
  currentIntegrations: string[],
): string[] => {
  const suggestions: string[] = [];

  // If they have marketing channels but no analytics
  const hasAnalytics = currentIntegrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return integration?.category === "analytics";
  });

  if (currentIntegrations.length > 0 && !hasAnalytics) {
    suggestions.push("google_analytics");
  }

  // PRODUCT_INTEGRATIONS doesn't currently expose "ecommerce" or
  // "email_marketing" categories — the checks were written for a wider
  // taxonomy. Cast to `string` so the comparisons compile; the runtime
  // behavior is unchanged (no integration matches either value today).
  const hasEcommerce = currentIntegrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return (integration?.category as string) === "ecommerce";
  });

  const hasEmailMarketing = currentIntegrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return (integration?.category as string) === "email_marketing";
  });

  if (hasEcommerce && !hasEmailMarketing) {
    suggestions.push("mailchimp");
  }

  return suggestions.filter(
    (id) => !currentIntegrations.includes(id) && isValidProductIntegration(id),
  );
};
