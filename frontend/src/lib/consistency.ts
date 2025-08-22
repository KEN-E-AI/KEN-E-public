/**
 * Account consistency checking utilities for detecting Neo4j/Firestore sync issues
 */

import type { Account } from "@/data/organizationTypes";

export interface ConsistencyCheck {
  isConsistent: boolean;
  inconsistencies: ConsistencyIssue[];
  totalAccounts: number;
  lastChecked: string;
}

export interface ConsistencyIssue {
  type: "missing_fields" | "data_mismatch" | "orphaned_record" | "timeout";
  accountId: string;
  accountName?: string;
  issue: string;
  severity: "warning" | "error" | "critical";
  suggestedAction?: string;
}

/**
 * Checks account data consistency by validating required fields and data integrity
 */
export function checkAccountConsistency(accounts: Account[]): ConsistencyCheck {
  const inconsistencies: ConsistencyIssue[] = [];

  for (const account of accounts) {
    // Check for missing critical fields that should have been saved
    if (
      !account.marketing_channels ||
      account.marketing_channels.length === 0
    ) {
      // Only flag as inconsistent if other setup fields suggest it should have marketing channels
      if (
        account.estimated_annual_ad_budget &&
        account.estimated_annual_ad_budget > 0
      ) {
        inconsistencies.push({
          type: "missing_fields",
          accountId: account.account_id,
          accountName: account.account_name,
          issue: "Account has ad budget but no marketing channels configured",
          severity: "warning",
          suggestedAction:
            "Re-run account setup wizard to configure marketing channels",
        });
      }
    }

    if (
      !account.product_integrations ||
      account.product_integrations.length === 0
    ) {
      // Only flag if account seems like it should have integrations
      if (account.websites && account.websites.length > 0) {
        inconsistencies.push({
          type: "missing_fields",
          accountId: account.account_id,
          accountName: account.account_name,
          issue: "Account has websites but no product integrations configured",
          severity: "warning",
          suggestedAction: "Add analytics or tracking integrations",
        });
      }
    }

    // Check for data integrity issues
    if (
      account.marketing_channels &&
      account.marketing_channels.includes("google_ads")
    ) {
      if (
        !account.product_integrations ||
        !account.product_integrations.includes("google_analytics")
      ) {
        inconsistencies.push({
          type: "data_mismatch",
          accountId: account.account_id,
          accountName: account.account_name,
          issue:
            "Google Ads selected but no analytics integration for conversion tracking",
          severity: "warning",
          suggestedAction:
            "Add Google Analytics integration for conversion tracking",
        });
      }
    }

    // Check for required fields
    if (
      !account.account_name ||
      !account.industry ||
      !account.organization_id
    ) {
      inconsistencies.push({
        type: "missing_fields",
        accountId: account.account_id,
        accountName: account.account_name || "Unknown",
        issue:
          "Account missing required fields (name, industry, or organization)",
        severity: "critical",
        suggestedAction: "Contact support - account may be corrupted",
      });
    }
  }

  return {
    isConsistent: inconsistencies.length === 0,
    inconsistencies,
    totalAccounts: accounts.length,
    lastChecked: new Date().toISOString(),
  };
}

/**
 * Checks if an account creation might have failed partially based on the account data
 */
export function detectPartialCreationFailure(
  account: Account,
): ConsistencyIssue | null {
  // Account exists but is missing expected setup data
  const hasBasicInfo = !!(
    account.account_name &&
    account.industry &&
    account.organization_id
  );
  const hasSetupData = !!(
    (account.marketing_channels && account.marketing_channels.length > 0) ||
    (account.product_integrations && account.product_integrations.length > 0) ||
    (account.websites && account.websites.length > 0)
  );

  if (hasBasicInfo && !hasSetupData) {
    // Account was created but setup data might not have been saved
    const createdRecently = account.created_at
      ? Date.now() - new Date(account.created_at).getTime() <
        24 * 60 * 60 * 1000 // Last 24 hours
      : false;

    if (createdRecently) {
      return {
        type: "missing_fields",
        accountId: account.account_id,
        accountName: account.account_name,
        issue:
          "Recently created account is missing setup data - creation may have failed partially",
        severity: "error",
        suggestedAction:
          "Re-run the account setup wizard to complete configuration",
      };
    }
  }

  return null;
}

/**
 * Validates that account data looks complete after creation
 */
export function validateAccountCreationSuccess(
  account: Account,
  expectedData: {
    marketing_channels?: string[];
    product_integrations?: string[];
    websites?: string[];
    estimated_annual_ad_budget?: number | null;
  },
): boolean {
  // Check that all expected data was saved
  const channelsMatch =
    !expectedData.marketing_channels ||
    (account.marketing_channels &&
      account.marketing_channels.length ===
        expectedData.marketing_channels.length &&
      expectedData.marketing_channels.every((channel) =>
        account.marketing_channels?.includes(channel),
      ));

  const integrationsMatch =
    !expectedData.product_integrations ||
    (account.product_integrations &&
      account.product_integrations.length ===
        expectedData.product_integrations.length &&
      expectedData.product_integrations.every((integration) =>
        account.product_integrations?.includes(integration),
      ));

  const websitesMatch =
    !expectedData.websites ||
    (account.websites &&
      account.websites.length === expectedData.websites.length &&
      expectedData.websites.every((website) =>
        account.websites?.includes(website),
      ));

  const budgetMatches =
    expectedData.estimated_annual_ad_budget === undefined ||
    account.estimated_annual_ad_budget ===
      expectedData.estimated_annual_ad_budget;

  return channelsMatch && integrationsMatch && websitesMatch && budgetMatches;
}

/**
 * Recovery suggestions for different types of consistency issues
 */
export function getRecoverySuggestions(issue: ConsistencyIssue): string[] {
  const suggestions: string[] = [];

  switch (issue.type) {
    case "missing_fields":
      suggestions.push("Re-run the account setup wizard");
      suggestions.push(
        "Check if the account creation process completed successfully",
      );
      if (issue.severity === "critical") {
        suggestions.push("Contact support if the issue persists");
      }
      break;

    case "data_mismatch":
      suggestions.push("Review and update account configuration");
      suggestions.push(
        "Ensure marketing channels and integrations are compatible",
      );
      break;

    case "timeout":
      suggestions.push("Check internet connection and try again");
      suggestions.push(
        "Verify the account was created by refreshing the accounts list",
      );
      break;

    default:
      suggestions.push("Contact support for assistance");
  }

  if (issue.suggestedAction) {
    suggestions.unshift(issue.suggestedAction);
  }

  return suggestions;
}

/**
 * Checks if an account needs immediate attention based on consistency issues
 */
export function requiresImmediateAttention(
  issues: ConsistencyIssue[],
): boolean {
  return issues.some(
    (issue) =>
      issue.severity === "critical" ||
      (issue.severity === "error" && issue.type === "missing_fields"),
  );
}
