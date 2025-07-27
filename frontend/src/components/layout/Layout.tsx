import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import ChatSidebar from "@/components/dashboard/ChatSidebar";
import { IconNavigation } from "@/components/layout/IconNavigation";
import { ContextSidebar } from "@/components/layout/ContextSidebar";

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
  hideContextSidebar?: boolean;
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
  hideContextSidebar = false,
}: LayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
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
        />
      )}

      {/* Main Content */}
      <div
        className={`transition-all duration-300 p-4 sm:p-6 space-y-6 min-h-screen ${
          hideContextSidebar
            ? "pl-[calc(3.5rem+1rem)] sm:pl-[calc(3.5rem+1.5rem)]" // Only IconNavigation width
            : contextSidebarCollapsed
              ? "pl-[calc(7.5rem+1rem)] sm:pl-[calc(7.5rem+1.5rem)]"
              : "pl-[calc(23.5rem+1rem)] sm:pl-[calc(23.5rem+1.5rem)]"
        } ${
          !hideChatSidebar
            ? sidebarCollapsed
              ? "pr-[calc(4rem+1rem)] sm:pr-[calc(4rem+1.5rem)]"
              : "pr-[calc(20rem+1rem)] sm:pr-[calc(20rem+1.5rem)]"
            : "pr-4 sm:pr-6"
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

      {/* Chat Sidebar - Fixed right sidebar */}
      {!hideChatSidebar && (
        <ChatSidebar
          selectedTab={selectedTab}
          selectedChannel={selectedChannel}
          selectedTactic={selectedTactic}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      )}
    </div>
  );
};

export default Layout;
