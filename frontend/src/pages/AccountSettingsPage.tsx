import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ContextBreadcrumb } from "@/components/ui/context-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Building2,
  Target,
  Shield,
  Link,
  TrendingUp,
  Settings,
  AlertCircle,
  CheckCircle,
  Clock,
  Users,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { AccountProfileSettings } from "@/components/settings/AccountProfileSettings";
import { AccountMarketingSettings } from "@/components/settings/AccountMarketingSettings";
import { AccountPrivacySettings } from "@/components/settings/AccountPrivacySettings";
import { AccountIntegrationsSettings } from "@/components/settings/AccountIntegrationsSettings";
import { AccountPerformanceSettings } from "@/components/settings/AccountPerformanceSettings";
import { AccountAccessSettings } from "@/components/settings/AccountAccessSettings";

const AccountSettingsPage = () => {
  const { accountId } = useParams<{ accountId: string }>();
  const navigate = useNavigate();
  const { user, selectedOrgAccount, accountMetadata } = useAuth();

  // Get account data
  const currentAccount = accountId ? accountMetadata[accountId] : null;

  // If no account ID or account not found, redirect
  useEffect(() => {
    if (!accountId || !currentAccount) {
      navigate("/settings");
    }
  }, [accountId, currentAccount, navigate]);

  if (!currentAccount) {
    return (
      <Layout pageTitle="Account Settings">
        <div>
          <div className="text-center py-8">
            <p className="text-gray-500">Account not found</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Mock data - in real app, this would come from API
  const mockAccountData = {
    account_name: currentAccount?.account_name || "",
    industry: currentAccount?.industry || "",
    status: currentAccount?.status || "Active",
    timezone: currentAccount?.timezone || "America/New_York",
    description: "Marketing account for product campaigns",
    website: "https://example.com",
    location: "New York, NY",
    template_id: "e-commerce",
  };

  const mockMarketingData = {
    objectives: [
      {
        id: "awareness",
        name: "Brand Awareness",
        description: "Increase brand recognition among target audience",
        priority: "high" as const,
        status: "active" as const,
      },
      {
        id: "conversion",
        name: "Lead Generation",
        description: "Generate qualified leads for sales team",
        priority: "medium" as const,
        status: "active" as const,
      },
    ],
    channels: [
      {
        id: "social",
        name: "Social Media",
        budget: 5000,
        status: "active" as const,
        tactics: ["Organic posts", "Paid ads", "Influencer partnerships"],
      },
      {
        id: "search",
        name: "Search Marketing",
        budget: 8000,
        status: "active" as const,
        tactics: ["Google Ads", "SEO", "Local search"],
      },
    ],
    budget: {
      total: 15000,
      period: "monthly" as const,
    },
    settings: {
      auto_optimization: true,
      performance_alerts: true,
      budget_alerts: true,
    },
  };

  const mockPrivacyData = {
    dataRetention: [
      {
        dataType: "Analytics Data",
        retentionPeriod: 365,
        unit: "days" as const,
        autoDelete: true,
      },
      {
        dataType: "User Data",
        retentionPeriod: 2,
        unit: "years" as const,
        autoDelete: false,
      },
    ],
    complianceFrameworks: [
      {
        id: "gdpr",
        name: "GDPR",
        enabled: true,
        requirements: [
          "Data minimization",
          "Right to erasure",
          "Consent management",
        ],
      },
      {
        id: "ccpa",
        name: "CCPA",
        enabled: false,
        requirements: [
          "Data disclosure",
          "Opt-out rights",
          "Non-discrimination",
        ],
      },
    ],
    dataProcessing: {
      collect_analytics: true,
      collect_behavioral: true,
      collect_personal: false,
      share_aggregated: true,
      anonymize_data: true,
    },
    userRights: {
      allow_data_export: true,
      allow_data_deletion: true,
      allow_opt_out: true,
      require_consent: true,
    },
  };

  const mockIntegrationsData = {
    integrations: [
      {
        id: "google-ads",
        name: "Google Ads",
        description: "Connect your Google Ads account",
        category: "Marketing Automation",
        status: "connected" as const,
        icon: "google",
        lastSync: "2024-01-15T10:30:00Z",
      },
      {
        id: "facebook-ads",
        name: "Facebook Ads",
        description: "Connect your Facebook Ads account",
        category: "Social Media",
        status: "disconnected" as const,
        icon: "facebook",
      },
    ],
    apiKeys: [
      {
        id: "key1",
        name: "Production API Key",
        created: "2024-01-01T00:00:00Z",
        lastUsed: "2024-01-15T12:00:00Z",
        permissions: ["read", "write"],
        status: "active" as const,
      },
    ],
    webhooks: [
      {
        url: "https://api.example.com/webhooks/account",
        events: ["campaign.created", "performance.alert"],
        active: true,
      },
    ],
    settings: {
      auto_sync: true,
      error_notifications: true,
      sync_frequency: "daily" as const,
    },
  };

  const mockPerformanceData = {
    kpis: [
      {
        id: "conversion-rate",
        name: "Conversion Rate",
        description: "Percentage of visitors who convert",
        target: 3.5,
        current: 2.8,
        unit: "%",
        trend: "up" as const,
        frequency: "weekly" as const,
        alerts: {
          threshold: 2.0,
          type: "below" as const,
          enabled: true,
        },
      },
      {
        id: "roas",
        name: "Return on Ad Spend",
        description: "Revenue generated per dollar spent",
        target: 4.0,
        current: 3.2,
        unit: "x",
        trend: "stable" as const,
        frequency: "monthly" as const,
        alerts: {
          threshold: 3.0,
          type: "below" as const,
          enabled: true,
        },
      },
    ],
    alerts: [
      {
        id: "low-conversion",
        name: "Low Conversion Rate Alert",
        condition: "below_threshold",
        threshold: 2.0,
        frequency: "immediate" as const,
        recipients: ["admin@example.com"],
        enabled: true,
      },
    ],
    reports: [
      {
        id: "weekly-report",
        name: "Weekly Performance Report",
        frequency: "weekly" as const,
        recipients: ["manager@example.com"],
        metrics: ["conversion-rate", "roas"],
        enabled: true,
      },
    ],
    dashboard: {
      refresh_interval: 300,
      show_trends: true,
      show_comparisons: true,
      default_date_range: "30d" as const,
    },
    targets: {
      auto_update: false,
      notification_threshold: 80,
      benchmark_comparison: true,
    },
  };

  const handleUpdate = (section: string, updates: any) => {
    // In real implementation, this would update the backend
    console.log(`Update ${section} for account ${accountId}:`, updates);
  };

  return (
    <Layout pageTitle="Account Settings">
      <div className="space-y-8">
        <ContextBreadcrumb currentPage="account" />

        {/* Account Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-dashboard-gray-900">
              Account Settings
            </h1>
            <p className="text-dashboard-gray-600 mt-2">
              Configure settings for "{currentAccount.account_name}"
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {currentAccount.industry}
            </Badge>
            <Badge
              variant={
                currentAccount.status === "Active" ? "secondary" : "outline"
              }
              className="text-xs"
            >
              {currentAccount.status}
            </Badge>
          </div>
        </div>

        {/* Account Context Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Account Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-dashboard-gray-700">
                  Account Name:
                </span>
                <p className="text-dashboard-gray-900">
                  {currentAccount.account_name}
                </p>
              </div>
              <div>
                <span className="font-medium text-dashboard-gray-700">
                  Industry:
                </span>
                <p className="text-dashboard-gray-900">
                  {currentAccount.industry}
                </p>
              </div>
              <div>
                <span className="font-medium text-dashboard-gray-700">
                  Status:
                </span>
                <p className="text-dashboard-gray-900">
                  {currentAccount.status}
                </p>
              </div>
              <div>
                <span className="font-medium text-dashboard-gray-700">
                  Timezone:
                </span>
                <p className="text-dashboard-gray-900">
                  {currentAccount.timezone || "Not set"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Settings Tabs */}
        <Tabs defaultValue="profile" className="w-full">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="profile" className="flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              Profile
            </TabsTrigger>
            <TabsTrigger value="marketing" className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              Marketing
            </TabsTrigger>
            <TabsTrigger value="privacy" className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              Privacy
            </TabsTrigger>
            <TabsTrigger
              value="integrations"
              className="flex items-center gap-2"
            >
              <Link className="h-4 w-4" />
              Integrations
            </TabsTrigger>
            <TabsTrigger
              value="performance"
              className="flex items-center gap-2"
            >
              <TrendingUp className="h-4 w-4" />
              Performance
            </TabsTrigger>
            <TabsTrigger value="access" className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Access
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="mt-6">
            <AccountProfileSettings
              accountId={accountId!}
              accountData={mockAccountData}
              onUpdate={(updates) => handleUpdate("profile", updates)}
            />
          </TabsContent>

          <TabsContent value="marketing" className="mt-6">
            <AccountMarketingSettings
              accountId={accountId!}
              marketingData={mockMarketingData}
              onUpdate={(updates) => handleUpdate("marketing", updates)}
            />
          </TabsContent>

          <TabsContent value="privacy" className="mt-6">
            <AccountPrivacySettings
              accountId={accountId!}
              privacyData={mockPrivacyData}
              onUpdate={(updates) => handleUpdate("privacy", updates)}
            />
          </TabsContent>

          <TabsContent value="integrations" className="mt-6">
            <AccountIntegrationsSettings
              accountId={accountId!}
              integrationsData={mockIntegrationsData}
              onUpdate={(updates) => handleUpdate("integrations", updates)}
            />
          </TabsContent>

          <TabsContent value="performance" className="mt-6">
            <AccountPerformanceSettings
              accountId={accountId!}
              performanceData={mockPerformanceData}
              onUpdate={(updates) => handleUpdate("performance", updates)}
            />
          </TabsContent>

          <TabsContent value="access" className="mt-6">
            <AccountAccessSettings
              accountId={accountId!}
              onUpdate={(updates) => handleUpdate("access", updates)}
            />
          </TabsContent>
        </Tabs>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={() => navigate("/organization-settings")}
                className="flex items-center gap-2"
              >
                <Building2 className="h-4 w-4" />
                Organization Settings
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate("/settings")}
                className="flex items-center gap-2"
              >
                <Settings className="h-4 w-4" />
                All Settings
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default AccountSettingsPage;
