import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Building } from "lucide-react";
import {
  organizations,
  COMPANY_SIZE_OPTIONS,
  type Organization,
} from "@/data/organizationData";

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

interface OrganizationFormProps {
  isCreatingNew: boolean;
  orgData: Organization | null;
  formData: NewOrgFormData;
  setFormData: (data: NewOrgFormData) => void;
  editAgencyData: EditAgencyData;
  setEditAgencyData: (data: EditAgencyData) => void;
  onSubmit: () => void;
}

const OrganizationForm = ({
  isCreatingNew,
  orgData,
  formData,
  setFormData,
  editAgencyData,
  setEditAgencyData,
  onSubmit,
}: OrganizationFormProps) => {
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
          Information
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Basic Organization Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="flex flex-col">
            <Label htmlFor="orgName" className="mr-auto">
              Organization Name
            </Label>
            <Input
              id="orgName"
              value={
                isCreatingNew
                  ? formData.organization_name
                  : orgData?.organization_name || ""
              }
              onChange={(e) => {
                if (isCreatingNew) {
                  setFormData({
                    ...formData,
                    organization_name: e.target.value,
                  });
                } else if (orgData) {
                  // Update orgData directly for existing organizations
                  orgData.organization_name = e.target.value;
                }
              }}
              placeholder="Enter organization name"
            />
          </div>
          <div className="flex flex-col">
            <Label htmlFor="size" className="mr-auto">
              Company Size
            </Label>
            <Select
              value={
                isCreatingNew
                  ? formData.company_size
                  : orgData?.company_size || ""
              }
              onValueChange={(value) => {
                if (isCreatingNew) {
                  setFormData({
                    ...formData,
                    company_size: value,
                  });
                } else if (orgData) {
                  // Update orgData directly for existing organizations
                  orgData.company_size = value;
                }
              }}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={isCreatingNew ? "Select company size" : ""}
                />
              </SelectTrigger>
              <SelectContent>
                {COMPANY_SIZE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Agency Configuration */}
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
                {organizations
                  .filter(
                    (org) => org.organization_id !== orgData?.organization_id,
                  )
                  .map((org) => (
                    <div
                      key={org.organization_id}
                      className="flex items-center space-x-2"
                    >
                      <Checkbox
                        id={`child-org-${org.organization_id}`}
                        checked={currentChildOrgs.includes(org.organization_id)}
                        onCheckedChange={(checked) =>
                          handleChildOrgChange(org.organization_id, !!checked)
                        }
                      />
                      <Label
                        htmlFor={`child-org-${org.organization_id}`}
                        className="text-sm cursor-pointer"
                      >
                        {org.organization_name}
                      </Label>
                    </div>
                  ))}
              </div>
              {currentChildOrgs.length === 0 && (
                <p className="text-sm text-gray-500">
                  No organizations selected for management
                </p>
              )}
            </div>
          )}
        </div>

        <Button onClick={onSubmit}>
          {isCreatingNew ? "Create Organization" : "Update Organization"}
        </Button>
      </CardContent>
    </Card>
  );
};

export default OrganizationForm;
