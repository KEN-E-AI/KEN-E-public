import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import { IconNavigation } from "@/components/layout/IconNavigation";
import { ContextSidebar } from "@/components/layout/ContextSidebar";

interface LayoutProps {
  children: React.ReactNode;
  pageTitle?: string;
  selectedTab?: string;
  dateRange?: {
    from: Date;
    to: Date;
  };
  setDateRange?: (range: { from: Date; to: Date }) => void;
  comparisonDateRange?: {
    from: Date;
    to: Date;
  };
  setComparisonDateRange?: (
    range: { from: Date; to: Date } | undefined,
  ) => void;
  hideContextSidebar?: boolean;
}

const Layout = ({
  children,
  pageTitle = "Marketing Strategies",
  selectedTab = "Awareness",
  dateRange = {
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  },
  setDateRange = () => {},
  comparisonDateRange,
  setComparisonDateRange = () => {},
  hideContextSidebar = false,
}: LayoutProps) => {
  const [contextSidebarCollapsed, setContextSidebarCollapsed] = useState(() => {
    // Initialize from localStorage
    const saved = localStorage.getItem("contextSidebarCollapsed");
    return saved === "true";
  });
  const { selectedOrgAccount, setSelectedOrgAccount } = useAuth();

  return (
    <div className="min-h-screen bg-dashboard-gray-50">
      {/* Icon Navigation - Fixed left sidebar */}
      <IconNavigation />

      {/* Context Sidebar - Fixed left sidebar (after IconNavigation) */}
      {!hideContextSidebar && (
        <ContextSidebar
          isCollapsed={contextSidebarCollapsed}
          onToggleCollapse={() => {
            const newState = !contextSidebarCollapsed;
            setContextSidebarCollapsed(newState);
            localStorage.setItem(
              "contextSidebarCollapsed",
              newState.toString(),
            );
          }}
          selectedTab={selectedTab}
        />
      )}

      {/* Main Content */}
      <div
        className={`transition-all duration-300 p-4 sm:p-6 space-y-6 min-h-screen pr-4 sm:pr-6 ${
          hideContextSidebar
            ? "pl-[calc(3.5rem+1rem)] sm:pl-[calc(3.5rem+1.5rem)]"
            : contextSidebarCollapsed
              ? "pl-[calc(7rem+1rem)] sm:pl-[calc(7rem+1.5rem)]"
              : "pl-[calc(3.5rem+360px+1rem)] sm:pl-[calc(3.5rem+360px+1.5rem)]"
        }`}
      >
        {/* Header */}
        <GlobalHeader
          pageTitle={pageTitle}
          dateRange={dateRange}
          setDateRange={setDateRange}
          comparisonDateRange={comparisonDateRange}
          setComparisonDateRange={setComparisonDateRange}
          selectedOrgAccount={selectedOrgAccount}
          setSelectedOrgAccount={setSelectedOrgAccount}
        />

        {/* Page Content */}
        {children}
      </div>
    </div>
  );
};

export default Layout;
