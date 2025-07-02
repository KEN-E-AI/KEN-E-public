import { useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Bell } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { iconMap } from "@/lib/iconMap";

interface HomeNotificationsSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

const HomeNotificationsSidebar: React.FC<HomeNotificationsSidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
}) => {
  const { notifications } = useAuth();
  return (
    <div
      className={cn(
        "fixed top-0 left-0 h-full bg-white border-r border-dashboard-gray-200 z-30 transition-all duration-300",
        isCollapsed ? "w-16" : "w-80 md:w-80",
      )}
    >
      {/* Header with toggle button */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-dashboard-gray-200">
        {!isCollapsed && (
          <h2 className="text-lg font-semibold text-dashboard-gray-900">
            Notifications
          </h2>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className="h-8 w-8 p-0"
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <div className="h-[calc(100%-4rem)] overflow-y-auto pr-4 pl-0 py-4">
          {/* Notifications List */}
          <div className="rounded-r-lg overflow-hidden border border-[#E2E8F0]">
            {notifications.map((notification, index) => {
              const iconName = notification.data.icon;
              const IconComponent = iconMap[iconName] || Bell;
              return (
                <div
                  key={notification.id}
                  className={`flex items-center gap-3 p-3 hover:bg-dashboard-gray-50 cursor-pointer transition-colors ${
                    index < notifications.length - 1
                      ? "border-b border-[#E2E8F0]"
                      : ""
                  }`}
                >
                  {/* Icon */}
                  <div className="flex-shrink-0">
                    <IconComponent className="h-4 w-4 text-dashboard-gray-600" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-dashboard-gray-900 leading-relaxed text-left">
                      {notification.data.title}
                    </p>
                  </div>

                  {/* Indicator */}
                  {notification.data.hasIndicator && (
                    <div className="flex-shrink-0">
                      <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Collapsed state - show icons only */}
      {isCollapsed && (
        <div className="h-[calc(100%-4rem)] overflow-y-auto p-2">
          <div className="space-y-2">
            {notifications.slice(0, 6).map((notification) => {
              const iconName = notification.data.icon;
              const IconComponent = iconMap[iconName] || Bell;
              return (
                <div
                  key={notification.id}
                  className="relative flex items-center justify-center h-10 w-10 mx-auto rounded-lg hover:bg-dashboard-gray-50 cursor-pointer transition-colors"
                  title={notification.data.title}
                >
                  <IconComponent className="h-4 w-4 text-dashboard-gray-600" />
                  {notification.data.hasIndicator && (
                    <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white"></div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default HomeNotificationsSidebar;
