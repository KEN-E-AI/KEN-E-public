import type { FlagKey } from "./types";

// Keys the app batch-evaluates on provider mount.
// Add entries here before using useFeatureFlag(key) anywhere in the app.
export const KNOWN_FLAGS: FlagKey[] = [
  // "automations_beta" as FlagKey,
] satisfies FlagKey[];
