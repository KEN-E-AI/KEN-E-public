import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import OrganizationSelection from "@/pages/OrganizationSelection";

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const location = useLocation();
  const {
    isAuthenticated,
    isAuthLoading,
    hasSelectedWorkspace,
    completeWorkspaceSelection,
  } = useAuth();

  // Show loading state while checking authentication
  if (isAuthLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 border-4 border-brand-medium-blue border-t-transparent rounded-full animate-spin" />
          <span className="text-gray-600">Loading...</span>
        </div>
      </div>
    );
  }

  // If not authenticated, redirect to /sign-in carrying the original path for
  // post-auth return navigation (AuthenticationPage already reads location.state?.from)
  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace state={{ from: location }} />;
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
