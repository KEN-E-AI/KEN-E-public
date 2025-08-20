import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FileUpload } from "@/components/ui/file-upload";
import { Building2, DollarSign, FileText } from "lucide-react";
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
    <>
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

          <div>
            <Label htmlFor="estimated_annual_ad_budget">
              <DollarSign className="inline h-4 w-4 mr-1" />
              Estimated Annual Ad Budget (USD)
            </Label>
            <Input
              id="estimated_annual_ad_budget"
              type="number"
              min="0"
              step="1000"
              value={formData.estimated_annual_ad_budget || ""}
              onChange={(e) => {
                const value = e.target.value;
                setFormData({
                  ...formData,
                  estimated_annual_ad_budget: value
                    ? parseInt(value, 10)
                    : null,
                });
              }}
              placeholder="e.g., 100000"
              className="mt-1"
            />
            <p className="text-xs text-dashboard-gray-500 mt-1">
              This helps KEN-E provide better budget optimization
              recommendations
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Business Strategy Documents
          </CardTitle>
          <p className="text-sm text-dashboard-gray-600">
            Upload documents to help KEN-E understand your business context
            (optional)
          </p>
        </CardHeader>
        <CardContent>
          <FileUpload
            files={formData.business_strategy_documents}
            onFilesChange={(files) =>
              setFormData({
                ...formData,
                business_strategy_documents: files,
              })
            }
            accept={[
              ".pdf",
              ".xlsx",
              ".docx",
              ".pptx",
              ".txt",
              ".png",
              ".jpg",
              ".jpeg",
            ]}
            multiple={true}
            maxSize={25 * 1024 * 1024} // 25MB
            maxTotalSize={100 * 1024 * 1024} // 100MB
            maxFiles={10}
          />
          <p className="text-xs text-dashboard-gray-500 mt-2">
            Examples: Business plan, marketing strategy, customer profiles,
            competitive analysis
          </p>
        </CardContent>
      </Card>
    </>
  );
};
