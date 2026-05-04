import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Authentication from "@/pages/Authentication";

type ProtectedRouteProps = {
  children: ReactNode;
};

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, isAuthLoading, hasSelectedWorkspace } = useAuth();

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

  if (!isAuthenticated) {
    return <Authentication onAuthenticated={() => {}} />;
  }

  if (!hasSelectedWorkspace) {
    return <Navigate to="/select-organization" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
