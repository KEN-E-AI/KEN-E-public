/**
 * Notification API client
 */

import axios from 'axios';
import type {
  CreateNotificationRequest,
  NotificationStatus,
  NotificationWithStatus,
  UpdateNotificationStatusRequest,
  UserNotificationPreferences,
} from '@/types/notification.types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const notificationApi = {
  /**
   * Create a new notification
   */
  createNotification: async (data: CreateNotificationRequest) => {
    const response = await axios.post(`${API_BASE_URL}/api/v1/notifications`, data);
    return response.data;
  },

  /**
   * Get notifications for an account
   */
  getNotifications: async (accountId: string, includeArchived = false): Promise<NotificationWithStatus[]> => {
    const response = await axios.get(`${API_BASE_URL}/api/v1/notifications`, {
      params: {
        account_id: accountId,
        include_archived: includeArchived,
      },
    });
    return response.data;
  },

  /**
   * Update notification status
   */
  updateNotificationStatus: async (notificationId: string, status: NotificationStatus, accountId: string) => {
    const response = await axios.put(
      `${API_BASE_URL}/api/v1/notifications/${notificationId}/status`, 
      { status },
      { params: { account_id: accountId } }
    );
    return response.data;
  },

  /**
   * Get user notification preferences
   */
  getPreferences: async (accountId: string): Promise<UserNotificationPreferences> => {
    const response = await axios.get(`${API_BASE_URL}/api/v1/notifications/preferences`, {
      params: { account_id: accountId },
    });
    return response.data;
  },

  /**
   * Update user notification preferences
   */
  updatePreferences: async (accountId: string, preferences: UserNotificationPreferences) => {
    const response = await axios.put(
      `${API_BASE_URL}/api/v1/notifications/preferences`, 
      preferences, 
      { params: { account_id: accountId } }
    );
    return response.data;
  },

  /**
   * Get unread notification count
   */
  getUnreadCount: async (accountId: string): Promise<number> => {
    const response = await axios.get(`${API_BASE_URL}/api/v1/notifications/unread-count`, {
      params: { account_id: accountId },
    });
    return response.data.unread_count;
  },

  /**
   * Mark notification as read
   */
  markAsRead: async (notificationId: string, accountId: string) => {
    return notificationApi.updateNotificationStatus(notificationId, 'read', accountId);
  },

  /**
   * Archive notification
   */
  archiveNotification: async (notificationId: string, accountId: string) => {
    return notificationApi.updateNotificationStatus(notificationId, 'archived', accountId);
  },
};