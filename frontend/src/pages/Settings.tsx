import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Building2, User, ArrowRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const Settings = () => {
  const navigate = useNavigate();
  const { user, setCurrentOrganization, orgMetadata } = useAuth();

  // Get organizations where user can modify settings (admin or owner role)
  const editableOrganizations = useMemo(() => {
    if (!user?.permissions?.organizations) return [];

    return Object.entries(user.permissions.organizations)
      .filter(([orgId, role]) => role === "admin" || role === "owner")
      .map(([orgId, role]) => ({
        id: orgId,
        name: orgMetadata[orgId]?.organization_name || orgId,
        role,
      }));
  }, [user?.permissions?.organizations, orgMetadata]);

  const handleOrganizationClick = (orgId: string) => {
    setCurrentOrganization(orgId);
    navigate("/settings/organization");
  };

  const handleUserSettingsClick = () => {
    navigate("/settings/user");
  };

  return (
    <SettingsLayout
      pageTitle="Settings"
      currentPage="settings"
      showBackButton={false}
      showEntitySelector={false}
      showContextSidebar={false}
    >
      {/* Header Description */}
      <div className="mb-8">
        <p className="text-dashboard-gray-600">
          Manage your personal and organization settings
        </p>
      </div>

      {/* User Settings Section */}
      <div className="mb-8">
        <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-2">
          <Card
            className="cursor-pointer hover:shadow-md transition-shadow group"
            onClick={handleUserSettingsClick}
          >
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-brand-light-blue/20 rounded-lg flex items-center justify-center">
                    <User className="h-5 w-5 text-brand-medium-blue" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-dashboard-gray-900">
                      User Settings
                    </h3>
                    <p className="text-sm text-dashboard-gray-600">
                      Manage your profile, notifications, and preferences
                    </p>
                  </div>
                </div>
                <ArrowRight className="h-5 w-5 text-dashboard-gray-400 group-hover:text-dashboard-gray-600 transition-colors" />
              </div>
            </CardHeader>
          </Card>
        </div>
      </div>

      {/* Organization Settings Section */}
      <div>
        <h2 className="text-xl font-semibold text-dashboard-gray-900 mb-2">
          Organizations
        </h2>
        <p className="text-dashboard-gray-600 mb-4">
          Select an organization to manage its settings
        </p>

        {editableOrganizations.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-2">
            {editableOrganizations.map((org) => (
              <Card
                key={org.id}
                className="cursor-pointer hover:shadow-md transition-shadow group"
                onClick={() => handleOrganizationClick(org.id)}
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-brand-light-blue/20 rounded-lg flex items-center justify-center">
                        <Building2 className="h-5 w-5 text-brand-medium-blue" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-dashboard-gray-900">
                          {org.name}
                        </h3>
                        <p className="text-sm text-dashboard-gray-600">
                          {org.role === "owner" ? "Owner" : "Administrator"}
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="h-5 w-5 text-dashboard-gray-400 group-hover:text-dashboard-gray-600 transition-colors" />
                  </div>
                </CardHeader>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="border-dashed">
            <CardContent className="text-center py-8">
              <Building2 className="h-12 w-12 mx-auto text-dashboard-gray-400 mb-3" />
              <p className="text-dashboard-gray-600">
                You don't have permission to manage any organizations
              </p>
            </CardContent>
          </Card>
        )}
      </div>

    </SettingsLayout>
  );
};

export default Settings;
