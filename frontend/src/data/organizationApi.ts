/**
 * API functions for organizations and accounts.
 */

import type { Organization, Account } from "./organizationTypes";

// Get API base URL from environment
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Helper function for API calls
async function apiCall<T>(path: string, options: RequestInit = {}): Promise<T> {
  console.log(`[organizationApi] Making API call to: ${API_BASE_URL}${path}`);
  console.log(`[organizationApi] Options:`, options);
  
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  console.log(`[organizationApi] Response status: ${response.status}`);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    console.error(`[organizationApi] API Error:`, error);
    throw new Error(error.detail || `HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  console.log(`[organizationApi] Response data:`, data);
  return data;
}

// Organization API functions
export async function getOrganizations(): Promise<Organization[]> {
  const data = await apiCall<{ organizations: Organization[]; total: number }>(
    "/api/v1/organizations/",
  );
  return data.organizations;
}

export async function getOrganizationById(
  organizationId: string,
): Promise<Organization | undefined> {
  try {
    const organization = await apiCall<Organization>(
      `/api/v1/organizations/${organizationId}`,
    );
    return organization;
  } catch (error) {
    console.error(`Failed to fetch organization ${organizationId}:`, error);
    return undefined;
  }
}

export async function createOrganization(orgData: {
  organization_name: string;
  plan: string;
  website: string;
  company_size: string;
  agency: boolean;
  child_organizations?: string[];
  subscription: Organization["subscription"];
  billing: Organization["billing"];
  team: Organization["team"];
}): Promise<Organization> {
  return apiCall<Organization>("/api/v1/organizations/", {
    method: "POST",
    body: JSON.stringify(orgData),
  });
}

export async function updateOrganization(
  organizationId: string,
  updates: Partial<Organization>,
): Promise<Organization> {
  return apiCall<Organization>(`/api/v1/organizations/${organizationId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteOrganization(
  organizationId: string,
): Promise<void> {
  await apiCall(`/api/v1/organizations/${organizationId}`, {
    method: "DELETE",
  });
}

// Account API functions
export async function getAccounts(organizationId?: string): Promise<Account[]> {
  const params = organizationId ? `?organization_id=${organizationId}` : "";
  const data = await apiCall<{ accounts: Account[]; total: number }>(
    `/api/v1/accounts/${params}`,
  );
  return data.accounts;
}

export async function getAllAccounts(): Promise<Account[]> {
  return getAccounts();
}

export async function getAccountsByOrganizationId(
  organizationId: string,
): Promise<Account[]> {
  return getAccounts(organizationId);
}

export async function getAccountById(
  accountId: string,
): Promise<Account | undefined> {
  try {
    const account = await apiCall<Account>(`/api/v1/accounts/${accountId}`);
    return account;
  } catch (error) {
    console.error(`Failed to fetch account ${accountId}:`, error);
    return undefined;
  }
}

export async function createAccount(accountData: {
  account_name: string;
  organization_id: string;
  industry: string;
  status: string;
  websites: string[];
  timezone: string;
  data_region?: string;
  region?: string[];
}): Promise<Account> {
  console.log("[organizationApi] Creating account with data:", accountData);
  console.log("[organizationApi] API URL:", `${API_BASE_URL}/api/v1/accounts/`);
  
  return apiCall<Account>("/api/v1/accounts/", {
    method: "POST",
    body: JSON.stringify(accountData),
  });
}

export async function updateAccount(
  accountId: string,
  updates: Partial<Omit<Account, "account_id" | "organization_id">>,
): Promise<Account> {
  return apiCall<Account>(`/api/v1/accounts/${accountId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteAccount(accountId: string): Promise<void> {
  await apiCall(`/api/v1/accounts/${accountId}`, {
    method: "DELETE",
  });
}

// Helper functions to maintain compatibility with existing code
export async function createNewOrganization(orgData: {
  organization_name: string;
  company_size: string;
  agency?: boolean;
  child_organizations?: string[];
}): Promise<Organization> {
  // Create a default organization with minimal data
  const newOrg = await createOrganization({
    organization_name: orgData.organization_name,
    plan: "Free",
    website: "",
    company_size: orgData.company_size,
    agency: orgData.agency || false,
    child_organizations: orgData.child_organizations || [],
    subscription: {
      plan_name: "Free Plan",
      plan_description: "Basic features for getting started",
      price: 0,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: new Date().toISOString(),
      features: ["Basic Reports", "1 User"],
      usage: {
        reports_generated: 0,
        reports_limit: 10,
      },
    },
    billing: {
      payment_method: {
        last_four: "",
        brand: "",
        expires: "",
      },
      address: "",
      tax_id: "",
    },
    team: {
      members_used: 1,
      members_limit: 1,
      pending_invitations: 0,
    },
  });

  return newOrg;
}

export async function createNewAccount(accountData: {
  account_name: string;
  organization_id: string;
  industry: string;
  status: string;
  websites: string[];
  timezone: string;
}): Promise<Account> {
  return createAccount({
    account_name: accountData.account_name,
    organization_id: accountData.organization_id,
    industry: accountData.industry,
    status: accountData.status,
    websites: accountData.websites.filter((url) => url.trim() !== ""),
    timezone: accountData.timezone,
  });
}

// Re-export the organizations array as a promise for initial compatibility
// This will be replaced by actual API calls
export const organizations = getOrganizations();
export const accounts = getAllAccounts();
