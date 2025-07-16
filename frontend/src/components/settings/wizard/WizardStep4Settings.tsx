import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Settings } from "lucide-react";
import { type AccountTemplate } from "@/data/accountTemplates";
import { AccountCreationData } from "../AccountCreationWizard";

interface WizardStep4SettingsProps {
  formData: AccountCreationData;
  setFormData: (data: AccountCreationData) => void;
  selectedTemplate: AccountTemplate | null;
}

export const WizardStep4Settings = ({
  formData,
  setFormData,
  selectedTemplate,
}: WizardStep4SettingsProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Settings & Preferences
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <Label className="text-base font-medium mb-4 block">
            Account Settings
          </Label>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">Auto-sync data</Label>
                <p className="text-sm text-dashboard-gray-600">
                  Automatically sync data from connected platforms
                </p>
              </div>
              <Checkbox
                checked={formData.auto_sync}
                onCheckedChange={(checked) =>
                  setFormData({
                    ...formData,
                    auto_sync: checked as boolean,
                  })
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">
                  Performance alerts
                </Label>
                <p className="text-sm text-dashboard-gray-600">
                  Get notified when performance exceeds or falls below
                  thresholds
                </p>
              </div>
              <Checkbox
                checked={formData.performance_alerts}
                onCheckedChange={(checked) =>
                  setFormData({
                    ...formData,
                    performance_alerts: checked as boolean,
                  })
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">Budget alerts</Label>
                <p className="text-sm text-dashboard-gray-600">
                  Receive notifications when approaching budget limits
                </p>
              </div>
              <Checkbox
                checked={formData.budget_alerts}
                onCheckedChange={(checked) =>
                  setFormData({
                    ...formData,
                    budget_alerts: checked as boolean,
                  })
                }
              />
            </div>
          </div>
        </div>

        <div>
          <Label htmlFor="data_retention">Data Retention (days)</Label>
          <Select
            value={formData.data_retention.toString()}
            onValueChange={(value) =>
              setFormData({
                ...formData,
                data_retention: parseInt(value),
              })
            }
          >
            <SelectTrigger className="mt-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="90">90 days</SelectItem>
              <SelectItem value="180">180 days</SelectItem>
              <SelectItem value="365">1 year</SelectItem>
              <SelectItem value="730">2 years</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Summary */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <h4 className="font-medium mb-2">Account Summary</h4>
          <div className="text-sm text-dashboard-gray-600 space-y-1">
            <p>
              <strong>Name:</strong> {formData.account_name}
            </p>
            <p>
              <strong>Industry:</strong> {formData.industry}
            </p>
            <p>
              <strong>Template:</strong> {selectedTemplate?.name}
            </p>
            <p>
              <strong>Objectives:</strong> {formData.objectives.length} selected
            </p>
            <p>
              <strong>Channels:</strong> {formData.channels.length} selected
            </p>
            <p>
              <strong>KPIs:</strong> {formData.kpis.length} selected
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
