import type { AccountId, ActivityId, ActivityLogId } from "@/lib/branded-types";

// Existing activity types
export interface ActivityLog {
  id: ActivityLogId;
  account_id: AccountId;
  start_date: string;
  end_date: string;
  description?: string;
  evidence?: any;
}

export interface Activity {
  id: ActivityId;
  account_id: AccountId;
  activity_name: string;
  activity_description: string;
  expected_impact: string;
  internal: boolean;
  known_activity: boolean;
  logs?: ActivityLog[];
}

// Sync operation types
export interface HolidaySyncRequest {
  account_id: AccountId;
}

export interface HolidaySyncResponse {
  success: boolean;
  message: string;
  data: HolidaySyncData;
}

export interface HolidaySyncData {
  account_id: AccountId;
  regions: string[];
  total_holidays_in_bigquery: number;
  existing_logs_before_sync: number;
  new_logs_created: number;
  logs_deleted: number;
  logs_protected_from_deletion: number;
  errors?: string[];
}

export interface HolidaySyncError {
  code: "SYNC_FAILED" | "PARTIAL_SYNC" | "BIGQUERY_ERROR" | "NEO4J_ERROR";
  message: string;
  details?: Record<string, unknown>;
}

// Request types
export interface ActivityRequest {
  account_id: AccountId;
  activity_id?: ActivityId;
  activity_name?: string;
  activity_description?: string;
  expected_impact?: string;
  internal?: boolean;
  known_activity?: boolean;
}

export interface ActivityLogRequest {
  account_id: AccountId;
  activity_id?: ActivityId;
  activity_log_id?: ActivityLogId;
  start_date?: string;
  end_date?: string;
  description?: string;
}
