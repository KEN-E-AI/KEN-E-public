// Hand-mirrors feature_flag_models.py — keep in sync via api/tests/fixtures/feature_flag_schema.snapshot.json.
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

// ─── Evaluation types (mirror feature_flag_models.py FlagEvaluation; reason is a TS-only superset adding "dev_override") ───

// Added here per FF-PRD-03 §4; FF-PRD-02 authored types.ts but omitted FlagEvaluation.
export type FlagEvaluation = {
  key: FlagKey;
  enabled: boolean;
  reason:
    | "kill_switch"
    | "email_match"
    | "domain_match"
    | "org_match"
    | "account_match"
    | "rollout"
    | "default"
    | "unknown_flag"
    | "dev_override";
};

export type FeatureFlagsContextValue = {
  evaluations: Record<string, FlagEvaluation>;
  isLoading: boolean;
  refetch: () => Promise<void>;
};

export type UseFeatureFlagResult = {
  enabled: boolean;
  reason: FlagEvaluation["reason"];
  isLoading: boolean;
};
