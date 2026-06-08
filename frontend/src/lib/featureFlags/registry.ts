import { toFlagKey, tryFlagKey } from "./types";
import type { FlagKey } from "./types";

const BASE_FLAGS: FlagKey[] = [
  // toFlagKey("automations_beta"),
  toFlagKey("chat_v2_enabled"),
  toFlagKey("chat_categories_enabled"),
  toFlagKey("invite_only_signup"),
] satisfies FlagKey[];

function parseFixtureFlags(): FlagKey[] {
  const raw: string | undefined = import.meta.env.VITE_FF_E2E_FIXTURE_FLAGS;
  if (!raw) return [];
  return raw
    .split(",")
    .map((s: string) => s.trim())
    .filter(Boolean)
    .reduce<FlagKey[]>((acc: FlagKey[], key: string) => {
      const validated = tryFlagKey(key);
      if (validated !== undefined) {
        if (!acc.includes(validated) && !BASE_FLAGS.includes(validated)) {
          acc.push(validated);
        }
      } else if (import.meta.env.VITE_ENVIRONMENT !== "production") {
        console.warn(
          `[FeatureFlags] VITE_FF_E2E_FIXTURE_FLAGS contains invalid key "${key}" — skipping.`,
        );
      }
      return acc;
    }, []);
}

// Keys the app batch-evaluates on provider mount.
// Add entries here before using useFeatureFlag(key) anywhere in the app.
// VITE_FF_E2E_FIXTURE_FLAGS (comma-separated) unions additional keys for E2E tests only.
export const KNOWN_FLAGS: FlagKey[] = [...BASE_FLAGS, ...parseFixtureFlags()];
