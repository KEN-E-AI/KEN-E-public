import { useNavigate } from "react-router-dom";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { EntitySelector } from "@/components/ui/entity-selector";
import {
  EnhancedEntitySelector,
  ContextualActionBar,
  ConfigurationStatusBadge,
  ConfigurationOverview,
  getOrganizationActions,
  getAccountActions,
  type ConfigurationStatus,
} from "@/components/settings/guidance";
import {
  Building2,
  User,
  Users,
  ArrowRight,
  CheckCircle,
  AlertCircle,
  Clock,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useSettingsNavigation } from "@/hooks/useSettingsNavigation";

const Settings = () => {
  const navigate = useNavigate();
  const { user, selectedOrgAccount, orgMetadata } = useAuth();
  const { navigationItems } = useSettingsNavigation();

  const currentOrgName =
    selectedOrgAccount?.metadata?.organization_name || "Organization";
  const currentAccountName =
    selectedOrgAccount?.metadata?.account_name || "Account";

  // Mock configuration completion data - in a real app, this would come from API
  const getConfigurationStatus = (cardId: string) => {
    switch (cardId) {
      case "organization":
        return {
          status: "complete" as ConfigurationStatus,
          completedSteps: 4,
          totalSteps: 4,
          requiredSteps: 3,
          lastUpdated: "2 days ago",
        };
      case "account":
        return {
          status: "warning" as ConfigurationStatus,
          completedSteps: 2,
          totalSteps: 3,
          requiredSteps: 2,
          lastUpdated: "1 week ago",
        };
      case "user":
        return {
          status: "incomplete" as ConfigurationStatus,
          completedSteps: 1,
          totalSteps: 3,
          requiredSteps: 2,
          lastUpdated: "Never",
        };
      default:
        return {
          status: "incomplete" as ConfigurationStatus,
          completedSteps: 0,
          totalSteps: 1,
          requiredSteps: 1,
          lastUpdated: "Never",
        };
    }
  };

  const settingsCards = [
    {
      id: "organization",
      title: "Organization Settings",
      description:
        "Manage organization profile, subscription, billing, and team settings",
      icon: Building2,
      route: "/settings/organization",
      context: currentOrgName,
      enabled: true,
      ...getConfigurationStatus("organization"),
    },
    {
      id: "account",
      title: "Account Management",
      description: "Create and manage accounts within your organization",
      icon: Users,
      route: "/settings/account",
      context: "Manage accounts",
      enabled: true,
      ...getConfigurationStatus("account"),
    },
    {
      id: "user",
      title: "User Settings",
      description:
        "Manage your personal profile, notifications, and preferences",
      icon: User,
      route: "/settings/user",
      context:
        `${user?.firstName} ${user?.lastName}`.trim() || "Personal Settings",
      enabled: true,
      ...getConfigurationStatus("user"),
    },
  ];

  const getStatusBadge = (status: "complete" | "incomplete" | "warning") => {
    switch (status) {
      case "complete":
        return (
          <Badge className="bg-brand-light-green/20 text-brand-dark-blue border-brand-light-green/40">
            <CheckCircle className="h-3 w-3 mr-1 text-brand-dark-blue" />
            Complete
          </Badge>
        );
      case "warning":
        return (
          <Badge className="bg-brand-yellow/20 text-brand-dark-blue border-brand-yellow/40">
            <AlertCircle className="h-3 w-3 mr-1 text-brand-dark-blue" />
            Needs Attention
          </Badge>
        );
      case "incomplete":
        return (
          <Badge className="bg-gray-50 text-gray-700 border-gray-200">
            <Clock className="h-3 w-3 mr-1" />
            Incomplete
          </Badge>
        );
    }
  };

  const handleCardClick = (route: string) => {
    navigate(route);
  };

  return (
    <SettingsLayout
      pageTitle="Settings"
      currentPage="settings"
      showBackButton={false}
      showEntitySelector={false}
    >
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-dashboard-gray-900">Settings</h1>
        <p className="text-dashboard-gray-600 mt-2">
          Manage your organization, accounts, and personal settings
        </p>
      </div>

      {/* Enhanced Entity Selector with Contextual Actions */}
      {selectedOrgAccount && (
        <EnhancedEntitySelector
          layout="card"
          showContextualActions={true}
          showCurrentContext={true}
          availableActions={["switch", "create", "manage"]}
          onActionClick={(action) => {
            console.log("Action clicked:", action);
          }}
        />
      )}

      {/* Configuration Overview */}
      <ConfigurationOverview
        sections={[
          {
            id: "organization",
            title: "Organization Settings",
            description: "Organization profile, billing, and team management",
            ...getConfigurationStatus("organization"),
          },
          {
            id: "account",
            title: "Account Management",
            description: "Account creation and configuration",
            ...getConfigurationStatus("account"),
          },
          {
            id: "user",
            title: "User Settings",
            description: "Personal profile and preferences",
            ...getConfigurationStatus("user"),
          },
        ]}
      />

      {/* Settings Cards with Status Indicators */}
      <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2">
        {settingsCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card
              key={card.id}
              className="cursor-pointer hover:shadow-md transition-shadow group"
              onClick={() => handleCardClick(card.route)}
            >
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-brand-light-blue/20 rounded-lg flex items-center justify-center">
                      <Icon className="h-5 w-5 text-brand-medium-blue" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-dashboard-gray-900">
                          {card.title}
                        </h3>
                        <ConfigurationStatusBadge
                          status={card.status}
                          completedSteps={card.completedSteps}
                          totalSteps={card.totalSteps}
                          requiredSteps={card.requiredSteps}
                          lastUpdated={card.lastUpdated}
                          size="sm"
                        />
                      </div>
                      <p className="text-sm text-dashboard-gray-600 font-normal">
                        {card.context}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className="h-5 w-5 text-dashboard-gray-400 group-hover:text-dashboard-gray-600 transition-colors" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-dashboard-gray-600 text-sm leading-relaxed mb-4">
                  {card.description}
                </p>

                {/* Configuration Progress */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-dashboard-gray-600">
                      Configuration
                    </span>
                    <span className="text-dashboard-gray-900 font-medium">
                      {card.completedSteps}/{card.totalSteps}
                    </span>
                  </div>
                  <Progress
                    value={(card.completedSteps / card.totalSteps) * 100}
                    className="h-2"
                  />
                  <p className="text-xs text-dashboard-gray-500">
                    Last updated: {card.lastUpdated}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Actions with Contextual Action Bar */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Quick Actions</span>
            <ContextualActionBar
              context="settings"
              actions={[
                ...getOrganizationActions(selectedOrgAccount?.orgId),
                ...getAccountActions(selectedOrgAccount?.accountId),
              ]}
              dropdownLabel="More Actions"
              onActionClick={(action) => {
                console.log("Quick action clicked:", action);
              }}
            />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => navigate("/organization-selection")}
              className="flex items-center gap-2"
            >
              <Building2 className="h-4 w-4" />
              Switch Organization
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/create-organization")}
              className="flex items-center gap-2"
            >
              <Building2 className="h-4 w-4" />
              Create Organization
            </Button>
          </div>
        </CardContent>
      </Card>
    </SettingsLayout>
  );
};

export default Settings;
