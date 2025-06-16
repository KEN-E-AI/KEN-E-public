import { useState } from "react";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import ChatSidebar from "@/components/dashboard/ChatSidebar";

interface LayoutProps {
  children: React.ReactNode;
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
  pageType?: "dashboard" | "knowledge-base";
  selectedKnowledgePage?: string;
  onKnowledgePageChange?: (page: string) => void;
}

const Layout = ({
  children,
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
  pageType = "dashboard",
  selectedKnowledgePage = "metrics",
  onKnowledgePageChange = () => {},
}: LayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-dashboard-gray-50">
      {/* Chat Sidebar - All screen sizes */}
      <ChatSidebar
        selectedTab={selectedTab}
        selectedChannel={selectedChannel}
        selectedTactic={selectedTactic}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        pageType={pageType}
        selectedKnowledgePage={selectedKnowledgePage}
        onKnowledgePageChange={onKnowledgePageChange}
      />

      {/* Main Content */}
      <div
        className={`transition-all duration-300 ${sidebarCollapsed ? "pl-16" : "pl-4 md:pl-80"}`}
      >
        <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
          {/* Header */}
          <GlobalHeader
            dateRange={dateRange}
            setDateRange={setDateRange}
            comparisonDateRange={comparisonDateRange}
            setComparisonDateRange={setComparisonDateRange}
          />

          {/* Page Content */}
          {children}
        </div>
      </div>
    </div>
  );
};

export default Layout;
