/**
 * Unified ID generation utilities following existing codebase patterns
 */

let counter = 0;

/**
 * Generate a unique ID using timestamp - matches existing codebase pattern but ensures uniqueness
 * @param prefix - Optional prefix for the ID
 * @returns Unique ID string
 */
export function generateId(prefix?: string): string {
  const timestamp = Date.now();
  const uniqueId = counter++;
  const id = `${timestamp}_${uniqueId}`;
  return prefix ? `${prefix}${id}` : id;
}

/**
 * Generate a unique organization ID - follows the same pattern as existing IDs
 * @returns Unique organization ID string
 */
export function generateOrganizationId(): string {
  return generateId("org_");
}

/**
 * Generate a unique account ID - matches backend format
 * @returns Unique account ID string in format 'acc_<uuid>'
 */
export function generateAccountId(): string {
  // Generate a UUID v4 equivalent using crypto API
  const uuid = crypto.randomUUID().replace(/-/g, '');
  return `acc_${uuid}`;
}

/**
 * Generate a unique metric ID - follows existing pattern from MetricsPage.tsx
 * @returns Unique metric ID string
 */
export function generateMetricId(): string {
  return generateId("metric-");
}

/**
 * Generate a unique activity ID - follows existing pattern from ActivitiesPage.tsx
 * @returns Unique activity ID string
 */
export function generateActivityId(): string {
  return generateId("activity-");
}

/**
 * Generate a unique intuition ID - follows existing pattern from ActivitiesPage.tsx
 * @returns Unique intuition ID string
 */
export function generateIntuitionId(): string {
  return generateId("i");
}

/**
 * Generate a unique log ID - follows existing pattern from ActivitiesPage.tsx
 * @returns Unique log ID string
 */
export function generateLogId(): string {
  return generateId("l");
}

/**
 * Generate a unique account ID - follows organization pattern
 * @returns Unique account ID string
 */
export function generateAccountId(): string {
  return generateId("acc_");
}

/**
 * Validate that an ID follows the expected format
 * @param id - The ID to validate
 * @param expectedPrefix - Optional expected prefix
 * @returns true if the ID is valid, false otherwise
 */
export function isValidId(id: string, expectedPrefix?: string): boolean {
  // Check if it has reasonable length
  if (id.length < 5) {
    return false;
  }

  // Check if it starts with expected prefix
  if (expectedPrefix && !id.startsWith(expectedPrefix)) {
    return false;
  }

  // Check if it contains only valid characters (letters, numbers, underscore, hyphen)
  const validChars = /^[a-zA-Z0-9_-]+$/;
  return validChars.test(id);
}
