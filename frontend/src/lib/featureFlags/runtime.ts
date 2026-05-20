// Runtime feature-flag evaluation shim.
//
// FF-PRD-03 ships a FeatureFlagsProvider + real useFeatureFlag hook backed by
// the /api/v1/feature-flags/evaluate endpoint. Until that PR lands, this shim
// resolves flag state by:
//   1. Dev-override from sessionStorage / URL params (?ff.<key>=on|off).
//   2. VITE_<UPPER_KEY> environment variable (build-time or .env).
//   3. false (default-off for safety).
//
// When FF-PRD-03 merges it replaces this file's body with a one-line re-export
// of the real hook. The import path in callers (App.tsx, etc.) never changes.
//
// TODO(ff-prd-03): replace body with re-export of the real runtime hook.

import { getDevOverride } from "./devOverride";
import type { FlagKey } from "./types";

/**
 * Returns whether a feature flag is enabled for the current user/session.
 *
 * This is a synchronous hook — it never causes a loading state. The real
 * FF-PRD-03 hook will be async-first but expose the same `boolean` return so
 * callers don't need to handle `isLoading`.
 */
export function useFlagEnabled(key: FlagKey): boolean {
  // 1. Dev override (URL param or sessionStorage) — non-production only.
  const devOverride = getDevOverride(key);
  if (devOverride !== undefined) return devOverride;

  // 2. Build-time env var: VITE_CHAT_V2_ENABLED=true enables chat_v2_enabled,
  //    VITE_FEATURE_CHAT_V2_ENABLED=true also works (both accepted for
  //    forward-compatibility with FF-PRD-03's naming convention).
  const envKey = `VITE_${key.toUpperCase()}`;
  const envVal = (import.meta.env as Record<string, string | undefined>)[
    envKey
  ];
  if (envVal === "true") return true;

  // 3. Default off.
  return false;
}
