import { tryFlagKey } from "./types";
import type { FlagKey } from "./types";

export const SESSION_STORAGE_KEY = "kene.ff-overrides";

function isProduction(): boolean {
  return import.meta.env.VITE_ENVIRONMENT === "production";
}

function loadFromSessionStorage(): Record<string, boolean> {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed))
      return {};
    const result: Record<string, boolean> = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (typeof v === "boolean" && tryFlagKey(k) !== undefined) {
        result[k] = v;
      }
    }
    return result;
  } catch {
    if (!isProduction()) {
      console.warn(
        "[FeatureFlags] Failed to read kene.ff-overrides from sessionStorage",
      );
    }
    return {};
  }
}

function saveToSessionStorage(overrides: Record<string, boolean>): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(overrides));
  } catch {
    if (!isProduction()) {
      console.warn(
        "[FeatureFlags] Failed to write kene.ff-overrides to sessionStorage",
      );
    }
  }
}

function parseUrlOverrides(): Record<string, boolean> {
  const params = new URLSearchParams(window.location.search);
  const result: Record<string, boolean> = {};
  for (const [param, value] of params.entries()) {
    if (!param.startsWith("ff.")) continue;
    const rawKey = param.slice(3);
    if (value !== "on" && value !== "off") continue;
    const flagKey: FlagKey | undefined = tryFlagKey(rawKey);
    if (flagKey === undefined) {
      if (!isProduction()) {
        console.warn(
          `[FeatureFlags] Ignoring invalid flag key in URL override: "${rawKey}"`,
        );
      }
      continue;
    }
    result[flagKey] = value === "on";
  }
  return result;
}

/**
 * Reads URL ?ff.<key>=on|off params and merges them with any persisted
 * sessionStorage overrides. Returns {} and never touches sessionStorage in
 * production.
 */
export function readDevOverrides(): Record<string, boolean> {
  if (isProduction()) return {};

  const persisted = loadFromSessionStorage();
  const fromUrl = parseUrlOverrides();
  const merged = { ...persisted, ...fromUrl };
  saveToSessionStorage(merged);
  return merged;
}

/**
 * Returns the override for a single flag key, or undefined when no override
 * exists. Always returns undefined in production.
 */
export function getDevOverride(key: string): boolean | undefined {
  if (isProduction()) return undefined;
  const overrides = readDevOverrides();
  return overrides[key];
}
