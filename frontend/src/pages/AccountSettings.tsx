import { useState, useMemo, useEffect } from "react";
import axios from "axios";
import { useNavigate, useLocation } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

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
      alert("Please fill in all required fields");
      return;
    }

    try {
      const newOrgId = newOrgFormData.organization_name.toLowerCase().replace(/\s+/g, "-");
      
      const res = await axios.post(`${API_BASE_URL}/api/v1/firestore/documents`, {
        account_id: user?.id,
        collection: "organizations",
        document_id: newOrgId,
        data: {
          ...newOrgFormData,
        },
      });

      const newOrg = res.data.data;

      // Add the new organization to user's permissions with admin level
      await axios.put(
        `${API_BASE_URL}/api/v1/firestore/documents/users/${user?.id}?account_id=${user?.id}`,
        {
          update: {
            // This is a nested field path for dot-notation update
            field: `permissions.organizations.${newOrgId}`,
            operator: "set",
            value: "admin",
          },
        }
      );

      // Update user's local permissions state
      updateUser({
        permissions: {
          ...user?.permissions,
          organizations: {
            ...user?.permissions?.organizations,
            [newOrgId]: "admin",
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

      navigate("/account-settings");
      alert(`Organization "${newOrg.organization_name}" created successfully!`);
    } catch (error) {
      console.error("Error creating organization:", error);
      alert("Failed to create organization. Please try again.");
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
        }
      );

      alert("Organization updated successfully!");
    } catch (error) {
      console.error("Error updating organization:", error);
      alert("Failed to update organization. Please try again.");
    }
  };



  const handleBackToSelection = () => {
    resetWorkspaceSelection();
    navigate("/organization-selection");
  };

  return (
    <Layout pageTitle="Organization Settings">
      <div className="max-w-4xl mx-auto space-y-8 flex flex-col">
        <BackButton onBack={handleBackToSelection} />

        {/* Organization Information */}
        <OrganizationForm
          isCreatingNew={isCreatingNew}
          orgData={orgData}
          formData={newOrgFormData}
          setFormData={setNewOrgFormData}
          editAgencyData={editAgencyData}
          setEditAgencyData={setEditAgencyData}
          onSubmit={isCreatingNew ? handleCreateOrganization : handleUpdateOrganization}
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
      Back to Organizations & Accounts
    </Button>
  </div>
);

export default AccountSettings;
