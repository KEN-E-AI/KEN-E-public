import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import ChatSidebar from "@/components/dashboard/ChatSidebar";

interface LayoutProps {
  children: React.ReactNode;
  pageTitle?: string;
  selectedTab?: string;
  selectedChannel?: string;
  selectedTactic?: string;
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
  hideChatSidebar?: boolean;
}

const Layout = ({
  children,
  pageTitle = "Measurement Strategy",
  selectedTab = "Awareness",
  selectedChannel = "Overview",
  selectedTactic = "",
  dateRange = {
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  },
  setDateRange = () => {},
  comparisonDateRange,
  setComparisonDateRange = () => {},
  hideChatSidebar = false,
}: LayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { selectedOrgAccount, setSelectedOrgAccount } = useAuth();

  return (
    <div className="min-h-screen bg-dashboard-gray-50">
      {/* Chat Sidebar - All screen sizes */}
      {!hideChatSidebar && (
        <ChatSidebar
          selectedTab={selectedTab}
          selectedChannel={selectedChannel}
          selectedTactic={selectedTactic}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      )}

      {/* Main Content */}
      <div
        className={`transition-all duration-300 ${
          hideChatSidebar
            ? "pl-4"
            : sidebarCollapsed
              ? "pl-16"
              : "pl-4 md:pl-80"
        }`}
      >
        <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6 h-screen">
          {/* Header */}
          <GlobalHeader
            pageTitle={pageTitle}
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

export default Layout;
