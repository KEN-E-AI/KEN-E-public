/**
 * Utility for creating branded types to ensure type safety for IDs
 * @see https://egghead.io/blog/using-branded-types-in-typescript
 *
 * Branded types help prevent mixing up different ID types at compile time.
 * For example, you can't accidentally pass an AccountId where an OrganizationId is expected.
 */

declare const __brand: unique symbol;

/**
 * Creates a branded type by adding a phantom brand property
 */
export type Brand<T, TBrand extends string> = T & { [__brand]: TBrand };

// ID type definitions
export type AccountId = Brand<string, "AccountId">;
export type OrganizationId = Brand<string, "OrganizationId">;
export type MetricId = Brand<string, "MetricId">;
export type ActivityId = Brand<string, "ActivityId">;
export type ActivityLogId = Brand<string, "ActivityLogId">;
export type UserId = Brand<string, "UserId">;
export type InsightId = Brand<string, "InsightId">;
export type IntuitionId = Brand<string, "IntuitionId">;
export type NotificationId = Brand<string, "NotificationId">;

// Type guards
export const isAccountId = (value: string): value is AccountId => {
  return value.startsWith("acc_");
};

export const isOrganizationId = (value: string): value is OrganizationId => {
  return value.startsWith("org_");
};

export const isMetricId = (value: string): value is MetricId => {
  return value.startsWith("metric_");
};

export const isActivityId = (value: string): value is ActivityId => {
  return value.startsWith("activity_");
};

export const isActivityLogId = (value: string): value is ActivityLogId => {
  return value.startsWith("activitylog_");
};

export const isUserId = (value: string): value is UserId => {
  // Firebase UIDs don't have a specific prefix
  return typeof value === "string" && value.length > 0;
};

export const isInsightId = (value: string): value is InsightId => {
  return value.startsWith("insight_");
};

export const isIntuitionId = (value: string): value is IntuitionId => {
  return value.startsWith("intuition_");
};

export const isNotificationId = (value: string): value is NotificationId => {
  return value.startsWith("notif_");
};

// Safe casting functions with runtime validation
export const toAccountId = (value: string): AccountId => {
  if (!isAccountId(value)) {
    throw new Error(`Invalid account ID format: ${value}`);
  }
  return value as AccountId;
};

export const toOrganizationId = (value: string): OrganizationId => {
  if (!isOrganizationId(value)) {
    throw new Error(`Invalid organization ID format: ${value}`);
  }
  return value as OrganizationId;
};

export const toMetricId = (value: string): MetricId => {
  if (!isMetricId(value)) {
    throw new Error(`Invalid metric ID format: ${value}`);
  }
  return value as MetricId;
};

export const toActivityId = (value: string): ActivityId => {
  if (!isActivityId(value)) {
    throw new Error(`Invalid activity ID format: ${value}`);
  }
  return value as ActivityId;
};

export const toActivityLogId = (value: string): ActivityLogId => {
  if (!isActivityLogId(value)) {
    throw new Error(`Invalid activity log ID format: ${value}`);
  }
  return value as ActivityLogId;
};

export const toUserId = (value: string): UserId => {
  if (!isUserId(value)) {
    throw new Error(`Invalid user ID format: ${value}`);
  }
  return value as UserId;
};

export const toInsightId = (value: string): InsightId => {
  if (!isInsightId(value)) {
    throw new Error(`Invalid insight ID format: ${value}`);
  }
  return value as InsightId;
};

export const toIntuitionId = (value: string): IntuitionId => {
  if (!isIntuitionId(value)) {
    throw new Error(`Invalid intuition ID format: ${value}`);
  }
  return value as IntuitionId;
};

export const toNotificationId = (value: string): NotificationId => {
  if (!isNotificationId(value)) {
    throw new Error(`Invalid notification ID format: ${value}`);
  }
  return value as NotificationId;
};

// Optional casting functions that return undefined instead of throwing
export const tryAccountId = (value: string): AccountId | undefined => {
  return isAccountId(value) ? (value as AccountId) : undefined;
};

export const tryOrganizationId = (
  value: string,
): OrganizationId | undefined => {
  return isOrganizationId(value) ? (value as OrganizationId) : undefined;
};

export const tryMetricId = (value: string): MetricId | undefined => {
  return isMetricId(value) ? (value as MetricId) : undefined;
};

export const tryActivityId = (value: string): ActivityId | undefined => {
  return isActivityId(value) ? (value as ActivityId) : undefined;
};

export const tryActivityLogId = (value: string): ActivityLogId | undefined => {
  return isActivityLogId(value) ? (value as ActivityLogId) : undefined;
};

export const tryUserId = (value: string): UserId | undefined => {
  return isUserId(value) ? (value as UserId) : undefined;
};

export const tryInsightId = (value: string): InsightId | undefined => {
  return isInsightId(value) ? (value as InsightId) : undefined;
};

export const tryIntuitionId = (value: string): IntuitionId | undefined => {
  return isIntuitionId(value) ? (value as IntuitionId) : undefined;
};

export const tryNotificationId = (
  value: string,
): NotificationId | undefined => {
  return isNotificationId(value) ? (value as NotificationId) : undefined;
};
