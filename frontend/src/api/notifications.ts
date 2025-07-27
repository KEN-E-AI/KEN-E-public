/**
 * Notification API client
 */

import api from "@/lib/api";
import type {
  CreateNotificationRequest,
  NotificationStatus,
  NotificationWithStatus,
  UpdateNotificationStatusRequest,
  UserNotificationPreferences,
} from "@/types/notification.types";

export const notificationApi = {
  /**
   * Create a new notification
   */
  createNotification: async (data: CreateNotificationRequest) => {
    const response = await api.post("/api/v1/notifications/", data);
    return response.data;
  },

  /**
   * Get notifications for current user
   */
  getNotifications: async (
    includeArchived = false,
  ): Promise<NotificationWithStatus[]> => {
    const response = await api.get("/api/v1/notifications/", {
      params: {
        include_archived: includeArchived,
      },
    });
    return response.data;
  },

  /**
   * Update notification status
   */
  updateNotificationStatus: async (
    notificationId: string,
    status: NotificationStatus,
  ) => {
    const response = await api.put(
      `/api/v1/notifications/${notificationId}/status`,
      { status },
    );
    return response.data;
  },

  /**
   * Get user notification preferences
   */
  getPreferences: async (): Promise<UserNotificationPreferences> => {
    const response = await api.get("/api/v1/notifications/preferences");
    return response.data;
  },

  /**
   * Update user notification preferences
   */
  updatePreferences: async (
    preferences: Omit<UserNotificationPreferences, "updated_at">,
  ) => {
    const response = await api.put(
      "/api/v1/notifications/preferences",
      preferences,
    );
    return response.data;
  },

  /**
   * Get unread notification count
   */
  getUnreadCount: async (): Promise<number> => {
    const response = await api.get("/api/v1/notifications/unread-count");
    return response.data.unread_count;
  },

  /**
   * Mark notification as read
   */
  markAsRead: async (notificationId: string) => {
    return notificationApi.updateNotificationStatus(notificationId, "read");
  },

  /**
   * Archive notification
   */
  archiveNotification: async (notificationId: string) => {
    return notificationApi.updateNotificationStatus(notificationId, "archived");
  },
};
