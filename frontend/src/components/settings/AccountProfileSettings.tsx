import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Form } from "@/components/ui/form";
import {
  Building2,
  Calendar,
  MapPin,
  Globe,
  Save,
  AlertTriangle,
} from "lucide-react";
import { getTemplateById } from "@/data/accountTemplates";
import { accountProfileSchema } from "./validation/accountValidation";
import { ErrorBoundary } from "./ErrorBoundary";
import {
  ScopeHelpIcon,
  ScopeBadge,
  EnhancedFormField,
  SimpleEnhancedFormField,
  ProgressiveDisclosure,
  SettingsGroup,
  CrossReferenceIndicator,
  getRelatedSettings,
  useSmartDefaults,
} from "./guidance";

interface AccountProfileSettingsProps {
  accountId: string;
  accountData: {
    account_name: string;
    industry: string;
    status: string;
    timezone?: string;
    description?: string;
    website?: string;
    location?: string;
    template_id?: string;
  };
  onUpdate: (
    updates: Partial<AccountProfileSettingsProps["accountData"]>,
  ) => void;
}

export const AccountProfileSettings = ({
  accountId,
  accountData,
  onUpdate,
}: AccountProfileSettingsProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { getDefaultValue } = useSmartDefaults("account");

  const form = useForm({
    resolver: zodResolver(accountProfileSchema),
    defaultValues: {
      account_name: accountData.account_name,
      industry: accountData.industry,
      description: accountData.description || "",
      website: accountData.website || "",
      location: accountData.location || "",
      timezone:
        accountData.timezone ||
        getDefaultValue("timezone", "America/New_York").value,
      status: accountData.status,
    },
  });

  const handleSubmit = async (data: any) => {
    setSubmitError(null);

    try {
      await onUpdate(data);
      setIsEditing(false);
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "An unexpected error occurred",
      );
    }
  };

  const handleCancel = () => {
    form.reset();
    setSubmitError(null);
    setIsEditing(false);
  };

  const template = accountData.template_id
    ? getTemplateById(accountData.template_id)
    : null;

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Account Information */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                Basic Information
                <ScopeHelpIcon scope="account" setting="account_profile" />
              </CardTitle>
              <div className="flex items-center gap-2">
                <ScopeBadge scope="account" size="sm" />
                <CrossReferenceIndicator
                  setting="account_profile"
                  relatedSettings={getRelatedSettings("account_name")}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <ProgressiveDisclosure
              basicSettings={
                <Form {...form}>
                  <form
                    onSubmit={form.handleSubmit(handleSubmit)}
                    className="space-y-4"
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <EnhancedFormField
                        control={form.control}
                        name="account_name"
                        label="Account Name"
                        scope="account"
                        helpText="The display name for this marketing account"
                        showInheritance={false}
                        showRecommendations={true}
                      >
                        <Input
                          disabled={!isEditing}
                          placeholder="Enter account name..."
                        />
                      </EnhancedFormField>

                      <EnhancedFormField
                        control={form.control}
                        name="industry"
                        label="Industry"
                        scope="account"
                        helpText="Your industry affects templates and benchmarks"
                        showRecommendations={true}
                      >
                        <Select disabled={!isEditing}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Technology">
                              Technology
                            </SelectItem>
                            <SelectItem value="Healthcare">
                              Healthcare
                            </SelectItem>
                            <SelectItem value="Finance">Finance</SelectItem>
                            <SelectItem value="Education">Education</SelectItem>
                            <SelectItem value="Retail">Retail</SelectItem>
                            <SelectItem value="Manufacturing">
                              Manufacturing
                            </SelectItem>
                            <SelectItem value="Professional Services">
                              Professional Services
                            </SelectItem>
                            <SelectItem value="Non-Profit">
                              Non-Profit
                            </SelectItem>
                            <SelectItem value="Other">Other</SelectItem>
                          </SelectContent>
                        </Select>
                      </EnhancedFormField>
                    </div>

                    <SimpleEnhancedFormField
                      control={form.control}
                      name="description"
                      label="Description"
                      scope="account"
                      helpText="Brief description of this account's purpose"
                    >
                      <Textarea
                        disabled={!isEditing}
                        placeholder="Brief description of this account..."
                        rows={3}
                      />
                    </SimpleEnhancedFormField>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <SimpleEnhancedFormField
                        control={form.control}
                        name="website"
                        label="Website"
                        scope="account"
                        helpText="Company or account website URL"
                      >
                        <Input
                          type="url"
                          disabled={!isEditing}
                          placeholder="https://example.com"
                        />
                      </SimpleEnhancedFormField>

                      <SimpleEnhancedFormField
                        control={form.control}
                        name="location"
                        label="Location"
                        scope="account"
                        helpText="Primary location for this account"
                      >
                        <Input
                          disabled={!isEditing}
                          placeholder="City, State, Country"
                        />
                      </SimpleEnhancedFormField>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <EnhancedFormField
                        control={form.control}
                        name="timezone"
                        label="Timezone"
                        scope="account"
                        helpText="Used for campaign scheduling and reporting"
                        showInheritance={true}
                        showRecommendations={true}
                      >
                        <Select disabled={!isEditing}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="America/New_York">
                              Eastern Time
                            </SelectItem>
                            <SelectItem value="America/Chicago">
                              Central Time
                            </SelectItem>
                            <SelectItem value="America/Denver">
                              Mountain Time
                            </SelectItem>
                            <SelectItem value="America/Los_Angeles">
                              Pacific Time
                            </SelectItem>
                            <SelectItem value="Europe/London">GMT</SelectItem>
                            <SelectItem value="Europe/Paris">CET</SelectItem>
                            <SelectItem value="Asia/Tokyo">JST</SelectItem>
                            <SelectItem value="Australia/Sydney">
                              AEST
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </EnhancedFormField>

                      <SimpleEnhancedFormField
                        control={form.control}
                        name="status"
                        label="Status"
                        scope="account"
                        helpText="Current operational status of this account"
                      >
                        <Select disabled={!isEditing}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Active">Active</SelectItem>
                            <SelectItem value="Inactive">Inactive</SelectItem>
                            <SelectItem value="Setup">Setup</SelectItem>
                            <SelectItem value="Paused">Paused</SelectItem>
                          </SelectContent>
                        </Select>
                      </SimpleEnhancedFormField>
                    </div>

                    {/* Global Error Display */}
                    {submitError && (
                      <Alert variant="destructive" className="mt-4">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>{submitError}</AlertDescription>
                      </Alert>
                    )}

                    <div className="flex justify-end gap-3 pt-4">
                      {isEditing ? (
                        <>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={handleCancel}
                            disabled={form.formState.isSubmitting}
                          >
                            Cancel
                          </Button>
                          <Button
                            type="submit"
                            disabled={form.formState.isSubmitting}
                          >
                            <Save className="h-4 w-4 mr-2" />
                            {form.formState.isSubmitting
                              ? "Saving..."
                              : "Save Changes"}
                          </Button>
                        </>
                      ) : (
                        <Button
                          type="button"
                          onClick={() => setIsEditing(true)}
                        >
                          Edit Profile
                        </Button>
                      )}
                    </div>
                  </form>
                </Form>
              }
              advancedSettings={
                <SettingsGroup
                  title="Advanced Configuration"
                  description="Additional settings for power users"
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SimpleEnhancedFormField
                      control={form.control}
                      name="template_id"
                      label="Account Template"
                      scope="account"
                      helpText="Industry-specific configuration template"
                    >
                      <Select disabled={!isEditing}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select template..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="e-commerce">E-Commerce</SelectItem>
                          <SelectItem value="saas">SaaS</SelectItem>
                          <SelectItem value="healthcare">Healthcare</SelectItem>
                          <SelectItem value="education">Education</SelectItem>
                        </SelectContent>
                      </Select>
                    </SimpleEnhancedFormField>
                  </div>
                </SettingsGroup>
              }
              advancedTitle="Advanced Account Settings"
              advancedDescription="Additional configuration options that affect account behavior"
              advancedWarning="Changes to these settings may affect how your account data is processed"
            />
          </CardContent>
        </Card>

        {/* Template Information */}
        {template && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <template.icon className="h-5 w-5" />
                  Account Template
                  <ScopeHelpIcon scope="account" setting="template_id" />
                </CardTitle>
                <div className="flex items-center gap-2">
                  <ScopeBadge scope="template" size="sm" />
                  <CrossReferenceIndicator
                    setting="template_id"
                    relatedSettings={getRelatedSettings("industry")}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 bg-brand-light-blue/20 rounded-lg flex items-center justify-center">
                  <template.icon className="h-6 w-6 text-brand-medium-blue" />
                </div>
                <div>
                  <h3 className="font-semibold">{template.name}</h3>
                  <p className="text-sm text-dashboard-gray-600">
                    {template.description}
                  </p>
                </div>
                <Badge variant="secondary">{template.category}</Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <h4 className="font-medium mb-2">Default Objectives</h4>
                  <ul className="space-y-1 text-dashboard-gray-600">
                    {template.defaultObjectives
                      .slice(0, 3)
                      .map((objective, index) => (
                        <li key={index}>• {objective}</li>
                      ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium mb-2">Recommended Channels</h4>
                  <ul className="space-y-1 text-dashboard-gray-600">
                    {template.defaultChannels
                      .slice(0, 3)
                      .map((channel, index) => (
                        <li key={index}>• {channel}</li>
                      ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium mb-2">Key KPIs</h4>
                  <ul className="space-y-1 text-dashboard-gray-600">
                    {template.defaultKPIs.slice(0, 3).map((kpi, index) => (
                      <li key={index}>• {kpi}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Account Settings */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Account Settings
                <ScopeHelpIcon scope="account" setting="account_settings" />
              </CardTitle>
              <div className="flex items-center gap-2">
                <ScopeBadge scope="account" size="sm" />
                <CrossReferenceIndicator
                  setting="account_settings"
                  relatedSettings={getRelatedSettings("auto_sync")}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div>
                    <Label className="text-sm font-medium">
                      Auto-sync data
                    </Label>
                    <p className="text-sm text-dashboard-gray-600">
                      Automatically sync data from connected platforms
                    </p>
                  </div>
                  <ScopeHelpIcon scope="account" setting="auto_sync" />
                </div>
                <Switch defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div>
                    <Label className="text-sm font-medium">
                      Performance alerts
                    </Label>
                    <p className="text-sm text-dashboard-gray-600">
                      Get notified when performance exceeds thresholds
                    </p>
                  </div>
                  <ScopeHelpIcon scope="account" setting="performance_alerts" />
                </div>
                <Switch defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div>
                    <Label className="text-sm font-medium">Data archival</Label>
                    <p className="text-sm text-dashboard-gray-600">
                      Automatically archive old data after 12 months
                    </p>
                  </div>
                  <ScopeHelpIcon scope="account" setting="data_retention" />
                </div>
                <Switch />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </ErrorBoundary>
  );
};
