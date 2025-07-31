import type React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Layout from "./Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EntitySelector } from "@/components/ui/entity-selector";
import { ContextBreadcrumb } from "@/components/ui/context-breadcrumb";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Building2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

interface SettingsLayoutProps {
  children: React.ReactNode;
  pageTitle: string; // This title is rendered as h1 by GlobalHeader - do not add h1 in page content
  currentPage: "settings" | "organization" | "account" | "user";
  showBackButton?: boolean;
  showEntitySelector?: boolean;
  showContextSidebar?: boolean;
  className?: string;
}

/**
 * SettingsLayout - Layout wrapper for all settings pages
 *
 * IMPORTANT: The pageTitle prop is rendered as an h1 element by GlobalHeader.
 * Do NOT add another h1 element in your page content to avoid duplicate h1 tags.
 * Use h2 or other heading levels for section titles within your page.
 */
export const SettingsLayout: React.FC<SettingsLayoutProps> = ({
  children,
  pageTitle,
  currentPage,
  showBackButton = true,
  showEntitySelector = true,
  showContextSidebar = true,
  className,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedOrgAccount } = useAuth();

  const currentOrgName =
    selectedOrgAccount?.metadata?.organization_name || "Organization";
  const currentAccountName =
    selectedOrgAccount?.metadata?.account_name || "Account";

  const handleBackToSettings = () => {
    navigate("/settings");
  };

  return (
    <Layout pageTitle={pageTitle} hideContextSidebar={!showContextSidebar}>
      <div className={cn("space-y-6", className)}>
        {/* Back Button - Only show for account-specific settings */}
        {showBackButton && currentPage === "account" && (
          <div className="pt-2">
            <Button
              variant="ghost"
              onClick={handleBackToSettings}
              className="text-dashboard-gray-600 hover:text-dashboard-gray-900 p-0 h-auto font-normal"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Settings
            </Button>
          </div>
        )}

        {/* Breadcrumb Navigation */}
        {currentPage !== "settings" &&
          currentPage !== "organization" &&
          currentPage !== "user" &&
          currentPage !== "admin" && (
            <ContextBreadcrumb currentPage={currentPage} />
          )}

        {/* Organization Selector - Only show for organization settings, but not on create-organization page */}
        {showEntitySelector &&
          currentPage === "organization" &&
          location.pathname !== "/create-organization" && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="text-lg">Organization Selection</span>
                  <EntitySelector
                    className="min-w-[300px]"
                    organizationOnly={true}
                  />
                </CardTitle>
              </CardHeader>
            </Card>
          )}

        {/* Current Context with Entity Selector - Show for account-specific settings */}
        {showEntitySelector &&
          selectedOrgAccount &&
          currentPage === "account" && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="text-lg">Current Context</span>
                  <EntitySelector className="min-w-[300px]" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 text-dashboard-gray-600">
                  <Building2 className="h-4 w-4" />
                  <span className="font-medium">Active Context:</span>
                  <span>{currentOrgName}</span>
                  {selectedOrgAccount.metadata?.account_name && (
                    <>
                      <span className="text-dashboard-gray-400">→</span>
                      <span>{currentAccountName}</span>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

        {/* Settings Content */}
        <div className="space-y-6">{children}</div>
      </div>
    </Layout>
  );
};

export default SettingsLayout;
