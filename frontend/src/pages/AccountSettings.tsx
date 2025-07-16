import { useState, useMemo, useEffect } from "react";
import axios from "axios";
import { useNavigate, useLocation } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { ContextBreadcrumb } from "@/components/ui/context-breadcrumb";
import { ArrowLeft } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { createOrganization } from "@/data/organizationApi";
import { useToast } from "@/hooks/use-toast";

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

const AccountSettings = () => {
  // Hooks
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const {
    user,
    updateUser,
    resetWorkspaceSelection,
    completeWorkspaceSelection,
    currentOrganizationId,
    setCurrentOrganization,
    orgMetadata,
    setOrgMetadata,
    selectedOrgAccount,
  } = useAuth();

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

  // Derived state
  const isCreatingNew = location.pathname === "/create-organization";

  // Organization data
  const currentOrgId = useMemo(() => {
    return isCreatingNew ? null : currentOrganizationId || "healthway";
  }, [isCreatingNew, currentOrganizationId]);

  const orgData = useMemo(() => {
    return currentOrgId ? orgMetadata[currentOrgId] || null : null;
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

  const [isCreatingOrganization, setIsCreatingOrganization] = useState(false);

  // Initialize edit agency state when orgData changes
  useEffect(() => {
    if (orgData && !isCreatingNew) {
      setEditAgencyData({
        agency: orgData.agency || false,
        child_organizations: orgData.child_organizations || [],
      });
    }
  }, [orgData, isCreatingNew]);

  // Early return for missing organization data
  if (!isCreatingNew && !orgData) {
    return (
      <Layout pageTitle="Organization Settings">
        <div className="max-w-4xl mx-auto space-y-8 flex flex-col">
          <BackButton onBack={() => navigate("/organization-selection")} />
          <div className="text-center py-8">
            <p className="text-gray-500">Organization not found</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Event handlers
  const handleCreateOrganization = async () => {
    if (!newOrgFormData.organization_name || !newOrgFormData.company_size) {
      toast({
        title: "Missing required fields",
        description: "Please fill in all required fields",
        variant: "destructive",
      });
      return;
    }

    setIsCreatingOrganization(true);
    try {
      // Create organization in Neo4j
      const newOrg = await createOrganization({
        organization_name: newOrgFormData.organization_name,
        plan: "Free", // Default plan
        website: "", // Can be added later
        company_size: newOrgFormData.company_size,
        agency: newOrgFormData.agency,
        child_organizations: newOrgFormData.child_organizations,
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

      // Add the new organization to user's permissions with admin level
      await axios.put(
        `${API_BASE_URL}/api/v1/firestore/documents/users/${user?.id}?account_id=${user?.id}`,
        {
          update: {
            // This is a nested field path for dot-notation update
            field: `permissions.organizations.${newOrg.organization_id}`,
            operator: "set",
            value: "admin",
          },
        },
      );

      // Update user's local permissions state
      updateUser({
        permissions: {
          ...user?.permissions,
          organizations: {
            ...user?.permissions?.organizations,
            [newOrg.organization_id]: "admin",
          },
        },
      });

      setCurrentOrganization(newOrg.organization_id);
      completeWorkspaceSelection();

      // Reset form
      setNewOrgFormData({
        organization_name: "",
        company_size: "",
        agency: false,
        child_organizations: [],
      });

      // Show success message and redirect to organization selection
      toast({
        title: "Organization created successfully!",
        description: `"${newOrg.organization_name}" has been created. You can now create accounts for this organization.`,
      });

      // Navigate immediately without blocking
      navigate("/settings");
    } catch (error) {
      console.error("Error creating organization:", error);
      toast({
        title: "Failed to create organization",
        description:
          "Please try again later. If the problem persists, contact support.",
        variant: "destructive",
      });
    } finally {
      setIsCreatingOrganization(false);
    }
  };

  const handleUpdateOrganization = async () => {
    if (!orgData?.organization_name || !orgData?.company_size) {
      alert("Please fill in all required fields");
      return;
    }

    try {
      await axios.put(
        `${API_BASE_URL}/api/v1/firestore/documents/organizations/${orgData.organization_id}?account_id=${user?.id}`,
        {
          organization_name: orgData.organization_name,
          company_size: orgData.company_size,
          agency: editAgencyData.agency,
          child_organizations: editAgencyData.child_organizations,
        },
      );

      alert("Organization updated successfully!");
    } catch (error) {
      console.error("Error updating organization:", error);
      alert("Failed to update organization. Please try again.");
    }
  };

  const handleBackToSelection = () => {
    navigate("/settings");
  };

  return (
    <Layout pageTitle="Organization Settings">
      <div className="max-w-4xl mx-auto space-y-8 flex flex-col">
        <ContextBreadcrumb currentPage="organization" />

        {/* Organization Information */}
        <OrganizationForm
          isCreatingNew={isCreatingNew}
          orgData={orgData}
          formData={newOrgFormData}
          setFormData={setNewOrgFormData}
          editAgencyData={editAgencyData}
          setEditAgencyData={setEditAgencyData}
          onSubmit={
            isCreatingNew ? handleCreateOrganization : handleUpdateOrganization
          }
          isLoading={isCreatingOrganization}
        />

        {/* Conditional sections for existing organizations */}
        {orgData && (
          <>
            <SubscriptionCard orgData={orgData} />
            <AccountsManagement
              orgData={orgData}
              currentOrgId={currentOrgId!}
            />
            <BillingSection orgData={orgData} />
            <TeamManagement orgData={orgData} />
            <DangerZone orgData={orgData} />
          </>
        )}
      </div>
    </Layout>
  );
};

// Reusable Back Button Component
const BackButton = ({ onBack }: { onBack: () => void }) => (
  <div className="pt-2 mr-auto">
    <Button
      variant="ghost"
      onClick={onBack}
      className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal"
    >
      <ArrowLeft className="h-4 w-4 mr-2" />
      Back to Settings
    </Button>
  </div>
);

export default AccountSettings;
