export interface UserProfile {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  job_title: string;
}

export interface NotificationSetting {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
}

export interface SecuritySetting {
  id: string;
  label: string;
  description: string;
  action_text: string;
  action_type: "button" | "switch";
  enabled?: boolean;
  status?: string;
}

export interface PreferenceSetting {
  id: string;
  label: string;
  description: string;
  type: "select";
  value: string;
  options: { value: string; label: string; icon?: string }[];
}

export interface UserSettingsData {
  page_title: string;
  header: {
    title: string;
    description: string;
  };
  profile: UserProfile;
  notifications: NotificationSetting[];
  security: SecuritySetting[];
  preferences: PreferenceSetting[];
}

// Language options
export const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
];

// Theme options
export const THEME_OPTIONS = [
  { value: "light", label: "Light", icon: "sun" },
  { value: "dark", label: "Dark", icon: "moon" },
];

// Date format options
export const DATE_FORMAT_OPTIONS = [
  { value: "mm-dd-yyyy", label: "MM/DD/YYYY" },
  { value: "dd-mm-yyyy", label: "DD/MM/YYYY" },
  { value: "yyyy-mm-dd", label: "YYYY-MM-DD" },
];

// Main user settings data
export const userSettingsData: UserSettingsData = {
  page_title: "User Settings",
  header: {
    title: "User Settings",
    description: "Manage your personal preferences and user settings",
  },
  profile: {
    user_id: "user_001",
    first_name: "John",
    last_name: "Doe",
    email: "john.doe@company.com",
    job_title: "Marketing Director",
  },
  notifications: [
    {
      id: "email_notifications",
      label: "Email Notifications",
      description: "Receive email updates about your campaigns and reports",
      enabled: true,
    },
    {
      id: "performance_alerts",
      label: "Performance Alerts",
      description:
        "Get notified when campaigns exceed or fall below thresholds",
      enabled: true,
    },
    {
      id: "product_updates",
      label: "Product Updates",
      description: "Stay informed about new features and improvements",
      enabled: true,
    },
  ],
  security: [
    {
      id: "two_factor_auth",
      label: "Two-Factor Authentication",
      description: "Add an extra layer of security to your account",
      action_text: "Enable 2FA",
      action_type: "button",
    },
    {
      id: "password",
      label: "Password",
      description: "Last updated 30 days ago",
      action_text: "Change Password",
      action_type: "button",
      status: "Last updated 30 days ago",
    },
  ],
  preferences: [
    {
      id: "language",
      label: "Language",
      description: "Choose your preferred language",
      type: "select",
      value: "en",
      options: LANGUAGE_OPTIONS,
    },
    {
      id: "theme",
      label: "Theme",
      description: "Switch between light and dark mode",
      type: "select",
      value: "light",
      options: THEME_OPTIONS,
    },
    {
      id: "date_format",
      label: "Date Format",
      description: "Choose how dates are displayed",
      type: "select",
      value: "mm-dd-yyyy",
      options: DATE_FORMAT_OPTIONS,
    },
  ],
};

// Helper functions
export const getUserProfile = (): UserProfile => {
  return userSettingsData.profile;
};

export const getNotificationSettings = (): NotificationSetting[] => {
  return userSettingsData.notifications;
};

export const getSecuritySettings = (): SecuritySetting[] => {
  return userSettingsData.security;
};

export const getPreferenceSettings = (): PreferenceSetting[] => {
  return userSettingsData.preferences;
};

export const updateUserProfile = (
  updates: Partial<UserProfile>,
): UserProfile => {
  return { ...userSettingsData.profile, ...updates };
};

export const updateNotificationSetting = (
  id: string,
  enabled: boolean,
): NotificationSetting[] => {
  return userSettingsData.notifications.map((setting) =>
    setting.id === id ? { ...setting, enabled } : setting,
  );
};

export const updatePreferenceSetting = (
  id: string,
  value: string,
): PreferenceSetting[] => {
  return userSettingsData.preferences.map((setting) =>
    setting.id === id ? { ...setting, value } : setting,
  );
};
