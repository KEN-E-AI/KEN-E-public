import { useAuth } from "@/contexts/AuthContext";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Building2, User } from "lucide-react";

interface ContextBreadcrumbProps {
  currentPage: "organization" | "user" | "account";
  showUserContext?: boolean;
}

export const ContextBreadcrumb = ({
  currentPage,
  showUserContext = false,
}: ContextBreadcrumbProps) => {
  const { user, selectedOrgAccount } = useAuth();

  const currentOrgName =
    selectedOrgAccount?.metadata?.organization_name || "Organization";
  const currentAccountName =
    selectedOrgAccount?.metadata?.account_name || "Account";
  const currentUserName =
    user?.firstName && user?.lastName
      ? `${user.firstName} ${user.lastName}`
      : user?.email || "User";

  const getPageTitle = () => {
    switch (currentPage) {
      case "organization":
        return "Organization Settings";
      case "user":
        return "User Settings";
      case "account":
        return "Account Settings";
      default:
        return "Settings";
    }
  };

  const getPageIcon = () => {
    switch (currentPage) {
      case "organization":
        return <Building2 className="h-3 w-3 mr-1" />;
      case "user":
        return <User className="h-3 w-3 mr-1" />;
      case "account":
        return <Building2 className="h-3 w-3 mr-1" />;
      default:
        return null;
    }
  };

  return (
    <Breadcrumb className="mb-6">
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink href="/settings" className="flex items-center">
            Settings
          </BreadcrumbLink>
        </BreadcrumbItem>

        {selectedOrgAccount && (
          <>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="flex items-center">
                <Building2 className="h-3 w-3 mr-1" />
                {currentOrgName}
              </BreadcrumbPage>
            </BreadcrumbItem>

            {selectedOrgAccount.metadata?.account_name && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage className="flex items-center">
                    <Building2 className="h-3 w-3 mr-1" />
                    {currentAccountName}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}
          </>
        )}

        {showUserContext && user && (
          <>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="flex items-center">
                <User className="h-3 w-3 mr-1" />
                {currentUserName}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </>
        )}

        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbPage className="flex items-center">
            {getPageIcon()}
            {getPageTitle()}
          </BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
};
