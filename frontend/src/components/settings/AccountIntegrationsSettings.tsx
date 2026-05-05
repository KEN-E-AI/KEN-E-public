import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Link,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
  Settings,
  Key,
  ExternalLink,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  status: "connected" | "disconnected" | "error" | "pending";
  icon: string;
  lastSync?: string;
  config?: {
    api_key?: string;
    webhook_url?: string;
    sync_frequency?: "realtime" | "hourly" | "daily";
    data_types?: string[];
  };
}

interface APIKey {
  id: string;
  name: string;
  created: string;
  lastUsed?: string;
  permissions: string[];
  status: "active" | "inactive";
}

interface AccountIntegrationsSettingsProps {
  accountId: string;
  integrationsData: {
    integrations: Integration[];
    apiKeys: APIKey[];
    webhooks: {
      url: string;
      events: string[];
      active: boolean;
    }[];
    settings: {
      auto_sync: boolean;
      error_notifications: boolean;
      sync_frequency: "realtime" | "hourly" | "daily";
    };
  };
  onUpdate: (
    updates: Partial<AccountIntegrationsSettingsProps["integrationsData"]>,
  ) => void;
}

export const AccountIntegrationsSettings = ({
  accountId,
  integrationsData,
  onUpdate,
}: AccountIntegrationsSettingsProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [integrations, setIntegrations] = useState(
    integrationsData.integrations,
  );
  const [apiKeys, setApiKeys] = useState(integrationsData.apiKeys);
  const [webhooks, setWebhooks] = useState(integrationsData.webhooks);
  const [settings, setSettings] = useState(integrationsData.settings);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({ integrations, apiKeys, webhooks, settings });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setIntegrations(integrationsData.integrations);
    setApiKeys(integrationsData.apiKeys);
    setWebhooks(integrationsData.webhooks);
    setSettings(integrationsData.settings);
    setIsEditing(false);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "connected":
        return <CheckCircle className="h-4 w-4 text-brand-dark-blue" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "pending":
        return <AlertCircle className="h-4 w-4 text-brand-dark-blue" />;
      default:
        return (
          <XCircle className="h-4 w-4 text-[var(--color-text-disabled)]" />
        );
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40";
      case "error":
        return "bg-red-50 text-red-700 border-red-200";
      case "pending":
        return "bg-brand-yellow/20 text-brand-dark-blue border-brand-yellow/40";
      default:
        return "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] border-[var(--color-border-default)]";
    }
  };

  const updateIntegration = (id: string, updates: Partial<Integration>) => {
    setIntegrations(
      integrations.map((int) => (int.id === id ? { ...int, ...updates } : int)),
    );
  };

  const connectIntegration = (id: string) => {
    // Simulate connection
    updateIntegration(id, {
      status: "connected",
      lastSync: new Date().toISOString(),
    });
  };

  const disconnectIntegration = (id: string) => {
    updateIntegration(id, { status: "disconnected" });
  };

  const addAPIKey = () => {
    const newKey: APIKey = {
      id: Date.now().toString(),
      name: "New API Key",
      created: new Date().toISOString(),
      permissions: ["read"],
      status: "active",
    };
    setApiKeys([...apiKeys, newKey]);
  };

  const removeAPIKey = (id: string) => {
    setApiKeys(apiKeys.filter((key) => key.id !== id));
  };

  const integrationCategories = [
    "All",
    "Marketing Automation",
    "Analytics",
    "CRM",
    "Social Media",
    "Email Marketing",
    "E-commerce",
    "Other",
  ];

  const [selectedCategory, setSelectedCategory] = useState("All");

  const filteredIntegrations =
    selectedCategory === "All"
      ? integrations
      : integrations.filter((int) => int.category === selectedCategory);

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit}>
        {/* Integration Categories */}
        <div className="flex flex-wrap gap-2 mb-6">
          {integrationCategories.map((category) => (
            <Button
              key={category}
              type="button"
              variant={selectedCategory === category ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategory(category)}
            >
              {category}
            </Button>
          ))}
        </div>

        {/* Available Integrations */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link className="h-5 w-5" />
              Available Integrations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredIntegrations.map((integration) => (
                <div key={integration.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-brand-light-blue/20 rounded-lg flex items-center justify-center">
                        <Link className="h-5 w-5 text-brand-medium-blue" />
                      </div>
                      <div>
                        <h3 className="font-medium">{integration.name}</h3>
                        <p className="text-sm text-dashboard-gray-600">
                          {integration.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(integration.status)}
                      <Badge className={getStatusColor(integration.status)}>
                        {integration.status}
                      </Badge>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="text-sm text-dashboard-gray-600">
                      {integration.lastSync && (
                        <span>
                          Last sync:{" "}
                          {new Date(integration.lastSync).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {integration.status === "connected" ? (
                        <>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              disconnectIntegration(integration.id)
                            }
                          >
                            Disconnect
                          </Button>
                          <Button type="button" variant="outline" size="sm">
                            <Settings className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => connectIntegration(integration.id)}
                        >
                          Connect
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* API Keys */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                API Keys
              </div>
              {isEditing && (
                <Button type="button" size="sm" onClick={addAPIKey}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add API Key
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {apiKeys.map((apiKey) => (
                <div key={apiKey.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-medium">{apiKey.name}</h3>
                      <p className="text-sm text-dashboard-gray-600">
                        Created: {new Date(apiKey.created).toLocaleDateString()}
                      </p>
                      {apiKey.lastUsed && (
                        <p className="text-sm text-dashboard-gray-600">
                          Last used:{" "}
                          {new Date(apiKey.lastUsed).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        className={
                          apiKey.status === "active"
                            ? getStatusColor("connected")
                            : getStatusColor("disconnected")
                        }
                      >
                        {apiKey.status}
                      </Badge>
                      {isEditing && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeAPIKey(apiKey.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-sm text-dashboard-gray-600">
                      Permissions:
                    </span>
                    {apiKey.permissions.map((permission) => (
                      <Badge key={permission} variant="secondary">
                        {permission}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Webhooks */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              Webhooks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {webhooks.map((webhook, index) => (
                <div key={index} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-medium">Webhook {index + 1}</h3>
                      <p className="text-sm text-dashboard-gray-600 font-mono">
                        {webhook.url}
                      </p>
                    </div>
                    <Switch
                      checked={webhook.active}
                      onCheckedChange={(checked) => {
                        const newWebhooks = [...webhooks];
                        newWebhooks[index] = { ...webhook, active: checked };
                        setWebhooks(newWebhooks);
                      }}
                      disabled={!isEditing}
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-sm text-dashboard-gray-600">
                      Events:
                    </span>
                    {webhook.events.map((event) => (
                      <Badge key={event} variant="secondary">
                        {event}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Integration Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Integration Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">Auto-sync</Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Automatically sync data from connected integrations
                  </p>
                </div>
                <Switch
                  checked={settings.auto_sync}
                  onCheckedChange={(checked) =>
                    setSettings({ ...settings, auto_sync: checked })
                  }
                  disabled={!isEditing}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">
                    Error notifications
                  </Label>
                  <p className="text-sm text-dashboard-gray-600">
                    Get notified when integration errors occur
                  </p>
                </div>
                <Switch
                  checked={settings.error_notifications}
                  onCheckedChange={(checked) =>
                    setSettings({ ...settings, error_notifications: checked })
                  }
                  disabled={!isEditing}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Sync frequency</Label>
                  <Select
                    value={settings.sync_frequency}
                    onValueChange={(value: "realtime" | "hourly" | "daily") =>
                      setSettings({ ...settings, sync_frequency: value })
                    }
                    disabled={!isEditing}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="realtime">Real-time</SelectItem>
                      <SelectItem value="hourly">Hourly</SelectItem>
                      <SelectItem value="daily">Daily</SelectItem>
                    </SelectContent>
                  </Select>
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
              Edit Integration Settings
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};
