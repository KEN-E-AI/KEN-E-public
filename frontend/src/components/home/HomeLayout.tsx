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
        className={`transition-all duration-300 p-4 sm:p-6 h-screen flex flex-col ${
          sidebarCollapsed
            ? "pl-[calc(7rem+1rem)] sm:pl-[calc(7rem+1.5rem)]"
            : "pl-[calc(3.5rem+360px+1rem)] sm:pl-[calc(3.5rem+360px+1.5rem)]"
        } pr-4 sm:pr-6`}
      >
        {/* Header */}
        <div className="flex-shrink-0">
          <GlobalHeader
            pageTitle="Home"
            dateRange={dateRange}
            setDateRange={setDateRange}
            comparisonDateRange={comparisonDateRange}
            setComparisonDateRange={setComparisonDateRange}
            selectedOrgAccount={selectedOrgAccount}
            setSelectedOrgAccount={setSelectedOrgAccount}
          />
        </div>

        {/* Page Content */}
        <div className="flex-1 min-h-0">{children}</div>
      </div>
    </div>
  );
};

export default HomeLayout;
