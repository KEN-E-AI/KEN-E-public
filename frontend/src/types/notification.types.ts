/**
 * Notification-related types and interfaces
 */

export type NotificationCategory =
  | 'Data Quality Alert'
  | 'News & Press'
  | 'Industry News'
  | 'Competitor Activities'
  | 'Scheduled Report Status'
  | 'KPI Performance'
  | 'New Features';

export type NotificationStatus = 'excluded' | 'unread' | 'read' | 'archived';

export type NotificationChannel = 'ui' | 'slack' | 'email';

export interface Notification {
  id: string;
  account_id: string;
  category: NotificationCategory;
  description: string;
  data?: Record<string, any>;
  created_at: string;
  archived_at?: string;
}

export interface NotificationWithStatus extends Notification {
  status: NotificationStatus;
  read_at?: string;
  user_archived_at?: string;
}

export interface CreateNotificationRequest {
  account_id: string;
  category: NotificationCategory;
  description: string;
  data?: Record<string, any>;
}

export interface UpdateNotificationStatusRequest {
  status: NotificationStatus;
}

export interface UserNotificationPreferences {
  categories: NotificationCategory[];
  channels: NotificationChannel[];
  updated_at?: string;
}

export interface NotificationIconMap {
  [key: string]: string;
}

// Icon mapping for notification categories
export const NOTIFICATION_ICONS: NotificationIconMap = {
  'Data Quality Alert': 'alert-triangle',
  'News & Press': 'newspaper',
  'Industry News': 'globe',
  'Competitor Activities': 'users',
  'Scheduled Report Status': 'file-text',
  'KPI Performance': 'trending-up',
  'New Features': 'sparkles',
};

// Category colors for visual distinction
export const NOTIFICATION_CATEGORY_COLORS: Record<NotificationCategory, string> = {
  'Data Quality Alert': 'text-red-600',
  'News & Press': 'text-blue-600',
  'Industry News': 'text-green-600',
  'Competitor Activities': 'text-purple-600',
  'Scheduled Report Status': 'text-gray-600',
  'KPI Performance': 'text-orange-600',
  'New Features': 'text-pink-600',
};

export const NOTIFICATION_CATEGORY_BG_COLORS: Record<NotificationCategory, string> = {
  'Data Quality Alert': 'bg-red-50',
  'News & Press': 'bg-blue-50',
  'Industry News': 'bg-green-50',
  'Competitor Activities': 'bg-purple-50',
  'Scheduled Report Status': 'bg-gray-50',
  'KPI Performance': 'bg-orange-50',
  'New Features': 'bg-pink-50',
};