import { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Authentication from "@/pages/Authentication";
import OrganizationSelection from "@/pages/OrganizationSelection";

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const location = useLocation();
  const {
    isAuthenticated,
    hasSelectedWorkspace,
    login,
    completeWorkspaceSelection,
  } = useAuth();

  // If not authenticated, show authentication page
  if (!isAuthenticated) {
    return (
      <Authentication
        onAuthenticated={() => {}}
      />
    );
  }

  // If authenticated but hasn't selected workspace, show organization selection
  if (!hasSelectedWorkspace) {
    return (
      <OrganizationSelection
        onComplete={() => {
          completeWorkspaceSelection();
        }}
      />
    );
  }

  // If authenticated and has selected workspace, show the protected content
  return <>{children}</>;
};

export default ProtectedRoute;
