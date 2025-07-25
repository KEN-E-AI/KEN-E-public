/**
 * NotificationPreferences component for managing notification settings
 */

import React, { useEffect, useState } from 'react';
import { 
  AlertTriangle, 
  Newspaper, 
  Globe, 
  Users, 
  FileText, 
  TrendingUp, 
  Sparkles,
  Monitor,
  Mail,
  MessageSquare,
  Check,
  Loader2,
} from 'lucide-react';
import { notificationApi } from '@/api/notifications';
import type { 
  NotificationCategory, 
  NotificationChannel, 
  UserNotificationPreferences 
} from '@/types/notification.types';

interface NotificationPreferencesProps {
  accountId: string;
  onSave?: () => void;
}

// Category configuration
const NOTIFICATION_CATEGORIES: {
  value: NotificationCategory;
  label: string;
  description: string;
  icon: React.ReactNode;
}[] = [
  {
    value: 'Data Quality Alert',
    label: 'Data Quality Alerts',
    description: 'Notifications about data quality issues and anomalies',
    icon: <AlertTriangle className="h-5 w-5" />,
  },
  {
    value: 'News & Press',
    label: 'News & Press',
    description: 'Updates about company news and press releases',
    icon: <Newspaper className="h-5 w-5" />,
  },
  {
    value: 'Industry News',
    label: 'Industry News',
    description: 'Relevant industry news and market updates',
    icon: <Globe className="h-5 w-5" />,
  },
  {
    value: 'Competitor Activities',
    label: 'Competitor Activities',
    description: 'Updates about competitor actions and strategies',
    icon: <Users className="h-5 w-5" />,
  },
  {
    value: 'Scheduled Report Status',
    label: 'Scheduled Report Status',
    description: 'Notifications about scheduled report generation',
    icon: <FileText className="h-5 w-5" />,
  },
  {
    value: 'KPI Performance',
    label: 'KPI Performance',
    description: 'Alerts about KPI changes and performance metrics',
    icon: <TrendingUp className="h-5 w-5" />,
  },
  {
    value: 'New Features',
    label: 'New Features',
    description: 'Announcements about new features and updates',
    icon: <Sparkles className="h-5 w-5" />,
  },
];

// Channel configuration
const NOTIFICATION_CHANNELS: {
  value: NotificationChannel;
  label: string;
  description: string;
  icon: React.ReactNode;
}[] = [
  {
    value: 'ui',
    label: 'UI Only',
    description: 'Show notifications in the application interface',
    icon: <Monitor className="h-5 w-5" />,
  },
  {
    value: 'email',
    label: 'Email',
    description: 'Send notifications to your email address',
    icon: <Mail className="h-5 w-5" />,
  },
  {
    value: 'slack',
    label: 'Slack',
    description: 'Send notifications to your Slack workspace',
    icon: <MessageSquare className="h-5 w-5" />,
  },
];

export const NotificationPreferences: React.FC<NotificationPreferencesProps> = ({
  accountId,
  onSave,
}) => {
  const [preferences, setPreferences] = useState<UserNotificationPreferences>({
    categories: [],
    channels: ['ui'],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Fetch current preferences
  useEffect(() => {
    const fetchPreferences = async () => {
      if (!accountId) return;
      
      try {
        setLoading(true);
        setError(null);
        const data = await notificationApi.getPreferences(accountId);
        setPreferences(data);
      } catch (err) {
        console.error('Error fetching preferences:', err);
        setError('Failed to load preferences');
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, [accountId]);

  // Toggle category
  const toggleCategory = (category: NotificationCategory) => {
    setPreferences(prev => ({
      ...prev,
      categories: prev.categories.includes(category)
        ? prev.categories.filter(c => c !== category)
        : [...prev.categories, category],
    }));
    setSuccess(false);
  };

  // Toggle channel
  const toggleChannel = (channel: NotificationChannel) => {
    setPreferences(prev => ({
      ...prev,
      channels: prev.channels.includes(channel)
        ? prev.channels.filter(c => c !== channel)
        : [...prev.channels, channel],
    }));
    setSuccess(false);
  };

  // Select/deselect all categories
  const toggleAllCategories = () => {
    setPreferences(prev => ({
      ...prev,
      categories: prev.categories.length === NOTIFICATION_CATEGORIES.length
        ? []
        : NOTIFICATION_CATEGORIES.map(c => c.value),
    }));
    setSuccess(false);
  };

  // Save preferences
  const handleSave = async () => {
    if (!accountId) return;
    
    // Validate at least one channel is selected
    if (preferences.channels.length === 0) {
      setError('Please select at least one notification channel');
      return;
    }
    
    try {
      setSaving(true);
      setError(null);
      setSuccess(false);
      await notificationApi.updatePreferences(accountId, preferences);
      setSuccess(true);
      onSave?.();
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Error saving preferences:', err);
      setError('Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Error/Success Messages */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-700 text-sm flex items-center gap-2">
          <Check className="h-4 w-4" />
          Preferences saved successfully
        </div>
      )}

      {/* Categories Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">Notification Categories</h3>
          <button
            onClick={toggleAllCategories}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            {preferences.categories.length === NOTIFICATION_CATEGORIES.length
              ? 'Deselect all'
              : 'Select all'}
          </button>
        </div>
        
        <div className="space-y-3">
          {NOTIFICATION_CATEGORIES.map((category) => (
            <label
              key={category.value}
              className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={preferences.categories.includes(category.value)}
                onChange={() => toggleCategory(category.value)}
                className="mt-1"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium text-gray-900">
                  {category.icon}
                  {category.label}
                </div>
                <p className="text-sm text-gray-600 mt-1">{category.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Channels Section */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-4">Notification Channels</h3>
        
        <div className="space-y-3">
          {NOTIFICATION_CHANNELS.map((channel) => (
            <label
              key={channel.value}
              className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={preferences.channels.includes(channel.value)}
                onChange={() => toggleChannel(channel.value)}
                className="mt-1"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium text-gray-900">
                  {channel.icon}
                  {channel.label}
                </div>
                <p className="text-sm text-gray-600 mt-1">{channel.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-4 border-t">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            'Save Preferences'
          )}
        </button>
      </div>
    </div>
  );
};