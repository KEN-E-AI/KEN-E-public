import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import HomeNotificationsSidebar from "./HomeNotificationsSidebar";

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { selectedOrgAccount, setSelectedOrgAccount } = useAuth();

  return (
    <div className="min-h-screen bg-dashboard-gray-50">
      {/* Notifications Sidebar */}
      <HomeNotificationsSidebar
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content */}
      <div
        className={`transition-all duration-300 ${
          sidebarCollapsed ? "pl-16" : "pl-4 md:pl-80"
        }`}
      >
        <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
          {/* Header */}
          <GlobalHeader
            pageTitle="Home"
            dateRange={dateRange}
            setDateRange={setDateRange}
            comparisonDateRange={comparisonDateRange}
            setComparisonDateRange={setComparisonDateRange}
            selectedOrgAccount={
              selectedOrgAccount || "healthway-intellipure-b2c"
            }
            setSelectedOrgAccount={setSelectedOrgAccount}
          />

          {/* Page Content */}
          {children}
        </div>
      </div>
    </div>
  );
};

export default HomeLayout;
