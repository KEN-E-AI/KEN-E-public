import { useState, useCallback, useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Menu,
  Home,
  BarChart3,
  Package,
  Search,
  BookOpen,
  Settings,
  Building,
  Check,
  Archive,
  CircleDot,
  AlertTriangle,
  MoreVertical,
  Newspaper,
  Globe,
  Users,
  FileText,
  TrendingUp,
  Sparkles,
  Send,
  Mic,
  AudioWaveform,
  Wrench,
  Mail,
  MessageSquare,
  Share2,
  Plus,
  User,
  Megaphone,
  Network,
  Glasses,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import type { SelectedOrgAccount } from "@/contexts/AuthContext";
import { useLocation, useNavigate } from "react-router-dom";
import { iconMap } from "@/lib/iconMap";
import api from "@/lib/api";
import type { NotificationCategory } from "@/types/notification.types";
import {
  chatService,
  type ChatMessage,
  type ConversationInfo,
} from "@/services/chatService";

interface SubMenuItem {
  id: string;
  label: string;
  route: string;
}

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

// Notification category icon mapping matching NotificationPreferences.tsx
const NOTIFICATION_CATEGORY_ICONS: Record<
  NotificationCategory,
  React.ComponentType<{ className?: string }>
> = {
  "Data Quality Alert": AlertTriangle,
  "News & Press": Newspaper,
  "Industry News": Globe,
  "Competitor Activities": Users,
  "Scheduled Report Status": FileText,
  "KPI Performance": TrendingUp,
  "New Features": Sparkles,
};

interface MenuSection {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: SubMenuItem[];
}

const menuConfigurations: Record<string, MenuSection> = {
  "/performance": {
    title: "Performance",
    icon: BarChart3,
    items: [
      { id: "overview", label: "Overview", route: "/performance" },
      {
        id: "channel",
        label: "Channel Performance",
        route: "/performance/channels",
      },
    ],
  },
  "/products": {
    title: "Products",
    icon: Package,
    items: [{ id: "overview", label: "Overview", route: "/products" }],
  },
  "/customers": {
    title: "Customers",
    icon: Users,
    items: [{ id: "overview", label: "Overview", route: "/customers" }],
  },
  "/campaigns": {
    title: "Campaigns",
    icon: Megaphone,
    items: [{ id: "overview", label: "Overview", route: "/campaigns" }],
  },
  "/channels": {
    title: "Channels",
    icon: Network,
    items: [{ id: "overview", label: "Overview", route: "/channels" }],
  },
  "/reports": {
    title: "Reports",
    icon: FileText,
    items: [{ id: "overview", label: "Overview", route: "/reports" }],
  },
  "/simulations": {
    title: "Simulations",
    icon: Glasses,
    items: [{ id: "overview", label: "Overview", route: "/simulations" }],
  },
  "/knowledge": {
    title: "Knowledge Base",
    icon: BookOpen,
    items: [
      { id: "products", label: "Products", route: "/knowledge/products" },
      { id: "metrics", label: "Metrics", route: "/knowledge/metrics" },
      { id: "activities", label: "Activities", route: "/knowledge/activities" },
      { id: "insights", label: "Insights", route: "/knowledge/insights" },
      {
        id: "strategy",
        label: "Measurement Strategy",
        route: "/knowledge/strategy",
      },
      { id: "account", label: "Account Overview", route: "/knowledge/account" },
      { id: "customers", label: "Customers", route: "/knowledge/customers" },
      {
        id: "competitors",
        label: "Competitors",
        route: "/knowledge/competitors",
      },
    ],
  },
  "/settings": {
    title: "Settings",
    icon: Settings,
    items: [
      {
        id: "organization",
        label: "Organization",
        route: "/settings/organization",
      },
      { id: "user", label: "User", route: "/settings/user" },
    ],
  },
};

interface ContextSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  selectedTab?: string;
}

export const ContextSidebar: React.FC<ContextSidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  selectedTab = "Awareness",
}) => {
  const {
    notifications,
    setNotifications,
    user,
    orgMetadata,
    accountMetadata,
    selectedOrgAccount,
    setSelectedOrgAccount,
    setCurrentOrganization,
    isSuperAdmin,
  } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isHomePage = location.pathname === "/";

  // Chat state (from ChatSidebar)
  const [newMessage, setNewMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [currentConversation, setCurrentConversation] =
    useState<ConversationInfo | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      id: "1",
      role: "assistant",
      content: `Hello! I'm here to help with your ${selectedTab} strategy. What would you like to discuss?`,
      timestamp: new Date().toISOString(),
    },
  ]);

  // Mark notification as read
  const markAsRead = async (notificationId: string) => {
    try {
      // Use the proper notifications API endpoint
      await api.put(`/api/v1/notifications/${notificationId}/status`, {
        status: "read",
      });

      // Update local state
      setNotifications(
        notifications.map((n) =>
          n.id === notificationId ? { ...n, status: "read" } : n,
        ),
      );
    } catch (error) {
      console.error("Failed to mark notification as read:", error);
    }
  };

  // Mark notification as unread
  const markAsUnread = async (notificationId: string) => {
    try {
      // Use the proper notifications API endpoint
      await api.put(`/api/v1/notifications/${notificationId}/status`, {
        status: "unread",
      });

      // Update local state
      setNotifications(
        notifications.map((n) =>
          n.id === notificationId ? { ...n, status: "unread" } : n,
        ),
      );
    } catch (error) {
      console.error("Failed to mark notification as unread:", error);
    }
  };

  // Archive notification
  const archiveNotification = async (notificationId: string) => {
    try {
      // Use the proper notifications API endpoint
      await api.put(`/api/v1/notifications/${notificationId}/status`, {
        status: "archived",
      });

      // Remove from local state (or update status to archived)
      setNotifications(notifications.filter((n) => n.id !== notificationId));
    } catch (error) {
      console.error("Failed to archive notification:", error);
    }
  };

  // Load conversations on component mount (chat functionality)
  useEffect(() => {
    if (isHomePage) return; // Skip chat loading on home page

    const loadConversations = async () => {
      try {
        const userConversations = await chatService.getConversations();
        setConversations(
          Array.isArray(userConversations) ? userConversations : [],
        );

        if (
          !sessionId &&
          Array.isArray(userConversations) &&
          userConversations.length > 0
        ) {
          const mostRecent = userConversations[0];
          setCurrentConversation(mostRecent);
          setSessionId(mostRecent.session_id);
        }
      } catch (error) {
        console.error("Failed to load conversations:", error);
        setConversations([]);
      }
    };

    loadConversations();
  }, [sessionId, isHomePage]);

  // Create a new chat conversation
  const createNewChat = useCallback(async () => {
    try {
      setIsLoading(true);
      const newConversation =
        await chatService.createConversation("Dashboard Chat");

      setConversations((prev) => [newConversation, ...prev]);
      setCurrentConversation(newConversation);
      setSessionId(newConversation.session_id);

      setMessages([
        {
          id: "1",
          role: "assistant",
          content: `Hello! I'm here to help with your ${selectedTab} strategy. What would you like to discuss?`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (error) {
      console.error("Failed to create new chat:", error);
    } finally {
      setIsLoading(false);
    }
  }, [selectedTab]);

  // Switch to an existing conversation
  const switchToConversation = useCallback(
    async (conversation: ConversationInfo) => {
      try {
        setIsLoading(true);
        setCurrentConversation(conversation);
        setSessionId(conversation.session_id);

        const history = await chatService.getConversationHistory(
          conversation.session_id,
        );

        if (history && (history.messages || history.events)) {
          const events = history.events || history.messages || [];
          const loadedMessages: DisplayMessage[] = events.map(
            (event: any, index: number) => {
              let content = "Empty message";
              let role = "assistant";

              if (
                event.content &&
                event.content.parts &&
                event.content.parts.length > 0
              ) {
                content =
                  event.content.parts[0].text ||
                  event.content.parts[0].content ||
                  "Empty message";
                role = event.content.role || event.role || "assistant";
              } else if (event.content) {
                content =
                  event.content.text || event.content || "Empty message";
                role = event.role || "assistant";
              }

              return {
                id: `${index}`,
                role: role === "user" ? "user" : "assistant",
                content: content,
                timestamp: new Date(
                  event.timestamp || Date.now(),
                ).toISOString(),
              };
            },
          );
          setMessages(loadedMessages);
        } else {
          setMessages([
            {
              id: "1",
              role: "assistant",
              content: `Resumed conversation: ${conversation.conversation_name || "Untitled Chat"} for ${selectedTab}`,
              timestamp: new Date().toISOString(),
            },
          ]);
        }
      } catch (error) {
        console.error("Failed to load conversation history:", error);
        setMessages([
          {
            id: "1",
            role: "assistant",
            content: `Error loading conversation history. Starting fresh chat for ${selectedTab}.`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [selectedTab],
  );

  // Send new chat message
  const sendNewMessage = useCallback(async () => {
    if (!newMessage.trim() || isLoading) return;

    const validation = chatService.validateMessage(newMessage);
    if (!validation.valid) {
      console.error("Invalid message:", validation.reason);
      return;
    }

    const userMessage = {
      id: Date.now().toString(),
      role: "user" as const,
      content: newMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setNewMessage("");
    setIsLoading(true);

    try {
      const chatMessages: ChatMessage[] = [...messages, userMessage].map(
        (msg) => ({
          role: msg.role,
          content: msg.content,
        }),
      );

      const response = await chatService.sendMessage(chatMessages, sessionId);

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant" as const,
        content: response.content,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error sending message:", error);

      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant" as const,
        content:
          "I'm sorry, I'm having trouble processing your request. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [newMessage, messages, isLoading, sessionId]);

  // Handle key press for chat input
  const handleNewKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendNewMessage();
    }
  };

  // Determine which menu to show based on current route
  const getActiveMenu = () => {
    const path = location.pathname;

    // Check each menu configuration to see if the current path starts with it
    for (const [menuPath, config] of Object.entries(menuConfigurations)) {
      if (path.startsWith(menuPath)) {
        // Add admin link to settings menu for super admins
        if (menuPath === "/settings" && isSuperAdmin) {
          return {
            path: menuPath,
            config: {
              ...config,
              items: [
                ...config.items,
                { id: "admin", label: "Admin", route: "/settings/admin" },
              ],
            },
          };
        }
        return { path: menuPath, config };
      }
    }

    // Default to home/notifications
    return null;
  };

  const activeMenu = getActiveMenu();

  // Organization dropdown logic
  const accessibleOrgIds = isSuperAdmin
    ? Object.keys(orgMetadata) // For super admins, show all organizations
    : Object.keys(user?.permissions?.organizations || {});

  const combinedOptions: Array<{
    value: string;
    label: string;
    orgName: string;
    orgId: string;
    accountId: string;
  }> = accessibleOrgIds
    .flatMap((orgId) => {
      const organization = orgMetadata[orgId];
      if (!organization) return [];

      const orgAccounts = organization.accounts || [];

      if (!organization.agency) {
        return orgAccounts.map((account: any) => ({
          value: JSON.stringify({ orgId, accountId: account.account_id }),
          label: account.account_name,
          orgName: organization.organization_name,
          orgId,
          accountId: account.account_id,
        }));
      }

      if (organization.agency && organization.child_organizations) {
        return organization.child_organizations.flatMap(
          (childOrgId: string) => {
            const childOrg = orgMetadata[childOrgId];
            if (!childOrg) return [];

            const childAccounts = childOrg.accounts || [];
            return childAccounts.map((account: any) => ({
              value: JSON.stringify({
                orgId: childOrgId,
                accountId: account.account_id,
              }),
              label: account.account_name,
              orgName: childOrg.organization_name,
              orgId: childOrgId,
              accountId: account.account_id,
            }));
          },
        );
      }

      return [];
    })
    .filter(Boolean);

  const currentValue = selectedOrgAccount
    ? JSON.stringify({
        orgId: selectedOrgAccount.orgId,
        accountId: selectedOrgAccount.accountId,
      })
    : "";

  const handleOrgAccountChange = (value: string) => {
    if (value === "all-orgs-accounts") {
      navigate("/organization-selection");
      return;
    }

    let parsed: { orgId: string; accountId: string };
    try {
      parsed = JSON.parse(value);
    } catch (err) {
      console.warn("⚠️ Failed to parse selection JSON:", value);
      return;
    }

    const { orgId, accountId } = parsed;
    const account = accountMetadata[accountId];
    const organization = orgMetadata[orgId];

    if (!account || !organization) {
      console.warn("⚠️ Invalid selection — no matching org/account.", {
        orgId,
        accountId,
      });
      return;
    }

    const selection: SelectedOrgAccount = {
      orgId,
      accountId,
      metadata: {
        organization_name: organization.organization_name,
        account_name: account.account_name,
        industry: account.industry,
        status: account.status,
        timezone: account.timezone,
        plan: organization.plan,
      },
    };

    setSelectedOrgAccount(selection);
    setCurrentOrganization(orgId);
  };

  return (
    <div
      className={cn(
        "fixed top-0 left-14 h-full bg-white border-r border-dashboard-gray-200 z-30 transition-all duration-300 flex flex-col",
        isCollapsed ? "w-14" : "w-[360px]",
      )}
    >
      {/* Header */}
      {isCollapsed ? (
        <div className="h-12 flex items-center justify-center border-b border-dashboard-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-8 w-8 p-0"
            aria-label="Toggle sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="flex items-center justify-between px-3 py-2 border-b border-dashboard-gray-200">
          {/* Organization/Account Selector */}
          {combinedOptions.length > 0 && (
            <div className="flex-1 mr-2">
              <Select
                value={currentValue}
                onValueChange={handleOrgAccountChange}
              >
                <SelectTrigger className="w-full h-auto py-2 text-sm border-0 bg-transparent hover:bg-gray-50 focus:ring-1 focus:ring-brand-medium-blue [&>svg]:hidden">
                  <div className="flex items-start gap-2 text-left w-full">
                    <ChevronDown className="h-4 w-4 mt-0.5 flex-shrink-0 text-gray-500" />
                    <SelectValue placeholder="Select Account">
                      {currentValue &&
                        (() => {
                          const selected = combinedOptions.find(
                            (opt) => opt.value === currentValue,
                          );
                          if (selected) {
                            return (
                              <div className="flex items-start gap-2 text-left">
                                <Building className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                <div className="min-w-0">
                                  <div className="font-semibold text-sm truncate">
                                    {selected.orgName}
                                  </div>
                                  <div className="text-xs text-gray-600 truncate">
                                    {selected.label}
                                  </div>
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })()}
                    </SelectValue>
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="max-w-[300px]">
                  {combinedOptions.map((option, index) => (
                    <SelectItem
                      key={`${option.orgId}-${option.accountId}-${index}`}
                      value={option.value}
                    >
                      <div className="flex items-start gap-2">
                        <Building className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        <div>
                          <div className="font-bold">{option.orgName}</div>
                          <div className="text-xs text-gray-600">
                            {option.label}
                          </div>
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                  {combinedOptions.length > 1 && (
                    <SelectItem
                      key="all-orgs-accounts"
                      value="all-orgs-accounts"
                      className="border-t border-gray-200 mt-1 pt-2"
                    >
                      <div className="flex items-center gap-2">
                        <Building className="h-4 w-4" />
                        <div className="truncate">All Orgs and Accounts</div>
                      </div>
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-8 w-8 p-0 flex-shrink-0"
            aria-label="Toggle sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Content - grows to fill available space */}
      {!isCollapsed && (
        <div className="flex-1 overflow-y-auto">
          {isHomePage ? (
            // Notifications content for home page
            <div className="pr-4 pl-0 py-4">
              <div className="rounded-r-lg overflow-hidden border border-[#E2E8F0]">
                {notifications && notifications.length > 0 ? (
                  notifications.map((notification, index) => {
                    console.log("🔍 Notification debug:", {
                      id: notification.id,
                      status: notification.status,
                      fullNotification: notification,
                    });
                    // Use category-based icon mapping instead of icon field
                    const IconComponent =
                      NOTIFICATION_CATEGORY_ICONS[
                        notification.category as NotificationCategory
                      ] || Home;
                    const isUnread = notification.status === "unread";
                    console.log("🔍 isUnread check:", {
                      id: notification.id,
                      status: notification.status,
                      isUnread,
                      statusType: typeof notification.status,
                      statusValue: JSON.stringify(notification.status),
                    });
                    return (
                      <div
                        key={notification.id}
                        className={cn(
                          "flex items-start gap-3 p-4 hover:bg-gray-50 transition-colors",
                          index !== notifications.length - 1 && "border-b",
                        )}
                      >
                        <div className="relative">
                          <div
                            className={cn(
                              "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0",
                              isUnread ? "bg-[#B8E2AF]" : "bg-gray-100",
                            )}
                          >
                            <IconComponent
                              className={cn(
                                "w-5 h-5",
                                isUnread ? "text-green-700" : "text-gray-600",
                              )}
                            />
                          </div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              {notification.data?.title && (
                                <p
                                  className={cn(
                                    "text-sm font-medium",
                                    isUnread
                                      ? "text-gray-900"
                                      : "text-gray-600",
                                  )}
                                >
                                  {notification.data.title}
                                </p>
                              )}
                              <p className="text-sm text-gray-500 mt-1">
                                {notification.description}
                              </p>
                              <p className="text-xs text-gray-400 mt-2">
                                {notification.created_at ||
                                notification.created_date
                                  ? new Date(
                                      notification.created_at ||
                                        notification.created_date ||
                                        "",
                                    ).toLocaleString()
                                  : ""}
                              </p>
                            </div>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 w-7 p-0"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MoreVertical className="h-4 w-4" />
                                  <span className="sr-only">
                                    Notification actions
                                  </span>
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                {isUnread ? (
                                  <DropdownMenuItem
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      markAsRead(notification.id);
                                    }}
                                  >
                                    <Check className="h-4 w-4 mr-2" />
                                    Mark as read
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      markAsUnread(notification.id);
                                    }}
                                  >
                                    <CircleDot className="h-4 w-4 mr-2" />
                                    Mark as unread
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuItem
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    archiveNotification(notification.id);
                                  }}
                                >
                                  <Archive className="h-4 w-4 mr-2" />
                                  Archive
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                        {notification.data?.badge && (
                          <Badge variant="secondary" className="flex-shrink-0">
                            {notification.data.badge}
                          </Badge>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="p-4 text-gray-500 text-center">
                    No notifications
                  </div>
                )}
              </div>
            </div>
          ) : (
            // Chat interface for non-home pages
            <div className="flex flex-col h-full">
              {/* Chat Controls */}
              <div className="p-4 border-b border-dashboard-gray-200">
                <div className="flex gap-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="flex-1">
                        <span className="lg:mr-auto">Resume Conversation</span>
                        <ChevronDown className="ml-2 h-3 w-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-56">
                      {!Array.isArray(conversations) ||
                      conversations.length === 0 ? (
                        <DropdownMenuItem disabled>
                          No previous conversations
                        </DropdownMenuItem>
                      ) : (
                        conversations.slice(0, 4).map((conversation) => (
                          <DropdownMenuItem
                            key={conversation.session_id}
                            onClick={() => switchToConversation(conversation)}
                            className="cursor-pointer"
                          >
                            {conversation.conversation_name ||
                              `Chat ${conversation.session_id.slice(-6)}`}
                          </DropdownMenuItem>
                        ))
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button
                    size="sm"
                    className="bg-brand-medium-blue hover:bg-brand-medium-blue/90"
                    onClick={createNewChat}
                    disabled={isLoading}
                  >
                    New
                  </Button>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-9 w-9 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900"
                      >
                        <Share2 className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                        <Mail className="h-4 w-4" />
                        Share chat by email
                      </DropdownMenuItem>
                      <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                        <MessageSquare className="h-4 w-4" />
                        Share chat by Slack
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>

              {/* Chat Messages - scrollable area with padding for fixed input */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 pb-48">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      "flex gap-3",
                      msg.role === "user" ? "justify-end" : "justify-start",
                    )}
                  >
                    {msg.role === "assistant" && (
                      <div className="w-6 h-6 rounded-sm flex items-center justify-center flex-shrink-0 mt-1 overflow-hidden">
                        <img
                          src="https://cdn.builder.io/api/v1/assets/c9d6292aa8bc48fc881c52163e11eef1/headshot-1-1-modified-178e67?format=webp&width=800"
                          alt="KEN-E Assistant"
                          className="w-full h-full object-cover rounded-sm"
                        />
                      </div>
                    )}
                    <div
                      className={cn(
                        "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                        msg.role === "user"
                          ? "bg-brand-medium-blue text-white"
                          : "bg-dashboard-gray-100 text-dashboard-gray-900",
                      )}
                    >
                      {msg.content}
                    </div>
                    {msg.role === "user" && (
                      <div className="w-6 h-6 bg-brand-medium-blue rounded-sm flex items-center justify-center flex-shrink-0 mt-1">
                        <User className="h-3 w-3 text-white" />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* New Message Input Section - Fixed at bottom */}
              <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-dashboard-gray-200 p-4">
                <div className="space-y-3">
                  {/* Input Container */}
                  <div className="border border-[#CBD5E1] rounded-md p-2">
                    <div className="flex flex-col gap-2">
                      {/* Input Field Row */}
                      <div className="flex-1">
                        <Input
                          value={newMessage}
                          onChange={(e) => setNewMessage(e.target.value)}
                          onKeyDown={handleNewKeyPress}
                          placeholder="What would you like to discuss?"
                          className="w-full border-0 focus:ring-0 focus:border-0 shadow-none"
                          disabled={isLoading}
                        />
                      </div>

                      {/* Buttons Row */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900 flex flex-col"
                        >
                          <Mic className="h-5 w-5 mx-auto" />
                        </Button>

                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900 flex flex-col mr-2"
                          title="Enable voice mode"
                        >
                          <AudioWaveform className="h-5 w-5" />
                        </Button>

                        <Button
                          onClick={sendNewMessage}
                          disabled={!newMessage.trim() || isLoading}
                          size="sm"
                          className="bg-brand-medium-blue hover:bg-brand-medium-blue/90 text-white px-4"
                        >
                          {isLoading ? "..." : "Send"}
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Action Button Row */}
                  <div className="flex items-center gap-2 justify-start">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900"
                      title="Upload a file"
                    >
                      <Plus className="h-5 w-5" />
                    </Button>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-10 w-10 p-0 text-dashboard-gray-600 hover:text-dashboard-gray-900"
                          title="Select a tool"
                        >
                          <Wrench className="h-5 w-5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                          Explain a change to a metric
                        </DropdownMenuItem>
                        <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                          Create a chart
                        </DropdownMenuItem>
                        <DropdownMenuItem className="flex items-center gap-2 cursor-pointer">
                          Draft content
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
