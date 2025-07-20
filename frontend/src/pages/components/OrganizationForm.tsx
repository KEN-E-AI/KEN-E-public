import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Building } from "lucide-react";
import { getOrganizations, type Organization } from "@/data";

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

interface OrganizationFormProps {
  isCreatingNew: boolean;
  orgData: Organization | null;
  formData: NewOrgFormData;
  setFormData: (data: NewOrgFormData) => void;
  editAgencyData: EditAgencyData;
  setEditAgencyData: (data: EditAgencyData) => void;
  editOrgName?: string;
  setEditOrgName?: (name: string) => void;
  onSubmit: () => void;
  isLoading?: boolean;
}

const OrganizationForm = ({
  isCreatingNew,
  orgData,
  formData,
  setFormData,
  editAgencyData,
  setEditAgencyData,
  editOrgName,
  setEditOrgName,
  onSubmit,
  isLoading = false,
}: OrganizationFormProps) => {
  const [allOrganizations, setAllOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadOrganizations = async () => {
      try {
        const orgs = await getOrganizations();
        setAllOrganizations(orgs);
      } catch (error) {
        console.error("Failed to load organizations:", error);
      } finally {
        setLoading(false);
      }
    };

    loadOrganizations();
  }, []);

  const currentAgencyValue = isCreatingNew
    ? formData.agency
    : editAgencyData.agency;
  const currentChildOrgs = isCreatingNew
    ? formData.child_organizations
    : editAgencyData.child_organizations;

  const handleAgencyChange = (checked: boolean) => {
    if (isCreatingNew) {
      setFormData({
        ...formData,
        agency: checked,
        child_organizations: checked ? formData.child_organizations : [],
      });
    } else {
      setEditAgencyData({
        ...editAgencyData,
        agency: checked,
        child_organizations: checked ? editAgencyData.child_organizations : [],
      });
    }
  };

  const handleChildOrgChange = (orgId: string, checked: boolean) => {
    if (isCreatingNew) {
      const newChildren = checked
        ? [...formData.child_organizations, orgId]
        : formData.child_organizations.filter((id) => id !== orgId);
      setFormData({
        ...formData,
        child_organizations: newChildren,
      });
    } else {
      const newChildren = checked
        ? [...editAgencyData.child_organizations, orgId]
        : editAgencyData.child_organizations.filter((id) => id !== orgId);
      setEditAgencyData({
        ...editAgencyData,
        child_organizations: newChildren,
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building className="h-5 w-5" />
          Organization Info
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Organization Name */}
          <div className="space-y-2">
            <Label htmlFor="org-name">Organization Name</Label>
            <Input
              id="org-name"
              value={
                isCreatingNew ? formData.organization_name : editOrgName || ""
              }
              onChange={(e) => {
                if (isCreatingNew) {
                  setFormData({
                    ...formData,
                    organization_name: e.target.value,
                  });
                } else if (setEditOrgName) {
                  setEditOrgName(e.target.value);
                }
              }}
              placeholder="Enter organization name"
            />
          </div>
        </div>

        {/* Agency Configuration - Only show if organization has no linked accounts */}
        {(!orgData?.accounts || orgData.accounts.length === 0) && (
          <div className="space-y-4 border-t border-gray-200 pt-6">
            <h3 className="text-lg font-medium text-gray-900">
              Agency Configuration
            </h3>

            <div className="flex items-center space-x-2">
              <Switch
                id="agency-switch"
                checked={currentAgencyValue}
                onCheckedChange={handleAgencyChange}
              />
              <Label htmlFor="agency-switch" className="text-sm font-medium">
                This organization is an agency that manages other organizations
              </Label>
            </div>

            {currentAgencyValue && (
              <div className="space-y-3">
                <Label className="text-sm font-medium">
                  Organizations this agency can manage:
                </Label>
                <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-md p-3">
                  {loading ? (
                    <p className="text-sm text-gray-500">
                      Loading organizations...
                    </p>
                  ) : (
                    allOrganizations
                      .filter(
                        (org) =>
                          org.organization_id !== orgData?.organization_id,
                      )
                      .map((org) => (
                        <div
                          key={org.organization_id}
                          className="flex items-center space-x-2"
                        >
                          <Checkbox
                            id={`org-${org.organization_id}`}
                            checked={currentChildOrgs.includes(
                              org.organization_id,
                            )}
                            onCheckedChange={(checked) =>
                              handleChildOrgChange(
                                org.organization_id,
                                checked as boolean,
                              )
                            }
                          />
                          <Label
                            htmlFor={`org-${org.organization_id}`}
                            className="text-sm font-normal cursor-pointer"
                          >
                            {org.organization_name}
                          </Label>
                        </div>
                      ))
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end pt-6">
          <Button onClick={onSubmit} disabled={loading || isLoading}>
            {isLoading ? (
              <>
                <span className="mr-2">⏳</span>
                {isCreatingNew ? "Creating..." : "Saving..."}
              </>
            ) : isCreatingNew ? (
              "Create Organization"
            ) : (
              "Save Changes"
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default OrganizationForm;
