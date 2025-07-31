import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import SettingsLayout from "@/components/layout/SettingsLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Globe,
  Activity,
  Users,
  BarChart3,
  CreditCard,
  ArrowRight,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";

const AdminSettings = () => {
  const navigate = useNavigate();
  const { isSuperAdmin } = useAuth();

  // Redirect if not super admin
  if (!isSuperAdmin) {
    navigate("/settings");
    return null;
  }

  const adminSections = [
    {
      id: "industry-keywords",
      title: "Industry Keywords",
      description: "Configure default keywords for each industry",
      icon: Globe,
      route: "/settings/admin/industry-keywords",
      implemented: true,
    },
    {
      id: "initial-activities",
      title: "Initial Activities",
      description: "Manage default activities for new accounts",
      icon: Activity,
      implemented: false,
    },
    {
      id: "user-management",
      title: "User Management",
      description: "View and manage all platform users",
      icon: Users,
      implemented: false,
    },
    {
      id: "initial-metrics",
      title: "Initial Metrics",
      description: "Configure default metrics for new accounts",
      icon: BarChart3,
      implemented: false,
    },
    {
      id: "subscription-plans",
      title: "Subscription Plans",
      description: "Manage pricing and subscription tiers",
      icon: CreditCard,
      implemented: false,
    },
  ];

  return (
    <SettingsLayout
      pageTitle="Admin Settings"
      currentPage="admin"
      showBackButton={true}
      showEntitySelector={false}
      showContextSidebar={false}
    >
      {/* Admin Sections Grid */}
      <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-2 mb-8">
        {adminSections.map((section) => {
          const IconComponent = section.icon;
          return (
            <Card
              key={section.id}
              className={cn(
                "transition-shadow",
                section.implemented
                  ? "cursor-pointer hover:shadow-md"
                  : "opacity-60 cursor-not-allowed",
              )}
              onClick={() => {
                if (section.implemented && section.route) {
                  navigate(section.route);
                }
              }}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-brand-light-blue/20 rounded-lg flex items-center justify-center">
                      <IconComponent className="h-5 w-5 text-brand-medium-blue" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-dashboard-gray-900">
                        {section.title}
                      </h3>
                      <p className="text-sm text-dashboard-gray-600">
                        {section.description}
                      </p>
                    </div>
                  </div>
                  {section.implemented && (
                    <ArrowRight className="h-5 w-5 text-dashboard-gray-400" />
                  )}
                </div>
              </CardHeader>
            </Card>
          );
        })}
      </div>

      {/* Coming Soon Notice */}
      <Card className="mt-8 border-dashed">
        <CardContent className="text-center py-8">
          <Shield className="h-12 w-12 mx-auto text-dashboard-gray-400 mb-3" />
          <p className="text-dashboard-gray-600">
            Additional admin features coming soon
          </p>
        </CardContent>
      </Card>
    </SettingsLayout>
  );
};

export default AdminSettings;
