/**
 * NotificationPreferences component for managing notification settings
 */

import React, { useEffect, useState } from "react";
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
} from "lucide-react";
import { notificationApi } from "@/api/notifications";
import type {
  NotificationCategory,
  NotificationChannel,
  UserNotificationPreferences,
} from "@/types/notification.types";

interface NotificationPreferencesProps {
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
    value: "Data Quality Alert",
    label: "Data Quality Alerts",
    description: "Notifications about data quality issues and anomalies",
    icon: <AlertTriangle className="h-5 w-5" />,
  },
  {
    value: "News & Press",
    label: "News & Press",
    description: "Updates about company news and press releases",
    icon: <Newspaper className="h-5 w-5" />,
  },
  {
    value: "Industry News",
    label: "Industry News",
    description: "Relevant industry news and market updates",
    icon: <Globe className="h-5 w-5" />,
  },
  {
    value: "Competitor Activities",
    label: "Competitor Activities",
    description: "Updates about competitor actions and strategies",
    icon: <Users className="h-5 w-5" />,
  },
  {
    value: "Scheduled Report Status",
    label: "Scheduled Report Status",
    description: "Notifications about scheduled report generation",
    icon: <FileText className="h-5 w-5" />,
  },
  {
    value: "KPI Performance",
    label: "KPI Performance",
    description: "Alerts about KPI changes and performance metrics",
    icon: <TrendingUp className="h-5 w-5" />,
  },
  {
    value: "New Features",
    label: "New Features",
    description: "Announcements about new features and updates",
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
    value: "ui",
    label: "UI Only",
    description: "Show notifications in the application interface",
    icon: <Monitor className="h-5 w-5" />,
  },
  {
    value: "email",
    label: "Email",
    description: "Send notifications to your email address",
    icon: <Mail className="h-5 w-5" />,
  },
  {
    value: "slack",
    label: "Slack",
    description: "Send notifications to your Slack workspace",
    icon: <MessageSquare className="h-5 w-5" />,
  },
];

export const NotificationPreferences: React.FC<
  NotificationPreferencesProps
> = ({ onSave }) => {
  const [preferences, setPreferences] = useState<UserNotificationPreferences>({
    categories: [],
    channels: ["ui"],
    updated_at: new Date().toISOString(),
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Fetch current preferences
  useEffect(() => {
    const fetchPreferences = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await notificationApi.getPreferences();
        setPreferences(data);
      } catch (err: any) {
        console.error("Error fetching preferences:", err);

        // If preferences don't exist yet (404), use defaults
        if (err?.response?.status === 404) {
          console.log("No preferences found, using defaults");
          setPreferences({
            categories: NOTIFICATION_CATEGORIES.map((c) => c.value), // All categories selected by default
            channels: ["ui"],
            updated_at: new Date().toISOString(),
          });
        } else {
          setError("Failed to load preferences");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, []);

  // Toggle category
  const toggleCategory = (category: NotificationCategory) => {
    setPreferences((prev) => ({
      ...prev,
      categories: prev.categories.includes(category)
        ? prev.categories.filter((c) => c !== category)
        : [...prev.categories, category],
    }));
    setSuccess(false);
  };

  // Toggle channel
  const toggleChannel = (channel: NotificationChannel) => {
    setPreferences((prev) => ({
      ...prev,
      channels: prev.channels.includes(channel)
        ? prev.channels.filter((c) => c !== channel)
        : [...prev.channels, channel],
    }));
    setSuccess(false);
  };

  // Select/deselect all categories
  const toggleAllCategories = () => {
    setPreferences((prev) => ({
      ...prev,
      categories:
        prev.categories.length === NOTIFICATION_CATEGORIES.length
          ? []
          : NOTIFICATION_CATEGORIES.map((c) => c.value),
    }));
    setSuccess(false);
  };

  // Save preferences
  const handleSave = async () => {
    // Validate at least one channel is selected
    if (preferences.channels.length === 0) {
      setError("Please select at least one notification channel");
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSuccess(false);
      await notificationApi.updatePreferences({
        categories: preferences.categories,
        channels: preferences.channels,
      });
      setSuccess(true);
      onSave?.();

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error("Error saving preferences:", err);
      setError("Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-disabled)]" />
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
          <h3 className="text-lg font-medium text-[var(--color-text-primary)]">
            Notification Categories
          </h3>
          <button
            onClick={toggleAllCategories}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            {preferences.categories.length === NOTIFICATION_CATEGORIES.length
              ? "Deselect all"
              : "Select all"}
          </button>
        </div>

        <div className="space-y-3">
          {NOTIFICATION_CATEGORIES.map((category) => (
            <label
              key={category.value}
              className="flex items-start gap-3 p-3 border rounded-lg hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={preferences.categories.includes(category.value)}
                onChange={() => toggleCategory(category.value)}
                className="mt-1"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 font-medium text-[var(--color-text-primary)]">
                  {category.icon}
                  {category.label}
                </div>
                <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
                  {category.description}
                </p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Channels Section */}
      <div>
        <h3 className="text-lg font-medium text-[var(--color-text-primary)] mb-4">
          Notification Channels
        </h3>

        <div className="space-y-3">
          {NOTIFICATION_CHANNELS.map((channel) => {
            const isDisabled = channel.value !== "ui";
            const isComingSoon =
              channel.value === "email" || channel.value === "slack";

            return (
              <label
                key={channel.value}
                className={`flex items-start gap-3 p-3 border rounded-lg transition-colors ${
                  isDisabled
                    ? "opacity-50 cursor-not-allowed bg-[var(--color-bg-secondary)]"
                    : "hover:bg-[var(--color-bg-secondary)] cursor-pointer"
                }`}
              >
                <input
                  type="checkbox"
                  checked={preferences.channels.includes(channel.value)}
                  onChange={() => !isDisabled && toggleChannel(channel.value)}
                  disabled={isDisabled}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2 font-medium text-[var(--color-text-primary)]">
                    {channel.icon}
                    {channel.label}
                    {isComingSoon && (
                      <span className="text-xs bg-[var(--color-bg-elevated)] text-[var(--color-text-tertiary)] px-2 py-0.5 rounded-full">
                        Coming Soon
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
                    {channel.description}
                  </p>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-4 border-t">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-[var(--color-text-disabled)] disabled:cursor-not-allowed flex items-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Preferences"
          )}
        </button>
      </div>
    </div>
  );
};
