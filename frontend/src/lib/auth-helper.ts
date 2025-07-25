import { User as FirebaseUser } from "firebase/auth";
import api from "./api";
import type { User } from "@/contexts/AuthContext";
import { toUserId } from "./branded-types";

export interface UserData {
  uid: string;
  email: string;
  profile: {
    email: string;
    first_name?: string;
    last_name?: string;
    job_title?: string;
    email_verified: boolean;
  };
  permissions: {
    accounts: Record<string, string>;
    organizations: Record<string, string>;
  };
}

export interface NotificationSettings {
  email_notifications: boolean;
  push_notifications: boolean;
  weekly_digest: boolean;
  marketing_updates: boolean;
}

export interface SecuritySettings {
  two_factor_enabled: boolean;
  last_login?: string;
  login_count: number;
}

/**
 * Fetch or create user data after Firebase authentication
 */
export async function fetchOrCreateUser(firebaseUser: FirebaseUser): Promise<{
  userData: UserData;
  notificationSettings: NotificationSettings;
  securitySettings: SecuritySettings;
}> {
  try {
    // Get user data from authenticated endpoint
    const userResponse = await api.get<UserData>("/api/v1/users/me");

    // Get notification settings
    const notificationResponse = await api.get<NotificationSettings>(
      "/api/v1/users/me/notifications",
    );

    // Get security settings
    const securityResponse = await api.get<SecuritySettings>(
      "/api/v1/users/me/security",
    );

    return {
      userData: userResponse.data,
      notificationSettings: notificationResponse.data,
      securitySettings: securityResponse.data,
    };
  } catch (error: any) {
    console.error("[auth-helper] Error fetching user data:", error);
    throw error;
  }
}

/**
 * Update user profile after sign up
 */
export async function updateUserProfile(profile: {
  first_name: string;
  last_name: string;
  email_verified?: boolean;
}): Promise<UserData> {
  try {
    const response = await api.put<UserData>("/api/v1/users/me/profile", {
      ...profile,
    });
    return response.data;
  } catch (error: any) {
    console.error("[auth-helper] Error updating user profile:", error);
    throw error;
  }
}

/**
 * Convert API user data to app User format
 */
export function convertToAppUser(userData: UserData): User {
  return {
    id: toUserId(userData.uid),
    email: userData.email,
    firstName: userData.profile.first_name || "",
    lastName: userData.profile.last_name || "",
    jobTitle: userData.profile.job_title,
    permissions: userData.permissions,
  };
}
