// Export all validation functions and types
export * from "./marketingChannelValidation";
export * from "./productIntegrationValidation";
export * from "./crossStepValidation";

// Re-export types for convenience
export type {
  ValidationResult,
  ValidationRule,
  ValidationSeverity,
  ValidationMessage,
  FormValidationState,
} from "@/types/validation";

export {
  MARKETING_CHANNEL_LIMITS,
  PRODUCT_INTEGRATION_LIMITS,
  INTEGRATION_CONFLICTS,
  INTEGRATION_PREREQUISITES,
  PAID_MARKETING_CHANNELS,
  CHANNEL_INTEGRATION_RECOMMENDATIONS,
} from "@/types/validation";
