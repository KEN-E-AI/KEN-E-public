/**
 * NotificationSidebar component for displaying notifications
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Newspaper,
  Globe,
  Users,
  FileText,
  TrendingUp,
  Sparkles,
  X,
  Archive,
  Circle,
  CheckCircle,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { notificationApi } from "@/api/notifications";
import type {
  NotificationWithStatus,
  NotificationCategory,
} from "@/types/notification.types";
import {
  NOTIFICATION_CATEGORY_COLORS,
  NOTIFICATION_CATEGORY_BG_COLORS,
} from "@/types/notification.types";

interface NotificationSidebarProps {
  accountId: string;
  isOpen: boolean;
  onClose: () => void;
  onNotificationClick?: (notification: NotificationWithStatus) => void;
}

// Icon mapping
const NOTIFICATION_ICONS: Record<NotificationCategory, React.ReactNode> = {
  "Data Quality Alert": <AlertTriangle className="h-5 w-5" />,
  "News & Press": <Newspaper className="h-5 w-5" />,
  "Industry News": <Globe className="h-5 w-5" />,
  "Competitor Activities": <Users className="h-5 w-5" />,
  "Scheduled Report Status": <FileText className="h-5 w-5" />,
  "KPI Performance": <TrendingUp className="h-5 w-5" />,
  "New Features": <Sparkles className="h-5 w-5" />,
};

export const NotificationSidebar: React.FC<NotificationSidebarProps> = ({
  accountId,
  isOpen,
  onClose,
  onNotificationClick,
}) => {
  const [notifications, setNotifications] = useState<NotificationWithStatus[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    if (!accountId) return;

    try {
      setLoading(true);
      setError(null);
      const data = await notificationApi.getNotifications(accountId, false);
      setNotifications(data);
    } catch (err) {
      console.error("Error fetching notifications:", err);
      setError("Failed to load notifications");
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen, fetchNotifications]);

  // Mark notification as read
  const handleMarkAsRead = async (notification: NotificationWithStatus) => {
    if (notification.status === "read") return;

    try {
      await notificationApi.markAsRead(notification.id, accountId);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notification.id
            ? { ...n, status: "read", read_at: new Date().toISOString() }
            : n,
        ),
      );
    } catch (err) {
      console.error("Error marking notification as read:", err);
    }
  };

  // Archive notification
  const handleArchive = async (
    notification: NotificationWithStatus,
    e: React.MouseEvent,
  ) => {
    e.stopPropagation();

    try {
      await notificationApi.archiveNotification(notification.id, accountId);
      setNotifications((prev) => prev.filter((n) => n.id !== notification.id));
    } catch (err) {
      console.error("Error archiving notification:", err);
    }
  };

  // Handle notification click
  const handleNotificationClick = (notification: NotificationWithStatus) => {
    handleMarkAsRead(notification);
    onNotificationClick?.(notification);
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40"
        onClick={onClose}
      />

      {/* Sidebar */}
      <div className="fixed right-0 top-0 h-full w-96 bg-[var(--color-bg-elevated)] shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Notifications</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-text-disabled)] hover:text-[var(--color-text-tertiary)] transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-[var(--color-text-tertiary)]">
              Loading notifications...
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">{error}</div>
          ) : notifications.length === 0 ? (
            <div className="p-4 text-center text-[var(--color-text-tertiary)]">
              No notifications
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onClick={() => handleNotificationClick(notification)}
                  onArchive={(e) => handleArchive(notification, e)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
};

interface NotificationItemProps {
  notification: NotificationWithStatus;
  onClick: () => void;
  onArchive: (e: React.MouseEvent) => void;
}

const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onClick,
  onArchive,
}) => {
  const isUnread = notification.status === "unread";
  const icon = NOTIFICATION_ICONS[notification.category];
  const colorClass = NOTIFICATION_CATEGORY_COLORS[notification.category];
  const bgColorClass = NOTIFICATION_CATEGORY_BG_COLORS[notification.category];

  return (
    <div
      className={`p-4 hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors ${
        isUnread ? "bg-blue-50/30" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={`${bgColorClass} ${colorClass} p-2 rounded-lg flex-shrink-0`}
        >
          {icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <p className="text-sm font-medium text-[var(--color-text-primary)] flex items-center gap-2">
                {notification.description}
                {isUnread && (
                  <Circle className="h-2 w-2 fill-blue-600 text-blue-600" />
                )}
              </p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                {notification.category} •{" "}
                {formatDistanceToNow(new Date(notification.created_at), {
                  addSuffix: true,
                })}
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1">
              {notification.status === "read" && (
                <CheckCircle className="h-4 w-4 text-green-500" />
              )}
              <button
                onClick={onArchive}
                className="text-[var(--color-text-disabled)] hover:text-[var(--color-text-tertiary)] transition-colors p-1"
                title="Archive"
              >
                <Archive className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Additional data preview if available */}
          {notification.data && Object.keys(notification.data).length > 0 && (
            <div className="mt-2 text-xs text-[var(--color-text-tertiary)] bg-[var(--color-bg-elevated)] rounded p-2">
              {Object.entries(notification.data)
                .slice(0, 2)
                .map(([key, value]) => (
                  <div key={key}>
                    <span className="font-medium">{key}:</span> {String(value)}
                  </div>
                ))}
              {Object.keys(notification.data).length > 2 && (
                <div className="text-[var(--color-text-disabled)]">...</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
