import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { BackgroundEffects } from "@/components/theme/BackgroundEffects";
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
import { AppErrorBoundary } from "@/components/layout/AppErrorBoundary";
import "./App.css";

import { LayoutC } from "@/components/layout/LayoutC";
import Index from "./pages/Index";
import Performance from "./pages/Performance";
import Recommendations from "./pages/Recommendations";
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
import KnowledgeStrategy from "./pages/KnowledgeStrategy";
import Insights from "./pages/Insights";
import AccountSettings from "./pages/AccountSettings";
import UserSettings from "./pages/UserSettings";
import OrganizationSelection from "./pages/OrganizationSelection";
import AcceptInvitation from "./pages/AcceptInvitation";
import NotFoundPage from "./pages/NotFoundPage";
import EmailActionHandler from "./components/auth/EmailActionHandler";
import Authentication from "./pages/Authentication";
// Import test utilities in development
if (import.meta.env.DEV) {
  import("./utils/testNotification");
}

// Dev-only lazy component — dynamic import is tree-shaken from the production bundle
// because import.meta.env.DEV evaluates to false at build time
const LazyLayoutSettingsHarness = import.meta.env.DEV
  ? lazy(() =>
      import("./pages/__dev__/LayoutSettingsHarness").then((m) => ({
        default: m.LayoutSettingsHarness,
      })),
    )
  : undefined;

const LazyDesignSystemPreview = import.meta.env.DEV
  ? lazy(() =>
      import("./pages/__dev__/DesignSystemPreview").then((m) => ({
        default: m.DesignSystemPreview,
      })),
    )
  : undefined;

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
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ThemeProvider>
        <AuthProvider>
          <ChatProvider>
            <AccountOperationsProvider>
              <BrowserRouter>
                <AppErrorBoundary>
                  <BackgroundEffects />
                  <Routes>
                    {/* Unprotected routes */}
                    <Route
                      path="/auth/signin"
                      element={<AuthenticationPage />}
                    />
                    <Route
                      path="/auth/signup"
                      element={<AuthenticationPage />}
                    />
                    <Route
                      path="/create-organization"
                      element={<AccountSettings />}
                    />
                    <Route
                      path="/invite/:token"
                      element={<AcceptInvitation />}
                    />
                    <Route
                      path="/auth/action"
                      element={<EmailActionHandler />}
                    />
                    {/* Backward compatibility redirects */}
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
                    {/* Protected routes — nested under LayoutC. ProtectedRoute
                        is hoisted to the parent so child routes don't repeat it. */}
                    <Route
                      element={
                        <ProtectedRoute>
                          <LayoutC />
                        </ProtectedRoute>
                      }
                    >
                      <Route
                        path="/"
                        element={<Navigate to="/chat" replace />}
                      />
                      <Route
                        path="/settings"
                        element={
                          <Navigate to="/settings/organization" replace />
                        }
                      />
                      <Route path="/performance" element={<Performance />} />
                      <Route
                        path="/recommendations"
                        element={<Recommendations />}
                      />
                      <Route path="/campaigns" element={<Campaigns />} />
                      <Route path="/reports" element={<Reports />} />
                      <Route path="/simulations" element={<Simulations />} />
                      <Route path="/knowledge" element={<Knowledge />} />
                      <Route
                        path="/knowledge/strategy"
                        element={<KnowledgeStrategy />}
                      />
                      <Route
                        path="/knowledge/products"
                        element={<Products />}
                      />
                      <Route
                        path="/knowledge/customers"
                        element={<KnowledgeCustomers />}
                      />
                      <Route
                        path="/knowledge/metrics"
                        element={<KnowledgeMetrics />}
                      />
                      <Route
                        path="/knowledge/activities"
                        element={<KnowledgeActivities />}
                      />
                      <Route
                        path="/knowledge/insights"
                        element={<Insights />}
                      />
                      <Route
                        path="/knowledge/account"
                        element={<KnowledgeAccount />}
                      />
                      <Route
                        path="/knowledge/competitors"
                        element={<KnowledgeCompetitors />}
                      />
                      <Route
                        path="/knowledge/brand"
                        element={<KnowledgeBrand />}
                      />
                      <Route path="/measurement-plan" element={<Index />} />
                      <Route
                        path="/analysis-report/:reportId"
                        element={<AnalysisReport />}
                      />
                      <Route
                        path="/settings/organization"
                        element={<AccountSettings />}
                      />
                      <Route
                        path="/settings/account/:accountId"
                        element={<AccountSettings />}
                      />
                      <Route path="/settings/user" element={<UserSettings />} />
                      <Route
                        path="/organization-selection"
                        element={<OrganizationSelectionPage />}
                      />
                      {/* Catch-all inside LayoutC so authenticated users see the 404 with chrome */}
                      <Route path="*" element={<NotFoundPage />} />
                    </Route>
                    {/* Dev-only harness routes — tree-shaken from production bundle */}
                    {import.meta.env.DEV && LazyLayoutSettingsHarness && (
                      <Route
                        path="/__dev__/layout-settings"
                        element={
                          <Suspense fallback={null}>
                            <LazyLayoutSettingsHarness />
                          </Suspense>
                        }
                      />
                    )}
                    {import.meta.env.DEV && LazyDesignSystemPreview && (
                      <Route
                        path="/__dev__/design-system"
                        element={
                          <Suspense fallback={null}>
                            <LazyDesignSystemPreview />
                          </Suspense>
                        }
                      />
                    )}
                  </Routes>
                  {/* Legacy Radix Toaster (88 callsites use useToast()) and sonner Toaster coexist */}
                  <Toaster />
                  <SonnerToaster />
                </AppErrorBoundary>
              </BrowserRouter>
            </AccountOperationsProvider>
          </ChatProvider>
        </AuthProvider>
      </ThemeProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
