import { tryFlagKey } from "./types";
import type { FlagKey } from "./types";

const BASE_FLAGS: FlagKey[] = [
  // "automations_beta" as FlagKey,
] satisfies FlagKey[];

function parseFixtureFlags(): FlagKey[] {
  const raw = import.meta.env.VITE_FF_E2E_FIXTURE_FLAGS;
  if (!raw) return [];
  return raw
    .split(",")
    .map((s: string) => s.trim())
    .filter(Boolean)
    .reduce<FlagKey[]>((acc, key) => {
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
export const KNOWN_FLAGS: FlagKey[] = [
  ...BASE_FLAGS,
  ...parseFixtureFlags(),
];
