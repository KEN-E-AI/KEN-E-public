import { useState, useMemo, useEffect } from "react";
import { useNavigate, useLocation, useParams } from "react-router-dom";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { useAuth } from "@/contexts/AuthContext";
import {
  createOrganization,
  updateOrganization,
  getOrganizationsBatch,
} from "@/data/organizationApi";
import { getDefaultPlan } from "@/data/subscriptionPlansApi";
import { useToast } from "@/hooks/use-toast";
import type { Organization } from "@/data/organizationTypes";
import type { SubscriptionPlanDefinition } from "@/types/subscription";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Plus,
  Shield,
  Building2,
  Package,
  CreditCard,
  Users,
  Plug,
  Check,
} from "lucide-react";

// Component imports
import OrganizationForm from "./components/OrganizationForm";
import SubscriptionCard from "./components/SubscriptionCard";
import AccountsManagement from "./components/AccountsManagement";
import BillingSection from "./components/BillingSection";
import TeamManagement from "./components/TeamManagement";
import DangerZone from "./components/DangerZone";
import { GoogleAnalyticsPropertySelector } from "@/components/integrations/GoogleAnalyticsPropertySelector";
import { AccountSettingsTabs } from "@/components/settings/AccountSettingsTabs";
import type { AccountId } from "@/lib/branded-types";

// Types
interface NewOrgFormData {
  organization_name: string;
  company_size?: string;
  agency: boolean;
  child_organizations: string[];
}

interface EditAgencyData {
  agency: boolean;
  child_organizations: string[];
}

interface ValidationResult {
  isValid: boolean;
  error?: {
    title: string;
    description: string;
  };
}

const AccountSettings = () => {
  // Hooks
  const navigate = useNavigate();
  const location = useLocation();
  const { accountId: accountIdParam } = useParams<{ accountId?: string }>();
  const { toast } = useToast();

  // State to track accounts being set up
  const [accountsInSetup, setAccountsInSetup] = useState<Set<string>>(
    new Set(),
  );
  const [showPropertySelector, setShowPropertySelector] = useState(false);
  const [propertySelectionAccountId, setPropertySelectionAccountId] = useState<
    string | null
  >(null);

  // Parse URL parameters using useMemo to ensure consistent hook order
  const {
    searchParams,
    shouldOpenCreateAccount,
    oauthSuccess,
    oauthAccount,
    shouldSelectProperties,
  } = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return {
      searchParams: params,
      shouldOpenCreateAccount: params.get("openCreateAccount") === "true",
      oauthSuccess: params.get("oauth_success"),
      oauthAccount: params.get("account"),
      shouldSelectProperties: params.get("select_properties") === "true",
    };
  }, [location.search]);

  // Enhanced debug logging - moved inside useMemo to avoid hooks order issues
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    console.log("[AccountSettings] URL params debug:", {
      fullURL: window.location.href,
      search: location.search,
      oauthSuccess,
      oauthAccount,
      shouldSelectProperties,
      searchParamsString: searchParams.toString(),
      allParams: Array.from(searchParams.entries()),
    });
  }, [
    location.search,
    oauthSuccess,
    oauthAccount,
    shouldSelectProperties,
    searchParams,
  ]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (window as any).showPropertySelector = (accountId?: string) => {
      const testAccountId =
        accountId || oauthAccount || "acc_ffe6269d30874f27b36a3cb1666a9037";
      setPropertySelectionAccountId(testAccountId);
      setShowPropertySelector(true);
    };
    return () => {
      delete (window as any).showPropertySelector;
    };
  }, [oauthAccount]);

  // Initialize property selector state based on URL params
  // This ensures the state is set immediately on component mount
  useEffect(() => {
    if (import.meta.env.DEV) {
      console.log(
        "[AccountSettings] Mount effect - checking for property selector trigger",
        {
          oauthSuccess,
          oauthAccount,
          shouldSelectProperties,
          condition:
            oauthSuccess === "google_analytics" &&
            oauthAccount &&
            shouldSelectProperties,
        },
      );
    }

    if (
      oauthSuccess === "google_analytics" &&
      oauthAccount &&
      shouldSelectProperties
    ) {
      if (import.meta.env.DEV) {
        console.log(
          "[AccountSettings] CONDITIONS MET! Showing property selector for account:",
          oauthAccount,
        );
      }
      setPropertySelectionAccountId(oauthAccount);
      setShowPropertySelector(true);

      const timer = setTimeout(() => {
        const newSearchParams = new URLSearchParams(window.location.search);
        newSearchParams.delete("oauth_success");
        newSearchParams.delete("account");
        newSearchParams.delete("select_properties");
        const newSearch = newSearchParams.toString();
        navigate(
          {
            pathname: location.pathname,
            search: newSearch ? `?${newSearch}` : "",
          },
          { replace: true },
        );
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [
    oauthSuccess,
    oauthAccount,
    shouldSelectProperties,
    navigate,
    location.pathname,
  ]); // Watch for changes in these params

  // Debug logging for component state
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    console.log("[AccountSettings] Component rendering with state:", {
      showPropertySelector,
      propertySelectionAccountId,
    });
  }, [showPropertySelector, propertySelectionAccountId]);

  // Clear the openCreateAccount param after reading it
  useEffect(() => {
    if (shouldOpenCreateAccount) {
      const newSearchParams = new URLSearchParams(location.search);
      newSearchParams.delete("openCreateAccount");
      const newSearch = newSearchParams.toString();
      navigate(
        {
          pathname: location.pathname,
          search: newSearch ? `?${newSearch}` : "",
        },
        { replace: true },
      );
    }
  }, [shouldOpenCreateAccount, navigate, location]);

  // Handle OAuth return - mark account as in setup
  useEffect(() => {
    if (import.meta.env.DEV) {
      console.log(
        "[AccountSettings] OAuth handling useEffect triggered - OAuth params:",
        {
          oauthSuccess,
          oauthAccount,
          shouldSelectProperties,
          showPropertySelector,
          propertySelectionAccountId,
        },
      );
    }

    if (oauthSuccess === "google_analytics" && oauthAccount) {
      if (import.meta.env.DEV) {
        console.log(
          "[AccountSettings] OAuth completed for account:",
          oauthAccount,
        );
      }

      // Add the account to the setup tracking
      setAccountsInSetup((prev) => new Set(prev).add(oauthAccount));

      // Check if we should show property selector
      // Note: We already set the state in the mount effect, but also handle it here for completeness
      if (shouldSelectProperties && !showPropertySelector) {
        if (import.meta.env.DEV) {
          console.log(
            "[AccountSettings] Setting up property selector from OAuth effect",
          );
        }
        setPropertySelectionAccountId(oauthAccount);
        setShowPropertySelector(true);
      } else if (!shouldSelectProperties) {
        // Show success toast if not selecting properties
        toast({
          title: "Google Analytics Connected",
          description:
            "Your account is being configured with personalized strategies. This typically takes 15-20 minutes.",
        });
      }

      // Don't clear the URL params yet if we're showing property selector
      // They will be cleared when the selector is closed
      if (!shouldSelectProperties) {
        // Clear OAuth params from URL
        const newSearchParams = new URLSearchParams(location.search);
        newSearchParams.delete("oauth_success");
        newSearchParams.delete("account");
        newSearchParams.delete("select_properties");
        const newSearch = newSearchParams.toString();
        navigate(
          {
            pathname: location.pathname,
            search: newSearch ? `?${newSearch}` : "",
          },
          { replace: true },
        );
      }
    }
  }, [
    oauthSuccess,
    oauthAccount,
    shouldSelectProperties,
    navigate,
    location,
    toast,
  ]);

  // Debug effect to monitor state changes
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    console.log("[AccountSettings] State changed:", {
      showPropertySelector,
      propertySelectionAccountId,
    });
  }, [showPropertySelector, propertySelectionAccountId]);
  const {
    user,
    updateUser,
    completeWorkspaceSelection,
    currentOrganizationId,
    selectedOrgAccount,
    setCurrentOrganization,
    setSelectedOrgAccount,
    orgMetadata,
    setOrgMetadata,
    isSuperAdmin,
  } = useAuth();

  // Derived state
  const isCreatingNew = location.pathname === "/create-organization";
  const isAccountSpecific =
    location.pathname === "/settings/account" ||
    location.pathname.startsWith("/settings/account/");

  // Organization data
  const currentOrgId = useMemo(() => {
    if (isCreatingNew) return null;

    if (import.meta.env.DEV) {
      console.log(`[AccountSettings] Determining currentOrgId...`);
      console.log(
        `[AccountSettings] currentOrganizationId:`,
        currentOrganizationId,
      );
      console.log(
        `[AccountSettings] user permissions:`,
        user?.permissions?.organizations,
      );
    }

    // If currentOrganizationId is set, use it
    if (currentOrganizationId) {
      if (import.meta.env.DEV) {
        console.log(
          `[AccountSettings] Using currentOrganizationId: ${currentOrganizationId}`,
        );
      }
      return currentOrganizationId;
    }

    // Next, fall back to the org backing the active workspace selection. This
    // matters for super admins: their membership doc lists only the orgs they
    // explicitly belong to, which is not the org shown in the header switcher.
    if (selectedOrgAccount?.orgId) {
      if (import.meta.env.DEV) {
        console.log(
          `[AccountSettings] Using selectedOrgAccount.orgId: ${selectedOrgAccount.orgId}`,
        );
      }
      return selectedOrgAccount.orgId;
    }

    // Otherwise, use the first organization the user has access to
    const userOrganizations = Object.keys(
      user?.permissions?.organizations || {},
    );
    const firstOrgId = userOrganizations[0] || null;

    if (import.meta.env.DEV) {
      console.log(
        `[AccountSettings] Available user organizations:`,
        userOrganizations,
      );
      console.log(`[AccountSettings] Selected firstOrgId: ${firstOrgId}`);
    }

    return firstOrgId;
  }, [
    isCreatingNew,
    currentOrganizationId,
    selectedOrgAccount?.orgId,
    user?.permissions?.organizations,
  ]);

  const orgData = useMemo(() => {
    const data = currentOrgId ? orgMetadata[currentOrgId] || null : null;
    if (import.meta.env.DEV) {
      console.log(`[AccountSettings] orgData calculation:`, {
        currentOrgId,
        hasOrgMetadata: !!orgMetadata[currentOrgId],
        orgDataExists: !!data,
        orgMetadataKeys: Object.keys(orgMetadata),
      });
    }
    return data;
  }, [currentOrgId, orgMetadata]);

  // Form state
  const [newOrgFormData, setNewOrgFormData] = useState<NewOrgFormData>({
    organization_name: "",
    agency: false,
    child_organizations: [],
  });

  const [editAgencyData, setEditAgencyData] = useState<EditAgencyData>({
    agency: false,
    child_organizations: [],
  });

  const [editOrgName, setEditOrgName] = useState<string>("");

  const [isCreatingOrganization, setIsCreatingOrganization] = useState(false);
  const [isLoadingOrgData, setIsLoadingOrgData] = useState(false);

  // Consolidated effect to load organization metadata using batch endpoint
  useEffect(() => {
    const loadOrganizationMetadata = async () => {
      if (currentOrgId && !orgMetadata[currentOrgId] && !isCreatingNew) {
        if (import.meta.env.DEV) {
          console.log(
            `[AccountSettings] Loading organization metadata for ${currentOrgId}`,
          );
          console.log(
            `[AccountSettings] Current orgMetadata:`,
            Object.keys(orgMetadata),
          );
        }
        setIsLoadingOrgData(true);

        try {
          // Use batch endpoint to fetch org with accounts in single request
          const batchResult = await getOrganizationsBatch([currentOrgId], true);
          const orgWithAccounts = batchResult[currentOrgId];

          if (import.meta.env.DEV) {
            console.log(
              `[AccountSettings] Batch API response:`,
              orgWithAccounts,
            );
          }

          if (orgWithAccounts) {
            setOrgMetadata((prev) => ({
              ...prev,
              [currentOrgId]: orgWithAccounts,
            }));

            if (import.meta.env.DEV) {
              console.log(
                `[AccountSettings] Organization metadata loaded for ${currentOrgId}`,
              );
            }
          } else {
            if (import.meta.env.DEV) {
              console.warn(
                `[AccountSettings] Organization ${currentOrgId} not found in Neo4j`,
              );
            }
          }
        } catch (err) {
          console.error("[AccountSettings] Failed to load org metadata", err);
          toast({
            title: "Error loading organization",
            description: "Failed to load organization data. Please try again.",
            variant: "destructive",
          });
        } finally {
          setIsLoadingOrgData(false);
        }
      } else if (currentOrgId && orgMetadata[currentOrgId]) {
        if (import.meta.env.DEV) {
          console.log(
            `[AccountSettings] Organization metadata already loaded for ${currentOrgId}`,
          );
        }
      }
    };

    if (currentOrgId && !isCreatingNew) {
      loadOrganizationMetadata();
    }
  }, [
    currentOrgId,
    isCreatingNew,
    setOrgMetadata,
    // Check if this specific org metadata exists without causing loops
    orgMetadata[currentOrgId] ? "loaded" : "not-loaded",
  ]);

  // Set current organization if not already set
  useEffect(() => {
    if (
      !isCreatingNew &&
      currentOrgId &&
      currentOrgId !== currentOrganizationId
    ) {
      setCurrentOrganization(currentOrgId);
    }
  }, [
    currentOrgId,
    currentOrganizationId,
    isCreatingNew,
    setCurrentOrganization,
  ]);

  // Initialize edit state when orgData changes
  useEffect(() => {
    if (orgData && !isCreatingNew) {
      setEditAgencyData({
        agency: orgData.agency || false,
        child_organizations: orgData.child_organizations || [],
      });
      setEditOrgName(orgData.organization_name || "");
    }
  }, [orgData, isCreatingNew]);

  // Helper functions for organization creation
  const validateOrganizationData = (
    formData: NewOrgFormData,
  ): ValidationResult => {
    if (!formData.organization_name) {
      return {
        isValid: false,
        error: {
          title: "Missing required fields",
          description: "Please enter an organization name",
        },
      };
    }
    return { isValid: true };
  };

  const generateOrganizationPayload = async (formData: NewOrgFormData) => {
    try {
      const defaultPlan = await getDefaultPlan();
      return {
        organization_name: formData.organization_name,
        plan: defaultPlan.plan_name,
        website: "", // Can be added later
        company_size: formData.company_size, // Optional field
        agency: formData.agency,
        child_organizations: formData.child_organizations,
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
      };
    } catch (error) {
      console.error("Failed to fetch default plan:", error);
      // Fallback to hardcoded values if API fails
      return {
        organization_name: formData.organization_name,
        plan: "Free",
        website: "",
        company_size: formData.company_size,
        agency: formData.agency,
        child_organizations: formData.child_organizations,
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
      };
    }
  };

  const updateLocalUserState = (organizationId: string) => {
    updateUser({
      permissions: {
        ...user?.permissions,
        organizations: {
          ...user?.permissions?.organizations,
          [organizationId]: "admin",
        },
      },
    });
  };

  const updateOrganizationMetadata = (newOrg: Organization) => {
    setOrgMetadata({
      ...orgMetadata,
      [newOrg.organization_id]: newOrg,
    });
  };

  const completeOrganizationSetup = (
    organizationId: string,
    organization: Organization,
  ) => {
    setCurrentOrganization(organizationId);

    // Also update the selectedOrgAccount to show in the dropdown
    const firstAccount = organization.accounts?.[0];
    setSelectedOrgAccount({
      orgId: organizationId,
      accountId: firstAccount?.account_id || "",
      metadata: {
        organization_name: organization.organization_name,
        account_name: firstAccount?.account_name || "",
        industry: firstAccount?.industry || "",
        status: firstAccount?.status || "Active",
        timezone: firstAccount?.timezone || "",
        plan: organization.plan,
      },
    });

    completeWorkspaceSelection();
  };

  const resetOrganizationForm = () => {
    setNewOrgFormData({
      organization_name: "",
      agency: false,
      child_organizations: [],
    });
  };

  const showSuccessMessage = (organizationName: string) => {
    toast({
      title: "Organization created successfully!",
      description: `"${organizationName}" has been created. You can now create accounts for this organization.`,
    });
  };

  const handleCreationError = (error: unknown) => {
    console.error("Error creating organization:", error);
    toast({
      title: "Failed to create organization",
      description:
        "Please try again later. If the problem persists, contact support.",
      variant: "destructive",
    });
  };

  // Main organization creation handler
  const handleCreateOrganization = async () => {
    const validationResult = validateOrganizationData(newOrgFormData);
    if (!validationResult.isValid) {
      toast({
        title: validationResult.error!.title,
        description: validationResult.error!.description,
        variant: "destructive",
      });
      return;
    }

    setIsCreatingOrganization(true);
    try {
      // Generate organization payload (backend will generate organization_id)
      const payload = await generateOrganizationPayload(newOrgFormData);

      // Create organization in Neo4j
      const newOrg = await createOrganization(payload);

      // Update local state
      updateLocalUserState(newOrg.organization_id);
      updateOrganizationMetadata(newOrg);
      completeOrganizationSetup(newOrg.organization_id, newOrg);

      // Reset form and show success
      resetOrganizationForm();
      showSuccessMessage(newOrg.organization_name);

      // Navigate to organization settings page
      navigate("/settings/organization");
    } catch (error) {
      handleCreationError(error);
    } finally {
      setIsCreatingOrganization(false);
    }
  };

  const handleUpdateOrganization = async () => {
    if (!editOrgName || !orgData) {
      toast({
        title: "Validation Error",
        description: "Please enter an organization name",
        variant: "destructive",
      });
      return;
    }

    try {
      const updatedOrg = await updateOrganization(orgData.organization_id, {
        organization_name: editOrgName,
        company_size: orgData.company_size,
        agency: editAgencyData.agency,
        child_organizations: editAgencyData.child_organizations,
      });

      // Update local orgData with the updated organization from API
      if (updatedOrg) {
        setOrgMetadata({
          ...orgMetadata,
          [updatedOrg.organization_id]: updatedOrg,
        });
      }

      toast({
        title: "Success",
        description: "Organization updated successfully!",
      });
    } catch (error) {
      console.error("Error updating organization:", error);
      toast({
        title: "Error",
        description: "Failed to update organization. Please try again.",
        variant: "destructive",
      });
    }
  };

  // Check if user has admin access to the current organization
  const hasAdminAccess =
    isSuperAdmin ||
    (currentOrgId &&
      (user?.permissions?.organizations?.[currentOrgId] === "admin" ||
        user?.permissions?.organizations?.[currentOrgId] === "owner"));

  // NOTE: window.showPropertySelector is now set up earlier in the component before any conditional returns

  const gaModal = showPropertySelector && propertySelectionAccountId && (
    <div
      className="fixed inset-0 bg-black/50 z-[9999] flex items-center justify-center p-4"
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0 }}
    >
      <GoogleAnalyticsPropertySelector
        accountId={propertySelectionAccountId}
        onComplete={(selectedProperties) => {
          if (import.meta.env.DEV) {
            console.log("Properties selected:", selectedProperties);
          }
          setShowPropertySelector(false);
          setPropertySelectionAccountId(null);
          const newSearchParams = new URLSearchParams(location.search);
          newSearchParams.delete("oauth_success");
          newSearchParams.delete("account");
          newSearchParams.delete("select_properties");
          const newSearch = newSearchParams.toString();
          navigate(
            {
              pathname: location.pathname,
              search: newSearch ? `?${newSearch}` : "",
            },
            { replace: true },
          );
          toast({
            title: "Properties Selected",
            description: `Successfully selected ${selectedProperties.length} ${selectedProperties.length === 1 ? "property" : "properties"} for Google Analytics integration.`,
          });
        }}
        onSkip={() => {
          setShowPropertySelector(false);
          setPropertySelectionAccountId(null);
          const newSearchParams = new URLSearchParams(location.search);
          newSearchParams.delete("oauth_success");
          newSearchParams.delete("account");
          newSearchParams.delete("select_properties");
          const newSearch = newSearchParams.toString();
          navigate(
            {
              pathname: location.pathname,
              search: newSearch ? `?${newSearch}` : "",
            },
            { replace: true },
          );
        }}
      />
    </div>
  );

  // Create Organization path — kept in SettingsLayout (unprotected route)
  if (isCreatingNew) {
    return (
      <>
        {gaModal}
        <SettingsLayout
          pageTitle="Create Organization"
          currentPage="organization"
          showBackButton={false}
          showContextSidebar={false}
        >
          <OrganizationForm
            isCreatingNew
            orgData={null}
            formData={newOrgFormData}
            setFormData={setNewOrgFormData}
            editAgencyData={editAgencyData}
            setEditAgencyData={setEditAgencyData}
            editOrgName={editOrgName}
            setEditOrgName={setEditOrgName}
            onSubmit={handleCreateOrganization}
            isLoading={isCreatingOrganization}
          />
        </SettingsLayout>
      </>
    );
  }

  // Account-specific path — 4-tab Figma AccountSettingsPage structure
  if (isAccountSpecific) {
    const activeAccountId = accountIdParam ?? selectedOrgAccount?.accountId;
    return (
      <>
        {gaModal}
        {activeAccountId ? (
          <AccountSettingsTabs accountId={activeAccountId as AccountId} />
        ) : (
          <Card className="p-6">
            <p className="text-sm text-muted-foreground">
              No account selected. Choose an account from the workspace switcher
              to manage its settings.
            </p>
          </Card>
        )}
      </>
    );
  }

  // Organization settings path — 6-tab Figma OrganizationSettingsPage structure
  return (
    <>
      {gaModal}
      <div className="flex justify-between items-start mb-6">
        <p className="text-sm text-muted-foreground">
          Manage your organization profile, subscription, and team settings
        </p>
        <Button
          onClick={() => navigate("/create-organization")}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Create New Organization
        </Button>
      </div>

      {currentOrgId && !hasAdminAccess && (
        <Alert className="mb-6">
          <Shield className="h-4 w-4" />
          <AlertDescription>
            You have view-only access to this organization. You can view
            settings but cannot make changes. To manage your own organization,
            click &quot;Create New Organization&quot; above.
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="general">
        <TabsList className="mb-6">
          <TabsTrigger value="general">
            <Building2 className="size-4 mr-2" />
            General
          </TabsTrigger>
          <TabsTrigger value="subscription">
            <Package className="size-4 mr-2" />
            Subscription
          </TabsTrigger>
          <TabsTrigger value="billing">
            <CreditCard className="size-4 mr-2" />
            Billing
          </TabsTrigger>
          <TabsTrigger value="team">
            <Users className="size-4 mr-2" />
            Team
          </TabsTrigger>
          <TabsTrigger value="integrations">
            <Plug className="size-4 mr-2" />
            Integrations
          </TabsTrigger>
          <TabsTrigger value="accounts">
            <Building2 className="size-4 mr-2" />
            Accounts
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          {isLoadingOrgData ? (
            <div className="text-center py-8">
              <div className="inline-flex items-center space-x-2">
                <div className="w-4 h-4 border-2 border-brand-medium-blue border-t-transparent rounded-full animate-spin" />
                <span className="text-[var(--color-text-tertiary)]">
                  Loading organization data...
                </span>
              </div>
            </div>
          ) : hasAdminAccess ? (
            <div className="space-y-6">
              <OrganizationForm
                isCreatingNew={false}
                orgData={orgData}
                formData={newOrgFormData}
                setFormData={setNewOrgFormData}
                editAgencyData={editAgencyData}
                setEditAgencyData={setEditAgencyData}
                editOrgName={editOrgName}
                setEditOrgName={setEditOrgName}
                onSubmit={handleUpdateOrganization}
                isLoading={isCreatingOrganization}
              />
              {orgData && <DangerZone orgData={orgData} />}
            </div>
          ) : (
            <Card className="p-6">
              <p className="text-sm text-muted-foreground">
                Organization:{" "}
                <span className="font-medium text-foreground">
                  {orgData?.organization_name}
                </span>
              </p>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="subscription">
          {orgData && hasAdminAccess ? (
            <SubscriptionCard
              orgData={orgData}
              onOrganizationUpdate={(updatedOrg) => {
                setOrgMetadata({
                  ...orgMetadata,
                  [updatedOrg.organization_id]: updatedOrg,
                });
              }}
            />
          ) : (
            <Card className="p-6">
              <p className="text-sm text-muted-foreground">
                Admin access required to view subscription details.
              </p>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="billing">
          {orgData && hasAdminAccess ? (
            <BillingSection orgData={orgData} />
          ) : (
            <Card className="p-6">
              <p className="text-sm text-muted-foreground">
                Admin access required to view billing details.
              </p>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="team">
          {orgData && hasAdminAccess ? (
            <TeamManagement orgData={orgData} />
          ) : (
            <Card className="p-6">
              <p className="text-sm text-muted-foreground">
                Admin or owner access required to manage team members.
              </p>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="integrations">
          <div className="space-y-6">
            <Card className="p-6">
              <div className="mb-6">
                <h2 className="mb-1">Available Integrations</h2>
                <p className="text-sm text-muted-foreground">
                  Connect third-party tools to extend KEN-E&apos;s capabilities
                </p>
              </div>

              <div className="space-y-4">
                <div className="flex items-start justify-between p-5 rounded-lg border-2 bg-muted/20">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-[var(--color-bg-elevated)] border flex items-center justify-center shrink-0">
                      <span className="font-bold text-sm text-[#E01E5A]">
                        Slack
                      </span>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-bold">Slack</h3>
                        <Badge
                          className="gap-1"
                          style={{
                            background: "var(--color-teal-500)",
                            color: "var(--color-text-inverse)",
                          }}
                        >
                          <Check className="size-3" />
                          Connected
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Receive notifications and updates from KEN-E directly in
                        your Slack workspace
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      Configure
                    </Button>
                    <Button variant="ghost" size="sm">
                      Disconnect
                    </Button>
                  </div>
                </div>

                <div className="flex items-start justify-between p-5 rounded-lg border-2">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-[#5059C9] flex items-center justify-center shrink-0">
                      <span className="text-white font-bold text-xs">
                        Teams
                      </span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold mb-2">Microsoft Teams</h3>
                      <p className="text-sm text-muted-foreground">
                        Share campaign insights and collaborate with your team
                        in Microsoft Teams
                      </p>
                      <Badge variant="outline" className="text-xs mt-2">
                        Coming Soon
                      </Badge>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" disabled>
                    Connect
                  </Button>
                </div>

                <div className="flex items-start justify-between p-5 rounded-lg border-2">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-[#FF4A00] flex items-center justify-center shrink-0">
                      <span className="text-white font-bold text-lg">Z</span>
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold mb-2">Zapier</h3>
                      <p className="text-sm text-muted-foreground">
                        Automate workflows by connecting KEN-E with 5,000+ apps
                      </p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    Connect
                  </Button>
                </div>

                <div className="flex items-start justify-between p-5 rounded-lg border-2">
                  <div className="flex items-start gap-4">
                    <div className="size-12 rounded-lg bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center shrink-0">
                      <Plug className="size-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold mb-2">Webhooks</h3>
                      <p className="text-sm text-muted-foreground">
                        Send real-time data to your custom endpoints when events
                        occur
                      </p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    Configure
                  </Button>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4">Slack Notification Settings</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Choose what notifications to send to your Slack workspace
              </p>
              <div className="space-y-4">
                {[
                  {
                    id: "slack-campaigns",
                    label: "Campaign Alerts",
                    desc: "Notify about campaign performance anomalies and important changes",
                    checked: true,
                  },
                  {
                    id: "slack-ai",
                    label: "AI Recommendations",
                    desc: "Share KEN-E's optimization suggestions with your team",
                    checked: true,
                  },
                  {
                    id: "slack-reports",
                    label: "Daily Performance Reports",
                    desc: "Receive daily summaries of account performance",
                    checked: false,
                  },
                  {
                    id: "slack-team",
                    label: "Team Activity",
                    desc: "Updates when team members make significant changes",
                    checked: true,
                  },
                ].map((item) => (
                  <div key={item.id} className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      id={item.id}
                      defaultChecked={item.checked}
                      className="mt-1"
                    />
                    <div>
                      <Label
                        htmlFor={item.id}
                        className="font-medium cursor-pointer"
                      >
                        {item.label}
                      </Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        {item.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="pt-6">
                <Button>Save Notification Settings</Button>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="accounts">
          {orgData ? (
            <AccountsManagement
              orgData={orgData}
              currentOrgId={currentOrgId!}
              openCreateModal={shouldOpenCreateAccount}
              hasAdminAccess={hasAdminAccess}
              accountsInSetup={accountsInSetup}
              setAccountsInSetup={setAccountsInSetup}
            />
          ) : (
            <Card className="p-6">
              <p className="text-sm text-muted-foreground">
                {isLoadingOrgData
                  ? "Loading..."
                  : "Admin access required to view accounts."}
              </p>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
};

export default AccountSettings;
