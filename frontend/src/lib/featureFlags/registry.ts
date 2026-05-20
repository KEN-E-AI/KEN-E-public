import { toFlagKey } from "./types";
import type { FlagKey } from "./types";

// Keys the app batch-evaluates on provider mount.
// Add entries here before using useFeatureFlag(key) anywhere in the app.
export const KNOWN_FLAGS: FlagKey[] = [
  // toFlagKey("automations_beta"),
  toFlagKey("chat_v2_enabled"),
] satisfies FlagKey[];
