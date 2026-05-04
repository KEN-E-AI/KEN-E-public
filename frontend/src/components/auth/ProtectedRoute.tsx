import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Authentication from "@/pages/Authentication";

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const location = useLocation();
  const { isAuthenticated, isAuthLoading, hasSelectedWorkspace } = useAuth();

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

  // If not authenticated, show authentication page
  if (!isAuthenticated) {
    return <Authentication onAuthenticated={() => {}} />;
  }

  // If authenticated but hasn't selected workspace, redirect to the canonical
  // workspace-selection page. The page itself calls completeWorkspaceSelection().
  if (!hasSelectedWorkspace) {
    return <Navigate to="/select-organization" replace />;
  }

  // If authenticated and has selected workspace, show the protected content
  return <>{children}</>;
};

export default ProtectedRoute;
