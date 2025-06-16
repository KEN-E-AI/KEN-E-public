import {
  Bell,
  AlertCircle,
  TrendingUp,
  Users,
  BarChart3,
  CheckCircle,
  ChevronDown,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Notification {
  id: string;
  title: string;
  type: "news" | "activity" | "insight" | "quality" | "experiment" | "analysis";
  hasIndicator: boolean;
  icon: React.ComponentType<any>;
}

const notifications: Notification[] = [
  {
    id: "1",
    title: "You're in the news",
    type: "news",
    hasIndicator: true,
    icon: Bell,
  },
  {
    id: "2",
    title: "Competitor activity",
    type: "activity",
    hasIndicator: true,
    icon: TrendingUp,
  },
  {
    id: "3",
    title: "Awareness is declining",
    type: "insight",
    hasIndicator: false,
    icon: AlertCircle,
  },
  {
    id: "4",
    title: "Data quality issue found",
    type: "quality",
    hasIndicator: true,
    icon: AlertCircle,
  },
  {
    id: "5",
    title: "Experiment complete",
    type: "experiment",
    hasIndicator: false,
    icon: CheckCircle,
  },
  {
    id: "6",
    title: "Your scheduled analysis is ready",
    type: "analysis",
    hasIndicator: false,
    icon: BarChart3,
  },
];

const NotificationsSidebar = () => {
  return (
    <div className="h-full p-6">
      {/* Chat Header */}
      <div className="mb-6">
        <div className="flex flex-col gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex items-center justify-between w-full"
              >
                <span>Resume Conversation</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-full">
              <DropdownMenuItem>Marketing Strategy Discussion</DropdownMenuItem>
              <DropdownMenuItem>Campaign Performance Review</DropdownMenuItem>
              <DropdownMenuItem>Data Analysis Session</DropdownMenuItem>
              <DropdownMenuItem>Customer Insights Review</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button size="sm" className="bg-blue-600 hover:bg-blue-700 w-full">
            New Chat
          </Button>
        </div>
      </div>

      {/* Notifications Header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Notifications</h2>
      </div>

      {/* Notifications List */}
      <div className="space-y-3">
        {notifications.map((notification) => {
          const IconComponent = notification.icon;
          return (
            <div
              key={notification.id}
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
            >
              {/* Icon */}
              <div className="flex-shrink-0">
                <IconComponent className="h-4 w-4 text-gray-600" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900 leading-relaxed">
                  {notification.title}
                </p>
              </div>

              {/* Indicator */}
              {notification.hasIndicator && (
                <div className="flex-shrink-0">
                  <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default NotificationsSidebar;
