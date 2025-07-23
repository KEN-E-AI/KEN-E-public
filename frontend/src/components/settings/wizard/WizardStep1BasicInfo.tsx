import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Building2 } from "lucide-react";
import { AccountCreationData } from "../AccountCreationWizard";
import { IndustrySelectDropdown as IndustrySelect } from "@/components/ui/industry-select-dropdown";

interface WizardStep1BasicInfoProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
}

export const WizardStep1BasicInfo = ({
  formData,
  setFormData,
}: WizardStep1BasicInfoProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="h-5 w-5" />
          Basic Information
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label htmlFor="account_name">Account Name *</Label>
          <Input
            id="account_name"
            value={formData.account_name}
            onChange={(e) =>
              setFormData({
                ...formData,
                account_name: e.target.value,
              })
            }
            placeholder="e.g., Q1 2024 Campaign"
            className="mt-1"
          />
        </div>

        <div>
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={formData.description}
            onChange={(e) =>
              setFormData({
                ...formData,
                description: e.target.value,
              })
            }
            placeholder="Brief description of this account..."
            rows={3}
            className="mt-1"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="industry">Industry *</Label>
            <IndustrySelect
              value={formData.industry}
              onValueChange={(value) =>
                setFormData({ ...formData, industry: value })
              }
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="location">Location</Label>
            <Input
              id="location"
              value={formData.location}
              onChange={(e) =>
                setFormData({ ...formData, location: e.target.value })
              }
              placeholder="City, State, Country"
              className="mt-1"
            />
          </div>
        </div>

        <div>
          <Label htmlFor="website">Website</Label>
          <Input
            id="website"
            type="url"
            value={formData.website}
            onChange={(e) =>
              setFormData({ ...formData, website: e.target.value })
            }
            placeholder="https://example.com"
            className="mt-1"
          />
        </div>
      </CardContent>
    </Card>
  );
};
