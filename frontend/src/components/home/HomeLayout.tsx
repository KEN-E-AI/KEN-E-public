import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import { IconNavigation } from "@/components/layout/IconNavigation";
import { ContextSidebar } from "@/components/layout/ContextSidebar";

interface HomeLayoutProps {
  children: React.ReactNode;
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
}

const HomeLayout = ({
  children,
  dateRange = {
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  },
  setDateRange = () => {},
  comparisonDateRange,
  setComparisonDateRange = () => {},
}: HomeLayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
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
      <ContextSidebar
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => {
          const newState = !sidebarCollapsed;
          setSidebarCollapsed(newState);
          localStorage.setItem("contextSidebarCollapsed", newState.toString());
        }}
      />

      {/* Main Content */}
      <div
        className={`transition-all duration-300 p-4 sm:p-6 space-y-6 min-h-screen ${
          sidebarCollapsed
            ? "pl-[calc(7.5rem+1rem)] sm:pl-[calc(7.5rem+1.5rem)]"
            : "pl-[calc(23.5rem+1rem)] sm:pl-[calc(23.5rem+1.5rem)]"
        } pr-4 sm:pr-6`}
      >
        {/* Header */}
        <GlobalHeader
          pageTitle="Home"
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

export default HomeLayout;
