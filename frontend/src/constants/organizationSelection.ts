/**
 * Constants for organization selection functionality
 */

// Timing constants
export const ACCOUNT_CREATION_REDIRECT_DELAY = 1500; // ms
export const WORKSPACE_SELECTION_DELAY = 1000; // ms
export const SINGLE_ACCOUNT_AUTO_NAVIGATE_DELAY = 500; // ms

// Default values for account creation
export const DEFAULT_TIMEZONE = "America/New_York";
export const DEFAULT_DATA_REGION = "United States";
export const DEFAULT_ACCOUNT_STATUS = "Active";
export const DEFAULT_REGION: string[] = [];

// UI Messages
export const AGENCY_ORGANIZATION_MESSAGE =
  "Agency organizations cannot create their own accounts. Select a client organization.";

export const ACCOUNT_CREATION_SUCCESS_TITLE = "Account created successfully!";
export const ACCOUNT_CREATION_SUCCESS_DESCRIPTION = (accountName: string) =>
  `"${accountName}" has been created. Redirecting to account settings...`;

// Validation messages
export const VALIDATION_MESSAGES = {
  SELECT_ORGANIZATION: "Please select an organization first.",
  SELECT_CLIENT_ORGANIZATION: "Please select a client organization first.",
  FILL_REQUIRED_FIELDS: "Please fill in all required fields",
} as const;
