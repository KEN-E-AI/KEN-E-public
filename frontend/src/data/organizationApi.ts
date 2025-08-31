/**
 * API functions for organizations and accounts.
 */

import type { Organization, Account } from "./organizationTypes";
import { getDefaultPlan } from "./subscriptionPlansApi";
import api from "@/lib/api";
import { FormDataBuilder } from "@/lib/form-data-builder";

// Helper function for API calls
async function apiCall<T>(
  path: string,
  options: {
    method?: string;
    data?: any;
    params?: any;
    headers?: Record<string, string>;
    timeout?: number;
  } = {},
): Promise<T> {
  try {
    const response = await api.request<T>({
      url: path,
      method: options.method || "GET",
      data: options.data,
      params: options.params,
      headers: options.headers,
      timeout: options.timeout || 300000, // Default 5 minute timeout
    });

    return response.data;
  } catch (error: any) {
    // Enhanced error handling for timeout and connection issues
    if (error.code === "ECONNABORTED" || error.code === "ETIME") {
      console.error(`[organizationApi] Request timeout for: ${path}`);
      throw new Error(
        `Request timeout. The operation took too long to complete.`,
      );
    }

    // Only log non-404 errors at error level
    if (error.response?.status === 404) {
      console.debug(`[organizationApi] Resource not found: ${path}`);
    } else {
      console.error(`[organizationApi] API Error:`, error);
      console.error(`[organizationApi] Response data:`, error.response?.data);
    }

    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw error;
  }
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
  } catch (error: any) {
    // Only log non-404 errors, as 404 is expected when org doesn't exist or user lacks access
    if (error.response?.status !== 404) {
      console.error(`Failed to fetch organization ${organizationId}:`, error);
    }
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
    data: orgData,
  });
}

export async function updateOrganization(
  organizationId: string,
  updates: Partial<Organization>,
): Promise<Organization> {
  return apiCall<Organization>(`/api/v1/organizations/${organizationId}`, {
    method: "PUT",
    data: updates,
  });
}

export async function updateOrganizationSubscription(
  organizationId: string,
  planId: string,
  accountId: string,
): Promise<Organization> {
  return apiCall<Organization>(
    `/api/v1/organizations/${organizationId}/subscription?account_id=${accountId}`,
    {
      method: "PUT",
      data: { plan_id: planId },
    },
  );
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

export async function createAccount(
  accountData: {
    account_name: string;
    organization_id: string;
    industry: string;
    status: string;
    websites: string[];
    timezone: string;
    data_region?: string;
    region?: string[];
    marketing_channels?: string[];
    product_integrations?: string[];
    estimated_annual_ad_budget?: number | null;
    business_strategy_documents?: File[];
  },
  options?: {
    idempotencyKey?: string;
    timeout?: number;
  },
): Promise<Account> {
  console.log("[organizationApi] Creating account with data:", accountData);

  // Prepare headers with idempotency support
  // DO NOT set Content-Type for FormData - let browser set it with boundary
  const headers: Record<string, string> = {};

  if (options?.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
    console.log(
      "[organizationApi] Using idempotency key:",
      options.idempotencyKey,
    );
  }

  // Use FormDataBuilder for consistent serialization
  const builder = new FormDataBuilder();
  
  // Add required fields
  builder
    .append("account_name", accountData.account_name)
    .append("organization_id", accountData.organization_id)
    .append("industry", accountData.industry)
    .append("status", accountData.status)
    .append("websites", accountData.websites)
    .append("timezone", accountData.timezone);
  
  // Add optional fields
  builder
    .append("account_id", accountData.account_id)
    .append("data_region", accountData.data_region)
    .append("region", accountData.region)
    .append("marketing_channels", accountData.marketing_channels)
    .append("product_integrations", accountData.product_integrations)
    .append("estimated_annual_ad_budget", accountData.estimated_annual_ad_budget);
  
  // Add files if they exist
  if (accountData.business_strategy_documents && accountData.business_strategy_documents.length > 0) {
    builder.appendFiles("files", accountData.business_strategy_documents);
    console.log("[organizationApi] Sending account creation with files as multipart/form-data");
  } else {
    console.log("[organizationApi] Sending account creation without files as multipart/form-data");
  }
  
  const formData = builder.build();
  
  // Always send as multipart/form-data
  return api.post<Account>("/api/v1/accounts/", formData, {
    headers: headers,  // Don't spread or modify - let axios handle Content-Type for FormData
    timeout: options?.timeout || 600000, // 10 minutes for account creation
  }).then(response => response.data);
}

export async function updateAccount(
  accountId: string,
  updates: Partial<Omit<Account, "account_id" | "organization_id">>,
): Promise<Account> {
  return apiCall<Account>(`/api/v1/accounts/${accountId}`, {
    method: "PUT",
    data: updates,
  });
}

export async function deleteAccount(accountId: string): Promise<void> {
  await apiCall(`/api/v1/accounts/${accountId}`, {
    method: "DELETE",
  });
}

export async function moveAccount(
  currentOrganizationId: string,
  accountId: string,
  newOrganizationId: string,
): Promise<void> {
  await apiCall(
    `/api/v1/organizations/${currentOrganizationId}/move-account/${accountId}`,
    {
      method: "PUT",
      data: { new_organization_id: newOrganizationId },
    },
  );
}

// Helper functions to maintain compatibility with existing code
export async function createNewOrganization(orgData: {
  organization_name: string;
  company_size?: string;
  agency?: boolean;
  child_organizations?: string[];
}): Promise<Organization> {
  try {
    // Fetch the default plan from API
    const defaultPlan = await getDefaultPlan();

    // Create organization with default plan
    const newOrg = await createOrganization({
      organization_name: orgData.organization_name,
      plan: defaultPlan.plan_name,
      website: "",
      company_size: orgData.company_size, // Optional field
      agency: orgData.agency || false,
      child_organizations: orgData.child_organizations || [],
      subscription: {
        plan_name: defaultPlan.plan_name,
        plan_description: defaultPlan.plan_description,
        price: defaultPlan.price,
        currency: defaultPlan.currency,
        billing_cycle: defaultPlan.billing_cycle,
        next_billing_date: new Date().toISOString(),
        features: defaultPlan.features.features,
        usage: {
          reports_generated: 0,
          reports_limit: defaultPlan.features.max_reports,
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
        members_limit: defaultPlan.features.max_users,
        pending_invitations: 0,
      },
    });

    return newOrg;
  } catch (error) {
    console.error("Failed to fetch default plan, using fallback:", error);

    // Fallback to hardcoded values if API fails
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

// Function to fetch child organizations for agency organizations
export async function getChildOrganizations(
  parentOrgId: string,
): Promise<Organization[]> {
  try {
    const parentOrg = await getOrganizationById(parentOrgId);
    if (!parentOrg || !parentOrg.agency || !parentOrg.child_organizations) {
      return [];
    }

    // Fetch each child organization
    const childOrgs = await Promise.all(
      parentOrg.child_organizations.map(async (childOrgId) => {
        const childOrg = await getOrganizationById(childOrgId);
        return childOrg;
      }),
    );

    // Filter out any undefined results
    return childOrgs.filter((org): org is Organization => org !== undefined);
  } catch (error) {
    console.error(
      `Failed to fetch child organizations for ${parentOrgId}:`,
      error,
    );
    return [];
  }
}

// Removed immediate API calls - these should be called when needed, not on module load
