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
  const errors: string[] = [];
  const warnings: string[] = [];

  // Get allowed integration IDs from the data source
  const allowedIntegrationIds = PRODUCT_INTEGRATIONS.map((int) => int.id);
  const availableIntegrationIds = PRODUCT_INTEGRATIONS.filter(
    (int) => int.status === "available",
  ).map((int) => int.id);

  // Check for duplicates
  const uniqueIntegrations = new Set(integrations);
  if (uniqueIntegrations.size !== integrations.length) {
    errors.push(
      "Duplicate product integrations detected. Please remove duplicates.",
    );
  }

  // Validate against allowed integrations
  const invalidIntegrations = integrations.filter(
    (id) => !allowedIntegrationIds.includes(id),
  );
  if (invalidIntegrations.length > 0) {
    errors.push(
      `Invalid product integrations selected: ${invalidIntegrations.join(", ")}. Please select from the available options.`,
    );
  }

  // Check for "coming soon" integrations
  const comingSoonIntegrations = integrations.filter(
    (id) =>
      !availableIntegrationIds.includes(id) &&
      allowedIntegrationIds.includes(id),
  );
  if (comingSoonIntegrations.length > 0) {
    const comingSoonNames = comingSoonIntegrations.map((id) => {
      const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
      return integration?.name || id;
    });
    errors.push(
      `These integrations are not yet available: ${comingSoonNames.join(", ")}. Please remove them or wait for availability.`,
    );
  }

  // Check maximum limit
  if (integrations.length > PRODUCT_INTEGRATION_LIMITS.MAX_INTEGRATIONS) {
    errors.push(
      `Maximum ${PRODUCT_INTEGRATION_LIMITS.MAX_INTEGRATIONS} product integrations allowed. You have selected ${integrations.length}.`,
    );
  }

  // Warning for too many integrations
  if (
    integrations.length > PRODUCT_INTEGRATION_LIMITS.RECOMMENDED_INTEGRATIONS &&
    integrations.length <= PRODUCT_INTEGRATION_LIMITS.MAX_INTEGRATIONS
  ) {
    warnings.push(
      `Consider limiting to ${PRODUCT_INTEGRATION_LIMITS.RECOMMENDED_INTEGRATIONS} product integrations for easier management and maintenance.`,
    );
  }

  // Check for conflicts
  const conflictingPairs: Array<{ integration: string; conflicts: string[] }> =
    [];
  integrations.forEach((integration) => {
    const conflicts = INTEGRATION_CONFLICTS[integration] || [];
    const hasConflict = integrations.filter((other) =>
      conflicts.includes(other),
    );
    if (hasConflict.length > 0) {
      const integrationName =
        PRODUCT_INTEGRATIONS.find((int) => int.id === integration)?.name ||
        integration;
      const conflictNames = hasConflict.map((id) => {
        const int = PRODUCT_INTEGRATIONS.find((i) => i.id === id);
        return int?.name || id;
      });
      conflictingPairs.push({
        integration: integrationName,
        conflicts: conflictNames,
      });
    }
  });

  if (conflictingPairs.length > 0) {
    conflictingPairs.forEach((pair) => {
      errors.push(
        `${pair.integration} conflicts with: ${pair.conflicts.join(", ")}. Please select only one integration per category.`,
      );
    });
  }

  // Check prerequisites
  const missingPrerequisites: Array<{
    integration: string;
    missing: string[];
  }> = [];
  integrations.forEach((integration) => {
    const prerequisites = INTEGRATION_PREREQUISITES[integration] || [];
    const missingPrereqs = prerequisites.filter(
      (req) => !integrations.includes(req),
    );
    if (missingPrereqs.length > 0) {
      const integrationName =
        PRODUCT_INTEGRATIONS.find((int) => int.id === integration)?.name ||
        integration;
      const prereqNames = missingPrereqs.map((id) => {
        const int = PRODUCT_INTEGRATIONS.find((i) => i.id === id);
        return int?.name || id;
      });
      missingPrerequisites.push({
        integration: integrationName,
        missing: prereqNames,
      });
    }
  });

  if (missingPrerequisites.length > 0) {
    missingPrerequisites.forEach((req) => {
      errors.push(
        `${req.integration} requires these integrations: ${req.missing.join(", ")}. Please add them or remove ${req.integration}.`,
      );
    });
  }

  // Category balance warnings
  const categories = new Set(
    integrations
      .map((id) => PRODUCT_INTEGRATIONS.find((int) => int.id === id)?.category)
      .filter(Boolean),
  );

  if (categories.size === 1 && integrations.length > 2) {
    warnings.push(
      "Consider diversifying your integrations across different categories (Analytics, E-commerce, Marketing, etc.) for better insights.",
    );
  }

  // Essential integration recommendations
  const hasAnalytics = integrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return integration?.category === "analytics";
  });

  if (integrations.length > 0 && !hasAnalytics) {
    warnings.push(
      "Consider adding an analytics integration (like Google Analytics) to track performance across all your other integrations.",
    );
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
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

  // If they have e-commerce but no email marketing
  const hasEcommerce = currentIntegrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return integration?.category === "ecommerce";
  });

  const hasEmailMarketing = currentIntegrations.some((id) => {
    const integration = PRODUCT_INTEGRATIONS.find((int) => int.id === id);
    return integration?.category === "email_marketing";
  });

  if (hasEcommerce && !hasEmailMarketing) {
    suggestions.push("mailchimp");
  }

  return suggestions.filter(
    (id) => !currentIntegrations.includes(id) && isValidProductIntegration(id),
  );
};
