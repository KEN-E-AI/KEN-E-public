/**
 * Canonical shared types for the Feature Flags component.
 *
 * This file is the contract owner for FF-PRD-02's typed-client agreement with FF-PRD-03.
 * The admin SDK (FF-PRD-02) and the runtime SDK (FF-PRD-03) both import from here.
 * Any change to this file must be kept in sync with the Pydantic models in
 * api/src/kene_api/models/feature_flag_models.py — verified via the schema snapshot
 * at api/tests/fixtures/feature_flag_schema.snapshot.json (FF-PRD-01 §5.4).
 *
 * NOTE: This file exports admin-config types (flag shape, CRUD).
 * The runtime evaluation types (useFeatureFlag hook result) are appended by FF-PRD-03
 * in frontend/src/contexts/FeatureFlagsContext.tsx.
 */
import type { Brand } from "@/lib/branded-types";

// ─── FlagKey branded type ────────────────────────────────────────────────────

/** Regex mirrors FLAG_KEY_REGEX in feature_flag_models.py */
const FLAG_KEY_REGEX = /^[a-z0-9][a-z0-9_]{2,63}$/;

export type FlagKey = Brand<string, "FlagKey">;

export const isFlagKey = (value: string): value is FlagKey =>
  FLAG_KEY_REGEX.test(value);

export const toFlagKey = (value: string): FlagKey => {
  if (!isFlagKey(value)) {
    throw new Error(
      `Invalid flag key "${value}". Must match ^[a-z0-9][a-z0-9_]{2,63}$`,
    );
  }
  return value as FlagKey;
};

export const tryFlagKey = (value: string): FlagKey | undefined =>
  isFlagKey(value) ? (value as FlagKey) : undefined;

// ─── Core types (mirror feature_flag_models.py) ───────────────────────────────

export type BucketingEntity = "account" | "organization" | "user";

export type TargetingRules = {
  user_emails: string[];
  email_domains: string[];
  organization_ids: string[];
  account_ids: string[];
  rollout_percentage: number; // 0-100
};

export type FeatureFlag = {
  key: FlagKey;
  description: string;
  default_enabled: boolean;
  is_active: boolean;
  targeting_rules: TargetingRules;
  bucketing_entity: BucketingEntity;
  owner: string;
  expected_ga_release: string | null;
  created_at: string; // ISO-8601
  updated_at: string; // ISO-8601
};

// ─── Audit types (mirrors FF-PRD-02 §4 / FF-14 backend Pydantic model) ────────

export type FeatureFlagAuditAction =
  | "create"
  | "update"
  | "delete"
  | "toggle_active";

export type FeatureFlagAuditDiff = Record<
  string,
  { before: unknown; after: unknown }
>;

export type FeatureFlagAuditEntry = {
  audit_id: string;
  flag_key: FlagKey;
  actor_email: string;
  action: FeatureFlagAuditAction;
  diff: FeatureFlagAuditDiff;
  created_at: string; // ISO-8601
};
