import { useState, useMemo, useEffect } from "react";
import axios from "axios";
import { useNavigate, useLocation } from "react-router-dom";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { useAuth } from "@/contexts/AuthContext";
import {
  createOrganization,
  updateOrganization,
  getOrganizationById,
  getAccountsByOrganizationId,
} from "@/data/organizationApi";
import { useToast } from "@/hooks/use-toast";
import type { Organization } from "@/data/organizationTypes";
import { useSettingsNavigation } from "@/hooks/useSettingsNavigation";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

// Component imports
import OrganizationForm from "./components/OrganizationForm";
import SubscriptionCard from "./components/SubscriptionCard";
import AccountsManagement from "./components/AccountsManagement";
import BillingSection from "./components/BillingSection";
import TeamManagement from "./components/TeamManagement";
import DangerZone from "./components/DangerZone";

// Types
interface NewOrgFormData {
  organization_name: string;
  company_size: string;
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
  const { toast } = useToast();
  const { currentSection } = useSettingsNavigation();
  const {
    user,
    updateUser,
    completeWorkspaceSelection,
    currentOrganizationId,
    setCurrentOrganization,
    orgMetadata,
    setOrgMetadata,
  } = useAuth();

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

  // Derived state
  const isCreatingNew = location.pathname === "/create-organization";
  const isAccountSpecific = location.pathname.startsWith("/settings/account/");

  // Organization data
  const currentOrgId = useMemo(() => {
    if (isCreatingNew) return null;

    console.log(`[AccountSettings] Determining currentOrgId...`);
    console.log(
      `[AccountSettings] currentOrganizationId:`,
      currentOrganizationId,
    );
    console.log(
      `[AccountSettings] user permissions:`,
      user?.permissions?.organizations,
    );

    // If currentOrganizationId is set, use it
    if (currentOrganizationId) {
      console.log(
        `[AccountSettings] Using currentOrganizationId: ${currentOrganizationId}`,
      );
      return currentOrganizationId;
    }

    // Otherwise, use the first organization the user has access to
    const userOrganizations = Object.keys(
      user?.permissions?.organizations || {},
    );
    const firstOrgId = userOrganizations[0] || null;

    console.log(
      `[AccountSettings] Available user organizations:`,
      userOrganizations,
    );
    console.log(`[AccountSettings] Selected firstOrgId: ${firstOrgId}`);

    return firstOrgId;
  }, [isCreatingNew, currentOrganizationId, user?.permissions?.organizations]);

  const orgData = useMemo(() => {
    const data = currentOrgId ? orgMetadata[currentOrgId] || null : null;
    console.log(`[AccountSettings] orgData calculation:`, {
      currentOrgId,
      hasOrgMetadata: !!orgMetadata[currentOrgId],
      orgDataExists: !!data,
      orgMetadataKeys: Object.keys(orgMetadata),
    });
    return data;
  }, [currentOrgId, orgMetadata]);


  // Form state
  const [newOrgFormData, setNewOrgFormData] = useState<NewOrgFormData>({
    organization_name: "",
    company_size: "",
    agency: false,
    child_organizations: [],
  });

  const [editAgencyData, setEditAgencyData] = useState<EditAgencyData>({
    agency: false,
    child_organizations: [],
  });

  const [editOrgName, setEditOrgName] = useState<string>("");

  const [isCreatingOrganization, setIsCreatingOrganization] = useState(false);

  // Load organization metadata if not already loaded
  useEffect(() => {
    const loadOrganizationMetadata = async () => {
      if (currentOrgId && !orgMetadata[currentOrgId]) {
        try {
          console.log(
            `[AccountSettings] Loading organization metadata for ${currentOrgId}`,
          );
          console.log(
            `[AccountSettings] Current orgMetadata:`,
            Object.keys(orgMetadata),
          );

          // Fetch organization details
          const org = await getOrganizationById(currentOrgId);
          console.log(`[AccountSettings] Organization API response:`, org);

          // Fetch accounts for this organization
          const accounts = await getAccountsByOrganizationId(currentOrgId);
          console.log(`[AccountSettings] Accounts API response:`, accounts);

          if (org) {
            const orgWithAccounts = { ...org, accounts };
            setOrgMetadata((prev) => ({
              ...prev,
              [currentOrgId]: orgWithAccounts,
            }));

            console.log(
              `[AccountSettings] Organization metadata loaded for ${currentOrgId}:`,
              orgWithAccounts,
            );
          } else {
            console.warn(
              `[AccountSettings] Organization ${currentOrgId} not found in Neo4j`,
            );
          }
        } catch (err) {
          console.error(
            `[AccountSettings] Failed to load org metadata for ${currentOrgId}`,
            err,
          );
        }
      } else if (currentOrgId && orgMetadata[currentOrgId]) {
        console.log(
          `[AccountSettings] Organization metadata already loaded for ${currentOrgId}`,
        );
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

  // Early return for missing organization data
  if (!isCreatingNew && !orgData) {
    // Show loading state if we have a currentOrgId but no orgData (still loading)
    if (currentOrgId) {
      return (
        <SettingsLayout
          pageTitle="Organization Settings"
          currentPage="organization"
        >
          <div className="text-center py-8">
            <p className="text-gray-500">Loading organization data...</p>
          </div>
        </SettingsLayout>
      );
    }

    // Show error state if we have no organization access
    return (
      <SettingsLayout
        pageTitle="Organization Settings"
        currentPage="organization"
      >
        <div className="text-center py-8">
          <p className="text-gray-500">No organization access found</p>
        </div>
      </SettingsLayout>
    );
  }

  // Helper functions for organization creation
  const validateOrganizationData = (
    formData: NewOrgFormData,
  ): ValidationResult => {
    if (!formData.organization_name || !formData.company_size) {
      return {
        isValid: false,
        error: {
          title: "Missing required fields",
          description: "Please fill in all required fields",
        },
      };
    }
    return { isValid: true };
  };

  const generateOrganizationPayload = (formData: NewOrgFormData) => {
    return {
      organization_name: formData.organization_name,
      plan: "Free", // Default plan
      website: "", // Can be added later
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
  };

  const updateUserPermissions = async (
    userId: string,
    organizationId: string,
  ) => {
    await axios.put(
      `${API_BASE_URL}/api/v1/firestore/documents/users/${userId}?account_id=${userId}`,
      {
        update: {
          // This is a nested field path for dot-notation update
          field: `permissions.organizations.${organizationId}`,
          operator: "set",
          value: "admin",
        },
      },
    );
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

  const completeOrganizationSetup = (organizationId: string) => {
    setCurrentOrganization(organizationId);
    completeWorkspaceSelection();
  };

  const resetOrganizationForm = () => {
    setNewOrgFormData({
      organization_name: "",
      company_size: "",
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
      const payload = generateOrganizationPayload(newOrgFormData);

      // Create organization in Neo4j
      const newOrg = await createOrganization(payload);

      // Update user permissions
      await updateUserPermissions(user?.id!, newOrg.organization_id);

      // Update local state
      updateLocalUserState(newOrg.organization_id);
      updateOrganizationMetadata(newOrg);
      completeOrganizationSetup(newOrg.organization_id);

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
    if (!editOrgName || !orgData || !orgData.company_size) {
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields",
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

  // Determine current page based on route
  const getCurrentPage = () => {
    if (isCreatingNew) return "organization";
    if (isAccountSpecific) return "account";
    return currentSection;
  };

  // Determine page title based on context
  const getPageTitle = () => {
    if (isCreatingNew) return "Create Organization";
    if (isAccountSpecific) return "Account Settings";
    return "Organization Settings";
  };

  return (
    <SettingsLayout
      pageTitle={getPageTitle()}
      currentPage={getCurrentPage()}
      showBackButton={!isCreatingNew}
    >
      {/* Organization Settings Header with create button */}
      {!isCreatingNew && !isAccountSpecific && (
        <div className="space-y-6 mb-6">
          {/* Title and Description */}
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-dashboard-gray-900">
                Organization Settings
              </h1>
              <p className="text-dashboard-gray-600 mt-1">
                Manage your organization profile, subscription, and team
                settings
              </p>
            </div>
            <Button
              onClick={() => navigate("/create-organization")}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Create New Organization
            </Button>
          </div>
        </div>
      )}

      {/* Organization Information */}
      <OrganizationForm
        isCreatingNew={isCreatingNew}
        orgData={orgData}
        formData={newOrgFormData}
        setFormData={setNewOrgFormData}
        editAgencyData={editAgencyData}
        setEditAgencyData={setEditAgencyData}
        editOrgName={editOrgName}
        setEditOrgName={setEditOrgName}
        onSubmit={
          isCreatingNew ? handleCreateOrganization : handleUpdateOrganization
        }
        isLoading={isCreatingOrganization}
      />

      {/* Conditional sections for existing organizations */}
      {orgData && (
        <>
          <SubscriptionCard orgData={orgData} />
          <AccountsManagement orgData={orgData} currentOrgId={currentOrgId!} />
          <BillingSection orgData={orgData} />
          <TeamManagement orgData={orgData} />
          <DangerZone orgData={orgData} />
        </>
      )}
    </SettingsLayout>
  );
};

export default AccountSettings;
