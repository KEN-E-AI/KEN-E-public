import { useState } from "react";
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
import { Building2, Calendar, MapPin, Globe, Save, AlertTriangle } from "lucide-react";
import { getTemplateById } from "@/data/accountTemplates";
import { validateAccountProfile } from "./validation/accountValidation";
import { ErrorBoundary } from "./ErrorBoundary";

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Array<{field: string; message: string}>>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    account_name: accountData.account_name,
    industry: accountData.industry,
    description: accountData.description || "",
    website: accountData.website || "",
    location: accountData.location || "",
    timezone: accountData.timezone || "America/New_York",
    status: accountData.status,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setValidationErrors([]);
    setSubmitError(null);

    try {
      // Validate form data
      const validation = validateAccountProfile(formData);
      
      if (!validation.success) {
        setValidationErrors(validation.errors || []);
        setIsSubmitting(false);
        return;
      }

      // Call the update function
      await onUpdate(validation.data);
      setIsEditing(false);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "An unexpected error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      account_name: accountData.account_name,
      industry: accountData.industry,
      description: accountData.description || "",
      website: accountData.website || "",
      location: accountData.location || "",
      timezone: accountData.timezone || "America/New_York",
      status: accountData.status,
    });
    setValidationErrors([]);
    setSubmitError(null);
    setIsEditing(false);
  };

  const getFieldError = (fieldName: string) => {
    return validationErrors.find(error => error.field === fieldName)?.message;
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
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Basic Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="account_name">Account Name</Label>
                <Input
                  id="account_name"
                  value={formData.account_name}
                  onChange={(e) =>
                    setFormData({ ...formData, account_name: e.target.value })
                  }
                  disabled={!isEditing}
                  className={`mt-1 ${getFieldError('account_name') ? 'border-red-500' : ''}`}
                />
                {getFieldError('account_name') && (
                  <p className="text-sm text-red-600 mt-1">{getFieldError('account_name')}</p>
                )}
              </div>
              <div>
                <Label htmlFor="industry">Industry</Label>
                <Select
                  value={formData.industry}
                  onValueChange={(value) =>
                    setFormData({ ...formData, industry: value })
                  }
                  disabled={!isEditing}
                >
                  <SelectTrigger className={`mt-1 ${getFieldError('industry') ? 'border-red-500' : ''}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Technology">Technology</SelectItem>
                    <SelectItem value="Healthcare">Healthcare</SelectItem>
                    <SelectItem value="Finance">Finance</SelectItem>
                    <SelectItem value="Education">Education</SelectItem>
                    <SelectItem value="Retail">Retail</SelectItem>
                    <SelectItem value="Manufacturing">Manufacturing</SelectItem>
                    <SelectItem value="Professional Services">
                      Professional Services
                    </SelectItem>
                    <SelectItem value="Non-Profit">Non-Profit</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
                {getFieldError('industry') && (
                  <p className="text-sm text-red-600 mt-1">{getFieldError('industry')}</p>
                )}
              </div>
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                disabled={!isEditing}
                className={`mt-1 ${getFieldError('description') ? 'border-red-500' : ''}`}
                placeholder="Brief description of this account..."
                rows={3}
              />
              {getFieldError('description') && (
                <p className="text-sm text-red-600 mt-1">{getFieldError('description')}</p>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="website">Website</Label>
                <Input
                  id="website"
                  type="url"
                  value={formData.website}
                  onChange={(e) =>
                    setFormData({ ...formData, website: e.target.value })
                  }
                  disabled={!isEditing}
                  className={`mt-1 ${getFieldError('website') ? 'border-red-500' : ''}`}
                  placeholder="https://example.com"
                />
                {getFieldError('website') && (
                  <p className="text-sm text-red-600 mt-1">{getFieldError('website')}</p>
                )}
              </div>
              <div>
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={formData.location}
                  onChange={(e) =>
                    setFormData({ ...formData, location: e.target.value })
                  }
                  disabled={!isEditing}
                  className={`mt-1 ${getFieldError('location') ? 'border-red-500' : ''}`}
                  placeholder="City, State, Country"
                />
                {getFieldError('location') && (
                  <p className="text-sm text-red-600 mt-1">{getFieldError('location')}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="timezone">Timezone</Label>
                <Select
                  value={formData.timezone}
                  onValueChange={(value) =>
                    setFormData({ ...formData, timezone: value })
                  }
                  disabled={!isEditing}
                >
                  <SelectTrigger className={`mt-1 ${getFieldError('timezone') ? 'border-red-500' : ''}`}>
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
                    <SelectItem value="Australia/Sydney">AEST</SelectItem>
                  </SelectContent>
                </Select>
                {getFieldError('timezone') && (
                  <p className="text-sm text-red-600 mt-1">{getFieldError('timezone')}</p>
                )}
              </div>
              <div>
                <Label htmlFor="status">Status</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) =>
                    setFormData({ ...formData, status: value })
                  }
                  disabled={!isEditing}
                >
                  <SelectTrigger className={`mt-1 ${getFieldError('status') ? 'border-red-500' : ''}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Active">Active</SelectItem>
                    <SelectItem value="Inactive">Inactive</SelectItem>
                    <SelectItem value="Setup">Setup</SelectItem>
                    <SelectItem value="Paused">Paused</SelectItem>
                  </SelectContent>
                </Select>
                {getFieldError('status') && (
                  <p className="text-sm text-red-600 mt-1">{getFieldError('status')}</p>
                )}
              </div>
            </div>

            {/* Global Error Display */}
            {(submitError || validationErrors.length > 0) && (
              <Alert variant="destructive" className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {submitError || "Please fix the validation errors above."}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-3 pt-4">
              {isEditing ? (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCancel}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    <Save className="h-4 w-4 mr-2" />
                    {isSubmitting ? "Saving..." : "Save Changes"}
                  </Button>
                </>
              ) : (
                <Button type="button" onClick={() => setIsEditing(true)}>
                  Edit Profile
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Template Information */}
      {template && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <template.icon className="h-5 w-5" />
              Account Template
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <template.icon className="h-6 w-6 text-blue-600" />
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
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Account Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">Auto-sync data</Label>
                <p className="text-sm text-dashboard-gray-600">
                  Automatically sync data from connected platforms
                </p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">
                  Email notifications
                </Label>
                <p className="text-sm text-dashboard-gray-600">
                  Receive email updates about account performance
                </p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">Data archival</Label>
                <p className="text-sm text-dashboard-gray-600">
                  Automatically archive old data after 12 months
                </p>
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
