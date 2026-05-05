import { useState } from "react";
import api from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { createOrganization } from "@/data/organizationApi";
import { getDefaultPlan } from "@/data/subscriptionPlansApi";
import { useToast } from "@/hooks/use-toast";
import type { Organization } from "@/data/organizationTypes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Logo } from "@/components/branding/Logo";
import { Building2 } from "lucide-react";

type NewOrgFormData = {
  organization_name: string;
  company_size?: string;
  agency: boolean;
  child_organizations: string[];
};

type ValidationResult = {
  isValid: boolean;
  error?: {
    title: string;
    description: string;
  };
};

export function CreateOrganization() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const {
    user,
    updateUser,
    completeWorkspaceSelection,
    setCurrentOrganization,
    setSelectedOrgAccount,
    orgMetadata,
    setOrgMetadata,
  } = useAuth();

  const [newOrgFormData, setNewOrgFormData] = useState<NewOrgFormData>({
    organization_name: "",
    agency: false,
    child_organizations: [],
  });
  const [isCreatingOrganization, setIsCreatingOrganization] = useState(false);

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
        website: "",
        company_size: formData.company_size,
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

  const updateUserPermissions = async (
    userId: string,
    organizationId: string,
  ) => {
    await api.put(
      `/api/v1/firestore/documents/users/${userId}?account_id=${userId}`,
      {
        update: {
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

  const completeOrganizationSetup = (
    organizationId: string,
    organization: Organization,
  ) => {
    setCurrentOrganization(organizationId);

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

  const handleCreateOrganization = async () => {
    if (!user) {
      toast({
        title: "Session expired",
        description: "Please sign in again to create an organization.",
        variant: "destructive",
      });
      navigate("/auth/signin");
      return;
    }

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
      const payload = await generateOrganizationPayload(newOrgFormData);

      const newOrg = await createOrganization(payload);

      await updateUserPermissions(user.id, newOrg.organization_id);

      updateLocalUserState(newOrg.organization_id);
      updateOrganizationMetadata(newOrg);
      completeOrganizationSetup(newOrg.organization_id, newOrg);

      resetOrganizationForm();
      showSuccessMessage(newOrg.organization_name);

      navigate("/settings/organization");
    } catch (error) {
      handleCreationError(error);
    } finally {
      setIsCreatingOrganization(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4 relative overflow-hidden">
      <div className="w-full max-w-md animate-page-enter">
        {/* Logo and Brand */}
        <div className="text-center mb-8">
          <div className="mb-2 flex justify-center animate-logo-float">
            <Logo size="2xl" variant="icon" />
          </div>
          <h1 className="mb-2">Create Organization</h1>
          <p className="text-sm text-muted-foreground">
            Set up your organization on KEN-E
          </p>
        </div>

        {/* Rainbow Gradient Accent */}
        <div
          className="h-[3px] rounded-full mb-6 mx-auto w-[80%]"
          style={{
            background:
              "linear-gradient(90deg, #3B82F6, #6366F1, #2EC4B6, #F59E0B)",
          }}
        />

        {/* Form Card */}
        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreateOrganization();
            }}
            className="space-y-4"
          >
            {/* Organization Name */}
            <div>
              <Label htmlFor="organization_name">Organization Name</Label>
              <div className="relative mt-1.5">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  id="organization_name"
                  type="text"
                  placeholder="Acme Corp"
                  value={newOrgFormData.organization_name}
                  onChange={(e) =>
                    setNewOrgFormData((prev) => ({
                      ...prev,
                      organization_name: e.target.value,
                    }))
                  }
                  className="pl-10 transition-all duration-200 focus:ring-2 focus:ring-[var(--color-violet-500)]/20"
                />
              </div>
            </div>

            {/* Agency Toggle */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="agency" className="cursor-pointer">
                  This is an agency
                </Label>
                <Switch
                  id="agency"
                  checked={newOrgFormData.agency}
                  onCheckedChange={(checked) =>
                    setNewOrgFormData((prev) => ({
                      ...prev,
                      agency: checked,
                      child_organizations: checked
                        ? prev.child_organizations
                        : [],
                    }))
                  }
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Agency organizations can manage multiple child organizations
              </p>
            </div>

            {/* Child Organizations (conditional) */}
            {newOrgFormData.agency && (
              <div className="animate-slide-in">
                <Label htmlFor="child_organizations">Child Organizations</Label>
                <Input
                  id="child_organizations"
                  type="text"
                  placeholder="Enter child organization names, comma-separated"
                  value={newOrgFormData.child_organizations.join(", ")}
                  onChange={(e) =>
                    setNewOrgFormData((prev) => ({
                      ...prev,
                      child_organizations: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    }))
                  }
                  className="mt-1.5 transition-all duration-200 focus:ring-2 focus:ring-[var(--color-violet-500)]/20"
                />
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isCreatingOrganization}
              className="w-full gap-2 bg-[#F97066] hover:bg-[#e85f55] text-white transition-all duration-200 hover:-translate-y-0.5 hover:rotate-[-1deg]"
              style={{ boxShadow: "0 4px 12px rgba(249, 112, 102, 0.3)" }}
            >
              {isCreatingOrganization ? "Creating..." : "Create Organization"}
            </Button>
          </form>
        </div>

        {/* Contact Support */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            Need help?{" "}
            <a
              href="mailto:support@ken-e.com"
              className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] transition-colors"
            >
              Contact Support
            </a>
          </p>
        </div>
      </div>

      {/* Animation Styles */}
      <style>{`
        @keyframes page-enter {
          from {
            opacity: 0;
            transform: translateY(40px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes logo-float {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-12px);
          }
        }

        @keyframes slide-in {
          from {
            opacity: 0;
            transform: translateX(-20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .animate-page-enter {
          animation: page-enter 600ms cubic-bezier(0.175, 0.885, 0.32, 1.1);
        }

        .animate-logo-float {
          animation: logo-float 6s ease-in-out infinite;
        }

        .animate-slide-in {
          animation: slide-in 400ms cubic-bezier(0.175, 0.885, 0.32, 1.1);
          animation-delay: 200ms;
          animation-fill-mode: backwards;
        }

        @media (prefers-reduced-motion: reduce) {
          .animate-page-enter,
          .animate-logo-float,
          .animate-slide-in {
            animation: none;
          }
          * {
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>
    </div>
  );
}

export default CreateOrganization;
