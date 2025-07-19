// Firebase User type (subset of actual Firebase User)
export interface FirebaseUser {
  uid: string;
  email: string | null;
  displayName: string | null;
}

// Firestore user profile structure
export interface UserProfile {
  email: string;
  first_name: string;
  last_name: string;
  job_title: string;
  uid?: string;
}

// Firestore user permissions
export interface UserPermissions {
  organizations: Record<string, unknown>;
  accounts: Record<string, unknown>;
}

// Firestore user preferences
export interface UserPreferences {
  language?: string;
  theme?: string;
  date_format?: string;
  [key: string]: unknown;
}

// Complete Firestore user data structure
export interface FirestoreUserData {
  profile: UserProfile;
  permissions: UserPermissions;
  preferences: UserPreferences;
  metadata?: {
    createdAt: string;
    lastUpdated: string;
  };
}

// Notification settings
export interface NotificationSettings {
  emailNotifications?: boolean;
  [key: string]: unknown;
}

// Security settings
export interface SecuritySettings {
  twoFactorEnabled?: boolean;
  [key: string]: unknown;
}

// API response for user data
export interface UserDataResponse {
  userData: FirestoreUserData;
  notificationsData: Array<{ data: NotificationSettings }>;
  securityData: Array<{ data: SecuritySettings }>;
}

// Auth helper function dependencies
export interface AuthHelperDeps {
  apiBaseUrl: string;
  login: (user: {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
    jobTitle: string;
    permissions: UserPermissions;
    preferences: UserPreferences;
  }) => void;
  setNotificationSettings: (settings: NotificationSettings) => void;
  setSecuritySettings: (settings: SecuritySettings) => void;
}
