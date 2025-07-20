import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Shield,
  Lock,
  Eye,
  Database,
  Download,
  Trash2,
  AlertTriangle,
  Info,
  Save,
  FileText,
  Calendar,
} from "lucide-react";

interface DataRetentionSetting {
  dataType: string;
  retentionPeriod: number;
  unit: "days" | "months" | "years";
  autoDelete: boolean;
}

interface ComplianceFramework {
  id: string;
  name: string;
  enabled: boolean;
  requirements: string[];
}

interface AccountPrivacySettingsProps {
  accountId: string;
  privacyData: {
    dataRetention: DataRetentionSetting[];
    complianceFrameworks: ComplianceFramework[];
    dataProcessing: {
      collect_analytics: boolean;
      collect_behavioral: boolean;
      collect_personal: boolean;
      share_aggregated: boolean;
      anonymize_data: boolean;
    };
    userRights: {
      allow_data_export: boolean;
      allow_data_deletion: boolean;
      allow_opt_out: boolean;
      require_consent: boolean;
    };
  };
  onUpdate: (
    updates: Partial<AccountPrivacySettingsProps["privacyData"]>,
  ) => void;
}

export const AccountPrivacySettings = ({
  accountId,
  privacyData,
  onUpdate,
}: AccountPrivacySettingsProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [dataRetention, setDataRetention] = useState(privacyData.dataRetention);
  const [complianceFrameworks, setComplianceFrameworks] = useState(
    privacyData.complianceFrameworks,
  );
  const [dataProcessing, setDataProcessing] = useState(
    privacyData.dataProcessing,
  );
  const [userRights, setUserRights] = useState(privacyData.userRights);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({
      dataRetention,
      complianceFrameworks,
      dataProcessing,
      userRights,
    });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setDataRetention(privacyData.dataRetention);
    setComplianceFrameworks(privacyData.complianceFrameworks);
    setDataProcessing(privacyData.dataProcessing);
    setUserRights(privacyData.userRights);
    setIsEditing(false);
  };

  const updateDataRetention = (
    index: number,
    updates: Partial<DataRetentionSetting>,
  ) => {
    const newRetention = [...dataRetention];
    newRetention[index] = { ...newRetention[index], ...updates };
    setDataRetention(newRetention);
  };

  const updateComplianceFramework = (id: string, enabled: boolean) => {
    setComplianceFrameworks((frameworks) =>
      frameworks.map((f) => (f.id === id ? { ...f, enabled } : f)),
    );
  };

  const getComplianceStatus = (framework: ComplianceFramework) => {
    return framework.enabled ? "Enabled" : "Disabled";
  };

  const getComplianceColor = (framework: ComplianceFramework) => {
    return framework.enabled
      ? "bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40"
      : "bg-gray-50 text-gray-700 border-gray-200";
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit}>
        {/* Data Retention */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Data Retention
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {dataRetention.map((retention, index) => (
                <div key={index} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium">{retention.dataType}</h3>
                    <Badge
                      variant={retention.autoDelete ? "default" : "secondary"}
                    >
                      {retention.autoDelete ? "Auto-Delete" : "Manual"}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label>Retention Period</Label>
                      <Select
                        value={retention.retentionPeriod.toString()}
                        onValueChange={(value) =>
                          updateDataRetention(index, {
                            retentionPeriod: parseInt(value),
                          })
                        }
                        disabled={!isEditing}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="30">30</SelectItem>
                          <SelectItem value="90">90</SelectItem>
                          <SelectItem value="180">180</SelectItem>
                          <SelectItem value="365">365</SelectItem>
                          <SelectItem value="730">730</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Unit</Label>
                      <Select
                        value={retention.unit}
                        onValueChange={(value: "days" | "months" | "years") =>
                          updateDataRetention(index, { unit: value })
                        }
                        disabled={!isEditing}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="days">Days</SelectItem>
                          <SelectItem value="months">Months</SelectItem>
                          <SelectItem value="years">Years</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center gap-2 mt-6">
                      <Switch
                        checked={retention.autoDelete}
                        onCheckedChange={(checked) =>
                          updateDataRetention(index, { autoDelete: checked })
                        }
                        disabled={!isEditing}
                      />
                      <Label>Auto-Delete</Label>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Compliance Frameworks */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Compliance Frameworks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {complianceFrameworks.map((framework) => (
                <div key={framework.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium">{framework.name}</h3>
                      <Badge className={getComplianceColor(framework)}>
                        {getComplianceStatus(framework)}
                      </Badge>
                    </div>
                    <Switch
                      checked={framework.enabled}
                      onCheckedChange={(checked) =>
                        updateComplianceFramework(framework.id, checked)
                      }
                      disabled={!isEditing}
                    />
                  </div>

                  {framework.enabled && (
                    <div>
                      <Label className="text-sm font-medium mb-2 block">
                        Requirements:
                      </Label>
                      <ul className="text-sm text-dashboard-gray-600 space-y-1">
                        {framework.requirements.map((req, index) => (
                          <li key={index} className="flex items-start gap-2">
                            <div className="w-1 h-1 bg-dashboard-gray-400 rounded-full mt-2 flex-shrink-0"></div>
                            {req}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Data Processing */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Data Processing
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Collect Analytics Data
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Collect user behavior and performance analytics
                  </p>
                </div>
                <Switch
                  checked={dataProcessing.collect_analytics}
                  onCheckedChange={(checked) =>
                    setDataProcessing({
                      ...dataProcessing,
                      collect_analytics: checked,
                    })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Collect Behavioral Data
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Track user interactions and engagement patterns
                  </p>
                </div>
                <Switch
                  checked={dataProcessing.collect_behavioral}
                  onCheckedChange={(checked) =>
                    setDataProcessing({
                      ...dataProcessing,
                      collect_behavioral: checked,
                    })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Collect Personal Data
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Collect personally identifiable information
                  </p>
                </div>
                <Switch
                  checked={dataProcessing.collect_personal}
                  onCheckedChange={(checked) =>
                    setDataProcessing({
                      ...dataProcessing,
                      collect_personal: checked,
                    })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Share Aggregated Data
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Share anonymized, aggregated data with third parties
                  </p>
                </div>
                <Switch
                  checked={dataProcessing.share_aggregated}
                  onCheckedChange={(checked) =>
                    setDataProcessing({
                      ...dataProcessing,
                      share_aggregated: checked,
                    })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">Anonymize Data</Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Automatically anonymize personal data after collection
                  </p>
                </div>
                <Switch
                  checked={dataProcessing.anonymize_data}
                  onCheckedChange={(checked) =>
                    setDataProcessing({
                      ...dataProcessing,
                      anonymize_data: checked,
                    })
                  }
                  disabled={!isEditing}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* User Rights */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              User Rights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Allow Data Export
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Users can request and download their data
                  </p>
                </div>
                <Switch
                  checked={userRights.allow_data_export}
                  onCheckedChange={(checked) =>
                    setUserRights({ ...userRights, allow_data_export: checked })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Allow Data Deletion
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Users can request deletion of their data
                  </p>
                </div>
                <Switch
                  checked={userRights.allow_data_deletion}
                  onCheckedChange={(checked) =>
                    setUserRights({
                      ...userRights,
                      allow_data_deletion: checked,
                    })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">Allow Opt-Out</Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Users can opt out of data collection
                  </p>
                </div>
                <Switch
                  checked={userRights.allow_opt_out}
                  onCheckedChange={(checked) =>
                    setUserRights({ ...userRights, allow_opt_out: checked })
                  }
                  disabled={!isEditing}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">Require Consent</Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Require explicit consent for data processing
                  </p>
                </div>
                <Switch
                  checked={userRights.require_consent}
                  onCheckedChange={(checked) =>
                    setUserRights({ ...userRights, require_consent: checked })
                  }
                  disabled={!isEditing}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Privacy Notice */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-5 w-5" />
              Privacy Notice
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-brand-light-blue/20 border border-brand-light-blue/40 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-brand-medium-blue mt-0.5" />
                <div>
                  <p className="text-sm text-brand-dark-blue">
                    Your privacy settings ensure compliance with data protection
                    regulations. Changes to these settings may affect data
                    collection and user experience.
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      <FileText className="h-4 w-4 mr-2" />
                      View Privacy Policy
                    </Button>
                    <Button variant="outline" size="sm">
                      <Download className="h-4 w-4 mr-2" />
                      Export Data
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          {isEditing ? (
            <>
              <Button type="button" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
              <Button type="submit">
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </>
          ) : (
            <Button type="button" onClick={() => setIsEditing(true)}>
              Edit Privacy Settings
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};
