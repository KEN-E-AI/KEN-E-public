import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import OrganizationSelection from "@/pages/OrganizationSelection";

// Outside <ProtectedRoute> to avoid the circular redirect (!hasSelectedWorkspace → /select-organization → !hasSelectedWorkspace).
const SelectOrganizationPage = () => {
  const navigate = useNavigate();
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
    return <Navigate to="/auth/signin" replace />;
  }

  if (hasSelectedWorkspace) {
    return <Navigate to="/" replace />;
  }

  return <OrganizationSelection onComplete={() => navigate("/")} />;
};

export default SelectOrganizationPage;
