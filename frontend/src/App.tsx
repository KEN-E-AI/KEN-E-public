import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import "./App.css";

import Index from "./pages/Index";
import Home from "./pages/Home";
import Performance from "./pages/Performance";
import BigBets from "./pages/BigBets";
import Exploration from "./pages/Exploration";
import AnalysisReport from "./pages/AnalysisReport";
import Knowledge from "./pages/Knowledge";
import KnowledgeMetrics from "./pages/KnowledgeMetrics";
import KnowledgeActivities from "./pages/KnowledgeActivities";
import AccountSettings from "./pages/AccountSettings";
import UserSettings from "./pages/UserSettings";
import OrganizationSelection from "./pages/OrganizationSelection";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

// Wrapper component to handle navigation after organization selection
const OrganizationSelectionPage = () => {
  const navigate = useNavigate();

  return <OrganizationSelection onComplete={() => navigate("/")} />;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Unprotected route for organization creation */}
            <Route path="/create-organization" element={<AccountSettings />} />
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
              path="/big-bets"
              element={
                <ProtectedRoute>
                  <BigBets />
                </ProtectedRoute>
              }
            />
            <Route
              path="/exploration"
              element={
                <ProtectedRoute>
                  <Exploration />
                </ProtectedRoute>
              }
            />
            <Route
              path="/measurement-strategy"
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
              path="/account-settings"
              element={
                <ProtectedRoute>
                  <AccountSettings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/user-settings"
              element={
                <ProtectedRoute>
                  <UserSettings />
                </ProtectedRoute>
              }
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
        </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
