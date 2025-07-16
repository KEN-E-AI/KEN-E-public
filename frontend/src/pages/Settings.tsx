import { useNavigate } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Building2, User, Users, ArrowRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const Settings = () => {
  const navigate = useNavigate();
  const { user, selectedOrgAccount, orgMetadata } = useAuth();

  const currentOrgName =
    selectedOrgAccount?.metadata?.organization_name || "Organization";
  const currentAccountName =
    selectedOrgAccount?.metadata?.account_name || "Account";

  const settingsCards = [
    {
      id: "organization",
      title: "Organization Settings",
      description:
        "Manage organization profile, subscription, billing, and team settings",
      icon: Building2,
      route: "/organization-settings",
      context: currentOrgName,
      enabled: true,
    },
    {
      id: "account",
      title: "Account Management",
      description: "Create and manage accounts within your organization",
      icon: Users,
      route: "/organization-settings", // For now, accounts are managed within org settings
      context: "Manage accounts",
      enabled: true,
    },
    {
      id: "user",
      title: "User Settings",
      description:
        "Manage your personal profile, notifications, and preferences",
      icon: User,
      route: "/user-settings",
      context:
        `${user?.firstName} ${user?.lastName}`.trim() || "Personal Settings",
      enabled: true,
    },
  ];

  const handleCardClick = (route: string) => {
    navigate(route);
  };

  return (
    <Layout pageTitle="Settings">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-dashboard-gray-900">
            Settings
          </h1>
          <p className="text-dashboard-gray-600 mt-2">
            Manage your organization, accounts, and personal settings
          </p>
        </div>

        {/* Current Context */}
        {selectedOrgAccount && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-2 text-blue-800">
              <Building2 className="h-4 w-4" />
              <span className="font-medium">Current Context:</span>
              <span>{currentOrgName}</span>
              {selectedOrgAccount.metadata?.account_name && (
                <>
                  <span className="text-blue-600">→</span>
                  <span>{currentAccountName}</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Settings Cards */}
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
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Icon className="h-5 w-5 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-dashboard-gray-900">
                          {card.title}
                        </h3>
                        <p className="text-sm text-dashboard-gray-600 font-normal">
                          {card.context}
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="h-5 w-5 text-dashboard-gray-400 group-hover:text-dashboard-gray-600 transition-colors" />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-dashboard-gray-600 text-sm leading-relaxed">
                    {card.description}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
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
      </div>
    </Layout>
  );
};

export default Settings;
