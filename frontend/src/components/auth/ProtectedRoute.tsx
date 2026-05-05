import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

type ProtectedRouteProps = {
  children: ReactNode;
};

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const location = useLocation();
  const { isAuthenticated, isAuthLoading, hasSelectedWorkspace } = useAuth();

  if (isAuthLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 border-4 border-brand-medium-blue border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--color-text-tertiary)]">Loading...</span>
        </div>
      </div>
    );
  }

  // If not authenticated, redirect to /sign-in carrying the original path for
  // post-auth return navigation (AuthenticationPage already reads location.state?.from)
  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace state={{ from: location }} />;
  }

  if (!hasSelectedWorkspace) {
    return <Navigate to="/select-organization" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
