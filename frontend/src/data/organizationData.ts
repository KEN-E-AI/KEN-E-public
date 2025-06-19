export interface Organization {
  organization_id: string;
  organization_name: string;
  plan: string;
  website: string;
  company_size: string;
  agency: boolean;
  child_organizations: string[];
  accounts: Account[];
  subscription: {
    plan_name: string;
    plan_description: string;
    price: number;
    currency: string;
    billing_cycle: string;
    next_billing_date: string;
    features: string[];
    usage: {
      reports_generated: number;
      reports_limit: number;
    };
  };
  billing: {
    payment_method: {
      last_four: string;
      brand: string;
      expires: string;
    };
    address: string;
    tax_id: string;
  };
  team: {
    members_used: number;
    members_limit: number;
    pending_invitations: number;
  };
}

export interface Account {
  account_id: string;
  account_name: string;
  organization_id: string;
  industry: string;
  status: string;
  websites: string[];
  timezone: string;
}

export const organizations: Organization[] = [
  {
    organization_id: "healthway",
    organization_name: "Healthway",
    plan: "Professional",
    website: "https://healthway.com",
    company_size: "medium",
    agency: false,
    child_organizations: [],
    accounts: [
      {
        account_id: "intellipure-b2c",
        account_name: "Intellipure (B2C)",
        organization_id: "healthway",
        industry: "Retail",
        status: "Active",
        websites: ["https://intellipure.com", "https://shop.intellipure.com"],
        timezone: "America/Los_Angeles",
      },
      {
        account_id: "intellipure-b2b",
        account_name: "Intellipure (B2B)",
        organization_id: "healthway",
        industry: "Retail",
        status: "Active",
        websites: ["https://b2b.intellipure.com"],
        timezone: "America/Los_Angeles",
      },
    ],
    subscription: {
      plan_name: "Professional Plan",
      plan_description: "Advanced analytics and reporting for growing teams",
      price: 99,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "February 15, 2024",
      features: ["Unlimited Reports", "Advanced Analytics", "API Access"],
      usage: {
        reports_generated: 847,
        reports_limit: 1000,
      },
    },
    billing: {
      payment_method: {
        last_four: "4242",
        brand: "Visa",
        expires: "12/26",
      },
      address: "123 Business St, San Francisco, CA 94105",
      tax_id: "US123456789",
    },
    team: {
      members_used: 5,
      members_limit: 10,
      pending_invitations: 2,
    },
  },
  {
    organization_id: "open-lines",
    organization_name: "Open Lines",
    plan: "Enterprise",
    website: "https://open-lines.com",
    company_size: "large",
    agency: true,
    child_organizations: ["healthway", "equity-trust"],
    accounts: [
      {
        account_id: "master-open-lines",
        account_name: "Master Open Lines Account",
        organization_id: "open-lines",
        industry: "Healthcare Services",
        status: "Active",
        websites: [
          "https://openlines.com",
          "https://portal.openlines.com",
          "https://support.openlines.com",
        ],
        timezone: "America/New_York",
      },
    ],
    subscription: {
      plan_name: "Enterprise Plan",
      plan_description: "Full-featured solution for large organizations",
      price: 299,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "March 1, 2024",
      features: [
        "Unlimited Everything",
        "Premium Support",
        "Custom Integrations",
      ],
      usage: {
        reports_generated: 2156,
        reports_limit: 5000,
      },
    },
    billing: {
      payment_method: {
        last_four: "8888",
        brand: "Mastercard",
        expires: "08/27",
      },
      address: "456 Healthcare Ave, Boston, MA 02101",
      tax_id: "US987654321",
    },
    team: {
      members_used: 25,
      members_limit: 50,
      pending_invitations: 3,
    },
  },
  {
    organization_id: "equity-trust",
    organization_name: "Equity Trust",
    plan: "Starter",
    website: "https://equity-trust.com",
    company_size: "small",
    agency: false,
    child_organizations: [],
    accounts: [
      {
        account_id: "etc-consumer",
        account_name: "ETC Consumer",
        organization_id: "equity-trust",
        industry: "Financial Services",
        status: "Active",
        websites: ["https://equitytrust.com"],
        timezone: "America/Chicago",
      },
      {
        account_id: "etc-business",
        account_name: "ETC Business",
        organization_id: "equity-trust",
        industry: "Financial Services",
        status: "Active",
        websites: [
          "https://business.equitytrust.com",
          "https://portal.equitytrust.com",
        ],
        timezone: "America/Chicago",
      },
    ],
    subscription: {
      plan_name: "Starter Plan",
      plan_description: "Essential features for small teams getting started",
      price: 29,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "February 20, 2024",
      features: ["Basic Reports", "Standard Analytics", "Email Support"],
      usage: {
        reports_generated: 45,
        reports_limit: 100,
      },
    },
    billing: {
      payment_method: {
        last_four: "1234",
        brand: "American Express",
        expires: "06/25",
      },
      address: "789 Finance Blvd, New York, NY 10001",
      tax_id: "US555666777",
    },
    team: {
      members_used: 3,
      members_limit: 5,
      pending_invitations: 1,
    },
  },
];

// Constants for dropdowns
export const INDUSTRY_OPTIONS = [
  { value: "technology", label: "Technology" },
  { value: "marketing", label: "Marketing" },
  { value: "finance", label: "Finance" },
  { value: "healthcare", label: "Healthcare" },
  { value: "retail", label: "Retail" },
  { value: "other", label: "Other" },
];

export const COMPANY_SIZE_OPTIONS = [
  { value: "small", label: "1-50 employees" },
  { value: "medium", label: "51-200 employees" },
  { value: "large", label: "201-1000 employees" },
  { value: "enterprise", label: "1000+ employees" },
];

export const TIMEZONE_OPTIONS = [
  { value: "America/New_York", label: "Eastern Time (ET)" },
  { value: "America/Chicago", label: "Central Time (CT)" },
  { value: "America/Denver", label: "Mountain Time (MT)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  { value: "America/Anchorage", label: "Alaska Time (AKT)" },
  { value: "Pacific/Honolulu", label: "Hawaii Time (HT)" },
  { value: "UTC", label: "Coordinated Universal Time (UTC)" },
  { value: "Europe/London", label: "Greenwich Mean Time (GMT)" },
  { value: "Europe/Paris", label: "Central European Time (CET)" },
  { value: "Asia/Tokyo", label: "Japan Standard Time (JST)" },
  { value: "Asia/Shanghai", label: "China Standard Time (CST)" },
  { value: "Asia/Kolkata", label: "India Standard Time (IST)" },
  { value: "Australia/Sydney", label: "Australian Eastern Time (AET)" },
];

// Helper function to get organization by ID
export const getOrganizationById = (
  organizationId: string,
): Organization | undefined => {
  return organizations.find((org) => org.organization_id === organizationId);
};

// Helper function to get all accounts across all organizations
export const getAllAccounts = (): Account[] => {
  return organizations.flatMap((org) => org.accounts);
};

// Helper function to get accounts for a specific organization
export const getAccountsByOrganizationId = (
  organizationId: string,
): Account[] => {
  const organization = organizations.find(
    (org) => org.organization_id === organizationId,
  );
  return organization?.accounts || [];
};

// Helper function to find an account by ID across all organizations
export const getAccountById = (accountId: string): Account | undefined => {
  return getAllAccounts().find((account) => account.account_id === accountId);
};

// Helper function to create a new organization
export const createNewOrganization = (orgData: {
  organization_name: string;
  company_size: string;
  agency?: boolean;
  child_organizations?: string[];
}): Organization => {
  // Generate unique organization ID
  const organizationId = orgData.organization_name
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  // Create a default account for the new organization
  const defaultAccount: Account = {
    account_id: `${organizationId}-main`,
    account_name: `${orgData.organization_name} Main Account`,
    organization_id: organizationId,
    industry: "Other",
    status: "Active",
    websites: [],
    timezone: "America/New_York",
  };

  const newOrganization: Organization = {
    organization_id: organizationId,
    organization_name: orgData.organization_name,
    plan: "Free",
    website: "",
    company_size: orgData.company_size,
    agency: orgData.agency || false,
    child_organizations: orgData.child_organizations || [],
    accounts: [defaultAccount],
    subscription: {
      plan_name: "Free Plan",
      plan_description: "Basic features for getting started",
      price: 0,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "N/A",
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
  };

  // Add to organizations array
  organizations.push(newOrganization);

  return newOrganization;
};

// Helper function to create a new account
export const createNewAccount = (accountData: {
  account_name: string;
  organization_id: string;
  industry: string;
  status: string;
  websites: string[];
  timezone: string;
}): Account => {
  // Generate unique account ID
  const accountId = `${accountData.organization_id}-${accountData.account_name
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")}`;

  const newAccount: Account = {
    account_id: accountId,
    account_name: accountData.account_name,
    organization_id: accountData.organization_id,
    industry: accountData.industry,
    status: accountData.status,
    websites: accountData.websites.filter((url) => url.trim() !== ""), // Remove empty websites
    timezone: accountData.timezone,
  };

  // Find the organization and add the account to it
  const organization = organizations.find(
    (org) => org.organization_id === accountData.organization_id,
  );
  if (organization) {
    organization.accounts.push(newAccount);
  }

  return newAccount;
};

// Legacy support: Export all accounts as a flat array for backward compatibility
export const accounts: Account[] = getAllAccounts();
