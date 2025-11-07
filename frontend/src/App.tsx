import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
  useSearchParams,
} from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ChatProvider } from "@/contexts/ChatContext";
import { AccountOperationsProvider } from "@/contexts/AccountOperationsContext";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import "./App.css";

import Index from "./pages/Index";
import Home from "./pages/Home";
import Performance from "./pages/Performance";
import Products from "./pages/Products";
import Campaigns from "./pages/Campaigns";
import Reports from "./pages/Reports";
import Simulations from "./pages/Simulations";
import AnalysisReport from "./pages/AnalysisReport";
import Knowledge from "./pages/Knowledge";
import KnowledgeMetrics from "./pages/KnowledgeMetrics";
import KnowledgeActivities from "./pages/KnowledgeActivities";
import KnowledgeAccount from "./pages/KnowledgeAccount";
import KnowledgeCustomers from "./pages/KnowledgeCustomers";
import KnowledgeCompetitors from "./pages/KnowledgeCompetitors";
import KnowledgeBrand from "./pages/KnowledgeBrand";
import Insights from "./pages/Insights";
import AccountSettings from "./pages/AccountSettings";
import UserSettings from "./pages/UserSettings";
import Settings from "./pages/Settings";
import AdminSettings from "./pages/AdminSettings";
import AdminIndustryKeywords from "./pages/AdminIndustryKeywords";
import AgentConfigManagement from "./pages/AgentConfigManagement";
import OrganizationSelection from "./pages/OrganizationSelection";
import AcceptInvitation from "./pages/AcceptInvitation";
import NotFound from "./pages/NotFound";
import EmailActionHandler from "./components/auth/EmailActionHandler";
import Authentication from "./pages/Authentication";

// Import test utilities in development
if (import.meta.env.DEV) {
  import("./utils/testNotification");
}

const queryClient = new QueryClient();

// Wrapper component to handle navigation after organization selection
const OrganizationSelectionPage = () => {
  const navigate = useNavigate();

  return <OrganizationSelection onComplete={() => navigate("/")} />;
};

// Wrapper component for Authentication with navigation
const AuthenticationPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const handleAuthenticated = () => {
    try {
      // Check if there's an invitation token
      const invitationToken = searchParams.get("invitation");
      if (invitationToken) {
        // Redirect to invitation acceptance page after authentication
        navigate(`/invite/${invitationToken}`);
      } else {
        // Check if there's a redirect location in state
        const from = location.state?.from || "/";
        navigate(from);
      }
    } catch (error) {
      console.error("[AuthenticationPage] Navigation error:", error);

      // Only fallback for specific navigation-related errors
      if (
        error instanceof TypeError ||
        (error instanceof Error && error.message.includes("navigate"))
      ) {
        console.warn(
          "[AuthenticationPage] Falling back to home page due to navigation error",
        );
        navigate("/");
      } else {
        // Re-throw unexpected errors for proper error handling
        throw error;
      }
    }
  };

  return <Authentication onAuthenticated={handleAuthenticated} />;
};

const App = () => (
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <AuthProvider>
          <ChatProvider>
            <AccountOperationsProvider>
              <BrowserRouter>
                <Routes>
                  {/* Unprotected routes */}
                  <Route path="/auth/signin" element={<AuthenticationPage />} />
                  <Route path="/auth/signup" element={<AuthenticationPage />} />
                  <Route
                    path="/create-organization"
                    element={<AccountSettings />}
                  />
                  <Route path="/invite/:token" element={<AcceptInvitation />} />
                  <Route path="/auth/action" element={<EmailActionHandler />} />
                  {/* Protected routes */}
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute>
                        <Home />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/performance"
                    element={
                      <ProtectedRoute>
                        <Performance />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/campaigns"
                    element={
                      <ProtectedRoute>
                        <Campaigns />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/reports"
                    element={
                      <ProtectedRoute>
                        <Reports />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/simulations"
                    element={
                      <ProtectedRoute>
                        <Simulations />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/strategy"
                    element={
                      <ProtectedRoute>
                        <Index />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/measurement-plan"
                    element={
                      <ProtectedRoute>
                        <Index />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/analysis-report/:reportId"
                    element={
                      <ProtectedRoute>
                        <AnalysisReport />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge"
                    element={
                      <ProtectedRoute>
                        <Knowledge />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/products"
                    element={
                      <ProtectedRoute>
                        <Products />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/metrics"
                    element={
                      <ProtectedRoute>
                        <KnowledgeMetrics />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/activities"
                    element={
                      <ProtectedRoute>
                        <KnowledgeActivities />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/insights"
                    element={
                      <ProtectedRoute>
                        <Insights />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/account"
                    element={
                      <ProtectedRoute>
                        <KnowledgeAccount />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/customers"
                    element={
                      <ProtectedRoute>
                        <KnowledgeCustomers />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/competitors"
                    element={
                      <ProtectedRoute>
                        <KnowledgeCompetitors />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/knowledge/brand"
                    element={
                      <ProtectedRoute>
                        <KnowledgeBrand />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <ProtectedRoute>
                        <Settings />
                      </ProtectedRoute>
                    }
                  />
                  {/* New organized settings routes */}
                  <Route
                    path="/settings/organization"
                    element={
                      <ProtectedRoute>
                        <AccountSettings />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings/account/:accountId"
                    element={
                      <ProtectedRoute>
                        <AccountSettings />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings/user"
                    element={
                      <ProtectedRoute>
                        <UserSettings />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings/admin"
                    element={
                      <ProtectedRoute>
                        <AdminSettings />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings/admin/industry-keywords"
                    element={
                      <ProtectedRoute>
                        <AdminIndustryKeywords />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings/admin/agent-configs"
                    element={
                      <ProtectedRoute>
                        <AgentConfigManagement />
                      </ProtectedRoute>
                    }
                  />
                  {/* Backward compatibility routes */}
                  <Route
                    path="/login"
                    element={<Navigate to="/auth/signin" replace />}
                  />
                  <Route
                    path="/signup"
                    element={<Navigate to="/auth/signup" replace />}
                  />
                  <Route
                    path="/organization-settings"
                    element={<Navigate to="/settings/organization" replace />}
                  />
                  <Route
                    path="/account-settings"
                    element={<Navigate to="/settings/organization" replace />}
                  />
                  <Route
                    path="/user-settings"
                    element={<Navigate to="/settings/user" replace />}
                  />
                  <Route
                    path="/organization-selection"
                    element={
                      <ProtectedRoute>
                        <OrganizationSelectionPage />
                      </ProtectedRoute>
                    }
                  />
                  {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                  <Route path="*" element={<NotFound />} />
                </Routes>
                <Toaster />
              </BrowserRouter>
            </AccountOperationsProvider>
          </ChatProvider>
        </AuthProvider>
      </TooltipProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
